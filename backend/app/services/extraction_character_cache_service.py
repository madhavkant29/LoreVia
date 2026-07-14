from __future__ import annotations

import uuid

from app.engine.character.deduplicator import (
    character_name_keys,
    resolve_character_match_id,
    resolve_character_match_ids,
)
from app.models.character import Character


def _find_character_id_in_cache(
    chars: list[Character],
    name: str,
    aliases: list[str] | None,
    blocked_ids: set[uuid.UUID] | None = None,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> uuid.UUID | None:
    roster = [
        (char.id, char.name, char.aliases or [])
        for char in chars
        if not blocked_ids or char.id not in blocked_ids
    ]
    return resolve_character_match_id(name, aliases or [], roster, blocked_ids=blocked_ids)


def _find_character_ids_in_cache(
    chars: list[Character],
    name: str,
    aliases: list[str] | None,
    blocked_ids: set[uuid.UUID] | None = None,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> list[uuid.UUID]:
    roster = [
        (char.id, char.name, char.aliases or [])
        for char in chars
        if not blocked_ids or char.id not in blocked_ids
    ]
    return resolve_character_match_ids(name, aliases or [], roster, blocked_ids=blocked_ids)


def _find_character_in_cache(
    chars: list[Character],
    name: str,
    *,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> Character | None:
    match_id = _find_character_id_in_cache(chars, name, [], key_cache=key_cache)
    if not match_id:
        return None
    return next((char for char in chars if char.id == match_id), None)


def _find_character_by_id(chars: list[Character], character_id: uuid.UUID) -> Character | None:
    return next((char for char in chars if char.id == character_id), None)


def _character_keys_for_cache(
    char: Character,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> set[str]:
    if key_cache is not None and char.id in key_cache:
        return key_cache[char.id]
    keys = character_name_keys(char.name, char.aliases or [])
    if key_cache is not None and char.id is not None:
        key_cache[char.id] = keys
    return keys


def _refresh_character_key_cache(key_cache: dict[uuid.UUID, set[str]], char: Character) -> None:
    if char.id is None:
        return
    key_cache[char.id] = character_name_keys(char.name, char.aliases or [])
