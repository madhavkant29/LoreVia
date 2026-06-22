"""
Index number formatting for chapters, scenes, and other story units.

Provides a single function to convert an integer index (1, 2, 3 …) into
various display formats: Arabic numerals, Roman numerals (upper/lower),
or alphabetic sequences (upper/lower).
"""

from __future__ import annotations

import re

# Supported format identifiers
INDEX_FORMATS = frozenset({"arabic", "roman-upper", "roman-lower", "alpha-upper", "alpha-lower"})

# ── Roman numeral conversion ────────────────────────────────────────────────

_ROMAN_MAP: list[tuple[int, str]] = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def _to_roman(n: int) -> str:
    if n < 1 or n > 3999:
        return str(n)
    result: list[str] = []
    remaining = n
    for value, numeral in _ROMAN_MAP:
        while remaining >= value:
            result.append(numeral)
            remaining -= value
    return "".join(result)


# ── Alphabetic conversion ───────────────────────────────────────────────────


def _to_alpha(n: int) -> str:
    """Convert 1 → a, 2 → b, … 26 → z, 27 → aa, 28 → ab, etc."""
    if n < 1:
        return str(n)
    result: list[str] = []
    remaining = n
    while remaining > 0:
        remaining -= 1
        result.append(chr(ord("a") + (remaining % 26)))
        remaining //= 26
    return "".join(reversed(result))


# ── Public API ──────────────────────────────────────────────────────────────


def format_index(n: int, fmt: str = "arabic") -> str:
    """Format an integer index into the chosen style.

    Args:
        n: The chapter/scene number (1-based).
        fmt: One of ``INDEX_FORMATS``: ``"arabic"`` (default),
            ``"roman-upper"``, ``"roman-lower"``, ``"alpha-upper"``,
            ``"alpha-lower"``.

    Returns:
        Formatted string such as ``"3"``, ``"III"``, ``"iii"``, ``"C"``, ``"c"``.

    Raises:
        ValueError: if *fmt* is not recognised.
    """
    if fmt == "arabic":
        return str(n)
    if fmt == "roman-upper":
        return _to_roman(n)
    if fmt == "roman-lower":
        return _to_roman(n).lower()
    if fmt == "alpha-upper":
        return _to_alpha(n).upper()
    if fmt == "alpha-lower":
        return _to_alpha(n)
    msg = f"Unknown index format: {fmt!r}. Choose from {sorted(INDEX_FORMATS)}."
    raise ValueError(msg)
