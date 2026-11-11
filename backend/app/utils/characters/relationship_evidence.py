"""Verify relationship citations against the submitted extraction passage."""

from __future__ import annotations

import re
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


def relationship_quote_anchors_participants(
    quote: object, character_a: object, character_b: object
) -> bool:
    """Require both named participants in a quote before saving an inferred tie."""
    text = str(quote or "")
    if not text.strip():
        return False
    return relationship_participant_name_distance(text, character_a, character_b) is not None


def _participant_name_spans(text: str, name: object) -> list[tuple[int, int]]:
    words = str(name or "").split()
    if not words:
        return []
    variants = [" ".join(words)]
    title_words = {
        "mr",
        "mrs",
        "ms",
        "miss",
        "mme",
        "madame",
        "monsieur",
        "dr",
        "doctor",
        "sir",
        "lady",
        "the",
        "old",
    }
    if len(words) > 1 and words[0].casefold() == "old":
        variants.append(words[-1])
    elif len(words) > 1 and words[0].casefold() not in title_words:
        variants.append(words[0])
    matches: list[tuple[int, int]] = []
    for variant in variants:
        joined = r"\s+".join(re.escape(part) for part in variant.split())
        pattern = rf"(?<!\w){joined}(?!\w)"
        matches.extend(
            (match.start(), match.end())
            for match in re.finditer(pattern, text, flags=re.IGNORECASE)
        )
    return matches


def relationship_participant_name_distance(
    text: str, character_a: object, character_b: object
) -> int | None:
    """Return the shortest gap between distinct named participants."""
    gaps = [
        max(right_start - left_end, left_start - right_end)
        for left_start, left_end in _participant_name_spans(text, character_a)
        for right_start, right_end in _participant_name_spans(text, character_b)
        if left_end <= right_start or right_end <= left_start
    ]
    return min(gaps) if gaps else None
