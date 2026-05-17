"""
Character utility helpers — shared across route modules.
Covers display filtering, status derivation, relationship summaries,
and text-sanitization helpers used on character data.
"""
from __future__ import annotations

import math
import re
import uuid
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any

import bleach  # type: ignore[import-untyped]
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine.character.entity_filters import (
    VISIBILITY_THRESHOLD,
    character_visibility_score,
    complex_character_score,
    compute_all_subtype_scores,
    gag_character_score,
    is_displayable_character_entity,
)
from app.engine.character.extractor import extract_characters_and_relationships
from app.engine.character.profile_builder import (
    build_description,
    choose_richer_text,
    flat,
    merge_growth_events,
    merge_list_values,
    merge_profile_fields,
    merge_trait_states,
)
from app.models.book import Chapter
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    QuoteEntry,
    WikiEntry,
)

BLEACH_EMPTY_TAGS: Any = frozenset()

# ─── Display filter ───────────────────────────────────────────────────────────

def is_displayable_character(char: Character) -> bool:
    name = " ".join((char.name or "").split())
    if not name:
        return False
    if getattr(char, "is_manual", False):
        return True
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
    description: str | None,
    relationship_summaries: list[str],
) -> str:
    preview = clean_string_list(relationship_summaries)[:2]
    base = clean_optional_text(description)
    if not preview:
        return base or ""
    if not base:
        return " ".join(preview)
    return f"{base}. {' '.join(preview)}"


def _ensure_sentence(text: str) -> str:
    cleaned = clean_optional_text(text)
    if not cleaned:
        return ""
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def compose_character_description(
    *,
    trait_state: dict[str, Any] | None,
    archetype: str | None,
    arc_summary: str | None = None,
    personality_tags: list[str] | None = None,
    motivations: list[str] | None = None,
    relationship_summaries: list[str] | None = None,
) -> str | None:
    segments: list[str] = []
    base = clean_optional_text(build_description(trait_state or {}, archetype))
    if base and base.casefold() != "appearance not yet described":
        segments.append(_ensure_sentence(base))

    arc = clean_optional_text(arc_summary)
    if arc and (not base or arc.casefold() != base.casefold()):
        segments.append(_ensure_sentence(arc))

    if not segments:
        cleaned_tags = clean_string_list(personality_tags)
        if cleaned_tags:
            segments.append(f"Disposition: {', '.join(cleaned_tags[:3])}.")
        cleaned_motivations = clean_string_list(motivations)
        if cleaned_motivations:
            segments.append(f"Wants: {', '.join(cleaned_motivations[:2])}.")

    relationship_preview = clean_string_list(relationship_summaries)[:2]
    if relationship_preview:
        segments.append(" ".join(_ensure_sentence(summary) for summary in relationship_preview if summary))

    composed = " ".join(segment for segment in segments if segment).strip()
    return composed or None


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
_TITLE_IDENTITY_GROUPS = {
    "mr": "male",
    "master": "male",
    "sir": "male",
    "mrs": "female",
    "ms": "female",
    "miss": "female",
    "mistress": "female",
}


def normalize_character_name(name: str | None) -> str:
    if not name:
        return ""
    tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name) if token.casefold() not in _NAME_TITLES]
    return " ".join(tokens).casefold().strip()


def _leading_title(name: str | None) -> str:
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name or "")]
    return tokens[0] if tokens and tokens[0] in _NAME_TITLES else ""


def partition_identity_key(name: str | None) -> str:
    normalized = normalize_character_name(name)
    if not normalized:
        return ""
    title = _leading_title(name)
    return f"{title}:{normalized}" if title else normalized


def has_conflicting_title_identity(name1: str | None, name2: str | None) -> bool:
    left_group = _TITLE_IDENTITY_GROUPS.get(_leading_title(name1))
    right_group = _TITLE_IDENTITY_GROUPS.get(_leading_title(name2))
    return bool(left_group and right_group and left_group != right_group)


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
        if has_conflicting_title_identity(name1, name2):
            return 0.35
        return 1.0

    jw = _sequence_ratio(left, right)
    token_sort = _sequence_ratio(" ".join(sorted(left.split())), " ".join(sorted(right.split())))
    token_set = _sequence_ratio(" ".join(sorted(set(left.split()))), " ".join(sorted(set(right.split()))))
    score = max(jw, token_sort, token_set)

    if has_conflicting_title_identity(name1, name2):
        score = min(score, 0.35)

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


GRAPH_VISIBILITY_OVERRIDE_KEY = "graph_visibility_override"
GRAPH_VISIBILITY_OVERRIDE_VALUES = {"include", "exclude"}


def graph_visibility_override_value(trait_state: dict[str, Any] | None) -> str | None:
    if not isinstance(trait_state, dict):
        return None
    raw = trait_state.get(GRAPH_VISIBILITY_OVERRIDE_KEY)
    if isinstance(raw, dict):
        value = clean_optional_text(raw.get("value"))
    else:
        value = clean_optional_text(raw)
    if not value:
        return None
    normalized = value.casefold()
    return normalized if normalized in GRAPH_VISIBILITY_OVERRIDE_VALUES else None


def get_graph_visibility_override(character: Character) -> str | None:
    trait_state = getattr(character, "trait_state", None)
    return graph_visibility_override_value(trait_state if isinstance(trait_state, dict) else None)


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


def _merge_character_descriptions(primary_description: str | None, secondary_description: str | None) -> str | None:
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


def _expand_reference_list(values: list[object] | None, *, matches: set[str], replacements: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    normalized_replacements = [" ".join(item.split()).strip() for item in replacements if " ".join(item.split()).strip()]
    for item in values or []:
        candidate = " ".join(str(item or "").split()).strip()
        if not candidate:
            continue
        next_values = normalized_replacements if _normalize_character_reference(candidate) in matches else [candidate]
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
        await db.execute(
            select(Character)
            .where(Character.book_id == book_id, Character.first_chapter > chapter_number)
            .order_by(Character.first_chapter.asc(), Character.name.asc())
        )
    ).scalars().all()

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
        if character.last_seen_chapter is None or character.last_seen_chapter < resolved_first_chapter:
            character.last_seen_chapter = resolved_first_chapter
        changed = True

    return changed


def _collect_partition_evidence(
    chapter_rows: list[tuple[int, str]],
    *,
    name: str,
    aliases: list[str],
) -> dict[str, Any]:
    candidates = merge_list_values([name], aliases)
    snippets: list[str] = []
    chapter_counts: dict[int, int] = {}
    mention_count = 0
    for chapter_number, text in chapter_rows:
        score = sum(_find_name_occurrences(text, candidate) for candidate in candidates)
        if score <= 0:
            continue
        mention_count += score
        chapter_counts[chapter_number] = chapter_counts.get(chapter_number, 0) + score
        if len(snippets) < 6:
            snippets.append(text[:2200])
    ordered_chapters = sorted(chapter_counts)
    return {
        "chapter_counts": chapter_counts,
        "snippets": snippets,
        "mention_count": mention_count,
        "first_chapter": ordered_chapters[0] if ordered_chapters else None,
        "last_seen_chapter": ordered_chapters[-1] if ordered_chapters else None,
    }


def _partition_matches_entity(name: str, aliases: list[str], entity: dict[str, Any]) -> bool:
    from app.engine.character.deduplicator import names_equivalent

    entity_name = str(entity.get("name") or "").strip()
    entity_aliases = [str(alias) for alias in (entity.get("aliases") or []) if str(alias).strip()]
    if not entity_name:
        return False
    if names_equivalent(name, aliases, entity_name, entity_aliases):
        return True
    partition_keys = {normalize_character_name(name), *(normalize_character_name(alias) for alias in aliases)}
    entity_keys = {normalize_character_name(entity_name), *(normalize_character_name(alias) for alias in entity_aliases)}
    partition_keys.discard("")
    entity_keys.discard("")
    return bool(partition_keys & entity_keys)


def _merge_partition_entities(name: str, aliases: list[str], entities: list[dict[str, Any]]) -> dict[str, Any]:
    merged_traits: dict[str, Any] = {}
    merged_growth_events: list[dict] = []
    merged_personality: list[str] = []
    merged_motivations: list[str] = []
    merged_fears: list[str] = []
    merged_aliases = merge_list_values([name], aliases)
    merged: dict[str, Any] = {
        "name": name,
        "aliases": aliases,
        "role": None,
        "goal": None,
        "lie_they_believe": None,
        "backstory_wound": None,
        "arc_type": None,
        "arc_summary": None,
        "archetype": None,
    }

    for entity in entities:
        merged_traits = merge_trait_states(merged_traits, entity.get("traits") if isinstance(entity.get("traits"), dict) else {})
        merged_aliases = merge_list_values(merged_aliases, entity.get("aliases") if isinstance(entity.get("aliases"), list) else [])
        merged_personality = merge_list_values(merged_personality, entity.get("personality_tags") if isinstance(entity.get("personality_tags"), list) else [])
        merged_motivations = merge_list_values(merged_motivations, entity.get("motivations") if isinstance(entity.get("motivations"), list) else [])
        merged_fears = merge_list_values(merged_fears, entity.get("fears") if isinstance(entity.get("fears"), list) else [])
        if not merged["role"]:
            merged["role"] = entity.get("role")
        merged["goal"] = choose_richer_text(merged["goal"], entity.get("goal"))
        merged["lie_they_believe"] = choose_richer_text(merged["lie_they_believe"], entity.get("lie_they_believe"))
        merged["backstory_wound"] = choose_richer_text(merged["backstory_wound"], entity.get("backstory_wound"))
        merged["arc_type"] = choose_richer_text(merged["arc_type"], entity.get("arc_type"))
        merged["arc_summary"] = choose_richer_text(merged["arc_summary"], entity.get("arc_summary"))
        merged["archetype"] = choose_richer_text(merged["archetype"], entity.get("archetype"))
        growth_event = entity.get("growth_event")
        merged_growth_events = merge_growth_events(merged_growth_events, [growth_event] if isinstance(growth_event, dict) else [])

    merged["traits"] = merged_traits
    merged["aliases"] = [alias for alias in merged_aliases if normalize_character_name(alias) != normalize_character_name(name)]
    merged["personality_tags"] = merged_personality
    merged["motivations"] = merged_motivations
    merged["fears"] = merged_fears
    merged["growth_events"] = merged_growth_events
    return merged


async def _build_partition_payload(
    *,
    source: Character,
    book_id: uuid.UUID,
    name: str,
    aliases: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    if evidence["snippets"]:
        try:
            extracted = await extract_characters_and_relationships("\n\n".join(evidence["snippets"])[:12000])
            entities = [
                entity
                for entity in extracted.get("characters", [])
                if isinstance(entity, dict) and _partition_matches_entity(name, aliases, entity)
            ]
        except Exception:
            entities = []

    merged_entity = _merge_partition_entities(name, aliases, entities)
    trait_state = merge_trait_states({}, merged_entity.get("traits") if isinstance(merged_entity.get("traits"), dict) else {})
    first_chapter = int(evidence.get("first_chapter") or source.first_chapter or 1)
    last_seen_chapter = int(
        evidence.get("last_seen_chapter")
        or source.last_seen_chapter
        or source.first_chapter
        or first_chapter
    )
    mention_count = max(1, int(evidence.get("mention_count") or 0))

    return {
        "book_id": book_id,
        "name": name,
        "aliases": merged_entity.get("aliases") or aliases,
        "role": merged_entity.get("role") or source.role,
        "first_chapter": first_chapter,
        "last_seen_chapter": last_seen_chapter,
        "mention_count": mention_count,
        "trait_state": trait_state,
        "hair": flat(trait_state, "hair"),
        "eyes": flat(trait_state, "eyes"),
        "build": flat(trait_state, "build"),
        "age_descriptor": flat(trait_state, "age"),
        "distinguishing": flat(trait_state, "distinguishing"),
        "personality_tags": merged_entity.get("personality_tags") or [],
        "goal": merged_entity.get("goal"),
        "motivations": merged_entity.get("motivations") or [],
        "fears": merged_entity.get("fears") or [],
        "lie_they_believe": merged_entity.get("lie_they_believe"),
        "backstory_wound": merged_entity.get("backstory_wound"),
        "arc_type": merged_entity.get("arc_type"),
        "arc_summary": merged_entity.get("arc_summary"),
        "archetype": merged_entity.get("archetype"),
        "growth_events": merged_entity.get("growth_events") or [],
    }


def _best_partition_for_chapter(
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
    chapter_number: int | None,
) -> Character | None:
    if chapter_number is None:
        return None
    scored = [
        (int((evidence_by_character_id.get(character.id) or {}).get("chapter_counts", {}).get(chapter_number, 0)), character)
        for character in partitions
    ]
    scored = [item for item in scored if item[0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def _best_partition_for_text(
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
    text: str | None,
) -> Character | None:
    scored = []
    for character in partitions:
        candidates = merge_list_values([character.name], character.aliases or [])
        score = sum(_find_name_occurrences(text or "", candidate) for candidate in candidates)
        if score > 0:
            scored.append((score, character))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None
        return scored[0][1]
    return None


async def _reassign_partition_references(
    db: AsyncSession,
    *,
    source: Character,
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
) -> None:
    primary_partition = max(
        partitions,
        key=lambda character: int((evidence_by_character_id.get(character.id) or {}).get("mention_count", 0)),
    )
    reference_values = _character_reference_values(source)

    state_rows = (await db.execute(select(CharacterState).where(CharacterState.character_id == source.id))).scalars().all()
    for state in state_rows:
        target = _best_partition_for_chapter(partitions, evidence_by_character_id, state.at_chapter) or primary_partition
        state.character_id = target.id

    relationships = (
        await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.book_id == source.book_id,
                or_(
                    CharacterRelationship.character_a_id == source.id,
                    CharacterRelationship.character_b_id == source.id,
                ),
            )
        )
    ).scalars().all()
    for relationship in relationships:
        target = _best_partition_for_chapter(partitions, evidence_by_character_id, relationship.from_chapter) or primary_partition
        if relationship.character_a_id == source.id:
            relationship.character_a_id = target.id
        if relationship.character_b_id == source.id:
            relationship.character_b_id = target.id
        if relationship.character_a_id == relationship.character_b_id:
            await db.delete(relationship)

    plot_threads = (await db.execute(select(PlotThread).where(PlotThread.book_id == source.book_id))).scalars().all()
    for thread in plot_threads:
        updated_ids = _expand_reference_list(
            thread.character_ids,
            matches=reference_values,
            replacements=[character.name for character in partitions],
        )
        if updated_ids:
            thread.character_ids = updated_ids

    wiki_entries = (await db.execute(select(WikiEntry).where(WikiEntry.book_id == source.book_id))).scalars().all()
    for entry in wiki_entries:
        updated_related = _expand_reference_list(
            entry.related_char_ids,
            matches=reference_values,
            replacements=[str(character.id) for character in partitions],
        )
        if updated_related:
            entry.related_char_ids = updated_related

    chapter_summaries = (
        await db.execute(
            select(ChapterSummary, Chapter.number)
            .join(ChapterSummary.chapter)
            .where(Chapter.book_id == source.book_id)
        )
    ).all()
    for summary, chapter_number in chapter_summaries:
        target = _best_partition_for_chapter(partitions, evidence_by_character_id, chapter_number) or primary_partition
        key_events = [dict(event) if isinstance(event, dict) else event for event in (summary.key_events or [])]
        key_events_changed = False
        for event in key_events:
            if not isinstance(event, dict):
                continue
            involved = _expand_reference_list(
                event.get("involved_characters"),
                matches=reference_values,
                replacements=[str(target.id)],
            )
            if involved != list(event.get("involved_characters") or []):
                event["involved_characters"] = involved
                key_events_changed = True
        if key_events_changed:
            summary.key_events = key_events

        char_changes = [dict(change) if isinstance(change, dict) else change for change in (summary.char_changes or [])]
        char_changes_changed = False
        for change in char_changes:
            if not isinstance(change, dict):
                continue
            candidate = " ".join(str(change.get("character") or "").split()).strip()
            if candidate and _normalize_character_reference(candidate) in reference_values:
                change["character"] = target.name
                char_changes_changed = True
        if char_changes_changed:
            summary.char_changes = char_changes

    quotes = (await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == source.book_id))).scalars().all()
    for quote in quotes:
        if _normalize_character_reference(quote.character_name) not in reference_values:
            continue
        target = _best_partition_for_text(partitions, evidence_by_character_id, quote.quote_text) or primary_partition
        quote.character_name = target.name


async def partition_character(
    db: AsyncSession,
    *,
    source: Character,
    partitions: list[dict[str, list[str] | str]],
) -> list[Character]:
    cleaned_partitions: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for partition in partitions:
        cleaned_name = clean_optional_text(partition.get("name"))
        if not cleaned_name:
            continue
        normalized_name = normalize_character_name(cleaned_name)
        identity_key = partition_identity_key(cleaned_name)
        if not identity_key or identity_key in seen_names:
            continue
        seen_names.add(identity_key)
        aliases = [
            alias
            for alias in clean_string_list(partition.get("aliases") if isinstance(partition.get("aliases"), list) else [])
            if normalize_character_name(alias) != normalized_name
        ]
        cleaned_partitions.append({"name": cleaned_name, "aliases": aliases})

    if len(cleaned_partitions) < 2:
        raise ValueError("At least two distinct partition targets are required")

    chapter_rows = (
        await db.execute(
            select(Chapter.number, BookChunk.text)
            .join(BookChunk, BookChunk.chapter_id == Chapter.id)
            .where(BookChunk.book_id == source.book_id)
            .order_by(Chapter.number.asc(), BookChunk.chunk_index.asc())
        )
    ).all()

    created_partitions: list[Character] = []
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]] = {}
    for partition in cleaned_partitions:
        evidence = _collect_partition_evidence(
            chapter_rows,
            name=str(partition["name"]),
            aliases=[str(alias) for alias in partition["aliases"]],
        )
        payload = await _build_partition_payload(
            source=source,
            book_id=source.book_id,
            name=str(partition["name"]),
            aliases=[str(alias) for alias in partition["aliases"]],
            evidence=evidence,
        )
        character = Character(**payload)
        db.add(character)
        await db.flush()
        update_character_classification(character)
        created_partitions.append(character)
        evidence_by_character_id[character.id] = evidence

    await _reassign_partition_references(
        db,
        source=source,
        partitions=created_partitions,
        evidence_by_character_id=evidence_by_character_id,
    )
    await _dedupe_relationships(db, source.book_id)
    await db.delete(source)
    await db.flush()
    return created_partitions


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
    merged_manual_description = _merge_character_descriptions(
        _manual_character_description_value(primary.trait_state),
        _manual_character_description_value(secondary.trait_state),
    )
    primary.aliases = merged["aliases"]
    primary.role = merged["role"]
    primary.first_chapter = merged["first_chapter"]
    primary.last_seen_chapter = merged["last_seen_chapter"]
    primary.mention_count = (primary.mention_count or 0) + (secondary.mention_count or 0)
    primary.trait_state = merged["trait_state"]
    if merged_manual_description:
        apply_manual_character_description(primary, merged_manual_description)
    primary.hair = merged["hair"]
    primary.eyes = merged["eyes"]
    primary.build = merged["build"]
    primary.age_descriptor = merged["age_descriptor"]
    primary.distinguishing = merged["distinguishing"]
    primary.personality_tags = merged["personality_tags"]
    primary.goal = merged["goal"]
    primary.motivations = merged["motivations"]
    primary.fears = merged["fears"]
    primary.lie_they_believe = merged["lie_they_believe"]
    primary.backstory_wound = merged["backstory_wound"]
    primary.arc_type = merged["arc_type"]
    primary.arc_summary = merged["arc_summary"]
    primary.archetype = merged["archetype"]
    primary.growth_events = merged["growth_events"]
    if primary.embedding is None and secondary.embedding is not None:
        primary.embedding = secondary.embedding
    if primary.voice_profile and secondary.voice_profile:
        _merge_voice_profiles(primary.voice_profile, secondary.voice_profile)
        # Detach the secondary profile and let delete-orphan remove it once.
        secondary.voice_profile = None
    elif primary.voice_profile is None and secondary.voice_profile is not None:
        moved_voice_profile = secondary.voice_profile
        secondary.voice_profile = None
        primary.voice_profile = moved_voice_profile
        moved_voice_profile.book_id = primary.book_id

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
            if state.motivations_snapshot and not existing_state.motivations_snapshot:
                existing_state.motivations_snapshot = state.motivations_snapshot
            if state.fears_snapshot and not existing_state.fears_snapshot:
                existing_state.fears_snapshot = state.fears_snapshot
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


def _clean_tracker_text(value: object | None) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or None


def _event_chapter(event: dict[str, Any], fallback: int) -> int:
    raw = event.get("chapter_number") or event.get("chapter") or fallback
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return fallback


def _trait_value_for_history(raw: object) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("value")
        return _clean_tracker_text(value)
    return _clean_tracker_text(raw)


def _dominant_marker_lines(profile: CharacterVoiceProfile | None) -> list[str]:
    if profile is None:
        return []
    markers: list[str] = []
    for key, value in (profile.dominant_markers or {}).items():
        cleaned_key = _clean_tracker_text(key)
        cleaned_value = _clean_tracker_text(value)
        if cleaned_key and cleaned_value:
            markers.append(f"{cleaned_key.replace('_', ' ').title()}: {cleaned_value}")
        elif cleaned_key:
            markers.append(cleaned_key.replace("_", " ").title())
    for phrase in profile.signature_phrases or []:
        cleaned_phrase = _clean_tracker_text(phrase)
        if cleaned_phrase:
            markers.append(f'Signature phrase: "{cleaned_phrase}"')
    return dedupe_preserve_order(markers)


def _trait_label(trait_key: str) -> str:
    labels = {
        "hair": "Hair",
        "eyes": "Eyes",
        "build": "Build",
        "age": "Age",
        "face": "Face",
        "distinguishing": "Distinguishing details",
        "manual_description": "Description",
    }
    return labels.get(trait_key, trait_key.replace("_", " ").title())


def build_physical_description_history(states: list[CharacterState]) -> list[dict[str, Any]]:
    tracked_keys = ("hair", "eyes", "build", "age", "face", "distinguishing", "manual_description")
    history: list[dict[str, Any]] = []
    previous_values: dict[str, str] = {}
    for state in sorted(states, key=lambda row: row.at_chapter):
        snapshot = state.trait_snapshot or {}
        for trait_key in tracked_keys:
            current_value = _trait_value_for_history(snapshot.get(trait_key))
            if not current_value:
                continue
            if previous_values.get(trait_key, "").casefold() == current_value.casefold():
                continue
            history.append(
                {
                    "chapter_number": state.at_chapter,
                    "trait": trait_key,
                    "label": _trait_label(trait_key),
                    "value": current_value,
                    "previous_value": previous_values.get(trait_key),
                }
            )
            previous_values[trait_key] = current_value
    return history


def build_relationship_change_entries(
    character: Character,
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in sorted(relationships, key=lambda item: (item.from_chapter or 0, item.to_chapter or 10**6, str(item.id))):
        counterpart_id = rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        rows.append(
            {
                "counterpart_id": str(counterpart_id),
                "counterpart_name": counterpart_names.get(counterpart_id, "Unknown character"),
                "chapter_number": rel.from_chapter or character.first_chapter,
                "to_chapter": rel.to_chapter,
                "type": rel.rel_type or "connection",
                "sentiment": rel.sentiment,
                "description": _clean_tracker_text(rel.description),
            }
        )
    return rows


def build_character_contradictions(
    character: Character,
    states: list[CharacterState],
    physical_history: list[dict[str, Any]],
) -> list[str]:
    contradictions: list[str] = []
    for item in physical_history:
        previous_value = _clean_tracker_text(item.get("previous_value"))
        current_value = _clean_tracker_text(item.get("value"))
        label = _clean_tracker_text(item.get("label"))
        chapter_number = item.get("chapter_number")
        if previous_value and current_value and label:
            contradictions.append(
                f"{label} shifts from {previous_value} to {current_value} by chapter {chapter_number}."
            )

    previous_motivations: list[str] | None = None
    previous_fears: list[str] | None = None
    for state in sorted(states, key=lambda row: row.at_chapter):
        current_motivations = [item for item in (state.motivations_snapshot or []) if _clean_tracker_text(item)]
        current_fears = [item for item in (state.fears_snapshot or []) if _clean_tracker_text(item)]
        if previous_motivations and current_motivations and previous_motivations != current_motivations:
            contradictions.append(
                f"Motivation profile changes by chapter {state.at_chapter}: {', '.join(previous_motivations[:2])} -> {', '.join(current_motivations[:2])}."
            )
        if previous_fears and current_fears and previous_fears != current_fears:
            contradictions.append(
                f"Fear profile changes by chapter {state.at_chapter}: {', '.join(previous_fears[:2])} -> {', '.join(current_fears[:2])}."
            )
        if current_motivations:
            previous_motivations = current_motivations
        if current_fears:
            previous_fears = current_fears
    return dedupe_preserve_order(contradictions)[:10]


def build_character_arc_tracker(
    character: Character,
    *,
    states: list[CharacterState],
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
    voice_profile: CharacterVoiceProfile | None,
    total_chapters: int | None = None,
) -> dict[str, Any]:
    sorted_states = sorted(states, key=lambda row: row.at_chapter)
    raw_events = [event for event in (character.growth_events or []) if isinstance(event, dict)]
    raw_events.sort(key=lambda event: (_event_chapter(event, character.first_chapter), _clean_tracker_text(event.get("event_title") or event.get("event")) or ""))

    turning_points: list[dict[str, Any]] = []
    arc_timeline: list[str] = []
    for event in raw_events:
        chapter_number = _event_chapter(event, character.first_chapter)
        if chapter_number <= 0:
            continue
        title = _clean_tracker_text(event.get("event_title") or event.get("event")) or f"Shift in chapter {chapter_number}"
        description = _clean_tracker_text(event.get("description") or event.get("impact"))
        turning_points.append(
            {
                "chapter_number": chapter_number,
                "title": title,
                "description": description,
                "impact_score": event.get("impact_score") or event.get("importance"),
                "growth_direction": _clean_tracker_text(event.get("growth_direction") or event.get("tone")),
                "is_major": bool(event.get("is_major", False)),
            }
        )
        arc_timeline.append(
            f"Chapter {chapter_number}: {title}" + (f" - {description}" if description else "")
        )

    relationship_changes = build_relationship_change_entries(character, relationships, counterpart_names)
    physical_history = build_physical_description_history(sorted_states)
    contradictions = build_character_contradictions(character, sorted_states, physical_history)
    voice_markers = _dominant_marker_lines(voice_profile)

    diagnostics: list[str] = []
    last_change_chapter = max([character.first_chapter, *[item["chapter_number"] for item in turning_points]], default=character.first_chapter)
    last_seen = character.last_seen_chapter or character.first_chapter
    if last_seen - last_change_chapter >= 14:
        diagnostics.append("Character has not changed meaningfully in 14 chapters.")

    previous_motivations: list[str] | None = None
    for state in sorted_states:
        current_motivations = [item for item in (state.motivations_snapshot or []) if _clean_tracker_text(item)]
        if previous_motivations and current_motivations and previous_motivations != current_motivations:
            explained = any(abs(item["chapter_number"] - state.at_chapter) <= 1 for item in turning_points)
            if not explained:
                diagnostics.append("Motivation changed, but no scene explains why.")
                break
        if current_motivations:
            previous_motivations = current_motivations

    pair_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in relationship_changes:
        pair_history[item["counterpart_name"]].append(item)
    for counterpart_name, items in pair_history.items():
        ordered = sorted(items, key=lambda row: row["chapter_number"])
        for previous, current in zip(ordered, ordered[1:]):
            previous_negative = (previous.get("sentiment") or 0) <= -0.35 or str(previous.get("type") or "").lower() in {"enemy", "rival", "hostile"}
            current_positive = (current.get("sentiment") or 0) >= 0.35 or str(current.get("type") or "").lower() in {"ally", "friend", "romantic", "family", "mentor"}
            if previous_negative and current_positive and (current["chapter_number"] - previous["chapter_number"]) <= 2:
                diagnostics.append(
                    f"Relationship with {counterpart_name} shifts from hostile to trusting too abruptly."
                )
                break
        if diagnostics and diagnostics[-1].endswith("too abruptly."):
            break

    if total_chapters and character.last_seen_chapter and total_chapters - character.last_seen_chapter >= 25:
        diagnostics.append(f"Character is absent for {total_chapters - character.last_seen_chapter} chapters after the latest appearance.")

    latest_description = _clean_tracker_text(character.description if hasattr(character, "description") else None)
    return {
        "goal": _clean_tracker_text(getattr(character, "goal", None)) or (character.motivations or [None])[0],
        "motivation": (character.motivations or [None])[0],
        "motivations": character.motivations or [],
        "fear": (character.fears or [None])[0],
        "fears": character.fears or [],
        "lie_they_believe": _clean_tracker_text(getattr(character, "lie_they_believe", None)),
        "wound_backstory": _clean_tracker_text(getattr(character, "backstory_wound", None)),
        "arc_type": _clean_tracker_text(getattr(character, "arc_type", None) or character.archetype),
        "first_appearance": character.first_chapter,
        "major_turning_points": turning_points,
        "relationship_changes": relationship_changes,
        "contradictions": contradictions,
        "voice_markers": voice_markers,
        "physical_description_history": physical_history,
        "arc_timeline": arc_timeline,
        "diagnostics": dedupe_preserve_order(diagnostics),
        "latest_arc_note": _clean_tracker_text(sorted_states[-1].arc_note) if sorted_states else character.arc_summary,
        "summary": _clean_tracker_text(character.arc_summary) or latest_description,
    }


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
