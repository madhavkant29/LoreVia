from __future__ import annotations

import re

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
