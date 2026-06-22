"""Focused character manual workflows."""

from __future__ import annotations

import re
import uuid
from collections.abc import Hashable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.character.profile_builder import (
    merge_list_values,
)
from app.models.book import Chapter
from app.models.character import (
    Character,
)
from app.models.intelligence import (
    BookChunk,
)
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_PROTECTED,
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
    CHARACTER_VISIBILITY_VISIBLE,
)
from app.utils.characters.graph import (
    GRAPH_VISIBILITY_OVERRIDE_KEY,
    GRAPH_VISIBILITY_OVERRIDE_VALUES,
)
from app.utils.characters.identity import (
    normalize_character_name,
)
from app.utils.characters.text import clean_optional_text, clean_string_list


def clean_markdown_asterisks(text: str) -> str:
    return text.replace("**", "").replace("*", "")


def apply_manual_character_description(character: Character, description: str | None) -> None:
    cleaned = clean_optional_text(description)
    trait_state = dict(character.trait_state or {})
    if cleaned:
        trait_state["manual_description"] = {
            "value": cleaned,
            "confidence": 1.0,
            "type": "abstract",
        }
    else:
        trait_state.pop("manual_description", None)
    character.trait_state = trait_state


def apply_graph_visibility_override(character: Character, override: str | None) -> None:
    normalized = clean_optional_text(override)
    trait_state = dict(character.trait_state or {})
    if not normalized:
        trait_state.pop(GRAPH_VISIBILITY_OVERRIDE_KEY, None)
        character.trait_state = trait_state
        return
    normalized = normalized.casefold()
    if normalized not in GRAPH_VISIBILITY_OVERRIDE_VALUES:
        raise ValueError("Graph visibility override must be include or exclude")
    trait_state[GRAPH_VISIBILITY_OVERRIDE_KEY] = {
        "value": normalized,
        "confidence": 1.0,
        "type": "abstract",
    }
    character.trait_state = trait_state


def build_manual_character(
    *,
    book_id: uuid.UUID,
    name: str,
    first_chapter: int,
    aliases: list[str] | None = None,
    role: str | None = None,
    description: str | None = None,
    goal: str | None = None,
    lie_they_believe: str | None = None,
    backstory_wound: str | None = None,
    arc_type: str | None = None,
    arc_summary: str | None = None,
    personality_tags: list[str] | None = None,
    motivations: list[str] | None = None,
    fears: list[str] | None = None,
) -> Character:
    cleaned_name = clean_optional_text(name)
    if not cleaned_name:
        raise ValueError("Character name cannot be empty")

    normalized_name = normalize_character_name(cleaned_name)
    cleaned_aliases = [
        alias
        for alias in clean_string_list(aliases)
        if normalize_character_name(alias) != normalized_name
    ]
    chapter_number = max(1, first_chapter)

    character = Character(
        book_id=book_id,
        name=cleaned_name,
        aliases=cleaned_aliases,
        role=role,
        first_chapter=chapter_number,
        last_seen_chapter=chapter_number,
        mention_count=1,
        trait_state={"manual_entry": {"value": "manual", "confidence": 0.0, "type": "abstract"}},
        personality_tags=clean_string_list(personality_tags),
        motivations=clean_string_list(motivations),
        fears=clean_string_list(fears),
        goal=clean_optional_text(goal),
        lie_they_believe=clean_optional_text(lie_they_believe),
        backstory_wound=clean_optional_text(backstory_wound),
        arc_type=clean_optional_text(arc_type),
        arc_summary=clean_optional_text(arc_summary),
        is_manual=True,
        visibility_state=CHARACTER_VISIBILITY_VISIBLE,
        approval_state=CHARACTER_APPROVAL_PROTECTED,
        approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
        approval_reason_codes=["manual_character"],
        approval_updated_at=datetime.now(UTC),
    )
    apply_manual_character_description(character, description)
    return character


def _manual_character_description_value(trait_state: dict[str, Any] | None) -> str | None:
    if not isinstance(trait_state, dict):
        return None
    manual = trait_state.get("manual_description")
    if not isinstance(manual, dict):
        return None
    return clean_optional_text(manual.get("value"))


def _merge_character_descriptions(
    primary_description: str | None, secondary_description: str | None
) -> str | None:
    primary_clean = clean_optional_text(primary_description)
    secondary_clean = clean_optional_text(secondary_description)
    if not primary_clean:
        return secondary_clean
    if not secondary_clean:
        return primary_clean

    primary_key = primary_clean.casefold()
    secondary_key = secondary_clean.casefold()
    if primary_key == secondary_key:
        return primary_clean
    if primary_key in secondary_key:
        return secondary_clean
    if secondary_key in primary_key:
        return primary_clean

    separator = "" if primary_clean.endswith((".", "!", "?", ";", ":")) else "."
    return f"{primary_clean}{separator} {secondary_clean}"


def _normalize_character_reference(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _character_reference_values(character: Character) -> set[str]:
    values = {
        _normalize_character_reference(character.id),
        _normalize_character_reference(character.name),
    }
    values.update(_normalize_character_reference(alias) for alias in (character.aliases or []))
    return {value for value in values if value}


def _replace_reference_list(
    values: list[object] | None, *, matches: set[str], replacement: str
) -> list[str]:
    replaced: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        candidate = " ".join(str(item or "").split()).strip()
        if not candidate:
            continue
        next_value = (
            replacement if _normalize_character_reference(candidate) in matches else candidate
        )
        if next_value.lower() in seen:
            continue
        seen.add(next_value.lower())
        replaced.append(next_value)
    return replaced


def _expand_reference_list(
    values: list[object] | None, *, matches: set[str], replacements: list[str]
) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    normalized_replacements = [
        " ".join(item.split()).strip() for item in replacements if " ".join(item.split()).strip()
    ]
    for item in values or []:
        candidate = " ".join(str(item or "").split()).strip()
        if not candidate:
            continue
        next_values = (
            normalized_replacements
            if _normalize_character_reference(candidate) in matches
            else [candidate]
        )
        for next_value in next_values:
            key = next_value.lower()
            if key in seen:
                continue
            seen.add(key)
            expanded.append(next_value)
    return expanded


def _find_name_occurrences(text: str, candidate: str) -> int:
    cleaned = " ".join(str(candidate or "").split()).strip()
    if not cleaned:
        return 0
    pattern = re.compile(rf"(?<![A-Za-z]){re.escape(cleaned)}(?![A-Za-z])")
    return len(pattern.findall(text or ""))


async def find_earliest_character_mention_chapter(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    name: str,
    aliases: list[str] | None = None,
    upto_chapter: int | None = None,
) -> int | None:
    candidates = merge_list_values([name], aliases)
    if not candidates:
        return None

    filters = [BookChunk.text.ilike(f"%{candidate}%") for candidate in candidates if candidate]
    if not filters:
        return None

    query = (
        select(Chapter.number, BookChunk.text)
        .join(BookChunk, BookChunk.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id, or_(*filters))
        .order_by(Chapter.number.asc(), BookChunk.chunk_index.asc())
    )
    if upto_chapter is not None:
        query = query.where(Chapter.number <= upto_chapter)

    rows = (await db.execute(query)).all()
    for chapter_number, text in rows:
        if any(_find_name_occurrences(text or "", candidate) > 0 for candidate in candidates):
            return int(chapter_number)
    return None


async def find_earliest_character_mention_chapters(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    candidates_by_key: Mapping[Hashable, Sequence[str]],
    upto_chapter: int | None = None,
) -> dict[Hashable, int]:
    normalized_candidates: dict[Hashable, list[str]] = {}
    filters: list[Any] = []

    for key, raw_candidates in candidates_by_key.items():
        candidates = merge_list_values([], list(raw_candidates))
        if not candidates:
            continue
        normalized_candidates[key] = candidates
        filters.extend(
            BookChunk.text.ilike(f"%{candidate}%") for candidate in candidates if candidate
        )

    if not normalized_candidates or not filters:
        return {}

    query = (
        select(Chapter.number, BookChunk.text)
        .join(BookChunk, BookChunk.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id, or_(*filters))
        .order_by(Chapter.number.asc(), BookChunk.chunk_index.asc())
    )
    if upto_chapter is not None:
        query = query.where(Chapter.number <= upto_chapter)

    rows = (await db.execute(query)).all()
    resolved: dict[Hashable, int] = {}
    unresolved = set(normalized_candidates)
    for chapter_number, text in rows:
        if not unresolved:
            break
        chapter_text = text or ""
        for key in list(unresolved):
            if any(
                _find_name_occurrences(chapter_text, candidate) > 0
                for candidate in normalized_candidates[key]
            ):
                resolved[key] = int(chapter_number)
                unresolved.remove(key)

    return resolved


async def backfill_character_first_chapters_for_chapter_text(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    chapter_text: str | None,
) -> bool:
    if not chapter_text or not chapter_text.strip():
        return False

    characters = (
        (
            await db.execute(
                select(Character)
                .where(Character.book_id == book_id, Character.first_chapter > chapter_number)
                .order_by(Character.first_chapter.asc(), Character.name.asc())
            )
        )
        .scalars()
        .all()
    )

    changed = False
    for character in characters:
        candidates = merge_list_values([character.name], character.aliases or [])
        if not any(_find_name_occurrences(chapter_text, candidate) > 0 for candidate in candidates):
            continue

        earliest_chapter = await find_earliest_character_mention_chapter(
            db,
            book_id=book_id,
            name=character.name,
            aliases=character.aliases or [],
            upto_chapter=chapter_number,
        )
        resolved_first_chapter = earliest_chapter or chapter_number
        if resolved_first_chapter >= character.first_chapter:
            continue

        character.first_chapter = resolved_first_chapter
        if (
            character.last_seen_chapter is None
            or character.last_seen_chapter < resolved_first_chapter
        ):
            character.last_seen_chapter = resolved_first_chapter
        changed = True

    return changed
