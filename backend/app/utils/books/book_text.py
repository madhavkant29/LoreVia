"""
Book utility helpers ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import bleach  # type: ignore[import-untyped]

if TYPE_CHECKING:
    pass


BLEACH_EMPTY_TAGS: Any = frozenset()


def _normalize_unicode_replacements(text: str) -> str:
    """
    Replace Unicode replacement characters and common encoding artifacts with
    appropriate ASCII/Unicode equivalents to prevent black squares in exports.
    """
    if not text:
        return text

    replacements = {
        "\ufffd": "",  # Unicode replacement character (black diamond/square)
        "\u25a0": "",  # Black square
        "\u25aa": "",  # Black small square
        "\u2022": "*",  # Bullet ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ asterisk
        "\u2013": "-",  # En dash
        "\u2014": "--",  # Em dash
        "\u2018": "'",  # Left single quote
        "\u2019": "'",  # Right single quote / apostrophe
        "\u201c": '"',  # Left double quote
        "\u201d": '"',  # Right double quote
        "\u2026": "...",  # Ellipsis
        "\u00a0": " ",  # Non-breaking space
        "\ufb00": "ff",  # Latin ligature ff
        "\ufb01": "fi",  # Latin ligature fi
        "\ufb02": "fl",  # Latin ligature fl
        "\ufb03": "ffi",  # Latin ligature ffi
        "\ufb04": "ffl",  # Latin ligature ffl
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


def _clean_optional_text(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None
