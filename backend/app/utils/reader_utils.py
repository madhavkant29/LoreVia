"""
Reader utility helpers — timeline and relationship-graph filtering,
chapter media serialization, summary normalization, and chapter
intelligence availability checks extracted from the reader route.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from typing import Any

import bleach  # type: ignore[import-untyped]
from fastapi import HTTPException
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import cache_del, cache_set_if_absent, key_analysis_queued
from app.core.security import create_asset_token
from app.core.storage import download_book, get_presigned_url
from app.engine.character.deduplicator import names_equivalent
from app.engine.character.entity_filters import (
    VISIBILITY_THRESHOLD,
    character_visibility_score,
)
from app.utils.plot_thread_utils import (
    build_plot_thread_payload,
    normalize_plot_thread_status,
)
from app.utils.tag_utils import (
    ENTITY_TYPE_CHAPTER,
    ENTITY_TYPE_PLOT_THREAD,
    get_custom_tags_for_entity,
    list_custom_tags_for_entity_ids,
)
from app.utils.billing_utils import has_paid_reading_access
from app.utils.character_utils import get_graph_visibility_override
from app.utils.queue_utils import queue_for_user
from app.engine.character.profile_builder import build_description
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import Character
from app.models.intelligence import ChapterSummary, PlotThread
from app.models.progress import ReadingProgress
from app.services.summary_service import get_or_generate_summary
from app.utils.book_utils import (
    build_book_access_context,
    collaboration_allows_chapter,
    deserialize_manuscript_content,
    normalize_collaboration_scope,
)
from app.utils.ingestion_utils import ANALYSIS_INFLIGHT_TTL_SECONDS
from app.utils.ingestion_utils import apply_chapter_number_strategy

BLEACH_EMPTY_TAGS: Any = frozenset()
log = logging.getLogger("lorevia.reader_utils")

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


def timeline_plot_thread_span(
    introduced_at: int | None,
    resolved_at: int | None,
    visible_chapters: set[int],
) -> tuple[int, int] | None:
    """Clamp a plot-thread span to the visible timeline window.

    Older or partial extraction runs can leave plot threads without an
    ``introduced_at`` chapter. In that case, keep the thread visible
    across the currently visible window instead of dropping it.
    """
    if not visible_chapters:
        return None

    visible_min = min(visible_chapters)
    visible_max = max(visible_chapters)

    if introduced_at is not None and introduced_at > visible_max:
        return None
    if resolved_at is not None and resolved_at < visible_min:
        return None

    start_chapter = introduced_at if introduced_at is not None else visible_min
    end_chapter = resolved_at if resolved_at is not None else visible_max

    start_chapter = min(max(start_chapter, visible_min), visible_max)
    end_chapter = min(max(end_chapter, visible_min), visible_max)

    if end_chapter < start_chapter:
        end_chapter = start_chapter

    return start_chapter, end_chapter


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


def graph_character_visibility_analysis(char: Character, relationship_count: int = 0) -> dict[str, Any]:
    name = " ".join((getattr(char, "name", "") or "").split())
    override = get_graph_visibility_override(char)
    reasons: list[str] = []

    if not name:
        return {
            "visible": False,
            "score": -99,
            "override": override,
            "reasons": ["missing_name"],
        }

    if getattr(char, "is_manual", False):
        reasons.append("manual_character")
    if relationship_count > 0:
        reasons.append("relationship_evidence")
    if (getattr(char, "mention_count", 0) or 0) > 1:
        reasons.append("repeat_mentions")
    if getattr(char, "aliases", None):
        reasons.append("has_aliases")
    if getattr(char, "arc_summary", None):
        reasons.append("has_arc_summary")
    if getattr(char, "personality_tags", None) or getattr(char, "motivations", None) or getattr(char, "fears", None):
        reasons.append("profile_details")

    # Possessive forms ("Author's note", "Narrator's voice") -> strip
    if name.endswith("'s"):
        reasons.append("possessive_name_shape")
        return {
            "visible": False if override != "include" else True,
            "score": -8,
            "override": override,
            "reasons": (["author_override_include"] if override == "include" else ["author_override_exclude"] if override == "exclude" else []) + reasons,
        }

    words = re.findall(r"[A-Za-z][A-Za-z'-]*", name)
    if not words:
        reasons.append("no_name_tokens")
        return {
            "visible": False,
            "score": -10,
            "override": override,
            "reasons": reasons,
        }

    if len(words) == 1 and words[0][0].islower():
        reasons.append("lowercase_single_word")
        return {
            "visible": False if override != "include" else True,
            "score": -7,
            "override": override,
            "reasons": (["author_override_include"] if override == "include" else ["author_override_exclude"] if override == "exclude" else []) + reasons,
        }

    score = character_visibility_score(
        name,
        role=getattr(char, "role", None),
        aliases=getattr(char, "aliases", None) or [],
        arc_summary=getattr(char, "arc_summary", None),
        personality_tags=getattr(char, "personality_tags", None) or [],
        motivations=getattr(char, "motivations", None) or [],
        fears=getattr(char, "fears", None) or [],
        archetype=getattr(char, "archetype", None),
        trait_state=getattr(char, "trait_state", None),
        relationship_count=relationship_count,
        stopwords=frozenset(GRAPH_CHARACTER_STOPWORDS),
        exact_blocklist=frozenset(TIMELINE_CHARACTER_EXACT_BLOCKLIST),
        concept_suffixes=tuple(TIMELINE_CHARACTER_SUFFIXES),
        use_ner=True,
    )

    if score >= VISIBILITY_THRESHOLD:
        reasons.append("score_meets_threshold")
    else:
        reasons.append("score_below_threshold")

    if override == "include":
        reasons.insert(0, "author_override_include")
        return {
            "visible": True,
            "score": score,
            "override": override,
            "reasons": reasons,
        }
    if override == "exclude":
        reasons.insert(0, "author_override_exclude")
        return {
            "visible": False,
            "score": score,
            "override": override,
            "reasons": reasons,
        }
    return {
        "visible": score >= VISIBILITY_THRESHOLD or getattr(char, "is_manual", False),
        "score": score,
        "override": override,
        "reasons": reasons,
    }


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
    return bool(graph_character_visibility_analysis(char, getattr(char, "_graph_relationship_count", 0)).get("visible"))


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
    if has_paid_reading_access(current_user):
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
    collaborator=None,
    *,
    availability: dict[int, bool] | None = None,
) -> set[int]:
    access = build_book_access_context(book, user_id=current_user.id, collaborator=collaborator)
    if access.workspace_shell == "author":
        if availability is not None:
            return {chapter for chapter, available in availability.items() if available}
        return await full_available_chapter_set(db, book, current_user)
    read_set = await read_chapter_set(db, current_user.id, book.id)
    return await read_available_chapter_set(db, book, current_user, read_set)


async def timeline_visible_chapter_set(
    db: AsyncSession,
    book: Book,
    current_user,
    collaborator=None,
) -> set[int]:
    access = build_book_access_context(book, user_id=current_user.id, collaborator=collaborator)
    if access.workspace_shell == "author":
        return await full_available_chapter_set(db, book, current_user)
    read_set = await read_chapter_set(db, current_user.id, book.id)
    if not read_set:
        return set()
    # Keep the timeline cumulative to the furthest visible chapter so
    # ongoing arcs still appear even when explicit read progress is sparse.
    return set(range(1, max(read_set) + 1))


async def build_reading_progress_payload(
    db: AsyncSession,
    *,
    book: Book,
    current_user,
    collaborator=None,
    progress: ReadingProgress | None = None,
) -> dict[str, Any]:
    scope = normalize_collaboration_scope(collaborator.scope) if collaborator else None
    if progress is None:
        progress = (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.user_id == current_user.id,
                    ReadingProgress.book_id == book.id,
                )
            )
        ).scalar()

    total = book.total_chapters or 0
    current_chapter = progress.current_chapter if progress else 1
    if scope:
        start = scope.get("chapter_start") or 1
        end = scope.get("chapter_end") or total
        total = max(0, min(end, total) - start + 1)
        if not collaboration_allows_chapter(collaborator, current_chapter):
            current_chapter = start

    chapters_read = sorted(set((progress.chapters_read or []) if progress else []))
    chapters_read = [chapter for chapter in chapters_read if collaboration_allows_chapter(collaborator, chapter)]
    if not chapters_read and progress and progress.current_chapter:
        chapters_read = [
            chapter
            for chapter in range(1, progress.current_chapter + 1)
            if collaboration_allows_chapter(collaborator, chapter)
        ]

    chapters_read_count = len(chapters_read)
    percent_complete = round((chapters_read_count / total) * 100, 1) if total else 0.0
    return {
        "current_chapter": current_chapter,
        "scroll_pct": progress.scroll_pct if progress else 0.0,
        "chapters_read_count": chapters_read_count,
        "percent_complete": percent_complete,
        "chapters_left": max(total - chapters_read_count, 0) if total else 0,
    }


async def build_chapter_list_payload(
    db: AsyncSession,
    *,
    book: Book,
    current_user,
    collaborator=None,
    progress: ReadingProgress | None = None,
    intelligence_map: dict[int, bool] | None = None,
) -> dict[str, Any]:
    collaboration_scope = normalize_collaboration_scope(collaborator.scope) if collaborator else None
    if progress is None:
        progress = (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.user_id == current_user.id,
                    ReadingProgress.book_id == book.id,
                )
            )
        ).scalar()
    read_upto = progress.current_chapter if progress else 0
    read_set = set(progress.chapters_read or []) if progress else set()

    chapters_result = await db.execute(
        select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number)
    )
    chapters = [
        chapter for chapter in chapters_result.scalars().all()
        if collaboration_allows_chapter(collaborator, chapter.number)
    ]
    chapter_start = collaboration_scope.get("chapter_start") if collaboration_scope else None
    chapter_end = collaboration_scope.get("chapter_end") if collaboration_scope else None
    if not chapters and book.total_chapters:
        first = chapter_start or 1
        last = chapter_end or book.total_chapters
        return {
            "read_upto": read_upto,
            "current_chapter": read_upto,
            "chapters": [
                {
                    "number": number,
                    "title": f"Chapter {number}",
                    "chapter_kind": "chapter",
                    "processed": False,
                    "intelligence_available": True,
                    "read": number in read_set,
                    "analysis_status": None,
                    "tags": [],
                }
                for number in range(first, min(last, book.total_chapters) + 1)
            ],
        }

    if intelligence_map is None:
        intelligence_map = await chapter_intelligence_map(db, book, current_user)
    access = build_book_access_context(book, user_id=current_user.id, collaborator=collaborator)
    if access.workspace_shell == "author":
        author_visible = [chapter for chapter, available in intelligence_map.items() if available]
        if author_visible:
            read_upto = max(author_visible)

    tags_by_chapter = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_CHAPTER,
        entity_ids=[chapter.id for chapter in chapters],
        book_id=book.id,
    )
    return {
        "read_upto": read_upto,
        "current_chapter": read_upto,
        "chapters": [
            {
                "number": chapter.number,
                "title": chapter.title,
                "chapter_kind": getattr(chapter, "chapter_kind", "chapter"),
                "processed": chapter.processed,
                "intelligence_available": intelligence_map.get(chapter.number, True),
                "read": access.workspace_shell == "author" or chapter.number in read_set,
                "analysis_status": chapter_analysis_status(chapter),
                "tags": tags_by_chapter.get(chapter.id, []),
            }
            for chapter in chapters
        ],
    }


async def build_summary_collection_payload(
    db: AsyncSession,
    *,
    book: Book,
    current_user,
    collaborator=None,
    progress: ReadingProgress | None = None,
    intelligence_map: dict[int, bool] | None = None,
) -> dict[str, Any]:
    if progress is None:
        progress = (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.user_id == current_user.id,
                    ReadingProgress.book_id == book.id,
                )
            )
        ).scalar()
    read_upto = progress.current_chapter if progress else 0
    available_set = await summary_visible_chapter_set(
        db, book, current_user, collaborator, availability=intelligence_map
    )
    if collaborator is not None:
        available_set = {chapter for chapter in available_set if collaboration_allows_chapter(collaborator, chapter)}

    if not available_set:
        return {"read_upto": 0, "summaries": []}

    access = build_book_access_context(book, user_id=current_user.id, collaborator=collaborator)
    if access.workspace_shell == "author":
        read_upto = max(available_set)

    chapters = (
        await db.execute(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.number.in_(sorted(available_set)))
            .order_by(Chapter.number)
        )
    ).scalars().all()

    summary_rows = (
        await db.execute(
            select(ChapterSummary.chapter_id, ChapterSummary.content, ChapterSummary.key_events)
            .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
            .where(Chapter.book_id == book.id, Chapter.number.in_(sorted(available_set)), ChapterSummary.mode == "short")
        )
    ).all()
    summary_by_chapter_id = {
        str(row[0]): {"content": row[1], "key_events": row[2] or []}
        for row in summary_rows
    }

    queued_chapter_ids: set[uuid.UUID] = set()
    for chapter in chapters:
        chapter_key = str(chapter.id)
        if chapter_key in summary_by_chapter_id:
            continue
        if await queue_analysis_if_missing(db, chapter, current_user):
            queued_chapter_ids.add(chapter.id)
        summary_data = await get_or_generate_summary(db, book.id, chapter.number, "short")
        if summary_data and summary_data.get("status") == "ready":
            summary_by_chapter_id[chapter_key] = {
                "content": summary_data["content"],
                "key_events": summary_data.get("key_events") or [],
            }

    return {
        "read_upto": read_upto,
        "summaries": [
            {
                "chapter_number": chapter.number,
                "chapter_title": chapter.title,
                "chapter_kind": getattr(chapter, "chapter_kind", "chapter"),
                "read": access.workspace_shell == "author" or chapter.number <= read_upto,
                "available": str(chapter.id) in summary_by_chapter_id,
                "status": (
                    "ready"
                    if str(chapter.id) in summary_by_chapter_id
                    else "queued"
                    if chapter.id in queued_chapter_ids
                    else str((chapter_analysis_status(chapter) or {}).get("status") or "pending")
                ),
                "content": summary_by_chapter_id.get(str(chapter.id), {}).get("content"),
                "key_events": summary_by_chapter_id.get(str(chapter.id), {}).get("key_events", []),
            }
            for chapter in chapters
        ],
    }


async def queue_analysis_if_missing(db: AsyncSession, chapter: Chapter, current_user=None) -> bool:
    if await chapter_has_detailed_summary(db, chapter.id):
        return False
    analysis_state = chapter.analysis_state if isinstance(chapter.analysis_state, dict) else {}
    if str(analysis_state.get("status") or "").strip() in {"queued", "running"}:
        return False
    queued_key = key_analysis_queued(str(chapter.id))
    if not await cache_set_if_absent(
        queued_key,
        {"chapter_id": str(chapter.id)},
        ANALYSIS_INFLIGHT_TTL_SECONDS,
    ):
        return False
    from app.workers.tasks.analysis_tasks import analyse_chapter_task
    try:
        analyse_chapter_task.apply_async(
            args=[str(chapter.id), str(chapter.book_id)],
            kwargs={"is_reprocessing": False},
            queue=queue_for_user(current_user, "analysis") if current_user else "analysis",
        )
    except Exception as exc:
        await cache_del(queued_key)
        log.warning(
            "analysis_queue_dispatch_failed chapter_id=%s error=%s",
            chapter.id,
            exc,
        )
        return False
    return True


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


def chapter_analysis_status(chapter: Chapter | None) -> dict[str, Any] | None:
    if chapter is None or not isinstance(getattr(chapter, "analysis_state", None), dict):
        return None
    source = chapter.analysis_state
    payload = {
        "status": " ".join(str(source.get("status") or "").split()).strip() or "pending",
        "generated_modes": [
            str(mode).strip()
            for mode in (source.get("generated_modes") or [])
            if str(mode).strip()
        ],
        "attempt_count": int(source.get("attempt_count") or 0),
        "last_error": " ".join(str(source.get("last_error") or "").split()).strip() or None,
        "updated_at": source.get("updated_at"),
    }
    return payload


def chapter_source_integrity(chapter: Chapter | None) -> dict[str, Any] | None:
    source = (
        chapter.analysis_state.get("source_integrity")
        if chapter is not None and isinstance(getattr(chapter, "analysis_state", None), dict)
        else None
    )
    if not isinstance(source, dict):
        return None
    return {
        "text_present": bool(source.get("text_present")),
        "media_marker_count": int(source.get("media_marker_count") or 0),
        "stored_media_count": int(source.get("stored_media_count") or 0),
        "recovery_status": " ".join(str(source.get("recovery_status") or "").split()).strip() or "ok",
        "last_recovery_error": " ".join(str(source.get("last_recovery_error") or "").split()).strip() or None,
        "updated_at": source.get("updated_at"),
    }


async def chapter_intelligence_map(db: AsyncSession, book: Book, current_user) -> dict[int, bool]:
    from app.models.book import Chapter as Ch
    if has_paid_reading_access(current_user):
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

MEDIA_MARKER_RE = re.compile(r"\[\[IMAGE:[^\]]+\]\]")


async def serialize_chapter_media(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    book_id: uuid.UUID | None = None,
    chapter_text: str | None = None,
) -> list[dict]:
    query = (
        select(ChapterMedia, Book.user_id)
        .join(Book, Book.id == ChapterMedia.book_id)
        .where(ChapterMedia.chapter_id == chapter_id)
        .order_by(ChapterMedia.sort_order, ChapterMedia.created_at)
    )
    if book_id and chapter_text:
        markers = set(MEDIA_MARKER_RE.findall(chapter_text))
        if markers:
            query = (
                select(ChapterMedia, Book.user_id)
                .join(Book, Book.id == ChapterMedia.book_id)
                .where(
                    or_(
                        ChapterMedia.chapter_id == chapter_id,
                        and_(
                            ChapterMedia.book_id == book_id,
                            ChapterMedia.marker.in_(list(markers)),
                        ),
                    )
                )
                .order_by(ChapterMedia.sort_order, ChapterMedia.created_at)
            )
    rows = (await db.execute(query)).all()
    seen_markers: set[str] = set()
    items: list[dict] = []
    for row, user_id in rows:
        if row.marker in seen_markers:
            continue
        seen_markers.add(row.marker)
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
                item["content_base64"] = None
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
        preserve_numbers = bool(book.preserve_chapter_numbers or getattr(book, "preserve_source_chapters", False)) and book.work_type != "screenplay"
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


def serialize_plot_thread(
    thread: PlotThread,
    *,
    current_chapter: int | None,
    tags: list[str] | None = None,
) -> dict:
    return build_plot_thread_payload(thread, current_chapter=current_chapter, tags=tags)


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
    current_chapter = chapter
    if current_chapter is None:
        current_chapter = await db.scalar(select(Book.total_chapters).where(Book.id == book_id))
    tags_by_thread = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_PLOT_THREAD,
        entity_ids=[thread.id for thread in threads],
        book_id=book_id,
    )
    return [
        serialize_plot_thread(thread, current_chapter=current_chapter, tags=tags_by_thread.get(thread.id, []))
        for thread in threads
    ]


async def update_plot_thread_note(
    db: AsyncSession,
    book_id: uuid.UUID,
    thread_id: uuid.UUID,
    note: str | None,
    status: str | None = None,
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
    thread.edited_by_author = True
    if status is not None:
        normalized_status = normalize_plot_thread_status(status, default=thread.status)
        thread.status = normalized_status
        if normalized_status in {"resolved", "abandoned"} and thread.resolved_at is None:
            thread.resolved_at = thread.last_mentioned_at or thread.introduced_at
        elif normalized_status not in {"resolved", "abandoned"}:
            thread.resolved_at = None
    await db.commit()
    await db.refresh(thread)
    current_chapter = await db.scalar(select(Book.total_chapters).where(Book.id == book_id))
    return serialize_plot_thread(
        thread,
        current_chapter=current_chapter,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_PLOT_THREAD,
            entity_id=thread.id,
            book_id=book_id,
        ),
    )
