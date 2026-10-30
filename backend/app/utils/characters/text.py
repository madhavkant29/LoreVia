"""Text normalization helpers for character workflows."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import bleach  # type: ignore[import-untyped]

BLEACH_EMPTY_TAGS: Any = frozenset()


def split_text_for_token_budget(
    text: str,
    *,
    max_tokens: int,
    count_tokens: Callable[[str], int],
    overlap_chars: int = 150,
) -> list[str]:
    """Cover an oversized source with bounded, overlapping extraction passages."""
    return [
        text[start:end]
        for start, end in split_text_for_token_budget_ranges(
            text,
            max_tokens=max_tokens,
            count_tokens=count_tokens,
            overlap_chars=overlap_chars,
        )
    ]


def split_text_for_token_budget_ranges(
    text: str,
    *,
    max_tokens: int,
    count_tokens: Callable[[str], int],
    overlap_chars: int = 150,
) -> list[tuple[int, int]]:
    """Return exact source offsets for every overlapping extraction passage."""
    if max_tokens < 1 or overlap_chars < 0:
        raise ValueError("invalid_extraction_window")
    if not text:
        return []
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        if count_tokens(text[start:]) <= max_tokens:
            ranges.append((start, len(text)))
            break
        low, high = start + 1, len(text)
        end = start
        while low <= high:
            mid = (low + high) // 2
            if count_tokens(text[start:mid]) <= max_tokens:
                end = mid
                low = mid + 1
            else:
                high = mid - 1
        if end <= start:
            raise ValueError("extraction_window_cannot_fit_character")
        boundary = text.rfind(" ", start + (end - start) // 2, end)
        if boundary > start and count_tokens(text[start : boundary + 1]) <= max_tokens:
            end = boundary + 1
        ranges.append((start, end))
        start = end - min(overlap_chars, (end - start) // 4)
    return ranges


def extraction_source_coverage(
    chunks: Sequence[str],
    batches: Sequence[Sequence[str]],
    *,
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> dict[str, Any]:
    """Verify submitted passages cover every chunk and record their source offsets."""
    submitted = [
        (batch_index, passage)
        for batch_index, batch in enumerate(batches, start=1)
        for passage in batch
    ]
    ranges: list[dict[str, int]] = []
    submitted_index = 0
    chunk_metadata: list[dict[str, Any]] = []
    for chunk_index, chunk in enumerate(chunks):
        chunk_metadata.append(
            {
                "chunk_index": chunk_index,
                "length": len(chunk),
                "sha256": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
            }
        )
        previous_end = 0
        for start, end in split_text_for_token_budget_ranges(
            chunk, max_tokens=max_tokens, count_tokens=count_tokens
        ):
            if start > previous_end or submitted_index >= len(submitted):
                raise ValueError("character_extraction_source_coverage_incomplete")
            batch_index, submitted_text = submitted[submitted_index]
            if submitted_text != chunk[start:end]:
                raise ValueError("character_extraction_source_coverage_incomplete")
            ranges.append(
                {
                    "chunk_index": chunk_index,
                    "start": start,
                    "end": end,
                    "batch_index": batch_index,
                }
            )
            submitted_index += 1
            previous_end = end
        if chunk and previous_end != len(chunk):
            raise ValueError("character_extraction_source_coverage_incomplete")
    if submitted_index != len(submitted):
        raise ValueError("character_extraction_source_coverage_incomplete")
    return {
        "complete": True,
        "source_characters": sum(len(chunk) for chunk in chunks),
        "chunks": chunk_metadata,
        "ranges": ranges,
    }


def source_excerpt_around_name(text: str, name: str, *, max_chars: int = 2_200) -> str:
    """Preserve a candidate's mention instead of the unrelated start of a batch."""
    start, end = source_excerpt_range_around_name(text, name, max_chars=max_chars)
    return text[start:end]


def _source_name_mentions(text: str, name: str) -> list[re.Match[str]]:
    """Do not anchor a capitalized single-token name to ordinary lowercase words."""
    cleaned_name = name.strip()
    if not cleaned_name:
        return []
    requires_capitalized_source = len(cleaned_name.split()) == 1 and cleaned_name[0].isupper()
    pattern = re.compile(r"(?<!\w)" + re.escape(cleaned_name) + r"(?!\w)", flags=re.IGNORECASE)
    return [
        match
        for match in pattern.finditer(text)
        if not requires_capitalized_source or match.group(0)[0].isupper()
    ]


def source_mention_spans_in_batch(
    batch_text: str, names: Sequence[str], source_ranges: Sequence[dict[str, int]]
) -> list[dict[str, int]]:
    """Map exact name mentions in a joined batch back to original chunk offsets."""
    positions = {
        (match.start(), match.end())
        for name in names
        if isinstance(name, str) and name.strip()
        for match in _source_name_mentions(batch_text, name)
    }
    mapped: set[tuple[int, int, int]] = set()
    batch_start = 0
    for index, source_range in enumerate(source_ranges):
        source_length = source_range["end"] - source_range["start"]
        batch_end = batch_start + source_length
        for start, end in positions:
            if batch_start <= start < end <= batch_end:
                mapped.add(
                    (
                        source_range["chunk_index"],
                        source_range["start"] + start - batch_start,
                        source_range["start"] + end - batch_start,
                    )
                )
        batch_start = batch_end + (2 if index < len(source_ranges) - 1 else 0)
    return unique_source_mention_spans(
        [
            {"chunk_index": chunk_index, "start": start, "end": end}
            for chunk_index, start, end in sorted(mapped)
        ]
    )


def unique_source_mention_spans(
    spans: Sequence[Mapping[str, int]],
) -> list[dict[str, int]]:
    """Count one physical occurrence when a full name contains an alias mention."""
    ordered = sorted(
        spans,
        key=lambda span: (span["chunk_index"], span["start"], -span["end"]),
    )
    unique: list[dict[str, int]] = []
    for span in ordered:
        if unique and (
            unique[-1]["chunk_index"] == span["chunk_index"]
            and unique[-1]["start"] <= span["start"]
            and span["end"] <= unique[-1]["end"]
        ):
            continue
        unique.append(dict(span))
    return unique


def source_excerpt_range_around_name(
    text: str, name: str | Sequence[str], *, max_chars: int = 2_200
) -> tuple[int, int]:
    """Anchor a bounded evidence window to the first supported name or alias."""
    if max_chars < 1:
        raise ValueError("invalid_source_excerpt_size")
    if len(text) <= max_chars:
        return (0, len(text))
    names = [name] if isinstance(name, str) else name
    match = min(
        (
            mention
            for candidate in names
            if isinstance(candidate, str)
            for mention in _source_name_mentions(text, candidate)
        ),
        key=lambda mention: mention.start(),
        default=None,
    )
    if match is None:
        return (0, max_chars)
    start = min(max(0, match.start() - max_chars // 4), len(text) - max_chars)
    return (start, start + max_chars)


def source_excerpt_ranges_around_names(
    text: str, names: Sequence[str], *, max_chars: int = 2_200
) -> list[tuple[int, int]]:
    """Cover every distinct supported name mention with bounded source windows."""
    if max_chars < 1:
        raise ValueError("invalid_source_excerpt_size")
    if not text:
        return []
    cleaned_names = [name.strip() for name in names if isinstance(name, str) and name.strip()]
    if not cleaned_names:
        return []
    windows: list[tuple[int, int]] = []
    matches = sorted(
        (match for name in set(cleaned_names) for match in _source_name_mentions(text, name)),
        key=lambda match: (match.start(), -match.end()),
    )
    for match in matches:
        # A mention near a window's right edge needs its own trailing context;
        # otherwise the profile pass never sees what the person does next.
        if windows and match.end() <= windows[-1][1] - max(1, max_chars // 4):
            continue
        start = min(max(0, match.start() - max_chars // 3), max(0, len(text) - max_chars))
        end = min(len(text), start + max_chars)
        if windows and end <= windows[-1][1]:
            continue
        windows.append((start, end))
    return windows


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


def _clean_reason_codes(values: Sequence[object] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = str(raw or "").strip()
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned
