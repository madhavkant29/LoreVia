import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.core.redis import (
    get_book_cache_version,
    get_reader_progress_cache_version,
    get_reader_timeline_cache,
    set_reader_timeline_cache,
)
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    get_book_with_collaboration_access,
)
from app.utils.plot_thread_utils import derive_plot_thread_status
from app.utils.reader_utils import (
    build_timeline_track_payload,
    dedupe_timeline_events,
    is_valid_timeline_character,
    timeline_character_detail,
    timeline_plot_thread_span,
    timeline_relationship_detail,
    timeline_visible_chapter_set,
)
from app.utils.sparse_utils import (
    apply_sparse_fields,
    apply_sparse_includes,
    include_requested,
    parse_csv_param,
)

router = APIRouter()


@router.get("/{book_id}/timeline")
async def get_timeline(
    book_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    include: str | None = Query(
        None,
        description="Comma-separated track types: chapters, events, character_tracks, thread_tracks, relationship_markers",
    ),
    fields: str | None = Query(
        None,
        description="Comma-separated fields per event: chapter_number, chapter_title, kind, title, detail",
    ),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is None:
        require_author_access(current_user)

    use_cache = parse_csv_param(include) is None
    if use_cache:
        book_version = await get_book_cache_version(str(book_id))
        progress_version = await get_reader_progress_cache_version(
            str(book_id), str(current_user.id)
        )
        cached = await get_reader_timeline_cache(
            str(book_id),
            str(current_user.id),
            book_version,
            progress_version,
        )
        if cached is not None:
            payload = cast(dict[str, Any], cached)
            payload = apply_sparse_includes(payload, include)
            all_events = payload.get("events", [])
            total_events = len(all_events)
            payload["events"] = all_events[offset : offset + limit]
            payload["total_events"] = total_events
            payload["limit"] = limit
            payload["offset"] = offset
            payload["has_more"] = (offset + limit) < total_events
            payload["next_offset"] = offset + limit if payload["has_more"] else None
            return apply_sparse_fields(payload, fields) if fields else payload

    read_set = await timeline_visible_chapter_set(db, book, current_user, collaborator)
    if collaborator is not None:
        read_set = {
            chapter for chapter in read_set if collaboration_allows_chapter(collaborator, chapter)
        }
    if not read_set:
        payload = build_timeline_track_payload([], [], [], [], [])
        payload = apply_sparse_includes(payload, include)
        return apply_sparse_fields(payload, fields) if fields else payload

    want_chapters = include_requested(include, "chapters")
    want_events = include_requested(include, "events")
    want_character_tracks = include_requested(include, "character_tracks")
    want_thread_tracks = include_requested(include, "thread_tracks")
    want_relationship_markers = include_requested(include, "relationship_markers")

    summary_rows = tuple()  # type: ignore[var-annotated]
    character_rows = tuple()  # type: ignore[var-annotated]
    if want_events:
        summary_rows = (
            await db.execute(
                select(Chapter.number, Chapter.title, ChapterSummary.key_events)
                .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
                .where(
                    Chapter.book_id == book_id,
                    Chapter.number.in_(sorted(read_set)),
                    ChapterSummary.mode == "short",
                )
                .order_by(Chapter.number)
            )
        ).all()
        character_rows = (
            await db.execute(
                select(
                    Character.name,
                    Character.first_chapter,
                    Character.role,
                    Character.aliases,
                    Character.arc_summary,
                )
                .where(Character.book_id == book_id, Character.first_chapter.in_(sorted(read_set)))
                .order_by(Character.first_chapter, Character.name)
            )
        ).all()
    chapter_meta_rows = tuple()  # type: ignore[var-annotated]
    if want_chapters or want_events:
        chapter_meta_rows = (
            await db.execute(
                select(Chapter.number, Chapter.title).where(
                    Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set))
                )
            )
        ).all()
    chapter_titles = {number: title for number, title in chapter_meta_rows}
    chapter_points = (
        [
            {"number": number, "title": title}
            for number, title in sorted(chapter_meta_rows, key=lambda item: item[0])
        ]
        if want_chapters
        else []
    )

    thread_rows = tuple()  # type: ignore[var-annotated]
    if want_events or want_thread_tracks:
        thread_rows = (
            await db.execute(
                select(
                    PlotThread.id,
                    PlotThread.title,
                    PlotThread.introduced_at,
                    PlotThread.last_mentioned_at,
                    PlotThread.resolved_at,
                    PlotThread.status,
                    PlotThread.note,
                    PlotThread.description,
                )
                .where(PlotThread.book_id == book_id)
                .order_by(PlotThread.introduced_at, PlotThread.importance.desc())
            )
        ).all()
    relationship_rows = tuple()  # type: ignore[var-annotated]
    character_lookup: dict = {}
    if want_events or want_relationship_markers:
        relationship_rows = (
            await db.execute(
                select(CharacterRelationship, Character.name, Character.role)
                .join(Character, Character.id == CharacterRelationship.character_a_id)
                .where(
                    CharacterRelationship.book_id == book_id,
                    CharacterRelationship.from_chapter.in_(sorted(read_set)),
                )
                .order_by(CharacterRelationship.from_chapter)
            )
        ).all()
        character_lookup_result = await db.execute(
            select(Character).where(Character.book_id == book_id)
        )
        character_lookup = {char.id: char.name for char in character_lookup_result.scalars().all()}

    events = []
    character_tracks = []
    thread_tracks = []
    relationship_markers = []

    if want_events:
        for chapter_num, chapter_title, key_events in summary_rows:
            for event in key_events or []:
                if isinstance(event, dict) and event.get("event"):
                    events.append(
                        {
                            "chapter_number": chapter_num,
                            "chapter_title": chapter_title,
                            "kind": "event",
                            "title": event.get("event"),
                            "detail": None,
                        }
                    )
        for name, first_chapter, role, aliases, arc_summary in character_rows:
            if not is_valid_timeline_character(name, role, aliases, arc_summary):
                continue
            events.append(
                {
                    "chapter_number": first_chapter,
                    "chapter_title": chapter_titles.get(first_chapter),
                    "kind": "character_entry",
                    "title": name,
                    "detail": timeline_character_detail(name, role, aliases, arc_summary),
                }
            )

    if want_character_tracks:
        visible_characters_result = await db.execute(
            select(Character)
            .where(Character.book_id == book_id, Character.first_chapter.in_(sorted(read_set)))
            .order_by(Character.first_chapter, Character.name)
        )
        visible_characters = visible_characters_result.scalars().all()
        for char in visible_characters:
            if not is_valid_timeline_character(
                char.name, char.role, char.aliases, char.arc_summary
            ):
                continue
            start_chapter = char.first_chapter
            end_chapter = char.last_seen_chapter or max(read_set)
            character_tracks.append(
                {
                    "id": str(char.id),
                    "name": char.name,
                    "role": char.role,
                    "start_chapter": start_chapter,
                    "end_chapter": max(start_chapter, min(end_chapter, max(read_set))),
                    "detail": timeline_character_detail(
                        char.name, char.role, char.aliases, char.arc_summary
                    ),
                }
            )

    if want_events or want_thread_tracks:
        for (
            thread_id,
            title,
            introduced_at,
            last_mentioned_at,
            resolved_at,
            status,
            note,
            description,
        ) in thread_rows:
            display_status = derive_plot_thread_status(
                status,
                introduced_at=introduced_at,
                last_mentioned_at=last_mentioned_at or introduced_at,
                resolved_at=resolved_at,
                current_chapter=max(read_set) if read_set else None,
            )
            if want_events:
                if introduced_at and introduced_at in read_set:
                    events.append(
                        {
                            "chapter_number": introduced_at,
                            "chapter_title": chapter_titles.get(introduced_at),
                            "kind": "thread_start",
                            "title": title,
                            "detail": display_status,
                        }
                    )
                if resolved_at and resolved_at in read_set:
                    events.append(
                        {
                            "chapter_number": resolved_at,
                            "chapter_title": chapter_titles.get(int(resolved_at)),
                            "kind": "thread_end",
                            "title": title,
                            "detail": "Resolved",
                        }
                    )
            if want_thread_tracks:
                span = timeline_plot_thread_span(introduced_at, resolved_at, read_set)
                if span:
                    start_chapter, end_chapter = span
                    thread_tracks.append(
                        {
                            "id": str(thread_id),
                            "title": title,
                            "status": display_status,
                            "start_chapter": start_chapter,
                            "end_chapter": end_chapter,
                            "note": note,
                            "detail": description,
                        }
                    )

    if want_events or want_relationship_markers:
        for rel, _, _ in relationship_rows:
            a_name = character_lookup.get(rel.character_a_id)
            b_name = character_lookup.get(rel.character_b_id)
            if not a_name or not b_name:
                continue
            title, detail = timeline_relationship_detail(
                a_name,
                b_name,
                rel.rel_type,
                rel.description,
                getattr(rel, "shared_labels", None),
                getattr(rel, "character_a_to_b_labels", None),
                getattr(rel, "character_b_to_a_labels", None),
            )
            if want_events:
                events.append(
                    {
                        "chapter_number": rel.from_chapter,
                        "chapter_title": chapter_titles.get(rel.from_chapter),
                        "kind": "relationship_shift",
                        "title": title,
                        "detail": detail,
                    }
                )
            if want_relationship_markers:
                relationship_markers.append(
                    {
                        "id": str(rel.id),
                        "title": title,
                        "chapter_number": rel.from_chapter,
                        "detail": detail,
                        "type": rel.rel_type,
                        "shared_labels": list(getattr(rel, "shared_labels", None) or []),
                        "character_a_to_b_labels": list(
                            getattr(rel, "character_a_to_b_labels", None) or []
                        ),
                        "character_b_to_a_labels": list(
                            getattr(rel, "character_b_to_a_labels", None) or []
                        ),
                    }
                )

    if want_events:
        events = dedupe_timeline_events(events)
        events.sort(key=lambda item: (item["chapter_number"], item["kind"], item["title"]))
    character_tracks.sort(key=lambda item: (item["start_chapter"], item["name"]))
    thread_tracks.sort(key=lambda item: (item["start_chapter"], item["title"]))
    relationship_markers.sort(key=lambda item: (item["chapter_number"], item["title"]))
    payload = build_timeline_track_payload(
        chapter_points, events, character_tracks, thread_tracks, relationship_markers
    )
    if use_cache:
        book_version = await get_book_cache_version(str(book_id))
        progress_version = await get_reader_progress_cache_version(
            str(book_id), str(current_user.id)
        )
        await set_reader_timeline_cache(
            str(book_id),
            str(current_user.id),
            book_version,
            progress_version,
            payload,
        )

    payload = apply_sparse_includes(payload, include)
    all_events = payload.get("events", [])
    total_events = len(all_events)
    payload["events"] = all_events[offset : offset + limit]
    payload["total_events"] = total_events
    payload["limit"] = limit
    payload["offset"] = offset
    payload["has_more"] = (offset + limit) < total_events
    payload["next_offset"] = offset + limit if payload["has_more"] else None
    return apply_sparse_fields(payload, fields) if fields else payload
