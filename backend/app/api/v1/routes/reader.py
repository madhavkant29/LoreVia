"""
Reader routes — the core intelligence surface.
Smart tap, summaries, relationship graph, memory recall, progress.
"""
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_recall, rate_limit_search, rate_limit_summary
from app.core.config import is_local_mode, settings
from app.core.database import get_db
from app.core.redis import (
    cache_get,
    cache_set,
    key_chapter_summary,
    key_memory_recall,
    key_relationship_graph,
    key_search_results,
)
from app.core.security import decode_token
from app.core.storage import download_book
from app.engine.analysis.recall import generate_recall
from app.engine.character.consolidator import consolidate_characters
from app.engine.search.semantic import build_search_result, find_context_for_tap, semantic_search
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import Character, CharacterState
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    QuoteEntry,
)
from app.models.progress import ReadingProgress
from app.schemas.books import BookEventsOut, CharacterEventOut, MajorEventOut
from app.schemas.reader import (
    PlotThreadOut,
    SaveQuoteBody,
    TimelineResponseOut,
    UpdatePlotThreadBody,
)
from app.services.chapter_recovery_service import resolve_reader_chapter_payload
from app.services.summary_service import get_or_generate_summary
from app.utils.beta_read_utils import sync_beta_assignments_for_reader_book
from app.utils.billing_utils import summary_mode_allowed
from app.utils.book_utils import (
    collaboration_allows_chapter,
    collaboration_can_copy_manuscript,
    get_book_with_collaboration_access,
)
from app.utils.character_utils import (
    append_unique_summary,
    backfill_character_first_chapters_for_chapter_text,
    relationship_summary_for_character,
    serialize_reader_character,
)
from app.utils.plot_thread_utils import derive_plot_thread_status
from app.utils.public_utils import ensure_public_mode_enabled
from app.utils.queue_utils import queue_for_user

# ── Utils imports ──────────────────────────────────────────────────────────────
from app.utils.reader_utils import (
    build_chapter_list_payload,
    build_reading_progress_payload,
    build_summary_collection_payload,
    build_timeline_track_payload,
    chapter_analysis_status,
    chapter_intelligence_available,
    chapter_intelligence_map,
    collapse_graph_characters,
    dedupe_timeline_events,
    graph_character_visibility_analysis,
    is_graph_character_visible,
    is_valid_timeline_character,
    list_plot_threads,
    normalize_summary_response,
    queue_analysis_if_missing,
    read_available_chapter_set,
    read_chapter_set,
    relationship_node_description,
    require_summary_access,
    summary_visible_chapter_set,
    timeline_character_detail,
    timeline_plot_thread_span,
    timeline_relationship_detail,
    timeline_visible_chapter_set,
    update_plot_thread_note,
)
from app.utils.tag_utils import ENTITY_TYPE_CHAPTER, get_custom_tags_for_entity

router = APIRouter()

BLEACH_EMPTY_TAGS: Any = frozenset()


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


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


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/media/{media_id}")
async def get_chapter_media_public(
    media_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    media = await db.get(ChapterMedia, media_id)
    if not media:
        raise HTTPException(404, "Chapter media not found")

    book = await db.get(Book, media.book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "asset"
        or payload.get("sub") != str(book.user_id)
        or payload.get("res") != f"chapter-media:{media.id}"
    ):
        raise HTTPException(401, "Invalid chapter media token")

    try:
        raw = download_book(media.storage_key)
    except Exception:
        raise HTTPException(404, "Chapter media not found")

    return Response(content=raw, media_type=media.content_type or "application/octet-stream")


@router.get("/{book_id}/chapter/{chapter_num}")
async def get_chapter(
    book_id: uuid.UUID,
    chapter_num: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Returns chapter text URL + all characters introduced up to this chapter."""
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter_num):
        raise HTTPException(403, "This share does not include that chapter.")
    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    resolved_chapter = await resolve_reader_chapter_payload(
        db,
        book=book,
        chapter=chapter,
        chapter_num=chapter_num,
        current_user=current_user,
    )
    if resolved_chapter is None:
        raise HTTPException(404, "Chapter not found")

    chapter_text_content = resolved_chapter["text_content"]
    if await backfill_character_first_chapters_for_chapter_text(
        db,
        book_id=book_id,
        chapter_number=chapter_num,
        chapter_text=chapter_text_content,
    ):
        await db.commit()

    chars_result = await db.execute(
        select(Character)
        .where(Character.book_id == book_id, Character.first_chapter <= chapter_num)
        .order_by(Character.first_chapter)
    )
    chars = chars_result.scalars().all()

    char_ids = [char.id for char in chars]
    states_by_character: dict[uuid.UUID, CharacterState] = {}
    if char_ids:
        states_result = await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id.in_(char_ids), CharacterState.at_chapter <= chapter_num)
            .order_by(CharacterState.character_id, desc(CharacterState.at_chapter))
        )
        states = states_result.scalars().all()
        for state in states:
            states_by_character.setdefault(state.character_id, state)

    char_data = []
    for char in chars:
        char_state = states_by_character.get(char.id)
        trait_snapshot_raw = cast(dict[str, Any], char_state.trait_snapshot) if char_state else cast(dict[str, Any], char.trait_state or {})
        char_data.append(serialize_reader_character(char, trait_snapshot=dict(trait_snapshot_raw)))

    return {
        "chapter_number": chapter_num,
        "chapter_title": resolved_chapter["chapter_title"],
        "content_version": resolved_chapter["content_version"],
        "total_chapters": book.total_chapters,
        "intelligence_available": await chapter_intelligence_available(db, book, current_user, chapter_num),
        "analysis_status": resolved_chapter["analysis_status"],
        "source_integrity": resolved_chapter["source_integrity"],
        "can_copy_manuscript": collaboration_can_copy_manuscript(book, collaborator),
        "text_url": resolved_chapter["text_url"],
        "text_content": resolved_chapter["text_content"],
        "html_content": resolved_chapter["html_content"],
        "media": resolved_chapter["media"],
        "tags": (
            await get_custom_tags_for_entity(
                db,
                entity_type=ENTITY_TYPE_CHAPTER,
                entity_id=chapter.id,
                book_id=book.id,
            )
            if chapter is not None
            else []
        ),
        "characters": char_data,
    }


@router.get("/{book_id}/context")
async def smart_tap(
    book_id: uuid.UUID,
    q: str = Query(..., description="Tapped word or phrase"),
    chapter: int = Query(..., description="Current chapter number"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Smart Tap — the core real-time intelligence endpoint.
    Tap any word → get character context, wiki entry, or relevant passage.
    Always spoiler-gated to current chapter.
    """
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter):
        raise HTTPException(403, "This share does not include that chapter.")
    
    # Check if book has embeddings (processing complete)
    chunk_count = await db.scalar(
        select(func.count()).select_from(BookChunk).where(BookChunk.book_id == book_id)
    )
    if chunk_count == 0:
        # Book still processing, return empty results
        return {"type": "search", "results": []}
    
    char_rows = (
        await db.execute(
            select(Character)
            .where(Character.book_id == book_id, Character.first_chapter <= chapter)
            .order_by(Character.first_chapter, Character.name)
        )
    ).scalars().all()
    needle = q.strip().casefold()
    char = next(
        (
            item
            for item in char_rows
            if needle
            and (
                needle == str(item.name or "").casefold()
                or needle in {str(alias or "").casefold() for alias in (item.aliases or [])}
                or needle in str(item.name or "").casefold()
                or any(needle in str(alias or "").casefold() for alias in (item.aliases or []))
            )
        ),
        None,
    )

    if char:
        states = (
            await db.execute(
                select(CharacterState)
                .where(CharacterState.character_id == char.id, CharacterState.at_chapter <= chapter)
                .order_by(CharacterState.at_chapter)
            )
        ).scalars().all()
        char_state_result = await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id == char.id, CharacterState.at_chapter <= chapter)
            .order_by(CharacterState.at_chapter.desc()).limit(1)
        )
        char_state = char_state_result.scalar()
        trait_snapshot_raw = cast(dict[str, Any], char_state.trait_snapshot) if char_state else cast(dict[str, Any], char.trait_state or {})
        trait_snapshot = dict(trait_snapshot_raw)

        rels_result = await db.execute(
            select(CharacterRelationship).where(
                or_(
                    CharacterRelationship.character_a_id == char.id,
                    CharacterRelationship.character_b_id == char.id
                ),
                CharacterRelationship.from_chapter <= chapter,
                or_(
                    CharacterRelationship.to_chapter.is_(None),
                    CharacterRelationship.to_chapter >= chapter
                ),
            )
        )
        rels = rels_result.scalars().all()
        counterpart_ids = {
            rel.character_b_id if rel.character_a_id == char.id else rel.character_a_id
            for rel in rels
        }
        counterparts = (
            await db.execute(select(Character).where(Character.id.in_(counterpart_ids)))
        ).scalars().all() if counterpart_ids else []
        counterpart_names = {item.id: item.name for item in counterparts}
        rel_summaries: dict[str, list[str]] = {}
        rel_keys: dict[str, set[str]] = {}
        for rel in rels:
            counterpart_name = counterpart_names.get(
                rel.character_b_id if rel.character_a_id == char.id else rel.character_a_id
            )
            if not counterpart_name:
                continue
            summary = relationship_summary_for_character(rel, char.name, counterpart_name, char.name)
            if summary:
                append_unique_summary(
                    rel_summaries,
                    rel_keys,
                    str(char.id),
                    f"{rel.rel_type}:{counterpart_name}".lower(),
                    summary,
                )

        return {
            "type": "character",
            "character": {
                **serialize_reader_character(
                    char,
                    trait_snapshot=trait_snapshot,
                    relationship_summaries=rel_summaries.get(str(char.id), []),
                ),
                "arc_note": char_state.arc_note if char_state else None,
            },
            "relationships": [
                {
                    "with": str(r.character_b_id if r.character_a_id == char.id else r.character_a_id),
                    "type": r.rel_type,
                    "sentiment": r.sentiment,
                    "description": r.description,
                }
                for r in rels
            ],
            "states": [
                {
                    "at_chapter": state.at_chapter,
                    "trait_state": state.trait_snapshot,
                    "arc_note": state.arc_note,
                    "prompt_delta": state.prompt_delta,
                }
                for state in states
            ],
        }

    results = await find_context_for_tap(db, book_id, q, chapter)
    if not results:
        lowered = q.strip().lower()
        lexical_rows = (await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(BookChunk.book_id == book_id, Chapter.number <= chapter, BookChunk.text.ilike(f"%{lowered}%"))
            .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
        )).all()
        results = [
            build_search_result(text=row[0], chunk_index=row[1], chapter_num=row[2], chapter_title=row[3], relevance=0.5)
            for row in lexical_rows
        ]
    return {"type": "search", "results": results}


@router.get("/{book_id}/summary/{chapter_num}")
async def get_summary(
    book_id: uuid.UUID,
    chapter_num: int,
    mode: str = Query("short", description="short | detailed | key_points"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_summary),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter_num):
        raise HTTPException(403, "This share does not include that chapter.")

    if mode not in ("short", "detailed", "key_points"):
        raise HTTPException(400, "Invalid mode")
    if not summary_mode_allowed(current_user, mode):
        raise HTTPException(403, "Upgrade to Author to unlock detailed and key-point summaries.")
    await require_summary_access(db, book, current_user, chapter_num)

    read_set = await read_chapter_set(db, current_user.id, book_id)
    if chapter_num not in read_set and not is_local_mode():
        raise HTTPException(403, "Read the chapter first to unlock its summary.")

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    data = await get_or_generate_summary(db, book_id, chapter_num, mode)
    if not data:
        await queue_analysis_if_missing(db, chapter, current_user)
        raise HTTPException(503, "Chapter text not available yet")
    if data.get("status") != "ready":
        await queue_analysis_if_missing(db, chapter, current_user)
        return {
            "status": data.get("status") or "pending",
            "content": None,
            "diagnostics": data.get("diagnostics") or {"analysis_status": chapter_analysis_status(chapter)},
        }

    data = normalize_summary_response(data["content"], data.get("key_events"), data.get("char_changes"), data.get("clues"))
    await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
    return {"status": "ready", **data, "diagnostics": {"analysis_status": chapter_analysis_status(chapter)}}


@router.get("/{book_id}/events", response_model=BookEventsOut)
async def get_reader_events(
    book_id: uuid.UUID,
    chapter: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    progress_result = await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )
    progress = progress_result.scalar()
    read_set = set(progress.chapters_read or []) if progress else set()
    max_visible_chapter = chapter or (max(read_set) if read_set else (progress.current_chapter if progress else 1))

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

    return BookEventsOut(major_events=major_events, character_events=character_events)


@router.get("/{book_id}/relationships")
async def get_relationships(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    cache_scope = "all" if include_inactive else "active"
    cache_key = f"{key_relationship_graph(str(book_id), chapter)}:v4:{cache_scope}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    chars_result = await db.execute(
        select(Character).where(Character.book_id == book_id, Character.first_chapter <= chapter)
    )
    chars = list(chars_result.scalars().all())

    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter <= chapter,
        )
    )
    historical_rels = list(rels_result.scalars().all())
    relationship_counts: dict[str, int] = {}
    for rel in historical_rels:
        relationship_counts[str(rel.character_a_id)] = relationship_counts.get(str(rel.character_a_id), 0) + 1
        relationship_counts[str(rel.character_b_id)] = relationship_counts.get(str(rel.character_b_id), 0) + 1

    for char in chars:
        setattr(char, "_graph_relationship_count", relationship_counts.get(str(char.id), 0))

    analyses = {
        str(char.id): graph_character_visibility_analysis(char, relationship_counts.get(str(char.id), 0))
        for char in chars
    }

    visible_chars = [char for char in chars if is_graph_character_visible(char)]
    visible_ids = {str(char.id) for char in visible_chars}
    hidden_chars = [char for char in chars if str(char.id) not in visible_ids]
    chars, id_map = collapse_graph_characters(visible_chars)
    canonical_ids = {str(char.id) for char in chars}
    char_names = {str(char.id): char.name for char in chars}
    rels = historical_rels if include_inactive else [
        rel
        for rel in historical_rels
        if rel.to_chapter is None or rel.to_chapter >= chapter
    ]
    rels = [
        rel for rel in rels
        if str(rel.character_a_id) in visible_ids and str(rel.character_b_id) in visible_ids
    ]

    rel_summaries: dict[str, list[str]] = {}
    edge_map: dict[tuple[str, ...], dict[str, Any]] = {}
    for rel in rels:
        source = id_map.get(str(rel.character_a_id), str(rel.character_a_id))
        target = id_map.get(str(rel.character_b_id), str(rel.character_b_id))
        if source == target or source not in canonical_ids or target not in canonical_ids:
            continue
        left_key, right_key = sorted((source, target))
        if include_inactive:
            key = (
                left_key,
                right_key,
                rel.rel_type or "neutral",
                str(rel.from_chapter or 0),
                str(rel.to_chapter or "open"),
            )
        else:
            key = (left_key, right_key, rel.rel_type or "neutral")
        bucket = edge_map.setdefault(key, {
            "relationship_ids": [], "source": key[0], "target": key[1],
            "type": rel.rel_type or "neutral", "sentiment_values": [],
            "descriptions": [], "chapters": [], "end_chapters": [],
        })
        bucket["relationship_ids"].append(str(rel.id))
        if rel.sentiment is not None:
            bucket["sentiment_values"].append(rel.sentiment)
        if rel.description:
            bucket["descriptions"].append(rel.description.strip())
        if rel.from_chapter is not None:
            bucket["chapters"].append(rel.from_chapter)
        if rel.to_chapter is not None:
            bucket["end_chapters"].append(rel.to_chapter)

    for item in edge_map.values():
        for char_id, other_id in ((item["source"], item["target"]), (item["target"], item["source"])):
            rel_summaries.setdefault(char_id, []).append(
                f"{item['type'].replace('_', ' ').capitalize()} connection with {char_names.get(other_id, other_id)}."
            )

    latest_states: dict[str, CharacterState] = {}
    if chars:
        state_rows_result = await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id.in_([char.id for char in chars]), CharacterState.at_chapter <= chapter)
            .order_by(CharacterState.character_id, desc(CharacterState.at_chapter))
        )
        state_rows = state_rows_result.scalars().all()
        for state in state_rows:
            latest_states.setdefault(str(state.character_id), state)

    chars_with_details = []
    for c in chars:
        latest_state = latest_states.get(str(c.id))
        trait_snapshot_raw = cast(dict[str, Any], latest_state.trait_snapshot) if latest_state else cast(dict[str, Any], c.trait_state or {})
        trait_snapshot = dict(trait_snapshot_raw)
        chars_with_details.append({
            "id": str(c.id), "name": c.name, "role": c.role, "first_chapter": c.first_chapter,
            "description": relationship_node_description(c, trait_snapshot, rel_summaries.get(str(c.id), [])),
            "trait_state": trait_snapshot, "personality_tags": c.personality_tags or [],
            "aliases": c.aliases or [], "motivations": c.motivations or [],
            "fears": c.fears or [], "archetype": c.archetype, "arc_summary": c.arc_summary,
            "mention_count": c.mention_count or 0, "is_manual": getattr(c, "is_manual", False),
            "graph_visibility_override": analyses[str(c.id)]["override"],
            "visibility_score": analyses[str(c.id)]["score"],
            "visibility_reasons": analyses[str(c.id)]["reasons"],
        })

    graph = {
        "nodes": chars_with_details,
        "edges": [
            {
                "id": item["relationship_ids"][0] if item["relationship_ids"] else None,
                "source": item["source"], "target": item["target"], "type": item["type"],
                "sentiment": round(sum(item["sentiment_values"]) / len(item["sentiment_values"]), 3) if item["sentiment_values"] else None,
                "description": " ".join(dict.fromkeys(item["descriptions"])) or None,
                "from_chapter": min(item["chapters"]) if item["chapters"] else None,
                "to_chapter": max(item["end_chapters"]) if item["end_chapters"] else None,
                "status": "ended" if item["end_chapters"] and max(item["end_chapters"]) < chapter else "ongoing",
            }
            for item in edge_map.values()
        ],
        "hidden_nodes": [
            {
                "id": str(char.id),
                "name": char.name,
                "role": char.role,
                "first_chapter": char.first_chapter,
                "mention_count": char.mention_count or 0,
                "is_manual": getattr(char, "is_manual", False),
                "graph_visibility_override": analyses[str(char.id)]["override"],
                "visibility_score": analyses[str(char.id)]["score"],
                "visibility_reasons": analyses[str(char.id)]["reasons"],
                "connected_relationship_count": relationship_counts.get(str(char.id), 0),
            }
            for char in sorted(hidden_chars, key=lambda item: (item.first_chapter, item.name))
        ],
    }
    if graph["nodes"] or graph["edges"] or graph["hidden_nodes"]:
        await cache_set(cache_key, graph, settings.REDIS_TTL_GRAPH)
    return graph


@router.get("/{book_id}/search")
async def search(
    book_id: uuid.UUID,
    q: str = Query(...),
    chapter: int = Query(..., description="Max chapter to search — spoiler gate"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_search),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    cache_key = key_search_results(str(book_id), q, chapter)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    results = await semantic_search(
        db,
        book_id,
        q,
        chapter,
        usage_user_id=current_user.id,
        usage_feature="reader_search",
    )
    if not results:
        lowered = q.strip().lower()
        lexical_rows = (await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(BookChunk.book_id == book_id, Chapter.number <= chapter, BookChunk.text.ilike(f"%{lowered}%"))
            .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
        )).all()
        results = [
            build_search_result(text=row[0], chunk_index=row[1], chapter_num=row[2], chapter_title=row[3], relevance=0.5)
            for row in lexical_rows
        ]
    if not results:
        terms = [term for term in q.strip().split() if len(term) >= 3]
        if terms:
            token_filters = [BookChunk.text.ilike(f"%{term}%") for term in terms]
            token_rows = (await db.execute(
                select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
                .join(Chapter, Chapter.id == BookChunk.chapter_id)
                .where(BookChunk.book_id == book_id, Chapter.number <= chapter, or_(*token_filters))
                .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
            )).all()
            results = [
                build_search_result(text=row[0], chunk_index=row[1], chapter_num=row[2], chapter_title=row[3], relevance=0.35)
                for row in token_rows
            ]
    await cache_set(cache_key, results, settings.REDIS_TTL_SEARCH)
    return results


@router.get("/{book_id}/chapters")
async def get_chapter_list(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    return await build_chapter_list_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )


@router.get("/{book_id}/summary-collection")
async def get_summary_collection(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    return await build_summary_collection_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )


@router.get("/{book_id}/foreshadowing")
async def get_foreshadowing_highlights(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await summary_visible_chapter_set(db, book, current_user)
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


@router.get("/{book_id}/timeline", response_model=TimelineResponseOut)
async def get_timeline(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await timeline_visible_chapter_set(db, book, current_user)
    if not read_set:
        return build_timeline_track_payload([], [], [], [], [])

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
    for thread_id, title, introduced_at, last_mentioned_at, resolved_at, status, note, description in thread_rows:
        display_status = derive_plot_thread_status(
            status,
            introduced_at=introduced_at,
            last_mentioned_at=last_mentioned_at or introduced_at,
            resolved_at=resolved_at,
            current_chapter=max(read_set) if read_set else None,
        )
        if introduced_at and introduced_at in read_set:
            events.append({"chapter_number": introduced_at, "chapter_title": chapter_titles.get(introduced_at),
                            "kind": "thread_start", "title": title, "detail": display_status})
        if resolved_at and resolved_at in read_set:
            events.append({"chapter_number": resolved_at, "chapter_title": chapter_titles.get(int(resolved_at)),
                            "kind": "thread_end", "title": title, "detail": "Resolved"})
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
    for rel, _, _ in relationship_rows:
        a_name = character_lookup.get(rel.character_a_id)
        b_name = character_lookup.get(rel.character_b_id)
        if not a_name or not b_name:
            continue
        title, detail = timeline_relationship_detail(a_name, b_name, rel.rel_type, rel.description)
        events.append({
            "chapter_number": rel.from_chapter,
            "chapter_title": chapter_titles.get(rel.from_chapter),
            "kind": "relationship_shift",
            "title": title,
            "detail": detail,
        })
        relationship_markers.append({
            "id": str(rel.id),
            "title": title,
            "chapter_number": rel.from_chapter,
            "detail": detail,
        })

    events = dedupe_timeline_events(events)
    events.sort(key=lambda item: (item["chapter_number"], item["kind"], item["title"]))
    character_tracks.sort(key=lambda item: (item["start_chapter"], item["name"]))
    thread_tracks.sort(key=lambda item: (item["start_chapter"], item["title"]))
    relationship_markers.sort(key=lambda item: (item["chapter_number"], item["title"]))
    return build_timeline_track_payload(chapter_points, events, character_tracks, thread_tracks, relationship_markers)


@router.get("/{book_id}/thematic-search")
async def thematic_search(
    book_id: uuid.UUID,
    q: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_search),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await summary_visible_chapter_set(db, book, current_user)
    if not read_set:
        return {"results": []}

    normalized_query = q.strip().lower()
    terms = [term for term in normalized_query.split() if len(term) >= 3]
    if not terms and normalized_query:
        terms = [normalized_query]
    rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events, ChapterSummary.clues)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)), ChapterSummary.mode.in_(["short", "detailed"]))
        .order_by(Chapter.number)
    )).all()

    results = []
    for chapter_num, chapter_title, content, key_events, clues in rows:
        haystacks = [content or ""]
        haystacks.extend(event.get("event", "") for event in (key_events or []) if isinstance(event, dict))
        haystacks.extend(clue.get("clue", "") for clue in (clues or []) if isinstance(clue, dict))
        haystack_text = " ".join(haystacks).lower()
        score = sum(1 for term in terms if term in haystack_text)
        if not score and normalized_query and normalized_query in haystack_text:
            score = 1
        if score:
            results.append({"chapter_number": chapter_num, "chapter_title": chapter_title,
                             "score": score, "summary": content})
    if not results:
        chapter_rows = (await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)))
            .order_by(Chapter.number)
        )).all()
        for chapter_num, chapter_title, s3_key in chapter_rows:
            if not s3_key:
                continue
            try:
                chapter_text = download_book(s3_key).decode("utf-8", errors="ignore")
            except Exception:
                continue
            normalized_text = chapter_text.lower()
            score = sum(1 for term in terms if term in normalized_text)
            if not score and normalized_query and normalized_query in normalized_text:
                score = 1
            if not score:
                continue
            results.append({"chapter_number": chapter_num, "chapter_title": chapter_title,
                             "score": score, "summary": chapter_text[:320] + ("..." if len(chapter_text) > 320 else "")})
    results.sort(key=lambda item: (-item["score"], item["chapter_number"]))
    return {"results": results[:20]}


@router.get("/{book_id}/relationship-evolution")
async def get_relationship_evolution(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter <= chapter,
        ).order_by(CharacterRelationship.from_chapter, CharacterRelationship.character_a_id, CharacterRelationship.character_b_id)
    )
    rels = rels_result.scalars().all()

    chars_result = await db.execute(select(Character).where(Character.book_id == book_id))
    chars = chars_result.scalars().all()
    name_by_id = {char.id: char.name for char in chars}

    grouped: dict[tuple[str, str], list[dict]] = {}
    for rel in rels:
        a_name = name_by_id.get(rel.character_a_id)
        b_name = name_by_id.get(rel.character_b_id)
        if not a_name or not b_name:
            continue
        key = (a_name, b_name) if a_name <= b_name else (b_name, a_name)
        grouped.setdefault(key, []).append({
            "chapter": rel.from_chapter, "type": rel.rel_type,
            "description": rel.description, "sentiment": rel.sentiment,
        })

    return {"pairs": [{"characters": list(key), "events": value} for key, value in grouped.items()]}


@router.post("/{book_id}/quotes")
async def save_quote(
    book_id: uuid.UUID,
    body: SaveQuoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    quote_text = _clean_text(body.quote_text)
    if not quote_text:
        raise HTTPException(400, "Quote text is required")
    character_name = _clean_text(body.character_name) or None
    note_text = _clean_text(body.note) or None

    quote = QuoteEntry(user_id=current_user.id, book_id=book_id, chapter_number=body.chapter_number,
                       character_name=character_name, quote_text=quote_text, note=note_text)
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return {"id": str(quote.id), "saved": True}


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

    recall_text = await generate_recall(
        title=book.title,
        last_chapter=last_chapter,
        recent_summary=recent_summary,
        active_characters=list(chars),
        open_threads=list(open_threads),
    )

    await cache_set(cache_key, recall_text, settings.REDIS_TTL_RECALL)
    return {"recall": recall_text, "last_chapter": last_chapter}


@router.get("/{book_id}/progress")
async def get_progress(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    return await build_reading_progress_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )


@router.put("/{book_id}/progress")
async def update_progress(
    book_id: uuid.UUID,
    current_chapter: int,
    scroll_pct: float,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, current_chapter):
        raise HTTPException(403, "This share does not include that chapter.")

    p = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()
    if p:
        read_set = set(p.chapters_read or [])
        read_set.add(current_chapter)
        p.current_chapter = current_chapter
        p.scroll_pct = scroll_pct
        p.chapters_read = sorted(read_set)
        p.last_read = datetime.now(UTC)
    else:
        db.add(ReadingProgress(user_id=current_user.id, book_id=book_id,
                               current_chapter=current_chapter, scroll_pct=scroll_pct, chapters_read=[current_chapter]))
    await db.commit()

    from app.workers.tasks.extraction_tasks import process_chapter_task
    total = book.total_chapters or 1
    for n in range(current_chapter + 1, min(current_chapter + 4, total + 1)):
        next_chapter = (await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == n)
        )).scalar()
        if next_chapter and next_chapter.processed:
            continue
        if not await chapter_intelligence_available(db, book, current_user, n):
            continue
        process_chapter_task.apply_async(
            args=[str(book_id), n],
            countdown=n * 3,
            queue=queue_for_user(current_user, "extraction"),
        )
    current_row = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == current_chapter)
    )).scalar()
    if current_row and await chapter_intelligence_available(db, book, current_user, current_chapter):
        await queue_analysis_if_missing(db, current_row, current_user)
    await sync_beta_assignments_for_reader_book(db, book_id=book_id, current_user=current_user)
    return {"ok": True}


@router.put("/{book_id}/progress/mark-book-read")
async def mark_book_read(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)

    total = book.total_chapters or 0
    if total <= 0:
        raise HTTPException(400, "Book has no chapters to mark as read")

    chapters_read = [number for number in range(1, total + 1) if collaboration_allows_chapter(collaborator, number)]
    if not chapters_read:
        raise HTTPException(403, "This share does not include any chapters.")
    progress = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()

    if progress is None:
        progress = ReadingProgress(user_id=current_user.id, book_id=book_id,
                                   current_chapter=max(chapters_read), scroll_pct=1.0, chapters_read=chapters_read)
        db.add(progress)
    else:
        progress.current_chapter = max(chapters_read)
        progress.scroll_pct = 1.0
        progress.chapters_read = chapters_read
        progress.last_read = datetime.now(UTC)

    await db.commit()
    await sync_beta_assignments_for_reader_book(db, book_id=book_id, current_user=current_user)
    return {"ok": True, "current_chapter": max(chapters_read), "chapters_read_count": len(chapters_read), "percent_complete": 100.0, "chapters_left": 0}


@router.put("/{book_id}/progress/chapter-status")
async def update_chapter_read_status(
    book_id: uuid.UUID,
    chapter: int,
    read: bool,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter):
        raise HTTPException(403, "This share does not include that chapter.")

    progress = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()

    if progress is None:
        chapters_read = [chapter] if read else []
        progress = ReadingProgress(user_id=current_user.id, book_id=book_id,
                                   current_chapter=max(chapter, 1), scroll_pct=0.0, chapters_read=chapters_read)
        db.add(progress)
    else:
        read_set = set(progress.chapters_read or [])
        if read:
            read_set.add(chapter)
            progress.current_chapter = max(progress.current_chapter, chapter)
        else:
            read_set.discard(chapter)
        progress.chapters_read = sorted(read_set)
        progress.last_read = datetime.now(UTC)

    await db.commit()
    if read:
        chapter_row = (await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter)
        )).scalar()
        if chapter_row and await chapter_intelligence_available(db, book, current_user, chapter):
            await queue_analysis_if_missing(db, chapter_row, current_user)
    await sync_beta_assignments_for_reader_book(db, book_id=book_id, current_user=current_user)
    return {"ok": True, "chapter": chapter, "read": read}
