"""Focused character identity helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.utils.characters.constants import FAMILY_ROLE_WORDS, ROLE_ONLY_REFERENCE_WORDS
from app.utils.characters.text import clean_string_list

TITLE_IDENTITY_GROUPS = {
    "mr": "male",
    "master": "male",
    "sir": "male",
    "mrs": "female",
    "ms": "female",
    "miss": "female",
    "mistress": "female",
}


def family_role_reference(name: str | None) -> tuple[str | None, str | None]:
    normalized = normalize_character_name(name)
    if not normalized:
        return None, None
    for role in FAMILY_ROLE_WORDS:
        suffix = f" {role}"
        if normalized.endswith(suffix):
            anchor = normalized[: -len(suffix)].strip()
            anchor = re.sub(r"\bs\b$", "", anchor).strip()
            anchor = re.sub(r"\s+", " ", anchor)
            if anchor.endswith("'"):
                anchor = anchor[:-1]
            if anchor.endswith(" s"):
                anchor = anchor[:-2].strip()
            if anchor:
                return anchor, role
    return None, None


def normalize_character_name(name: str | None) -> str:
    if not name:
        return ""
    tokens = [
        token
        for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name)
        if token.casefold() not in NAME_TITLES
    ]
    return " ".join(tokens).casefold().strip()


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


def _leading_title(name: str | None) -> str:
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name or "")]
    return tokens[0] if tokens and tokens[0] in NAME_TITLES else ""


def partition_identity_key(name: str | None) -> str:
    normalized = normalize_character_name(name)
    if not normalized:
        return ""
    title = _leading_title(name)
    return f"{title}:{normalized}" if title else normalized


def has_conflicting_title_identity(name1: str | None, name2: str | None) -> bool:
    left_group = TITLE_IDENTITY_GROUPS.get(_leading_title(name1))
    right_group = TITLE_IDENTITY_GROUPS.get(_leading_title(name2))
    return bool(left_group and right_group and left_group != right_group)


def filter_character_identity_aliases(
    name: str | None, aliases: Sequence[object] | None
) -> list[str]:
    canonical_tokens = _name_tokens(name)
    if not canonical_tokens:
        return []

    filtered: list[str] = []
    for alias in clean_string_list([str(item) for item in aliases or []]):
        alias_tokens = _name_tokens(alias)
        if not alias_tokens or alias_tokens == canonical_tokens:
            continue
        if family_role_reference(alias)[1] or is_role_only_character_name(alias):
            continue
        if _leading_title(alias) and partition_identity_key(alias) != partition_identity_key(name):
            continue
        if len(alias_tokens) == 1:
            if len(canonical_tokens) < 2 or alias_tokens[0] != canonical_tokens[0]:
                continue
        elif set(alias_tokens) != set(canonical_tokens):
            continue
        filtered.append(alias)
    return filtered


def _name_tokens(name: str | None) -> list[str]:
    normalized = normalize_character_name(name)
    return normalized.split() if normalized else []


def has_shared_surname(name1: str | None, name2: str | None) -> bool:
    left_tokens = _name_tokens(name1)
    right_tokens = _name_tokens(name2)
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return False
    return left_tokens[-1] == right_tokens[-1]


def is_role_only_character_name(name: str | None) -> bool:
    normalized = normalize_character_name(name)
    if not normalized:
        return False
    if normalized in ROLE_ONLY_REFERENCE_WORDS:
        return True
    tokens = normalized.split()
    return bool(tokens and all(token in ROLE_ONLY_REFERENCE_WORDS for token in tokens))
