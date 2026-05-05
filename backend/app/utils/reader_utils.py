"""
Reader utility helpers — timeline and relationship-graph filtering,
chapter media serialization, summary normalization, and chapter
intelligence availability checks extracted from the reader route.
"""
from __future__ import annotations

import base64
import json
import re
import uuid
from typing import Any

import bleach  # type: ignore[import-untyped]
from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import effective_tier, settings
from app.core.security import create_asset_token
from app.core.storage import download_book, get_presigned_url
from app.engine.character.deduplicator import names_equivalent
from app.engine.character.entity_filters import (
    VISIBILITY_THRESHOLD,
    character_visibility_score,
)
from app.engine.character.profile_builder import build_description
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import Character
from app.models.intelligence import ChapterSummary, PlotThread
from app.utils.ingestion_utils import apply_chapter_number_strategy

BLEACH_EMPTY_TAGS: Any = frozenset()

# ─── Character stopwords / filter sets ───────────────────────────────────────

TIMELINE_CHARACTER_STOPWORDS = {
    "after", "and", "but", "faculty", "goodbye", "indeed", "just", "lady",
    "leaving", "maybe", "miss", "now", "once", "regardless", "seeing", "she",
    "that", "the narrator", "this", "though", "using", "very", "well", "what",
    "when", "with", "yes", "you", "my brother", "recalling", "considering",
    "looking", "taking", "matching", "hearing", "creation",
}
TIMELINE_CHARACTER_PREFIXES = ("the ",)
TIMELINE_CHARACTER_EXACT_BLOCKLIST = {
    "Clock Tower", "Far East", "Fourth Holy Grail", "Great Ritual", "Mage's Association",
    "Magic Circles", "Magic Circuits", "Magic Crest", "Milky Way", "Modern Magecraft",
    "Mystic Codes", "New Age", "Nuclear Energy", "Seven Wonders", "Source Crest",
    "The Twin Towers", "United States",
}
TIMELINE_CHARACTER_SUFFIXES = (" Association", " Convention", " Fundamentals", " Energy", " Sequence")
GRAPH_CHARACTER_STOPWORDS = TIMELINE_CHARACTER_STOPWORDS | {"lord", "lords", "war", "are", "around", "however"}


# ─── Timeline helpers ─────────────────────────────────────────────────────────

def normalize_timeline_label(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def is_valid_timeline_character(
    name: str | None,
    role: str | None,
    aliases: list[str] | None,
    arc_summary: str | None,
) -> bool:
    """Determine whether a named entity qualifies as a visible timeline character.

    Architecture: composite scoring instead of hard boolean gates.

    Absolute pre-filters (kept as hard gates — no score can override):
      - Empty / None name
      - Single all-lowercase word  (never a proper character name)
      - Starts with "the "         (article + noun compound, not a name)

    Everything else contributes to character_visibility_score():
      + NER label            PERSON → +3 | ORG/GPE → penalised
      + shape heuristics     multi-word, hyphenated, title-prefix …
      + profile evidence     role, aliases, arc_summary …
      - STOPWORD_PENALTY     name is in TIMELINE_CHARACTER_STOPWORDS  (← soft)
      - KNOWN_CONCEPT_PENALTY exact blocklist entries
      - SUFFIX_CONCEPT_PENALTY " Association", " Energy" …
      ± gerund/adverb penalty  -ing / -ed / -ly / -tion suffix  (← soft)
    """
    if not name:
        return False

    title = re.sub(r"\s+", " ", name.strip())
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", title)
    if not words:
        return False

    # ── Absolute pre-filters (no score can override these) ───────────────────
    # Single completely lowercase word → not a proper name
    if len(words) == 1 and words[0][0].islower():
        return False
    # Article + noun compound → not a character label
    if title.casefold().startswith("the "):
        return False

    # ── Soft extra penalties (beyond the scored stopword set) ────────────────
    normalized = normalize_timeline_label(name)
    # Gerund / adverb / nominalised suffix — a soft signal, not a hard block.
    # A name like "Ling" ends in "-ing" but NER will correctly score it +3.
    gerund_penalty = (
        -2
        if any(normalized.endswith(sfx) for sfx in ("ing", "ed", "ly", "tion"))
        and len(normalized) > 5
        else 0
    )
    # Very short single-word candidate — too ambiguous
    short_word_penalty = -3 if len(words) == 1 and len(words[0]) <= 3 else 0

    # ── Composite score ────────────────────────────────────────────────────
    score = character_visibility_score(
        name,
        role=role,
        aliases=aliases or [],
        arc_summary=arc_summary,
        stopwords=frozenset(TIMELINE_CHARACTER_STOPWORDS),
        exact_blocklist=frozenset(TIMELINE_CHARACTER_EXACT_BLOCKLIST),
        concept_suffixes=tuple(TIMELINE_CHARACTER_SUFFIXES),
        use_ner=True,
    ) + gerund_penalty + short_word_penalty

    return score >= VISIBILITY_THRESHOLD


def timeline_character_detail(
    name: str | None,
    role: str | None,
    aliases: list[str] | None,
    arc_summary: str | None,
) -> str:
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


def dedupe_timeline_events(events: list[dict]) -> list[dict]:
    seen: set[tuple[int, str, str]] = set()
    deduped = []
    for event in events:
        key = (
            int(event["chapter_number"]),
            str(event["kind"]),
            normalize_timeline_label(str(event["title"])),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


# ─── Relationship graph helpers ───────────────────────────────────────────────

def relationship_node_description(
    char: Character,
    trait_snapshot: dict,
    relationship_summaries: list[str],
) -> str:
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


def is_graph_character_visible(char: Character) -> bool:
    """Determine whether a Character should appear in the relationship graph.

    Same composite scoring as the timeline filter, but with the richer
    profile data (personality_tags, motivations, fears, trait_state) that
    is available for full Character objects.

    Absolute pre-filters retained:
      - No name / empty name
      - Possessive suffix ("'s")   → not a character label
      - Single all-lowercase word  → not a proper name
    """
    name = " ".join((char.name or "").split())
    if not name:
        return False
    # Possessive forms ("Author's note", "Narrator's voice") → strip
    if name.endswith("'s"):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", name)
    if not words:
        return False
    if len(words) == 1 and words[0][0].islower():
        return False

    score = character_visibility_score(
        name,
        role=char.role,
        aliases=char.aliases or [],
        arc_summary=char.arc_summary,
        personality_tags=char.personality_tags or [],
        motivations=char.motivations or [],
        fears=char.fears or [],
        archetype=char.archetype,
        trait_state=char.trait_state,
        relationship_count=0,
        stopwords=frozenset(GRAPH_CHARACTER_STOPWORDS),
        exact_blocklist=frozenset(TIMELINE_CHARACTER_EXACT_BLOCKLIST),
        concept_suffixes=tuple(TIMELINE_CHARACTER_SUFFIXES),
        use_ner=True,
    )
    return score >= VISIBILITY_THRESHOLD


def character_evidence_score(char: Character) -> tuple[int, int]:
    score = sum(
        1
        for value in [
            char.role, char.aliases, char.personality_tags, char.motivations,
            char.fears, char.arc_summary, char.archetype, char.trait_state,
        ]
        if value
    )
    return score, len((char.name or "").strip())


def collapse_graph_characters(chars: list[Character]) -> tuple[list[Character], dict[str, str]]:
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
        if character_evidence_score(char) > character_evidence_score(match):
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
        personality_tags: list[str] = []
        motivations: list[str] = []
        fears: list[str] = []
        seen_personality_tags: set[str] = set()
        seen_motivations: set[str] = set()
        seen_fears: set[str] = set()
        for tag in [*(primary.personality_tags or []), *(duplicate.personality_tags or [])]:
            if tag and tag not in seen_personality_tags:
                seen_personality_tags.add(tag)
                personality_tags.append(tag)
        for item in [*(primary.motivations or []), *(duplicate.motivations or [])]:
            if item and item not in seen_motivations:
                seen_motivations.add(item)
                motivations.append(item)
        for item in [*(primary.fears or []), *(duplicate.fears or [])]:
            if item and item not in seen_fears:
                seen_fears.add(item)
                fears.append(item)
        primary.personality_tags = personality_tags
        primary.motivations = motivations
        primary.fears = fears
        primary.role = primary.role or duplicate.role
        primary.arc_summary = primary.arc_summary or duplicate.arc_summary
        primary.archetype = primary.archetype or duplicate.archetype
        primary.trait_state = primary.trait_state or duplicate.trait_state
        primary.first_chapter = min(primary.first_chapter, duplicate.first_chapter)

        id_map[str(char.id)] = str(primary.id)
        id_map[str(duplicate.id)] = str(primary.id)

    return sorted(canonical, key=lambda item: (item.first_chapter, item.name)), id_map


# ─── Summary normalization ────────────────────────────────────────────────────

def normalize_summary_response(content, key_events, char_changes, clues) -> dict:
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = strip_json_fence(stripped)
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


def strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    elif stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    return stripped.strip()


# ─── Chapter intelligence / access ───────────────────────────────────────────

async def require_summary_access(db: AsyncSession, book: Book, current_user, chapter_num: int | None = None) -> None:
    if effective_tier(current_user.tier) in ("pro", "power", "admin"):
        return
    if not book.is_truncated:
        return
    if chapter_num is None:
        raise HTTPException(402, "This book has reached the Starter plan reading capacity. Upgrade to Pro to unlock more summaries and intelligence views.")
    if not await chapter_intelligence_available(db, book, current_user, chapter_num):
        raise HTTPException(402, f"Chapter {chapter_num} summary is unavailable because this book has reached the Starter plan reading capacity. Upgrade to Pro to continue.")


async def read_chapter_set(db: AsyncSession, user_id: uuid.UUID, book_id: uuid.UUID) -> set[int]:
    from app.models.progress import ReadingProgress
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


async def read_available_chapter_set(
    db: AsyncSession,
    book: Book,
    current_user,
    read_set: set[int],
) -> set[int]:
    availability = await chapter_intelligence_map(db, book, current_user)
    return {chapter for chapter in read_set if availability.get(chapter, False)}


async def full_available_chapter_set(
    db: AsyncSession,
    book: Book,
    current_user,
) -> set[int]:
    availability = await chapter_intelligence_map(db, book, current_user)
    return {chapter for chapter, available in availability.items() if available}


async def summary_visible_chapter_set(
    db: AsyncSession,
    book: Book,
    current_user,
) -> set[int]:
    if book.mode == "author":
        return await full_available_chapter_set(db, book, current_user)
    read_set = await read_chapter_set(db, current_user.id, book.id)
    return await read_available_chapter_set(db, book, current_user, read_set)


async def timeline_visible_chapter_set(
    db: AsyncSession,
    book: Book,
    current_user,
) -> set[int]:
    if book.mode == "author":
        return await full_available_chapter_set(db, book, current_user)
    read_set = await read_chapter_set(db, current_user.id, book.id)
    if not read_set:
        return set()
    # Keep the timeline cumulative to the furthest visible chapter so
    # ongoing arcs still appear even when explicit read progress is sparse.
    return set(range(1, max(read_set) + 1))


async def queue_analysis_if_missing(db: AsyncSession, chapter: Chapter) -> None:
    if await chapter_has_detailed_summary(db, chapter.id):
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


async def chapter_has_detailed_summary(db: AsyncSession, chapter_id: uuid.UUID) -> bool:
    row = (
        await db.execute(
            select(ChapterSummary.id).where(
                ChapterSummary.chapter_id == chapter_id,
                ChapterSummary.mode == "detailed",
            ).limit(1)
        )
    ).first()
    return row is not None


async def chapter_intelligence_available(db: AsyncSession, book: Book, current_user, chapter_num: int) -> bool:
    availability = await chapter_intelligence_map(db, book, current_user)
    return availability.get(chapter_num, False)


async def chapter_intelligence_map(db: AsyncSession, book: Book, current_user) -> dict[int, bool]:
    from app.models.book import Chapter as Ch
    if effective_tier(current_user.tier) in ("pro", "power", "admin"):
        rows = (await db.execute(
            select(Ch.number).where(Ch.book_id == book.id).order_by(Ch.number)
        )).all()
        return {number: True for (number,) in rows}
    if not book.is_truncated:
        rows = (await db.execute(
            select(Ch.number).where(Ch.book_id == book.id).order_by(Ch.number)
        )).all()
        return {number: True for (number,) in rows}
    rows = (await db.execute(
        select(Ch.number, Ch.token_count).where(Ch.book_id == book.id).order_by(Ch.number)
    )).all()
    running_total = 0
    availability: dict[int, bool] = {}
    for number, token_count in rows:
        running_total += token_count or 0
        availability[number] = running_total <= (book.total_tokens or 0)
    return availability


# ─── Media helpers ────────────────────────────────────────────────────────────

async def serialize_chapter_media(db: AsyncSession, chapter_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(
        select(ChapterMedia, Book.user_id)
        .join(Book, Book.id == ChapterMedia.book_id)
        .where(ChapterMedia.chapter_id == chapter_id)
        .order_by(ChapterMedia.sort_order, ChapterMedia.created_at)
    )).all()
    items: list[dict] = []
    for row, user_id in rows:
        token = create_asset_token(str(user_id), f"chapter-media:{row.id}", expires_minutes=120)
        item = {
            "id": str(row.id),
            "marker": row.marker,
            "asset_type": row.asset_type,
            "content_type": row.content_type,
            "caption": row.caption,
            "sort_order": row.sort_order,
            "url": f"{settings.API_V1_PREFIX}/reader/media/{row.id}?token={token}",
            "content_base64": None,
        }
        if get_presigned_url(row.storage_key) is None:
            try:
                item["content_base64"] = base64.b64encode(download_book(row.storage_key)).decode("ascii")
            except Exception:
                continue
        items.append(item)
    return items


def serialize_inline_images(images: list[dict]) -> list[dict]:
    serialized: list[dict] = []
    for index, image in enumerate(images):
        raw = image.get("bytes")
        marker = image.get("marker")
        if not raw or not marker:
            continue
        serialized.append({
            "marker": marker,
            "asset_type": "image",
            "content_type": image.get("content_type"),
            "caption": None,
            "sort_order": index,
            "url": None,
            "content_base64": base64.b64encode(raw).decode("ascii"),
        })
    return serialized


def extract_media_markers(text: str | None) -> list[str]:
    if not text:
        return []
    return re.findall(r"\[\[IMAGE:[^\]]+\]\]", text)


def merge_media_items(primary: list[dict], fallback: list[dict]) -> list[dict]:
    if not primary:
        return fallback
    merged = {item["marker"]: item for item in primary if item.get("marker")}
    for item in fallback:
        marker = item.get("marker")
        if marker and marker not in merged:
            merged[marker] = item
    return sorted(merged.values(), key=lambda item: item.get("sort_order", 0))


def parse_chapter_from_source(book: Book, chapter_num: int) -> dict | None:
    try:
        raw = download_book(book.s3_key)
    except Exception:
        return None
    try:
        preserve_numbers = bool(book.preserve_chapter_numbers) and book.work_type != "screenplay"
        if book.format == "pdf":
            from app.parsers.pdf_parser import parse_pdf

            chapters = parse_pdf(raw, split_large_chapters=not preserve_numbers)
        else:
            from app.parsers.epub_parser import parse_epub

            chapters = parse_epub(raw, split_large_chapters=not preserve_numbers)
        chapters = apply_chapter_number_strategy(
            chapters,
            preserve_chapter_numbers=preserve_numbers,
            generic_titles=book.work_type != "screenplay" and not preserve_numbers,
        )
    except Exception:
        return None
    chapter = next((item for item in chapters if item.get("number") == chapter_num), None)
    return chapter or None


def timeline_relationship_detail(
    character_a: str,
    character_b: str,
    rel_type: str | None,
    description: str | None,
) -> tuple[str, str]:
    relation = (rel_type or "connection").replace("_", " ")
    title = f"{character_a} and {character_b}"
    if description and description.strip():
        return title, description.strip()
    return title, f"Their {relation} dynamic shifts here."


def build_timeline_track_payload(
    chapters: list[dict],
    events: list[dict],
    character_tracks: list[dict],
    thread_tracks: list[dict],
    relationship_markers: list[dict],
) -> dict:
    return {
        "chapters": chapters,
        "events": events,
        "character_tracks": character_tracks,
        "thread_tracks": thread_tracks,
        "relationship_markers": relationship_markers,
    }


def serialize_plot_thread(thread: PlotThread) -> dict:
    return {
        "id": str(thread.id),
        "title": thread.title,
        "type": thread.thread_type,
        "status": thread.status,
        "description": thread.description,
        "introduced_at": thread.introduced_at,
        "resolved_at": thread.resolved_at,
        "importance": thread.importance,
        "note": thread.note,
        "character_ids": thread.character_ids or [],
    }


async def list_plot_threads(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter: int | None = None,
) -> list[dict]:
    query = select(PlotThread).where(PlotThread.book_id == book_id)
    if chapter is not None:
        query = query.where(PlotThread.introduced_at <= chapter)
    threads_result = await db.execute(
        query.order_by(PlotThread.importance.desc(), desc(PlotThread.introduced_at), PlotThread.title)
    )
    threads = threads_result.scalars().all()
    return [serialize_plot_thread(thread) for thread in threads]


async def update_plot_thread_note(
    db: AsyncSession,
    book_id: uuid.UUID,
    thread_id: uuid.UUID,
    note: str | None,
) -> dict | None:
    thread = (
        await db.execute(
            select(PlotThread).where(PlotThread.book_id == book_id, PlotThread.id == thread_id)
        )
    ).scalar_one_or_none()
    if thread is None:
        return None

    cleaned = str(bleach.clean(" ".join(str(note or "").split()).strip(), tags=BLEACH_EMPTY_TAGS, strip=True)) or None
    thread.note = cleaned
    await db.commit()
    await db.refresh(thread)
    return serialize_plot_thread(thread)
