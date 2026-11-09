"""Conservative, source-exact first-person narrator identity evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


def _narrator_spoke_quote(text: str, quote_start: int, quote_end: int) -> bool:
    """Accept only dialogue explicitly attributed to the first-person narrator."""
    before = text[max(0, quote_start - 90) : quote_start]
    after = text[quote_end : quote_end + 60]
    quote_content = text[quote_start + 1 : quote_end - 1].rstrip()
    return bool(
        re.search(
            r"\bI\s+(?:said|replied|answered|explained)(?:\s+to\s+\w+)?\s*[:,]?\s*$"
            r"|\bI\s+told\s+[^.!?\n]{1,35}[:,]?\s*$",
            before,
            flags=re.IGNORECASE,
        )
        or (
            quote_content.endswith(",")
            and re.match(
                r"\s*I\s+(?:said|replied|answered|explained)\b",
                after,
                flags=re.IGNORECASE,
            )
        )
    )


def first_person_self_identification(
    text: str, name: str, *, allow_single_name: bool = False
) -> str | None:
    """Return a self-naming phrase in narration or narrator-attributed dialogue."""
    cleaned_name = " ".join(name.split())
    if not text or not cleaned_name or (len(cleaned_name.split()) < 2 and not allow_single_name):
        return None
    escaped_name = re.escape(cleaned_name)
    name_end = r"(?![\w'’]|\s+[A-Z][\w'’-]*)"
    patterns = (
        rf"\bI\s+(?:told|said|explained)\b[^.!?\n]{{0,80}}\bI\s+(?:am|was)\s+{escaped_name}{name_end}",
        rf"\bI\s+(?:am|was)\s+{escaped_name}{name_end}",
        rf"\b[Mm]y\s+name\s+(?:is|was)\s+{escaped_name}{name_end}",
        rf"\bI\s+(?:introduced|identified)\s+myself\s+as\s+{escaped_name}{name_end}",
        rf"\b[Mm]y\s+(?:pass|badge|identification|identity\s+card)\s+"
        rf"(?:identified|listed|named)\s+me\s+as\s+{escaped_name}{name_end}",
    )
    quoted_ranges = [
        (match.start(), match.end())
        for match in re.finditer(
            r"""["“][^"”]*["”]|‘[^’]*’|(?<!\w)'[^']*'(?!\w)""", text, flags=re.DOTALL
        )
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            enclosing_quote = next(
                (
                    (start, end)
                    for start, end in quoted_ranges
                    if start < match.end() and match.start() < end
                ),
                None,
            )
            if enclosing_quote is None:
                return match.group(0)
            quote_start, quote_end = enclosing_quote
            if (
                not text[quote_start + 1 : match.start()].isspace()
                and match.start() != quote_start + 1
            ):
                continue
            if not _narrator_spoke_quote(text, quote_start, quote_end):
                continue
            return match.group(0)
    return None


def first_person_addressed_name(
    text: str, name: str, *, allow_single_name: bool = False
) -> str | None:
    """Return a tentative direct-address clue followed by a narrator response.

    Being addressed is weaker than self-identification: the response might be
    from a bystander. Callers must not treat this as an explicit identity link.
    """
    cleaned_name = " ".join(name.split())
    if not text or not cleaned_name or (len(cleaned_name.split()) < 2 and not allow_single_name):
        return None
    name_pattern = re.escape(cleaned_name)
    for quote in re.finditer(
        r"""["“][^"”]*["”]|‘[^’]*’|(?<!\w)'[^']*'(?!\w)""", text, flags=re.DOTALL
    ):
        spoken = text[quote.start() + 1 : quote.end() - 1]
        address = re.search(
            rf"\b(?:you\b[^.!?\n]{{0,120}}?,\s*|(?:dear|hello|goodbye)\s+)"
            rf"{name_pattern}(?![\w'’]|\s+[A-Z][\w'’-]*)",
            spoken,
            flags=re.IGNORECASE,
        )
        if not address:
            continue
        response = text[quote.end() : quote.end() + 80]
        if re.match(
            r"\s*I\s+(?:thanked|replied|answered|nodded|said|asked|turned|looked)\b",
            response,
            flags=re.IGNORECASE,
        ):
            return spoken[address.start() : address.end()]
    return None


def explicit_first_person_narrators(
    text: str, characters: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """List known people who explicitly self-identify as the passage's narrator."""
    matches: list[Mapping[str, Any]] = []
    for character in characters:
        names = [character.get("name"), *(character.get("aliases") or [])]
        if any(
            first_person_self_identification(text, name, allow_single_name=True)
            for name in names
            if isinstance(name, str) and name.strip()
        ):
            matches.append(character)
    return matches


def detect_explicit_first_person_narrator(
    text: str, characters: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    """Resolve one known narrator only from an unambiguous first-person self-identification."""
    matches = explicit_first_person_narrators(text, characters)
    return matches[0] if len(matches) == 1 else None


def contextual_first_person_narrators(
    text: str, characters: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Find directly addressed narrators without promoting the clue to identity proof."""
    matches: list[Mapping[str, Any]] = []
    for character in characters:
        names = [character.get("name"), *(character.get("aliases") or [])]
        if any(
            first_person_addressed_name(text, name, allow_single_name=True)
            for name in names
            if isinstance(name, str) and name.strip()
        ):
            matches.append(character)
    return matches
