import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_recall
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import (
    cache_get,
    cache_set,
    get_book_cache_version,
    get_reader_events_cache,
    get_reader_progress_cache_version,
    get_reader_timeline_cache,
    key_memory_recall,
    set_reader_events_cache,
    set_reader_timeline_cache,
)
from app.engine.analysis.recall import generate_recall
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread
from app.models.progress import ReadingProgress
from app.schemas.books import BookEventsOut, CharacterEventOut, MajorEventOut
from app.schemas.reader import PlotThreadOut, UpdatePlotThreadBody
from app.utils.book_utils import (
    collaboration_allows_chapter,
    get_book_with_collaboration_access,
)
from app.utils.plot_thread_utils import derive_plot_thread_status
from app.utils.reader_utils import (
    build_timeline_track_payload,
    dedupe_timeline_events,
    is_valid_timeline_character,
    list_plot_threads,
    queue_analysis_if_missing,
    summary_visible_chapter_set,
    timeline_character_detail,
    timeline_plot_thread_span,
    timeline_relationship_detail,
    timeline_visible_chapter_set,
    update_plot_thread_note,
)
from app.utils.sparse_utils import apply_sparse_fields, apply_sparse_includes, include_requested, parse_csv_param

router = APIRouter()


def _normalize_reader_major_event(chapter_number: int, chapter_title: str | None, event: dict, names_by_id: dict[str, str]) -> dict:
    involved_ids = [str(item).strip() for item in (event.get("involved_characters") or []) if str(item).strip()]
    return {
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "event_title": str(event.get("event_title") or event.get("event") or "").strip(),
        "description": str(event.get("description") or event.get("impact") or "").strip(),
        "importance": int(event.get("importance") or 5),
        "involved_characters": involved_ids or None,
        "involved_character_names": [names_by_id.get(item, item) for item in involved_ids] or None,
        "event_type": event.get("event_type"),
    }


def _normalize_reader_character_event(character: Character, event: dict) -> dict:
    return {
        "character_id": str(character.id),
        "character_name": character.name,
        "chapter_number": int(event.get("chapter_number") or character.first_chapter),
        "event_title": str(event.get("event_title") or event.get("event") or "").strip(),
        "description": str(event.get("description") or event.get("impact") or "").strip(),
        "impact_score": int(event.get("impact_score") or event.get("importance") or 5),
        "role": event.get("role") or character.role,
        "accomplishments": [str(item).strip() for item in (event.get("accomplishments") or []) if str(item).strip()],
        "growth_direction": str(event.get("growth_direction") or "neutral"),
        "growth_magnitude": int(event.get("growth_magnitude") or event.get("impact_score") or 0),
        "is_major": bool(event.get("is_major", False)),
    }


def _build_combined_events(major_events: list[MajorEventOut], character_events: list[CharacterEventOut]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for e in major_events:
        events.append({"type": "major", **e.model_dump(mode="json")})
    for e in character_events:
        events.append({"type": "character", **e.model_dump(mode="json")})
    type_order = {"major": 0, "character": 1}
    events.sort(
        key=lambda item: (
            item.get("chapter_number", 0),
            type_order.get(str(item.get("type")), 9),
            item.get("event_title", "").lower()
            if item.get("type") == "major"
            else item.get("character_name", "").lower(),
        )
    )
    return events


def _paginated_events_response(events: list[dict[str, Any]], limit: int, offset: int) -> dict[str, Any]:
    total = len(events)
    paged = events[offset : offset + limit]
    return {
        "items": paged,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


@router.get("/{book_id}/events")
async def get_reader_events(
    book_id: uuid.UUID,
    chapter: int | None = Query(None),
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    progress_result = await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )
    progress = progress_result.scalar()
    read_set = set(progress.chapters_read or []) if progress else set()
    max_visible_chapter = chapter or (max(read_set) if read_set else (progress.current_chapter if progress else 1))
    book_version = await get_book_cache_version(str(book_id))
    progress_version = await get_reader_progress_cache_version(str(book_id), str(current_user.id))
    cached = await get_reader_events_cache(
        str(book_id),
        str(current_user.id),
        int(max_visible_chapter),
        book_version,
        progress_version,
    )
    if cached is not None:
        cached_payload = BookEventsOut(**cached)
        all_events = _build_combined_events(cached_payload.major_events, cached_payload.character_events)
        return _paginated_events_response(all_events, limit, offset)

    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book_id, ChapterSummary.mode == "detailed", Chapter.number <= max_visible_chapter)
            .order_by(Chapter.number)
        )
    ).all()
    characters_result = await db.execute(select(Character).where(Character.book_id == book_id))
    characters = characters_result.scalars().all()
    names_by_id = {str(character.id): character.name for character in characters}

    major_events: list[MajorEventOut] = []
    for chapter_number, chapter_title, key_events in chapter_rows:
        for event in key_events or []:
            if isinstance(event, dict):
                major_events.append(MajorEventOut(**_normalize_reader_major_event(chapter_number, chapter_title, event, names_by_id)))

    character_events: list[CharacterEventOut] = []
    for character in characters:
        for event in character.growth_events or []:
            if isinstance(event, dict) and int(event.get("chapter_number") or 0) <= max_visible_chapter:
                character_events.append(CharacterEventOut(**_normalize_reader_character_event(character, event)))

    payload = BookEventsOut(major_events=major_events, character_events=character_events)
    await set_reader_events_cache(
        str(book_id),
        str(current_user.id),
        int(max_visible_chapter),
        book_version,
        progress_version,
        payload.model_dump(mode="json"),
    )
    all_events = _build_combined_events(major_events, character_events)
    return _paginated_events_response(all_events, limit, offset)


@router.get("/{book_id}/foreshadowing")
async def get_foreshadowing_highlights(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)

    read_set = await summary_visible_chapter_set(db, book, current_user, collaborator)
    if collaborator is not None:
        read_set = {chapter for chapter in read_set if collaboration_allows_chapter(collaborator, chapter)}
    if not read_set:
        return {"items": []}

    rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.clues)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)), ChapterSummary.mode == "detailed")
        .order_by(Chapter.number)
    )).all()

    items = []
    for number, title, clues in rows:
        for clue in clues or []:
            if isinstance(clue, dict) and clue.get("clue"):
                items.append({"chapter_number": number, "chapter_title": title,
                               "clue": clue.get("clue"), "foreshadows": clue.get("foreshadows")})
    if items:
        return {"items": items}

    chapters = (
        await db.execute(
            select(Chapter)
            .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)))
            .order_by(Chapter.number)
        )
    ).scalars().all()
    for chapter in chapters:
        await queue_analysis_if_missing(db, chapter, current_user)
    return {"items": items}


@router.get("/{book_id}/timeline")
async def get_timeline(
    book_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    include: str | None = Query(None, description="Comma-separated track types: chapters, events, character_tracks, thread_tracks, relationship_markers"),
    fields: str | None = Query(None, description="Comma-separated fields per event: chapter_number, chapter_title, kind, title, detail"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)

    use_cache = parse_csv_param(include) is None
    if use_cache:
        book_version = await get_book_cache_version(str(book_id))
        progress_version = await get_reader_progress_cache_version(str(book_id), str(current_user.id))
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
            return apply_sparse_fields(payload, fields) if fields else payload

    read_set = await timeline_visible_chapter_set(db, book, current_user, collaborator)
    if collaborator is not None:
        read_set = {chapter for chapter in read_set if collaboration_allows_chapter(collaborator, chapter)}
    if not read_set:
        payload = build_timeline_track_payload([], [], [], [], [])
        payload = apply_sparse_includes(payload, include)
        return apply_sparse_fields(payload, fields) if fields else payload

    summary_rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.key_events)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)), ChapterSummary.mode == "short")
        .order_by(Chapter.number)
    )).all()
    character_rows = (await db.execute(
        select(Character.name, Character.first_chapter, Character.role, Character.aliases, Character.arc_summary)
        .where(Character.book_id == book_id, Character.first_chapter.in_(sorted(read_set)))
        .order_by(Character.first_chapter, Character.name)
    )).all()
    chapter_meta_rows = (await db.execute(
        select(Chapter.number, Chapter.title)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)))
    )).all()
    chapter_titles = {number: title for number, title in chapter_meta_rows}
    chapter_points = [{"number": number, "title": title} for number, title in sorted(chapter_meta_rows, key=lambda item: item[0])]

    want_events = include_requested(include, "events")
    want_character_tracks = include_requested(include, "character_tracks")
    want_thread_tracks = include_requested(include, "thread_tracks")
    want_relationship_markers = include_requested(include, "relationship_markers")

    thread_rows = tuple()  # type: ignore[var-annotated]
    if want_events or want_thread_tracks:
        thread_rows = (await db.execute(
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
        )).all()
    relationship_rows = tuple()  # type: ignore[var-annotated]
    character_lookup: dict = {}
    if want_events or want_relationship_markers:
        relationship_rows = (await db.execute(
            select(CharacterRelationship, Character.name, Character.role)
            .join(Character, Character.id == CharacterRelationship.character_a_id)
            .where(
                CharacterRelationship.book_id == book_id,
                CharacterRelationship.from_chapter.in_(sorted(read_set)),
            )
            .order_by(CharacterRelationship.from_chapter)
        )).all()
        character_lookup_result = await db.execute(select(Character).where(Character.book_id == book_id))
        character_lookup = {char.id: char.name for char in character_lookup_result.scalars().all()}

    events = []
    character_tracks = []
    thread_tracks = []
    relationship_markers = []

    if want_events:
        for chapter_num, chapter_title, key_events in summary_rows:
            for event in key_events or []:
                if isinstance(event, dict) and event.get("event"):
                    events.append({"chapter_number": chapter_num, "chapter_title": chapter_title,
                                    "kind": "event", "title": event.get("event"), "detail": None})
        for name, first_chapter, role, aliases, arc_summary in character_rows:
            if not is_valid_timeline_character(name, role, aliases, arc_summary):
                continue
            events.append({"chapter_number": first_chapter, "chapter_title": chapter_titles.get(first_chapter), "kind": "character_entry",
                            "title": name, "detail": timeline_character_detail(name, role, aliases, arc_summary)})

    if want_character_tracks:
        visible_characters_result = await db.execute(
            select(Character).where(Character.book_id == book_id, Character.first_chapter.in_(sorted(read_set))).order_by(Character.first_chapter, Character.name)
        )
        visible_characters = visible_characters_result.scalars().all()
        for char in visible_characters:
            if not is_valid_timeline_character(char.name, char.role, char.aliases, char.arc_summary):
                continue
            start_chapter = char.first_chapter
            end_chapter = char.last_seen_chapter or max(read_set)
            character_tracks.append({
                "id": str(char.id),
                "name": char.name,
                "role": char.role,
                "start_chapter": start_chapter,
                "end_chapter": max(start_chapter, min(end_chapter, max(read_set))),
                "detail": timeline_character_detail(char.name, char.role, char.aliases, char.arc_summary),
            })

    if want_events or want_thread_tracks:
        for thread_id, title, introduced_at, last_mentioned_at, resolved_at, status, note, description in thread_rows:
            display_status = derive_plot_thread_status(
                status,
                introduced_at=introduced_at,
                last_mentioned_at=last_mentioned_at or introduced_at,
                resolved_at=resolved_at,
                current_chapter=max(read_set) if read_set else None,
            )
            if want_events:
                if introduced_at and introduced_at in read_set:
                    events.append({"chapter_number": introduced_at, "chapter_title": chapter_titles.get(introduced_at),
                                    "kind": "thread_start", "title": title, "detail": display_status})
                if resolved_at and resolved_at in read_set:
                    events.append({"chapter_number": resolved_at, "chapter_title": chapter_titles.get(int(resolved_at)),
                                    "kind": "thread_end", "title": title, "detail": "Resolved"})
            if want_thread_tracks:
                span = timeline_plot_thread_span(introduced_at, resolved_at, read_set)
                if span:
                    start_chapter, end_chapter = span
                    thread_tracks.append({
                        "id": str(thread_id),
                        "title": title,
                        "status": display_status,
                        "start_chapter": start_chapter,
                        "end_chapter": end_chapter,
                        "note": note,
                        "detail": description,
                    })

    if want_events or want_relationship_markers:
        for rel, _, _ in relationship_rows:
            a_name = character_lookup.get(rel.character_a_id)
            b_name = character_lookup.get(rel.character_b_id)
            if not a_name or not b_name:
                continue
            title, detail = timeline_relationship_detail(a_name, b_name, rel.rel_type, rel.description)
            if want_events:
                events.append({
                    "chapter_number": rel.from_chapter,
                    "chapter_title": chapter_titles.get(rel.from_chapter),
                    "kind": "relationship_shift",
                    "title": title,
                    "detail": detail,
                })
            if want_relationship_markers:
                relationship_markers.append({
                    "id": str(rel.id),
                    "title": title,
                    "chapter_number": rel.from_chapter,
                    "detail": detail,
                })

    if want_events:
        events = dedupe_timeline_events(events)
        events.sort(key=lambda item: (item["chapter_number"], item["kind"], item["title"]))
    character_tracks.sort(key=lambda item: (item["start_chapter"], item["name"]))
    thread_tracks.sort(key=lambda item: (item["start_chapter"], item["title"]))
    relationship_markers.sort(key=lambda item: (item["chapter_number"], item["title"]))
    payload = build_timeline_track_payload(chapter_points, events, character_tracks, thread_tracks, relationship_markers)
    if use_cache:
        book_version = await get_book_cache_version(str(book_id))
        progress_version = await get_reader_progress_cache_version(str(book_id), str(current_user.id))
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
    return apply_sparse_fields(payload, fields) if fields else payload


@router.get("/{book_id}/plot-threads", response_model=list[PlotThreadOut])
async def get_plot_threads(
    book_id: uuid.UUID,
    chapter: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    return await list_plot_threads(db, book_id, chapter)


@router.put("/{book_id}/plot-threads/{thread_id}", response_model=PlotThreadOut)
async def save_plot_thread_note(
    book_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: UpdatePlotThreadBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    thread = await update_plot_thread_note(db, book_id, thread_id, body.note, body.status)
    if thread is None:
        raise HTTPException(404, "Plot thread not found")
    return thread


@router.get("/{book_id}/recall")
async def memory_recall(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_recall),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    book_title = book.title

    cache_key = key_memory_recall(str(current_user.id), str(book_id))
    cached = await cache_get(cache_key)
    if cached:
        return {"recall": cached, "cached": True}

    progress_result = await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )
    progress = progress_result.scalar()
    if not progress:
        return {"recall": None}

    last_chapter = progress.current_chapter
    chapter_result = await db.execute(select(Chapter).where(Chapter.book_id == book_id, Chapter.number == last_chapter))
    chapter = chapter_result.scalar()

    recent_summary = ""
    if chapter:
        summ_result = await db.execute(
            select(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id, ChapterSummary.mode == "short")
        )
        summ = summ_result.scalar()
        if summ:
            recent_summary = summ.content

    chars_result = await db.execute(
        select(Character.name).where(Character.book_id == book_id, Character.first_chapter <= last_chapter).limit(8)
    )
    chars = chars_result.scalars().all()

    open_threads_result = await db.execute(
        select(PlotThread.title, PlotThread.status, PlotThread.introduced_at, PlotThread.last_mentioned_at, PlotThread.resolved_at)
        .where(
            PlotThread.book_id == book_id,
            PlotThread.introduced_at <= last_chapter,
        )
        .limit(6)
    )
    open_threads = [
        title
        for title, status, introduced_at, last_mentioned_at, resolved_at in open_threads_result.all()
        if derive_plot_thread_status(
            status,
            introduced_at=introduced_at,
            last_mentioned_at=last_mentioned_at or introduced_at,
            resolved_at=resolved_at,
            current_chapter=last_chapter,
        ) not in {"resolved", "abandoned"}
    ][:3]

    await db.rollback()
    recall_text = await generate_recall(
        title=book_title,
        last_chapter=last_chapter,
        recent_summary=recent_summary,
        active_characters=list(chars),
        open_threads=list(open_threads),
        user_id=current_user.id,
        book_id=book_id,
        usage_db=db,
    )
    await db.commit()

    await cache_set(cache_key, recall_text, settings.REDIS_TTL_RECALL)
    return {"recall": recall_text, "last_chapter": last_chapter}
