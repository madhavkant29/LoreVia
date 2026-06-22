"""Focused character graph helpers."""

from __future__ import annotations

from typing import Any

from app.models.character import Character
from app.utils.characters.text import clean_optional_text

GRAPH_VISIBILITY_OVERRIDE_KEY = "graph_visibility_override"
GRAPH_VISIBILITY_OVERRIDE_VALUES = {"include", "exclude"}


def get_graph_visibility_override(character: Character) -> str | None:
    trait_state = getattr(character, "trait_state", None)
    return graph_visibility_override_value(trait_state if isinstance(trait_state, dict) else None)


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
