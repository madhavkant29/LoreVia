"""
Reader routes — the core intelligence surface.
Smart tap, summaries, relationship graph, memory recall, progress.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_search, rate_limit_summary
from app.core.config import is_local_mode, settings
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_chapter_summary, key_relationship_graph, key_memory_recall, key_search_results
from app.core.storage import download_book, get_presigned_url
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState
from app.models.intelligence import BookChunk, ChapterSummary, CharacterRelationship, PlotThread, QuoteEntry
from app.models.progress import ReadingProgress
from app.schemas.reader import (
    PlotThreadOut,
    SaveQuoteBody,
    TimelineResponseOut,
    UpdatePlotThreadBody,
)
from app.engine.search.semantic import build_search_result, find_context_for_tap, semantic_search
from app.engine.analysis.recall import generate_recall
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.profile_builder import build_description
from app.services.summary_service import get_or_generate_summary

# ── Utils imports ──────────────────────────────────────────────────────────────
from app.utils.reader_utils import (
    GRAPH_CHARACTER_STOPWORDS,
    TIMELINE_CHARACTER_EXACT_BLOCKLIST,
    TIMELINE_CHARACTER_PREFIXES,
    TIMELINE_CHARACTER_STOPWORDS,
    TIMELINE_CHARACTER_SUFFIXES,
    chapter_has_any_summary,
    chapter_intelligence_available,
    chapter_intelligence_map,
    collapse_graph_characters,
    dedupe_timeline_events,
    extract_media_markers,
    build_timeline_track_payload,
    is_graph_character_visible,
    is_valid_timeline_character,
    merge_media_items,
    normalize_summary_response,
    normalize_timeline_label,
    parse_chapter_from_source,
    queue_analysis_if_missing,
    read_available_chapter_set,
    read_chapter_set,
    relationship_node_description,
    require_summary_access,
    list_plot_threads,
    serialize_chapter_media,
    serialize_inline_images,
    timeline_character_detail,
    timeline_relationship_detail,
    update_plot_thread_note,
)
from app.utils.book_utils import deserialize_manuscript_content

router = APIRouter()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/{book_id}/chapter/{chapter_num}")
async def get_chapter(
    book_id: uuid.UUID,
    chapter_num: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Returns chapter text URL + all characters introduced up to this chapter."""
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    await consolidate_characters(db, book_id, up_to_chapter=chapter_num)

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    fallback_text = None
    fallback_title = None
    fallback_media = []
    stored_text_content = None
    stored_html_content = None
    stored_media = []
    if not chapter:
        fallback = parse_chapter_from_source(book, chapter_num)
        if fallback:
            fallback_title = fallback.get("title")
            fallback_text = fallback.get("text")
            fallback_media = serialize_inline_images(fallback.get("images", []))
        if fallback_text is None:
            raise HTTPException(404, "Chapter not found")
    else:
        if chapter.s3_key:
            try:
                stored_payload = deserialize_manuscript_content(download_book(chapter.s3_key))
                stored_text_content = str(stored_payload.get("text") or "")
                stored_html_content = str(stored_payload.get("html") or "") or None
            except Exception:
                stored_text_content = None
                stored_html_content = None
        else:
            stored_html_content = None
        stored_media = await serialize_chapter_media(db, chapter.id)

        stored_markers = extract_media_markers(stored_text_content)
        needs_source_recovery = (
            book.format == "pdf"
            and (
                not stored_text_content
                or ("[[IMAGE:" in stored_text_content and not stored_media)
                or (stored_media and not stored_markers)
                or (stored_markers and len(stored_markers) != len(stored_media))
            )
        )
        if needs_source_recovery:
            fallback = parse_chapter_from_source(book, chapter_num)
            if fallback:
                fallback_title = fallback.get("title")
                fallback_text = fallback.get("text")
                fallback_media = serialize_inline_images(fallback.get("images", []))
                fallback_markers = extract_media_markers(fallback_text)
                if fallback_text and fallback_markers and len(fallback_markers) == len(fallback_media):
                    stored_text_content = fallback_text
                    stored_media = fallback_media
                else:
                    if not stored_text_content and fallback_text:
                        stored_text_content = fallback_text
                    if fallback_media:
                        stored_media = merge_media_items(stored_media, fallback_media)

    chars = (await db.execute(
        select(Character)
        .where(Character.book_id == book_id, Character.first_chapter <= chapter_num)
        .order_by(Character.first_chapter)
    )).scalars().all()

    char_ids = [char.id for char in chars]
    states_by_character: dict[uuid.UUID, CharacterState] = {}
    if char_ids:
        states = (await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id.in_(char_ids), CharacterState.at_chapter <= chapter_num)
            .order_by(CharacterState.character_id, desc(CharacterState.at_chapter))
        )).scalars().all()
        for state in states:
            states_by_character.setdefault(state.character_id, state)

    char_data = []
    for char in chars:
        char_state = states_by_character.get(char.id)
        trait_snapshot = char_state.trait_snapshot if char_state else (char.trait_state or {})
        char_data.append({
            "id": str(char.id),
            "name": char.name,
            "aliases": char.aliases or [],
            "role": char.role,
            "first_chapter": char.first_chapter,
            "description": build_description(trait_snapshot, char.archetype),
            "personality_tags": char.personality_tags or [],
        })

    return {
        "chapter_number": chapter_num,
        "chapter_title": chapter.title if chapter else fallback_title,
        "total_chapters": book.total_chapters,
        "intelligence_available": await chapter_intelligence_available(db, book, current_user, chapter_num),
        "text_url": get_presigned_url(chapter.s3_key) if chapter and chapter.s3_key else None,
        "text_content": stored_text_content if chapter else fallback_text,
        "html_content": stored_html_content if chapter else None,
        "media": stored_media if chapter else fallback_media,
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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await consolidate_characters(db, book_id, up_to_chapter=chapter)

    char = (await db.execute(
        select(Character).where(Character.book_id == book_id, Character.name.ilike(f"%{q}%"), Character.first_chapter <= chapter)
    )).scalar()

    if char:
        char_state = (await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id == char.id, CharacterState.at_chapter <= chapter)
            .order_by(CharacterState.at_chapter.desc()).limit(1)
        )).scalar()

        rels = (await db.execute(
            select(CharacterRelationship).where(
                (CharacterRelationship.character_a_id == char.id) | (CharacterRelationship.character_b_id == char.id),
                CharacterRelationship.from_chapter <= chapter,
                (CharacterRelationship.to_chapter == None) | (CharacterRelationship.to_chapter >= chapter),
            )
        )).scalars().all()

        return {
            "type": "character",
            "character": {
                "id": str(char.id),
                "name": char.name,
                "aliases": char.aliases or [],
                "role": char.role,
                "trait_state": char_state.trait_snapshot if char_state else char.trait_state,
                "description": build_description(char_state.trait_snapshot if char_state else (char.trait_state or {}), char.archetype),
                "personality_tags": char.personality_tags or [],
                "motivations": char.motivations or [],
                "fears": char.fears or [],
                "arc_note": char_state.arc_note if char_state else None,
                "first_chapter": char.first_chapter,
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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await require_summary_access(db, book, current_user, chapter_num)

    if mode not in ("short", "detailed", "key_points"):
        raise HTTPException(400, "Invalid mode")

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
        await queue_analysis_if_missing(db, chapter)
        raise HTTPException(503, "Chapter text not available yet")

    data = normalize_summary_response(data["content"], data.get("key_events"), data.get("char_changes"), data.get("clues"))
    await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
    return data


@router.get("/{book_id}/relationships")
async def get_relationships(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await consolidate_characters(db, book_id, up_to_chapter=chapter)

    cache_key = f"{key_relationship_graph(str(book_id), chapter)}:v3"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    chars = (await db.execute(
        select(Character).where(Character.book_id == book_id, Character.first_chapter <= chapter)
    )).scalars().all()
    chars = [char for char in chars if is_graph_character_visible(char)]
    visible_ids = {str(char.id) for char in chars}
    chars, id_map = collapse_graph_characters(chars)
    canonical_ids = {str(char.id) for char in chars}
    char_names = {str(char.id): char.name for char in chars}

    rels = (await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter <= chapter,
            (CharacterRelationship.to_chapter == None) | (CharacterRelationship.to_chapter >= chapter),
        )
    )).scalars().all()
    rels = [
        rel for rel in rels
        if str(rel.character_a_id) in visible_ids and str(rel.character_b_id) in visible_ids
    ]

    rel_summaries: dict[str, list[str]] = {}
    edge_map: dict[tuple[str, str, str], dict] = {}
    for rel in rels:
        source = id_map.get(str(rel.character_a_id), str(rel.character_a_id))
        target = id_map.get(str(rel.character_b_id), str(rel.character_b_id))
        if source == target or source not in canonical_ids or target not in canonical_ids:
            continue
        key = tuple(sorted([source, target])) + (rel.rel_type or "neutral",)
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
        state_rows = (await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id.in_([char.id for char in chars]), CharacterState.at_chapter <= chapter)
            .order_by(CharacterState.character_id, desc(CharacterState.at_chapter))
        )).scalars().all()
        for state in state_rows:
            latest_states.setdefault(str(state.character_id), state)

    chars_with_details = []
    for c in chars:
        latest_state = latest_states.get(str(c.id))
        trait_snapshot = latest_state.trait_snapshot if latest_state else (c.trait_state or {})
        chars_with_details.append({
            "id": str(c.id), "name": c.name, "role": c.role, "first_chapter": c.first_chapter,
            "description": relationship_node_description(c, trait_snapshot, rel_summaries.get(str(c.id), [])),
            "trait_state": trait_snapshot, "personality_tags": c.personality_tags or [],
            "aliases": c.aliases or [], "motivations": c.motivations or [],
            "fears": c.fears or [], "archetype": c.archetype, "arc_summary": c.arc_summary,
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
            }
            for item in edge_map.values()
        ],
    }
    if graph["nodes"] or graph["edges"]:
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

    results = await semantic_search(db, book_id, q, chapter)
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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
        )
    )).scalar()
    read_upto = progress.current_chapter if progress else 0
    read_set = set(progress.chapters_read or []) if progress else set()

    chapters = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number)
    )).scalars().all()
    if not chapters and book.total_chapters:
        return {
            "read_upto": read_upto,
            "current_chapter": read_upto,
            "chapters": [
                {"number": number, "title": f"Chapter {number}", "processed": False,
                 "intelligence_available": True, "read": number in read_set}
                for number in range(1, book.total_chapters + 1)
            ],
        }
    intelligence_map = await chapter_intelligence_map(db, book, current_user)

    return {
        "read_upto": read_upto,
        "current_chapter": read_upto,
        "chapters": [
            {
                "number": chapter.number, "title": chapter.title, "processed": chapter.processed,
                "intelligence_available": intelligence_map.get(chapter.number, True),
                "read": chapter.number in read_set,
            }
            for chapter in chapters
        ],
    }


@router.get("/{book_id}/summary-collection")
async def get_summary_collection(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
        )
    )).scalar()
    read_upto = progress.current_chapter if progress else 0
    read_set = set(progress.chapters_read or []) if progress else set()
    available_set = await read_available_chapter_set(db, book, current_user, read_set)

    if not available_set:
        return {"read_upto": 0, "summaries": []}

    chapter_rows = (await db.execute(
        select(Chapter.number, Chapter.title, Chapter.id)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(available_set)))
        .order_by(Chapter.number)
    )).all()

    summary_rows = (await db.execute(
        select(ChapterSummary.chapter_id, ChapterSummary.content, ChapterSummary.key_events)
        .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(available_set)), ChapterSummary.mode == "short")
    )).all()
    summary_by_chapter_id = {str(row[0]): {"content": row[1], "key_events": row[2] or []} for row in summary_rows}

    for chapter_number, chapter_title, chapter_id in chapter_rows:
        chapter_key = str(chapter_id)
        if chapter_key in summary_by_chapter_id:
            continue
        summary_data = await get_or_generate_summary(db, book_id, chapter_number, "short")
        if summary_data:
            summary_by_chapter_id[chapter_key] = {
                "content": summary_data["content"],
                "key_events": summary_data.get("key_events") or [],
            }

    return {
        "read_upto": read_upto,
        "summaries": [
            {
                "chapter_number": row[0], "chapter_title": row[1], "read": True,
                "available": str(row[2]) in summary_by_chapter_id,
                "content": summary_by_chapter_id.get(str(row[2]), {}).get("content"),
                "key_events": summary_by_chapter_id.get(str(row[2]), {}).get("key_events", []),
            }
            for row in chapter_rows
        ],
    }


@router.get("/{book_id}/foreshadowing")
async def get_foreshadowing_highlights(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await read_available_chapter_set(db, book, current_user, await read_chapter_set(db, current_user.id, book_id))
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

    chapter_rows = (await db.execute(
        select(Chapter.number, Chapter.title, Chapter.id, Chapter.s3_key)
        .where(Chapter.book_id == book_id, Chapter.number.in_(sorted(read_set)))
        .order_by(Chapter.number)
    )).all()

    from app.engine.analysis.summariser import generate_summary

    generated_rows = []
    for number, title, chapter_id, s3_key in chapter_rows:
        existing = (await db.execute(
            select(ChapterSummary).where(ChapterSummary.chapter_id == chapter_id, ChapterSummary.mode == "detailed")
        )).scalar()
        if existing:
            generated_rows.append((number, title, existing.clues or []))
            continue
        if not s3_key:
            continue
        try:
            chapter_text = download_book(s3_key).decode("utf-8", errors="ignore")
        except Exception:
            continue
        data = await generate_summary(chapter_text, "detailed", title or "")
        row = ChapterSummary(chapter_id=chapter_id, mode="detailed", content=data["content"],
                             key_events=data.get("key_events"), char_changes=data.get("char_changes"), clues=data.get("clues"))
        db.add(row)
        generated_rows.append((number, title, data.get("clues") or []))

    if generated_rows:
        await db.commit()

    for number, title, clues in generated_rows:
        for clue in clues or []:
            if isinstance(clue, dict) and clue.get("clue"):
                items.append({"chapter_number": number, "chapter_title": title,
                               "clue": clue.get("clue"), "foreshadows": clue.get("foreshadows")})
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

    base_read_set = await read_chapter_set(db, current_user.id, book_id)
    if book.mode == "author":
        availability = await chapter_intelligence_map(db, book, current_user)
        read_set = {chapter for chapter, available in availability.items() if available}
    else:
        # Timeline should reflect what the reader has actually read.
        # Do not gate it on intelligence availability/budgets; the payload will naturally be sparse
        # until summaries/relationships/threads exist.
        read_set = base_read_set
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
        select(PlotThread.id, PlotThread.title, PlotThread.introduced_at, PlotThread.resolved_at, PlotThread.status, PlotThread.note, PlotThread.description)
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
    character_lookup = {
        char.id: char.name
        for char in (await db.execute(select(Character).where(Character.book_id == book_id))).scalars().all()
    }

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
    visible_characters = (
        await db.execute(
            select(Character).where(Character.book_id == book_id, Character.first_chapter.in_(sorted(read_set))).order_by(Character.first_chapter, Character.name)
        )
    ).scalars().all()
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
    for thread_id, title, introduced_at, resolved_at, status, note, description in thread_rows:
        if introduced_at and introduced_at in read_set:
            events.append({"chapter_number": introduced_at, "chapter_title": chapter_titles.get(introduced_at),
                            "kind": "thread_start", "title": title, "detail": status})
        if resolved_at and resolved_at in read_set:
            events.append({"chapter_number": resolved_at, "chapter_title": chapter_titles.get(int(resolved_at)),
                            "kind": "thread_end", "title": title, "detail": "Resolved"})
        if introduced_at and introduced_at in read_set:
            thread_tracks.append({
                "id": str(thread_id),
                "title": title,
                "status": status,
                "start_chapter": introduced_at,
                "end_chapter": max(introduced_at, min(resolved_at or max(read_set), max(read_set))),
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
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await read_available_chapter_set(db, book, current_user, await read_chapter_set(db, current_user.id, book_id))
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

    rels = (await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter <= chapter,
        ).order_by(CharacterRelationship.from_chapter, CharacterRelationship.character_a_id, CharacterRelationship.character_b_id)
    )).scalars().all()

    chars = (await db.execute(select(Character).where(Character.book_id == book_id))).scalars().all()
    name_by_id = {char.id: char.name for char in chars}

    grouped: dict[tuple[str, str], list[dict]] = {}
    for rel in rels:
        a_name = name_by_id.get(rel.character_a_id)
        b_name = name_by_id.get(rel.character_b_id)
        if not a_name or not b_name:
            continue
        key = tuple(sorted([a_name, b_name]))
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
    import bleach  # type: ignore[import-untyped]
    quote_text = bleach.clean((body.quote_text or "").strip(), tags=[], strip=True)
    if not quote_text:
        raise HTTPException(400, "Quote text is required")
    character_name = bleach.clean((body.character_name or "").strip(), tags=[], strip=True) or None
    note_text = bleach.clean((body.note or "").strip(), tags=[], strip=True) or None

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

    thread = await update_plot_thread_note(db, book_id, thread_id, body.note)
    if thread is None:
        raise HTTPException(404, "Plot thread not found")
    return thread


@router.get("/{book_id}/recall")
async def memory_recall(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    cache_key = key_memory_recall(str(current_user.id), str(book_id))
    cached = await cache_get(cache_key)
    if cached:
        return {"recall": cached, "cached": True}

    progress = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()
    if not progress:
        return {"recall": None}

    last_chapter = progress.current_chapter
    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == last_chapter)
    )).scalar()

    recent_summary = ""
    if chapter:
        summ = (await db.execute(
            select(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id, ChapterSummary.mode == "short")
        )).scalar()
        if summ:
            recent_summary = summ.content

    chars = (await db.execute(
        select(Character.name).where(Character.book_id == book_id, Character.first_chapter <= last_chapter).limit(8)
    )).scalars().all()

    open_threads = (await db.execute(
        select(PlotThread.title).where(
            PlotThread.book_id == book_id,
            PlotThread.status.in_(["ongoing", "introduced"]),
            PlotThread.introduced_at <= last_chapter,
        ).limit(3)
    )).scalars().all()

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
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    p = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()
    total = book.total_chapters or 0
    chapters_read = sorted(set((p.chapters_read or []) if p else []))
    if not chapters_read and p and p.current_chapter:
        chapters_read = list(range(1, p.current_chapter + 1))
    chapters_read_count = len(chapters_read)
    percent_complete = round((chapters_read_count / total) * 100, 1) if total else 0.0
    return {
        "current_chapter": p.current_chapter if p else 1,
        "scroll_pct": p.scroll_pct if p else 0.0,
        "chapters_read_count": chapters_read_count,
        "percent_complete": percent_complete,
        "chapters_left": max(total - chapters_read_count, 0) if total else 0,
    }


@router.put("/{book_id}/progress")
async def update_progress(
    book_id: uuid.UUID,
    current_chapter: int,
    scroll_pct: float,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    p = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()
    if p:
        read_set = set(p.chapters_read or [])
        read_set.add(current_chapter)
        p.current_chapter = current_chapter
        p.scroll_pct = scroll_pct
        p.chapters_read = sorted(read_set)
        p.last_read = datetime.now(timezone.utc)
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
        process_chapter_task.apply_async(args=[str(book_id), n, "", ""], countdown=n * 3, queue="extraction")
    current_row = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == current_chapter)
    )).scalar()
    if current_row and await chapter_intelligence_available(db, book, current_user, current_chapter):
        await queue_analysis_if_missing(db, current_row)
    return {"ok": True}


@router.put("/{book_id}/progress/mark-book-read")
async def mark_book_read(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    total = book.total_chapters or 0
    if total <= 0:
        raise HTTPException(400, "Book has no chapters to mark as read")

    chapters_read = list(range(1, total + 1))
    progress = (await db.execute(
        select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id)
    )).scalar()

    if progress is None:
        progress = ReadingProgress(user_id=current_user.id, book_id=book_id,
                                   current_chapter=total, scroll_pct=1.0, chapters_read=chapters_read)
        db.add(progress)
    else:
        progress.current_chapter = total
        progress.scroll_pct = 1.0
        progress.chapters_read = chapters_read
        progress.last_read = datetime.now(timezone.utc)

    await db.commit()
    return {"ok": True, "current_chapter": total, "chapters_read_count": total, "percent_complete": 100.0, "chapters_left": 0}


@router.put("/{book_id}/progress/chapter-status")
async def update_chapter_read_status(
    book_id: uuid.UUID,
    chapter: int,
    read: bool,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

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
        progress.last_read = datetime.now(timezone.utc)

    await db.commit()
    if read:
        chapter_row = (await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter)
        )).scalar()
        if chapter_row and await chapter_intelligence_available(db, book, current_user, chapter):
            await queue_analysis_if_missing(db, chapter_row)
    return {"ok": True, "chapter": chapter, "read": read}
