"""Bounded source windows and strict citation checks for relationship review."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from app.utils.characters.profile_evidence import source_quote_span
from app.utils.characters.relationship_evidence import relationship_quote_anchors_participants
from app.utils.characters.text import source_excerpt_ranges_around_names


def relationship_evidence_windows(
    source: str,
    left_names: Sequence[str],
    right_names: Sequence[str],
    *,
    preferred_quote: str | None = None,
    max_chars: int = 3_200,
    max_windows: int = 2,
) -> list[tuple[int, int, str]]:
    """Select at most two source passages that actually name both endpoints."""
    if max_chars < 1 or max_windows < 1:
        raise ValueError("invalid_relationship_evidence_window_limit")
    left = [name.strip() for name in left_names if isinstance(name, str) and name.strip()]
    right = [name.strip() for name in right_names if isinstance(name, str) and name.strip()]
    if not source or not left or not right:
        return []
    ranges = source_excerpt_ranges_around_names(source, [*left, *right], max_chars=max_chars)
    eligible = [
        (start, end)
        for start, end in ranges
        if any(
            relationship_quote_anchors_participants(source[start:end], a, b)
            for a in left
            for b in right
        )
    ]
    preferred_span = source_quote_span(source, preferred_quote) if preferred_quote else None
    if preferred_span is not None:
        eligible.sort(
            key=lambda window: (
                not (window[0] <= preferred_span[0] < preferred_span[1] <= window[1]),
                window[0],
            )
        )
    return [(start, end, source[start:end]) for start, end in eligible[:max_windows]]


def verified_relationship_evidence_proposal(
    raw_response: str,
    *,
    windows: Sequence[tuple[int, int, str]],
    left_name: str,
    right_name: str,
) -> dict[str, Any] | None:
    """Keep only an exact source quote; a proposal never establishes a tie."""
    try:
        payload = json.loads(raw_response)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("supported") is not True:
        return None
    label = str(payload.get("relationship_type") or "").strip().casefold()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,49}", label):
        return None
    quote = payload.get("quote")
    for start, _end, text in windows:
        span = source_quote_span(text, quote)
        if span is None:
            continue
        exact_quote = text[span[0] : span[1]]
        return {
            "relationship_type": label,
            "quote": exact_quote,
            "source_start": start + span[0],
            "source_end": start + span[1],
            "participants_anchored": relationship_quote_anchors_participants(
                exact_quote, left_name, right_name
            ),
        }
    return None
