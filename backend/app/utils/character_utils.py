"""
Character utility helpers — shared across route modules.
Covers display filtering, status derivation, relationship summaries,
and text-sanitization helpers used on character data.
"""
from __future__ import annotations

import bleach  # type: ignore[import-untyped]

from app.engine.character.entity_filters import is_displayable_character_entity
from app.models.character import Character
from app.models.intelligence import CharacterRelationship

# ─── Display filter ───────────────────────────────────────────────────────────

def is_displayable_character(char: Character) -> bool:
    name = " ".join((char.name or "").split())
    if not name:
        return False
    return is_displayable_character_entity(
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

def clean_optional_text(value: str | None) -> str | None:
    cleaned = bleach.clean((value or "").strip(), tags=[], strip=True)
    return cleaned or None


def clean_string_list(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = bleach.clean((raw or "").strip(), tags=[], strip=True)
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


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
