"""
Reader routes — the core intelligence surface.
Smart tap, summaries, relationship graph, memory recall, progress.
"""
import base64
import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_search, rate_limit_summary
from app.core.config import effective_tier, settings
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_chapter_summary, key_relationship_graph, key_memory_recall, key_search_results
from app.core.storage import download_book, get_presigned_url
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import Character, CharacterState
from app.models.intelligence import BookChunk, ChapterSummary, CharacterRelationship, PlotThread, QuoteEntry
from app.models.progress import ReadingProgress, ReadingSession
from app.engine.search.semantic import build_search_result, find_context_for_tap, semantic_search
from app.engine.analysis.recall import generate_recall
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.deduplicator import names_equivalent
from app.engine.character.profile_builder import build_description

router = APIRouter()

TIMELINE_CHARACTER_STOPWORDS = {
    "after", "and", "but", "faculty", "goodbye", "indeed", "just", "lady",
    "leaving", "maybe", "miss", "now", "once", "regardless", "seeing", "she",
    "that", "the narrator", "this", "though", "using", "very", "well", "what",
    "when", "with", "yes", "you", "my brother", "recalling", "considering",
    "looking", "taking", "matching", "hearing", "creation",
}
TIMELINE_CHARACTER_PREFIXES = (
    "the ",
)
TIMELINE_CHARACTER_EXACT_BLOCKLIST = {
    "Clock Tower", "Far East", "Fourth Holy Grail", "Great Ritual", "Mage's Association",
    "Magic Circles", "Magic Circuits", "Magic Crest", "Milky Way", "Modern Magecraft",
    "Mystic Codes", "New Age", "Nuclear Energy", "Seven Wonders", "Source Crest",
    "The Twin Towers", "United States",
}
TIMELINE_CHARACTER_SUFFIXES = (
    " Association",
    " Convention",
    " Fundamentals",
    " Energy",
    " Sequence",
)
GRAPH_CHARACTER_STOPWORDS = TIMELINE_CHARACTER_STOPWORDS | {"lord", "lords", "war", "are", "around", "however"}


class SaveQuoteBody(BaseModel):
    quote_text: str
    chapter_number: int | None = None
    character_name: str | None = None
    note: str | None = None


def _normalize_timeline_label(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _is_valid_timeline_character(name: str | None, role: str | None, aliases: list[str] | None, arc_summary: str | None) -> bool:
    normalized = _normalize_timeline_label(name)
    if not normalized:
        return False
    if normalized in TIMELINE_CHARACTER_STOPWORDS:
        return False
    if any(normalized.endswith(suffix) for suffix in ("ing", "ed", "ly", "tion")) and len(normalized) > 5:
        return False
    if any(normalized.startswith(prefix) for prefix in TIMELINE_CHARACTER_PREFIXES):
        return False

    title = re.sub(r"\s+", " ", (name or "").strip())
    if title in TIMELINE_CHARACTER_EXACT_BLOCKLIST:
        return False
    if any(title.endswith(suffix) for suffix in TIMELINE_CHARACTER_SUFFIXES):
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'-]*", title)
    if not words:
        return False
    if len(words) == 1 and len(words[0]) <= 3:
        return False
    if len(words) == 1 and words[0][0].islower():
        return False

    has_supporting_profile = bool(role or aliases or arc_summary)
    looks_person_like = len(words) >= 2 or any("'" in word or "-" in word for word in words)
    if not has_supporting_profile and not looks_person_like:
        return False
    return True


def _timeline_character_detail(name: str | None, role: str | None, aliases: list[str] | None, arc_summary: str | None) -> str:
    if arc_summary:
        return arc_summary
    if role == "mc":
        return "Major character becomes part of the story."
    if role == "sc":
        return "Supporting character enters the story."
    if aliases:
        alias_preview = ", ".join(alias for alias in aliases[:2] if alias and alias != name)
        if alias_preview:
            return f"Also referred to as {alias_preview}."
    return "Character enters the story."


def _dedupe_timeline_events(events: list[dict]) -> list[dict]:
    seen: set[tuple[int, str, str]] = set()
    deduped = []
    for event in events:
        key = (
            int(event["chapter_number"]),
            str(event["kind"]),
            _normalize_timeline_label(str(event["title"])),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


def _relationship_node_description(char: Character, trait_snapshot: dict, relationship_summaries: list[str]) -> str:
    segments: list[str] = []
    base = build_description(trait_snapshot, char.archetype)
    if base and base != "appearance not yet described":
        segments.append(base)
    if char.arc_summary:
        segments.append(char.arc_summary)
    if char.personality_tags:
        segments.append(f"Disposition: {', '.join(char.personality_tags[:3])}.")
    if char.motivations:
        segments.append(f"Wants: {', '.join(char.motivations[:2])}.")
    if relationship_summaries:
        segments.append(" ".join(relationship_summaries[:2]))
    return " ".join(segment.strip() for segment in segments if segment).strip() or "No narrative details discovered yet."


def _is_graph_character_visible(char: Character) -> bool:
    name = " ".join((char.name or "").split())
    normalized = _normalize_timeline_label(name)
    if not normalized or normalized in GRAPH_CHARACTER_STOPWORDS:
        return False
    if any(normalized.endswith(suffix) for suffix in ("ing", "ed", "ly", "tion")) and len(normalized) > 5:
        return False
    if name in TIMELINE_CHARACTER_EXACT_BLOCKLIST:
        return False
    if any(name.endswith(suffix) for suffix in TIMELINE_CHARACTER_SUFFIXES):
        return False
    if name.endswith("'s"):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", name)
    if not words:
        return False
    if len(words) == 1 and len(words[0]) <= 3:
        return False
    evidence = any([
        char.role,
        char.aliases,
        char.personality_tags,
        char.motivations,
        char.fears,
        char.arc_summary,
        char.archetype,
        char.trait_state,
    ])
    return len(words) > 1 or bool(evidence)


def _character_evidence_score(char: Character) -> tuple[int, int]:
    score = sum(
        1
        for value in [
            char.role,
            char.aliases,
            char.personality_tags,
            char.motivations,
            char.fears,
            char.arc_summary,
            char.archetype,
            char.trait_state,
        ]
        if value
    )
    return score, len((char.name or "").strip())


def _collapse_graph_characters(chars: list[Character]) -> tuple[list[Character], dict[str, str]]:
    canonical: list[Character] = []
    id_map: dict[str, str] = {}

    for char in chars:
        match = next(
            (
                existing
                for existing in canonical
                if names_equivalent(char.name, char.aliases or [], existing.name, existing.aliases or [])
            ),
            None,
        )
        if match is None:
            canonical.append(char)
            id_map[str(char.id)] = str(char.id)
            continue

        primary, duplicate = (match, char)
        if _character_evidence_score(char) > _character_evidence_score(match):
            primary, duplicate = char, match
            canonical = [item for item in canonical if item.id != match.id]
            canonical.append(primary)
            for source_id, target_id in list(id_map.items()):
                if target_id == str(match.id):
                    id_map[source_id] = str(primary.id)

        merged_aliases = {
            alias.strip()
            for alias in [*(primary.aliases or []), *(duplicate.aliases or []), primary.name, duplicate.name]
            if alias and alias.strip() and alias.strip().lower() != primary.name.strip().lower()
        }
        primary.aliases = sorted(merged_aliases)
        primary.personality_tags = list(dict.fromkeys([*(primary.personality_tags or []), *(duplicate.personality_tags or [])]))
        primary.motivations = list(dict.fromkeys([*(primary.motivations or []), *(duplicate.motivations or [])]))
        primary.fears = list(dict.fromkeys([*(primary.fears or []), *(duplicate.fears or [])]))
        primary.role = primary.role or duplicate.role
        primary.arc_summary = primary.arc_summary or duplicate.arc_summary
        primary.archetype = primary.archetype or duplicate.archetype
        primary.trait_state = primary.trait_state or duplicate.trait_state
        primary.first_chapter = min(primary.first_chapter, duplicate.first_chapter)

        id_map[str(char.id)] = str(primary.id)
        id_map[str(duplicate.id)] = str(primary.id)

    return sorted(canonical, key=lambda item: (item.first_chapter, item.name)), id_map


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
    stored_media = []
    if not chapter:
        fallback = _parse_chapter_from_source(book, chapter_num)
        if fallback:
            fallback_title = fallback.get("title")
            fallback_text = fallback.get("text")
            fallback_media = _serialize_inline_images(fallback.get("images", []))
        if fallback_text is None:
            raise HTTPException(404, "Chapter not found")
    else:
        if chapter.s3_key and not get_presigned_url(chapter.s3_key):
            try:
                stored_text_content = download_book(chapter.s3_key).decode("utf-8", errors="ignore")
            except Exception:
                stored_text_content = None
        stored_media = await _serialize_chapter_media(db, chapter.id)

        stored_markers = _extract_media_markers(stored_text_content)
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
            fallback = _parse_chapter_from_source(book, chapter_num)
            if fallback:
                fallback_title = fallback.get("title")
                fallback_text = fallback.get("text")
                fallback_media = _serialize_inline_images(fallback.get("images", []))
                fallback_markers = _extract_media_markers(fallback_text)
                if fallback_text and fallback_markers and len(fallback_markers) == len(fallback_media):
                    stored_text_content = fallback_text
                    stored_media = fallback_media
                else:
                    if not stored_text_content and fallback_text:
                        stored_text_content = fallback_text
                    if fallback_media:
                        stored_media = _merge_media_items(stored_media, fallback_media)
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
        state = states_by_character.get(char.id)
        trait_snapshot = state.trait_snapshot if state else (char.trait_state or {})

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
        "intelligence_available": await _chapter_intelligence_available(db, book, current_user, chapter_num),
        "text_url": get_presigned_url(chapter.s3_key) if chapter and chapter.s3_key else None,
        "text_content": stored_text_content if chapter else fallback_text,
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

    # 1. Exact character name match
    char = (await db.execute(
        select(Character).where(Character.book_id == book_id, Character.name.ilike(f"%{q}%"), Character.first_chapter <= chapter)
    )).scalar()

    if char:
        state = (await db.execute(
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
                "trait_state": state.trait_snapshot if state else char.trait_state,
                "description": build_description(state.trait_snapshot if state else (char.trait_state or {}), char.archetype),
                "personality_tags": char.personality_tags or [],
                "motivations": char.motivations or [],
                "fears": char.fears or [],
                "arc_note": state.arc_note if state else None,
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

    # 2. Semantic search fallback
    results = await find_context_for_tap(db, book_id, q, chapter)
    if not results:
        lowered = q.strip().lower()
        lexical_rows = (await db.execute(
            select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == BookChunk.chapter_id)
            .where(
                BookChunk.book_id == book_id,
                Chapter.number <= chapter,
                BookChunk.text.ilike(f"%{lowered}%"),
            )
            .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
        )).all()

        results = [
            build_search_result(
                text=row[0],
                chunk_index=row[1],
                chapter_num=row[2],
                chapter_title=row[3],
                relevance=0.5,
            )
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
    _require_summary_access(book, current_user, chapter_num)

    if mode not in ("short", "detailed", "key_points"):
        raise HTTPException(400, "Invalid mode")

    read_set = await _read_chapter_set(db, current_user.id, book_id)
    if chapter_num not in read_set:
        raise HTTPException(403, "Read the chapter first to unlock its summary.")

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    # Try Redis cache
    cached = await cache_get(key_chapter_summary(str(chapter.id), mode))
    if cached:
        return cached

    # Try DB
    summary = (await db.execute(
        select(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id, ChapterSummary.mode == mode)
    )).scalar()

    if summary:
        data = _normalize_summary_response(summary.content, summary.key_events, summary.char_changes, summary.clues)
        await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
        return data

    # Generate on demand (fallback — normally pre-generated by worker)
    from app.engine.analysis.summariser import generate_summary
    from app.core.storage import download_book
    try:
        raw = download_book(chapter.s3_key)
        chapter_text = raw.decode("utf-8", errors="ignore")
    except Exception:
        await _queue_analysis_if_missing(db, chapter)
        raise HTTPException(503, "Chapter text not available yet")

    data = await generate_summary(chapter_text, mode, chapter.title or "")
    row = ChapterSummary(chapter_id=chapter.id, mode=mode, content=data["content"],
                          key_events=data.get("key_events"), char_changes=data.get("char_changes"),
                          clues=data.get("clues"))
    db.add(row)
    await db.commit()
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

    cache_key = f"{key_relationship_graph(str(book_id), chapter)}:v2"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    chars = (await db.execute(
        select(Character).where(Character.book_id == book_id, Character.first_chapter <= chapter)
    )).scalars().all()
    chars = [char for char in chars if _is_graph_character_visible(char)]
    visible_ids = {str(char.id) for char in chars}
    chars, id_map = _collapse_graph_characters(chars)
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
            "source": key[0],
            "target": key[1],
            "type": rel.rel_type or "neutral",
            "sentiment_values": [],
            "descriptions": [],
            "chapters": [],
        })
        if rel.sentiment is not None:
            bucket["sentiment_values"].append(rel.sentiment)
        if rel.description:
            bucket["descriptions"].append(rel.description.strip())
        if rel.from_chapter is not None:
            bucket["chapters"].append(rel.from_chapter)

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
            char_id = str(state.character_id)
            latest_states.setdefault(char_id, state)

    chars_with_details = []
    for c in chars:
        state = latest_states.get(str(c.id))
        trait_snapshot = state.trait_snapshot if state else (c.trait_state or {})
        chars_with_details.append({
            "id": str(c.id),
            "name": c.name,
            "role": c.role,
            "first_chapter": c.first_chapter,
            "description": _relationship_node_description(c, trait_snapshot, rel_summaries.get(str(c.id), [])),
            "trait_state": trait_snapshot,
            "personality_tags": c.personality_tags or [],
            "aliases": c.aliases or [],
            "motivations": c.motivations or [],
            "fears": c.fears or [],
            "archetype": c.archetype,
            "arc_summary": c.arc_summary,
        })

    graph = {
        "nodes": chars_with_details,
        "edges": [
            {
                "source": item["source"],
                "target": item["target"],
                "type": item["type"],
                "sentiment": round(sum(item["sentiment_values"]) / len(item["sentiment_values"]), 3) if item["sentiment_values"] else None,
                "description": " ".join(dict.fromkeys(item["descriptions"])) or None,
                "from_chapter": min(item["chapters"]) if item["chapters"] else None,
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
            .where(
                BookChunk.book_id == book_id,
                Chapter.number <= chapter,
                BookChunk.text.ilike(f"%{lowered}%"),
            )
            .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
        )).all()

        results = [
            build_search_result(
                text=row[0],
                chunk_index=row[1],
                chapter_num=row[2],
                chapter_title=row[3],
                relevance=0.5,
            )
            for row in lexical_rows
        ]
    if not results:
        terms = [term for term in q.strip().split() if len(term) >= 3]
        if terms:
            token_filters = [BookChunk.text.ilike(f"%{term}%") for term in terms]
            token_rows = (await db.execute(
                select(BookChunk.text, BookChunk.chunk_index, Chapter.number, Chapter.title)
                .join(Chapter, Chapter.id == BookChunk.chapter_id)
                .where(
                    BookChunk.book_id == book_id,
                    Chapter.number <= chapter,
                    or_(*token_filters),
                )
                .limit(settings.SEARCH_MAX_CONTEXT_CHUNKS)
            )).all()

            results = [
                build_search_result(
                    text=row[0],
                    chunk_index=row[1],
                    chapter_num=row[2],
                    chapter_title=row[3],
                    relevance=0.35,
                )
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
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.book_id == book_id,
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
                {
                    "number": number,
                    "title": f"Chapter {number}",
                    "processed": False,
                    "intelligence_available": True,
                    "read": number in read_set,
                }
                for number in range(1, book.total_chapters + 1)
            ],
        }
    intelligence_map = await _chapter_intelligence_map(db, book, current_user)

    return {
        "read_upto": read_upto,
        "current_chapter": read_upto,
        "chapters": [
            {
                "number": chapter.number,
                "title": chapter.title,
                "processed": chapter.processed,
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
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.book_id == book_id,
        )
    )).scalar()
    read_upto = progress.current_chapter if progress else 0
    read_set = set(progress.chapters_read or []) if progress else set()
    available_set = await _read_available_chapter_set(db, book, current_user, read_set)

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
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(available_set)),
            ChapterSummary.mode == "short",
        )
    )).all()
    summary_by_chapter_id = {
        str(row[0]): {"content": row[1], "key_events": row[2] or []}
        for row in summary_rows
    }

    return {
        "read_upto": read_upto,
        "summaries": [
            {
                "chapter_number": row[0],
                "chapter_title": row[1],
                "read": True,
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

    read_set = await _read_available_chapter_set(db, book, current_user, await _read_chapter_set(db, current_user.id, book_id))
    if not read_set:
        return {"items": []}

    rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.clues)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(read_set)),
            ChapterSummary.mode == "detailed",
        )
        .order_by(Chapter.number)
    )).all()

    items = []
    for number, title, clues in rows:
        for clue in clues or []:
            if isinstance(clue, dict) and clue.get("clue"):
                items.append({
                    "chapter_number": number,
                    "chapter_title": title,
                    "clue": clue.get("clue"),
                    "foreshadows": clue.get("foreshadows"),
                })
    if items:
        return {"items": items}

    chapter_rows = (await db.execute(
        select(Chapter.number, Chapter.title, Chapter.id, Chapter.s3_key)
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(read_set)),
        )
        .order_by(Chapter.number)
    )).all()

    from app.engine.analysis.summariser import generate_summary

    generated_rows = []
    for number, title, chapter_id, s3_key in chapter_rows:
        existing = (await db.execute(
            select(ChapterSummary).where(
                ChapterSummary.chapter_id == chapter_id,
                ChapterSummary.mode == "detailed",
            )
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
        row = ChapterSummary(
            chapter_id=chapter_id,
            mode="detailed",
            content=data["content"],
            key_events=data.get("key_events"),
            char_changes=data.get("char_changes"),
            clues=data.get("clues"),
        )
        db.add(row)
        generated_rows.append((number, title, data.get("clues") or []))

    if generated_rows:
        await db.commit()

    for number, title, clues in generated_rows:
        for clue in clues or []:
            if isinstance(clue, dict) and clue.get("clue"):
                items.append({
                    "chapter_number": number,
                    "chapter_title": title,
                    "clue": clue.get("clue"),
                    "foreshadows": clue.get("foreshadows"),
                })
    return {"items": items}


@router.get("/{book_id}/timeline")
async def get_timeline(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    read_set = await _read_available_chapter_set(db, book, current_user, await _read_chapter_set(db, current_user.id, book_id))
    if not read_set:
        return {"events": []}

    summary_rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.key_events)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(read_set)),
            ChapterSummary.mode == "short",
        )
        .order_by(Chapter.number)
    )).all()
    character_rows = (await db.execute(
        select(Character.name, Character.first_chapter, Character.role, Character.aliases, Character.arc_summary)
        .where(Character.book_id == book_id, Character.first_chapter.in_(sorted(read_set)))
        .order_by(Character.first_chapter, Character.name)
    )).all()
    thread_rows = (await db.execute(
        select(PlotThread.title, PlotThread.introduced_at, PlotThread.resolved_at, PlotThread.status)
        .where(PlotThread.book_id == book_id)
        .order_by(PlotThread.introduced_at, PlotThread.importance.desc())
    )).all()

    events = []
    for chapter_num, chapter_title, key_events in summary_rows:
        for event in key_events or []:
            if isinstance(event, dict) and event.get("event"):
                events.append({
                    "chapter_number": chapter_num,
                    "chapter_title": chapter_title,
                    "kind": "event",
                    "title": event.get("event"),
                    "detail": None,
                })
    for name, first_chapter, role, aliases, arc_summary in character_rows:
        if not _is_valid_timeline_character(name, role, aliases, arc_summary):
            continue
        events.append({
            "chapter_number": first_chapter,
            "chapter_title": None,
            "kind": "character_entry",
            "title": name,
            "detail": _timeline_character_detail(name, role, aliases, arc_summary),
        })
    for title, introduced_at, resolved_at, status in thread_rows:
        if introduced_at and introduced_at in read_set:
            events.append({
                "chapter_number": introduced_at,
                "chapter_title": None,
                "kind": "thread_start",
                "title": title,
                "detail": status,
            })
        if resolved_at and resolved_at in read_set:
            events.append({
                "chapter_number": resolved_at,
                "chapter_title": None,
                "kind": "thread_end",
                "title": title,
                "detail": "Resolved",
            })

    events = _dedupe_timeline_events(events)
    events.sort(key=lambda item: (item["chapter_number"], item["kind"], item["title"]))
    return {"events": events}


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

    read_set = await _read_available_chapter_set(db, book, current_user, await _read_chapter_set(db, current_user.id, book_id))
    if not read_set:
        return {"results": []}

    normalized_query = q.strip().lower()
    terms = [term for term in normalized_query.split() if len(term) >= 3]
    if not terms and normalized_query:
        terms = [normalized_query]
    rows = (await db.execute(
        select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events, ChapterSummary.clues)
        .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
        .where(
            Chapter.book_id == book_id,
            Chapter.number.in_(sorted(read_set)),
            ChapterSummary.mode.in_(["short", "detailed"]),
        )
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
            results.append({
                "chapter_number": chapter_num,
                "chapter_title": chapter_title,
                "score": score,
                "summary": content,
            })
    if not results:
        chapter_rows = (await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(
                Chapter.book_id == book_id,
                Chapter.number.in_(sorted(read_set)),
            )
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

            results.append({
                "chapter_number": chapter_num,
                "chapter_title": chapter_title,
                "score": score,
                "summary": chapter_text[:320] + ("..." if len(chapter_text) > 320 else ""),
            })
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
            "chapter": rel.from_chapter,
            "type": rel.rel_type,
            "description": rel.description,
            "sentiment": rel.sentiment,
        })

    return {
        "pairs": [
            {
                "characters": list(key),
                "events": value,
            }
            for key, value in grouped.items()
        ]
    }


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
    quote_text = (body.quote_text or "").strip()
    if not quote_text:
        raise HTTPException(400, "Quote text is required")

    quote = QuoteEntry(
        user_id=current_user.id,
        book_id=book_id,
        chapter_number=body.chapter_number,
        character_name=body.character_name,
        quote_text=quote_text,
        note=body.note,
    )
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return {"id": str(quote.id), "saved": True}


@router.get("/{book_id}/plot-threads")
async def get_plot_threads(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    threads = (await db.execute(
        select(PlotThread).where(
            PlotThread.book_id == book_id,
            PlotThread.introduced_at <= chapter,
        ).order_by(PlotThread.importance.desc())
    )).scalars().all()

    return [{"id": str(t.id), "title": t.title, "type": t.thread_type, "status": t.status,
             "description": t.description, "introduced_at": t.introduced_at,
             "resolved_at": t.resolved_at, "importance": t.importance} for t in threads]


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

    # Get reading progress
    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
        )
    )).scalar()
    if not progress:
        return {"recall": None}

    last_chapter = progress.current_chapter

    # Get most recent summary as context
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

    # Active characters
    chars = (await db.execute(
        select(Character.name).where(Character.book_id == book_id, Character.first_chapter <= last_chapter).limit(8)
    )).scalars().all()

    # Open threads
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

    # Trigger lazy processing ahead
    from app.workers.tasks.extraction_tasks import process_chapter_task
    total = book.total_chapters or 1
    for n in range(current_chapter + 1, min(current_chapter + 4, total + 1)):
        next_chapter = (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book_id, Chapter.number == n)
            )
        ).scalar()
        if next_chapter and next_chapter.processed:
            continue
        if not await _chapter_intelligence_available(db, book, current_user, n):
            continue
        process_chapter_task.apply_async(
            args=[str(book_id), n, "", ""],  # text fetched from S3 in consumer
            countdown=n * 3, queue="extraction",
        )
    current_row = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == current_chapter)
        )
    ).scalar()
    if current_row and await _chapter_intelligence_available(db, book, current_user, current_chapter):
        await _queue_analysis_if_missing(db, current_row)
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
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.book_id == book_id,
        )
    )).scalar()

    if progress is None:
        progress = ReadingProgress(
            user_id=current_user.id,
            book_id=book_id,
            current_chapter=total,
            scroll_pct=1.0,
            chapters_read=chapters_read,
        )
        db.add(progress)
    else:
        progress.current_chapter = total
        progress.scroll_pct = 1.0
        progress.chapters_read = chapters_read
        progress.last_read = datetime.now(timezone.utc)

    await db.commit()
    return {
        "ok": True,
        "current_chapter": total,
        "chapters_read_count": total,
        "percent_complete": 100.0,
        "chapters_left": 0,
    }


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
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.book_id == book_id,
        )
    )).scalar()

    if progress is None:
        chapters_read = [chapter] if read else []
        progress = ReadingProgress(
            user_id=current_user.id,
            book_id=book_id,
            current_chapter=max(chapter, 1),
            scroll_pct=0.0,
            chapters_read=chapters_read,
        )
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
        chapter_row = (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter)
            )
        ).scalar()
        if chapter_row and await _chapter_intelligence_available(db, book, current_user, chapter):
            await _queue_analysis_if_missing(db, chapter_row)
    return {"ok": True, "chapter": chapter, "read": read}


def _normalize_summary_response(content, key_events, char_changes, clues):
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = _strip_json_fence(stripped)
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and "summary" in parsed:
                return {
                    "content": parsed.get("summary", content),
                    "key_events": parsed.get("key_events") or key_events or [],
                    "char_changes": parsed.get("char_changes") or char_changes or [],
                    "clues": parsed.get("clues") or clues or [],
                }
        except Exception:
            pass

    return {
        "content": content,
        "key_events": key_events or [],
        "char_changes": char_changes or [],
        "clues": clues or [],
    }


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    elif stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    return stripped.strip()


def _require_summary_access(book: Book, current_user, chapter_num: int | None = None) -> None:
    if effective_tier(current_user.tier) in ("pro", "power", "admin"):
        return
    if chapter_num is not None and book.is_truncated:
        detail = "This book has reached the Starter plan reading capacity. Upgrade to Pro to unlock more summaries and intelligence views."
        detail = f"Chapter {chapter_num} summary is unavailable because this book has reached the Starter plan reading capacity. Upgrade to Pro to continue."
        raise HTTPException(402, detail)


async def _read_chapter_set(db: AsyncSession, user_id: uuid.UUID, book_id: uuid.UUID) -> set[int]:
    progress = (await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == user_id,
            ReadingProgress.book_id == book_id,
        )
    )).scalar()
    if not progress:
        return set()
    explicit = set(progress.chapters_read or [])
    if explicit:
        return explicit
    if progress.current_chapter and progress.current_chapter > 0:
        return set(range(1, progress.current_chapter + 1))
    return set()


async def _read_available_chapter_set(
    db: AsyncSession,
    book: Book,
    current_user,
    read_set: set[int],
) -> set[int]:
    availability = await _chapter_intelligence_map(db, book, current_user)
    return {chapter for chapter in read_set if availability.get(chapter, False)}


async def _queue_analysis_if_missing(db: AsyncSession, chapter: Chapter) -> None:
    summary_exists = await _chapter_has_any_summary(db, chapter.id)
    if summary_exists:
        return
    from app.workers.tasks.analysis_tasks import analyse_chapter_task

    try:
        chapter_text = download_book(chapter.s3_key).decode("utf-8", errors="ignore")
    except Exception:
        return

    analyse_chapter_task.apply_async(
        args=[str(chapter.id), chapter_text, chapter.title or ""],
        queue="analysis",
    )


async def _chapter_has_any_summary(db: AsyncSession, chapter_id: uuid.UUID) -> bool:
    row = (
        await db.execute(
            select(ChapterSummary.id).where(ChapterSummary.chapter_id == chapter_id).limit(1)
        )
    ).first()
    return row is not None


async def _chapter_intelligence_available(db: AsyncSession, book: Book, current_user, chapter_num: int) -> bool:
    availability = await _chapter_intelligence_map(db, book, current_user)
    return availability.get(chapter_num, False)


async def _chapter_intelligence_map(db: AsyncSession, book: Book, current_user) -> dict[int, bool]:
    if effective_tier(current_user.tier) in ("pro", "power", "admin"):
        rows = (await db.execute(
            select(Chapter.number)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number)
        )).all()
        return {number: True for (number,) in rows}
    if not book.is_truncated:
        rows = (await db.execute(
            select(Chapter.number)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number)
        )).all()
        return {number: True for (number,) in rows}
    rows = (await db.execute(
        select(Chapter.number, Chapter.token_count)
        .where(Chapter.book_id == book.id)
        .order_by(Chapter.number)
    )).all()
    running_total = 0
    availability: dict[int, bool] = {}
    for number, token_count in rows:
        running_total += token_count or 0
        availability[number] = running_total <= (book.total_tokens or 0)
    return availability


async def _serialize_chapter_media(db: AsyncSession, chapter_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(
        select(ChapterMedia)
        .where(ChapterMedia.chapter_id == chapter_id)
        .order_by(ChapterMedia.sort_order, ChapterMedia.created_at)
    )).scalars().all()
    items: list[dict] = []
    for row in rows:
        item = {
            "marker": row.marker,
            "asset_type": row.asset_type,
            "content_type": row.content_type,
            "caption": row.caption,
            "sort_order": row.sort_order,
            "url": get_presigned_url(row.storage_key),
            "content_base64": None,
        }
        if item["url"] is None:
            try:
                item["content_base64"] = base64.b64encode(download_book(row.storage_key)).decode("ascii")
            except Exception:
                continue
        items.append(item)
    return items


def _serialize_inline_images(images: list[dict]) -> list[dict]:
    serialized: list[dict] = []
    for index, image in enumerate(images):
        raw = image.get("bytes")
        marker = image.get("marker")
        if not raw or not marker:
            continue
        serialized.append(
            {
                "marker": marker,
                "asset_type": "image",
                "content_type": image.get("content_type"),
                "caption": None,
                "sort_order": index,
                "url": None,
                "content_base64": base64.b64encode(raw).decode("ascii"),
            }
        )
    return serialized


def _extract_media_markers(text: str | None) -> list[str]:
    if not text:
        return []
    return re.findall(r"\[\[IMAGE:[^\]]+\]\]", text)


def _merge_media_items(primary: list[dict], fallback: list[dict]) -> list[dict]:
    if not primary:
        return fallback
    merged = {item["marker"]: item for item in primary if item.get("marker")}
    for item in fallback:
        marker = item.get("marker")
        if marker and marker not in merged:
            merged[marker] = item
    return sorted(merged.values(), key=lambda item: item.get("sort_order", 0))


def _parse_chapter_from_source(book: Book, chapter_num: int) -> dict | None:
    try:
        raw = download_book(book.s3_key)
    except Exception:
        return None

    try:
        if book.format == "pdf":
            from app.parsers.pdf_parser import parse_pdf

            chapters = parse_pdf(raw)
        else:
            from app.parsers.epub_parser import parse_epub

            chapters = parse_epub(raw)
    except Exception:
        return None

    chapter = next((item for item in chapters if item.get("number") == chapter_num), None)
    if not chapter:
        return None
    return chapter
