from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

NAME_TITLES = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "sir",
    "lady",
    "lord",
    "prof",
    "professor",
    "capt",
    "captain",
    "commander",
    "master",
    "mistress",
}


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    tokens = [
        token
        for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name)
        if token.casefold() not in NAME_TITLES
    ]
    return " ".join(tokens).casefold().strip()


def name_tokens(name: str | None) -> list[str]:
    normalized = normalize_name(name)
    return normalized.split() if normalized else []


def is_single_token_name(name: str | None) -> bool:
    return len(name_tokens(name)) == 1


def first_name_token(name: str | None) -> str:
    tokens = name_tokens(name)
    return tokens[0] if tokens else ""


def assign_unique_active_normalized_names(characters: Iterable[Any]) -> None:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for character in characters:
        normalized = normalize_name(getattr(character, "name", None))
        if normalized:
            grouped[normalized].append(character)
        else:
            character.normalized_name = None

    for normalized, matches in grouped.items():
        ordered = sorted(
            matches,
            key=lambda item: (
                int(getattr(item, "mention_count", 0) or 0),
                -int(getattr(item, "first_chapter", 0) or 0),
                str(getattr(item, "id", "")),
            ),
            reverse=True,
        )
        for index, character in enumerate(ordered):
            character.normalized_name = normalized if index == 0 else None
