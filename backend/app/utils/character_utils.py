"""
Character utility helpers — shared across route modules.
Covers display filtering, status derivation, relationship summaries,
and text-sanitization helpers used on character data.
"""
from __future__ import annotations

import re
import math
import uuid
from collections import Counter
from difflib import SequenceMatcher
from typing import Any

import bleach  # type: ignore[import-untyped]
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine.character.entity_filters import (
    complex_character_score,
    compute_all_subtype_scores,
    gag_character_score,
    character_visibility_score,
    VISIBILITY_THRESHOLD,
    is_displayable_character_entity,
)
from app.engine.character.profile_builder import merge_profile_fields
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, QuoteEntry, WikiEntry

BLEACH_EMPTY_TAGS: Any = frozenset()

# ─── Display filter ───────────────────────────────────────────────────────────

def is_displayable_character(char: Character) -> bool:
    name = " ".join((char.name or "").split())
    if not name:
        return False
    score = character_visibility_score(
        name,
        role=char.role,
        aliases=char.aliases or [],
        arc_summary=char.arc_summary,
        personality_tags=char.personality_tags or [],
        motivations=char.motivations or [],
        fears=char.fears or [],
        archetype=char.archetype or char.arc_summary,
        trait_state=char.trait_state or {},
        relationship_count=0,
    )
    return score >= VISIBILITY_THRESHOLD and is_displayable_character_entity(
        name,
        role=char.role,
        aliases=char.aliases or [],
        personality_tags=char.personality_tags or [],
        motivations=char.motivations or [],
        fears=char.fears or [],
        archetype=char.archetype or char.arc_summary,
        trait_state=char.trait_state or {},
        relationship_count=0,
    )


# ─── Status derivation ────────────────────────────────────────────────────────

def character_status(char: Character) -> str:
    text = " ".join(
        part
        for part in [
            char.arc_summary or "",
            " ".join(event.get("event", "") for event in (char.growth_events or []) if isinstance(event, dict)),
        ]
        if part
    ).lower()
    deceased_markers = ("deceased", "dead", "dies", "died", "killed", "murdered", "executed", "buried")
    return "deceased" if any(marker in text for marker in deceased_markers) else "alive"


# ─── Relationship summary helpers ─────────────────────────────────────────────

def relationship_summary_for_character(
    rel: CharacterRelationship,
    name_a: str,
    name_b: str,
    perspective_name: str,
) -> str | None:
    counterpart = name_b if perspective_name == name_a else name_a
    rel_type = (rel.rel_type or "connection").replace("_", " ").strip()
    if not rel_type:
        rel_type = "connection"
    return f"{rel_type.capitalize()} connection with {counterpart}."


def relationship_summary(
    description: str | None,
    rel_type: str | None,
    name_a: str,
    name_b: str,
) -> str | None:
    if description:
        return " ".join(description.split())
    if rel_type:
        return f"{name_a} has a {rel_type} relationship with {name_b}."
    return None


def append_unique_summary(
    rel_summaries: dict[str, list[str]],
    rel_keys: dict[str, set[str]],
    char_id: str,
    signature: str,
    summary: str,
) -> None:
    bucket = rel_keys.setdefault(char_id, set())
    if signature in bucket:
        return
    bucket.add(signature)
    rel_summaries.setdefault(char_id, []).append(summary)


# ─── List / string deduplication helpers ─────────────────────────────────────

def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def merge_description_with_relationships(
    description: str,
    relationship_summaries: list[str],
) -> str:
    preview = relationship_summaries[:2]
    if not preview:
        return description
    return f"{description}. {' '.join(preview)}"


# ─── Text-cleaning helpers ────────────────────────────────────────────────────

def clean_optional_text(value: object | None) -> str | None:
    cleaned = str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))
    return cleaned or None


def clean_string_list(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = str(bleach.clean(str(raw or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


# ─── Name / similarity helpers ───────────────────────────────────────────────

_NAME_TITLES = {
    "mr", "mrs", "ms", "miss", "dr", "sir", "lady", "lord", "prof", "professor",
    "capt", "captain", "commander", "master", "mistress",
}


def normalize_character_name(name: str | None) -> str:
    if not name:
        return ""
    tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name) if token.casefold() not in _NAME_TITLES]
    return " ".join(tokens).casefold().strip()


def _name_tokens(name: str | None) -> list[str]:
    normalized = normalize_character_name(name)
    return normalized.split() if normalized else []


def has_shared_surname(name1: str | None, name2: str | None) -> bool:
    left_tokens = _name_tokens(name1)
    right_tokens = _name_tokens(name2)
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return False
    return left_tokens[-1] == right_tokens[-1]


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current = [i]
        for j, char_right in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (char_left != char_right)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _sequence_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def name_similarity(name1: str | None, name2: str | None) -> float:
    left = normalize_character_name(name1)
    right = normalize_character_name(name2)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    jw = _sequence_ratio(left, right)
    token_sort = _sequence_ratio(" ".join(sorted(left.split())), " ".join(sorted(right.split())))
    token_set = _sequence_ratio(" ".join(sorted(set(left.split()))), " ".join(sorted(set(right.split()))))
    score = max(jw, token_sort, token_set)

    if has_shared_surname(name1, name2) and score >= 0.70:
        score = min(1.0, score + 0.15)

    left_tokens = left.split()
    right_tokens = right.split()
    if (
        len(left_tokens) <= 2
        and len(right_tokens) <= 2
        and _levenshtein_distance(left, right) <= 2
    ):
        score = max(score, 0.9)

    if (
        len(left_tokens) >= 2
        and len(right_tokens) >= 2
        and (left.startswith(right) or right.startswith(left))
    ):
        score = max(score, 0.88)

    return min(score, 1.0)


def description_similarity(desc1: str | None, desc2: str | None) -> float:
    left = " ".join((desc1 or "").split()).strip()
    right = " ".join((desc2 or "").split()).strip()
    if not left or not right:
        return 0.0
    if left.casefold() == right.casefold():
        return 1.0
    try:
        left_tokens = _similarity_tokens(left)
        right_tokens = _similarity_tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0

        doc_freq: dict[str, int] = {}
        for token in set(left_tokens) | set(right_tokens):
            doc_freq[token] = int(token in left_tokens) + int(token in right_tokens)

        def _vector(tokens: list[str]) -> dict[str, float]:
            counts = Counter(tokens)
            total = len(tokens)
            vector: dict[str, float] = {}
            for token, count in counts.items():
                idf = math.log((2 + 1) / (doc_freq[token] + 1)) + 1
                vector[token] = (count / total) * idf
            return vector

        left_vec = _vector(left_tokens)
        right_vec = _vector(right_tokens)
        return _cosine_from_vectors(left_vec, right_vec)
    except Exception:
        return 0.0


def _similarity_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9]+", text.casefold()) if len(token) > 2]


def _cosine_from_vectors(left_vec: dict[str, float], right_vec: dict[str, float]) -> float:
    shared = set(left_vec) & set(right_vec)
    if not shared:
        return 0.0
    dot = sum(left_vec[token] * right_vec[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left_vec.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vec.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def clean_markdown_asterisks(text: str) -> str:
    return text.replace("**", "").replace("*", "")


def apply_manual_character_description(character: Character, description: str | None) -> None:
    cleaned = clean_optional_text(description)
    trait_state = dict(character.trait_state or {})
    if cleaned:
        trait_state["manual_description"] = {"value": cleaned, "confidence": 1.0, "type": "abstract"}
    else:
        trait_state.pop("manual_description", None)
    character.trait_state = trait_state


def _normalize_character_reference(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _character_reference_values(character: Character) -> set[str]:
    values = {_normalize_character_reference(character.id), _normalize_character_reference(character.name)}
    values.update(_normalize_character_reference(alias) for alias in (character.aliases or []))
    return {value for value in values if value}


def _replace_reference_list(values: list[object] | None, *, matches: set[str], replacement: str) -> list[str]:
    replaced: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        candidate = " ".join(str(item or "").split()).strip()
        if not candidate:
            continue
        next_value = replacement if _normalize_character_reference(candidate) in matches else candidate
        if next_value.lower() in seen:
            continue
        seen.add(next_value.lower())
        replaced.append(next_value)
    return replaced


def _merge_voice_profiles(primary_profile: CharacterVoiceProfile | None, secondary_profile: CharacterVoiceProfile | None) -> None:
    if primary_profile is None or secondary_profile is None:
        return
    primary_profile.sample_dialogue_count = int(primary_profile.sample_dialogue_count or 0) + int(secondary_profile.sample_dialogue_count or 0)
    primary_profile.sample_word_count = int(primary_profile.sample_word_count or 0) + int(secondary_profile.sample_word_count or 0)
    for field_name in (
        "avg_sentence_length",
        "avg_word_length_x100",
        "contraction_rate_x1000",
        "question_rate_x1000",
        "exclamation_rate_x1000",
        "ellipsis_rate_x1000",
        "dash_rate_x1000",
        "uppercase_rate_x1000",
        "formality_score_x1000",
        "lexical_complexity_x1000",
        "emotional_intensity_x1000",
    ):
        if getattr(primary_profile, field_name) is None:
            setattr(primary_profile, field_name, getattr(secondary_profile, field_name))
    if not primary_profile.dominant_markers and secondary_profile.dominant_markers:
        primary_profile.dominant_markers = secondary_profile.dominant_markers
    if not primary_profile.signature_phrases and secondary_profile.signature_phrases:
        primary_profile.signature_phrases = secondary_profile.signature_phrases


async def _merge_character_references(
    db: AsyncSession,
    *,
    primary: Character,
    secondary: Character,
    book_id: uuid.UUID,
) -> None:
    reference_values = _character_reference_values(secondary)

    plot_threads = (
        await db.execute(select(PlotThread).where(PlotThread.book_id == book_id))
    ).scalars().all()
    for thread in plot_threads:
        updated_ids = _replace_reference_list(thread.character_ids, matches=reference_values, replacement=primary.name)
        if updated_ids:
            thread.character_ids = updated_ids

    wiki_entries = (
        await db.execute(select(WikiEntry).where(WikiEntry.book_id == book_id))
    ).scalars().all()
    for entry in wiki_entries:
        related = _replace_reference_list(entry.related_char_ids, matches=reference_values, replacement=str(primary.id))
        if related:
            entry.related_char_ids = related

    chapter_summaries = (
        await db.execute(
            select(ChapterSummary)
            .join(ChapterSummary.chapter)
            .where(ChapterSummary.chapter.has(book_id=book_id))
        )
    ).scalars().all()
    for summary in chapter_summaries:
        key_events = [dict(event) if isinstance(event, dict) else event for event in (summary.key_events or [])]
        changed = False
        for event in key_events:
            if not isinstance(event, dict):
                continue
            involved = _replace_reference_list(event.get("involved_characters"), matches=reference_values, replacement=str(primary.id))
            if involved != list(event.get("involved_characters") or []):
                event["involved_characters"] = involved
                changed = True
        if changed:
            summary.key_events = key_events

        char_changes = [dict(change) if isinstance(change, dict) else change for change in (summary.char_changes or [])]
        char_change_changed = False
        for change in char_changes:
            if not isinstance(change, dict):
                continue
            candidate = " ".join(str(change.get("character") or "").split()).strip()
            if candidate and _normalize_character_reference(candidate) in reference_values:
                change["character"] = primary.name
                char_change_changed = True
        if char_change_changed:
            summary.char_changes = char_changes

    quotes = (
        await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == book_id))
    ).scalars().all()
    for quote in quotes:
        if _normalize_character_reference(quote.character_name) in reference_values:
            quote.character_name = primary.name


async def merge_characters(
    db: AsyncSession,
    primary_id: uuid.UUID,
    secondary_id: uuid.UUID,
    book_id: uuid.UUID,
) -> Character:
    """Merge duplicate character records and preserve aliases / references."""
    characters = (
        await db.execute(
            select(Character)
            .options(selectinload(Character.voice_profile))
            .where(Character.id.in_([primary_id, secondary_id]))
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    characters_by_id = {character.id: character for character in characters}
    primary = characters_by_id.get(primary_id)
    secondary = characters_by_id.get(secondary_id)
    if not primary or not secondary:
        raise ValueError("Character not found")
    if primary.book_id != book_id or secondary.book_id != book_id:
        raise ValueError("Characters must belong to the same book")
    if primary.id == secondary.id:
        return primary

    merged = merge_profile_fields(primary, secondary)
    primary.aliases = merged["aliases"]
    primary.role = merged["role"]
    primary.first_chapter = merged["first_chapter"]
    primary.last_seen_chapter = merged["last_seen_chapter"]
    primary.mention_count = (primary.mention_count or 0) + (secondary.mention_count or 0)
    primary.trait_state = merged["trait_state"]
    primary.hair = merged["hair"]
    primary.eyes = merged["eyes"]
    primary.build = merged["build"]
    primary.age_descriptor = merged["age_descriptor"]
    primary.distinguishing = merged["distinguishing"]
    primary.personality_tags = merged["personality_tags"]
    primary.motivations = merged["motivations"]
    primary.fears = merged["fears"]
    primary.arc_summary = merged["arc_summary"]
    primary.archetype = merged["archetype"]
    primary.growth_events = merged["growth_events"]
    if primary.embedding is None and secondary.embedding is not None:
        primary.embedding = secondary.embedding
    if primary.voice_profile and secondary.voice_profile:
        _merge_voice_profiles(primary.voice_profile, secondary.voice_profile)
        await db.delete(secondary.voice_profile)
    elif primary.voice_profile is None and secondary.voice_profile is not None:
        secondary.voice_profile.character_id = primary.id
        secondary.voice_profile.book_id = primary.book_id

    state_rows_result = await db.execute(select(CharacterState).where(CharacterState.character_id == secondary.id))
    state_rows = state_rows_result.scalars().all()
    for state in state_rows:
        existing_state = (
            await db.execute(
                select(CharacterState).where(
                    CharacterState.character_id == primary.id,
                    CharacterState.at_chapter == state.at_chapter,
                )
            )
        ).scalar()
        if existing_state:
            existing_state.trait_snapshot = state.trait_snapshot or existing_state.trait_snapshot
            if state.prompt_delta and not existing_state.prompt_delta:
                existing_state.prompt_delta = state.prompt_delta
            if state.arc_note and not existing_state.arc_note:
                existing_state.arc_note = state.arc_note
            if state.growth_event and not existing_state.growth_event:
                existing_state.growth_event = state.growth_event
            await db.delete(state)
        else:
            state.character_id = primary.id

    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            or_(
                CharacterRelationship.character_a_id == secondary.id,
                CharacterRelationship.character_b_id == secondary.id,
            ),
        )
    )
    rels = rels_result.scalars().all()
    for rel in rels:
        if rel.character_a_id == secondary.id:
            rel.character_a_id = primary.id
        if rel.character_b_id == secondary.id:
            rel.character_b_id = primary.id
        if rel.character_a_id == rel.character_b_id:
            await db.delete(rel)

    await _merge_character_references(db, primary=primary, secondary=secondary, book_id=book_id)
    await _dedupe_relationships(db, book_id)
    await db.delete(secondary)
    await db.flush()
    update_character_classification(primary)
    return primary


async def _dedupe_relationships(db: AsyncSession, book_id: uuid.UUID) -> None:
    rels_result = await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
    rels = rels_result.scalars().all()
    seen: set[tuple[str, str, str, int | None, int | None, str]] = set()
    for rel in rels:
        pair = sorted([str(rel.character_a_id), str(rel.character_b_id)])
        key = (
            pair[0],
            pair[1],
            rel.rel_type or "",
            rel.from_chapter,
            rel.to_chapter,
            (rel.description or "").strip().lower(),
        )
        if key in seen:
            await db.delete(rel)
            continue
        seen.add(key)


# ─── Character classification scoring ───────────────────────────────────────────

def compute_character_classification(char: Character) -> tuple[str, int, dict[str, int]]:
    """Compute character type and subtype scores for a character.

    Returns:
        (character_type, character_type_score, subtype_scores)
        character_type: "complex" | "normal" | "gag" | "meme"
        character_type_score: 0-10 score for main type
        subtype_scores: dict of subtype names to scores (only >= 3)
    """
    # Compute main type scores
    gag_score = gag_character_score(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        mention_count=char.mention_count or 0,
        role=char.role,
        growth_events=char.growth_events,
    )
    
    complex_score = complex_character_score(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        mention_count=char.mention_count or 0,
        role=char.role,
        growth_events=char.growth_events,
        motivations=char.motivations,
        fears=char.fears,
    )
    
    # Determine main type based on scores
    if gag_score >= 3:
        character_type = "gag" if gag_score > complex_score else "complex"
        character_type_score = max(gag_score, complex_score)
    elif complex_score >= 5:
        character_type = "complex"
        character_type_score = complex_score
    else:
        character_type = "normal"
        character_type_score = complex_score
    
    # Compute subtype scores
    subtype_scores = compute_all_subtype_scores(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        growth_events=char.growth_events,
    )
    
    return character_type, character_type_score, subtype_scores


def update_character_classification(char: Character) -> None:
    """Update character's classification fields with computed scores."""
    character_type, character_type_score, subtype_scores = compute_character_classification(char)
    char.character_type = character_type
    char.character_type_score = character_type_score
    char.subtype_scores = subtype_scores
