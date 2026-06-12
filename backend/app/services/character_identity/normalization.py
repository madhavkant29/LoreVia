from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

HONORIFIC_COMPARISON_FORMS = {
    "capt": "captain",
    "dr": "doctor",
    "mr": "mister",
    "mrs": "mrs",
    "prof": "professor",
}

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


def display_name_form(name: str | None) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"\s+", " ", str(name).strip())
    cleaned = re.sub(r"[\s.,;:!?]+$", "", cleaned)
    return cleaned


def normalized_comparison_name(name: str | None) -> str:
    display_name = display_name_form(name)
    if not display_name:
        return ""
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", display_name)
    normalized_tokens: list[str] = []
    for token in tokens:
        normalized = token.casefold().strip(".")
        normalized_tokens.append(HONORIFIC_COMPARISON_FORMS.get(normalized, normalized))
    return " ".join(normalized_tokens).strip()


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
