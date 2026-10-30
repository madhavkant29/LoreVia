"""Verify relationship citations against the submitted extraction passage."""

from __future__ import annotations

from typing import Any

from app.utils.characters.profile_evidence import source_quote_span


def grounded_relationship_evidence(
    relationship: dict[str, Any], source_text: str
) -> dict[str, Any] | None:
    """Return a source-backed citation, or None when a label lacks a real quote."""
    raw = relationship.get("label_evidence")
    if not isinstance(raw, dict):
        raw = relationship.get("evidence")
    if not isinstance(raw, dict):
        return None
    span = source_quote_span(source_text, raw.get("quote"))
    if span is None:
        return None
    return {
        **raw,
        "quote": source_text[span[0] : span[1]],
        "source_start": span[0],
        "source_end": span[1],
    }
