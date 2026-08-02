"""Text normalization helpers for character workflows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import bleach  # type: ignore[import-untyped]

BLEACH_EMPTY_TAGS: Any = frozenset()


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
