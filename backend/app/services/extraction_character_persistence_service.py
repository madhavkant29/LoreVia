from __future__ import annotations

import uuid
from typing import Any

from app.engine.character.deduplicator import (
    character_name_keys,
    is_valid_alias,
    names_equivalent,
)
from app.engine.character.profile_builder import build_character_profile, update_profile
from app.models.character import Character, CharacterState
from app.services.extraction_character_cache_service import (
    _character_keys_for_cache,
    _find_character_by_id,
    _refresh_character_key_cache,
)
from app.services.extraction_character_decision_service import (
    _candidate_record_evidence,
    _entity_dossier_summary,
    _entity_evidence,
)
from app.services.extraction_character_reporting_service import _first_chapter_lookup_candidates
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
    CHARACTER_VISIBILITY_VISIBLE,
)
from app.utils.characters.extraction import (
    build_character_mention_cluster_key,
    record_character_mention,
)
from app.utils.characters.identity import (
    filter_character_identity_aliases,
    normalize_character_name,
)
from app.utils.characters.review import record_character_candidate


async def _accept_existing_character_match(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    existing_id: uuid.UUID,
    existing_characters: list[Character],
    character_key_cache: dict[uuid.UUID, set[str]],
    pending_first_chapter_candidates: dict[uuid.UUID, list[str]],
    pending_first_chapter_updates: dict[uuid.UUID, Character],
    reason_code: str,
    source_batch_key: str | None,
) -> bool:
    char = _find_character_by_id(existing_characters, existing_id)
    if char is None:
        return False
    safe_aliases = filter_character_identity_aliases(
        char.name,
        [
            entity.get("name"),
            *(entity.get("aliases") if isinstance(entity.get("aliases"), list) else []),
        ],
    )
    updated = update_profile(
        char,
        {**entity, "name": char.name, "aliases": safe_aliases, "first_chapter": chapter_number},
    )
    changed = _changed(char.trait_state or {}, updated["trait_state"])
    _apply_character_update(char, updated)
    _refresh_character_key_cache(character_key_cache, char)
    pending_first_chapter_candidates[existing_id] = _first_chapter_lookup_candidates(
        char.name,
        updated.get("aliases") or char.aliases or [],
    )
    pending_first_chapter_updates[existing_id] = char
    if changed:
        growth_event = entity.get("growth_event")
        if isinstance(growth_event, dict):
            growth_event = {**growth_event, "chapter": chapter_number}
        db.add(
            CharacterState(
                character_id=existing_id,
                at_chapter=chapter_number,
                trait_snapshot=updated["trait_state"],
                motivations_snapshot=updated.get("motivations") or [],
                fears_snapshot=updated.get("fears") or [],
                prompt_delta=_diff(char.trait_state or {}, updated["trait_state"]),
                arc_note=entity.get("arc_summary"),
                growth_event=growth_event if isinstance(growth_event, dict) else None,
            )
        )
    await record_character_candidate(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        raw_name=str(entity.get("name") or ""),
        proposed_name=str(entity.get("name") or ""),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        matched_character_id=existing_id,
        status="accepted",
        confidence=entity.get("confidence"),
        reason_codes=[reason_code],
        evidence=_candidate_record_evidence(entity),
        source_batch_key=source_batch_key,
    )
    _merge_alias_in_memory(char, entity["name"] if char else None)
    return True


async def _promote_new_character_from_entity(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    embedding: list[float],
    existing_characters: list[Character],
    character_key_cache: dict[uuid.UUID, set[str]],
    pending_first_chapter_candidates: dict[uuid.UUID, list[str]],
    pending_first_chapter_updates: dict[uuid.UUID, Character],
    source_batch_key: str | None,
) -> Character:
    dossier_summary = _entity_dossier_summary(entity)
    entity["aliases"] = filter_character_identity_aliases(
        entity.get("name"),
        entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
    )
    entity["visibility_state"] = CHARACTER_VISIBILITY_VISIBLE
    entity["approval_state"] = CHARACTER_APPROVAL_APPROVED
    entity["approval_source"] = CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO
    entity["approval_reason_codes"] = [
        "deterministic_auto_promotion",
        *[
            str(reason).strip()
            for reason in (dossier_summary.get("summary_reason_codes") or [])
            if str(reason).strip()
        ],
    ]
    entity["dossier_summary"] = dossier_summary
    profile = build_character_profile(entity, book_id, chapter_number)
    profile["normalized_name"] = normalize_character_name(str(profile.get("name") or "")) or None
    char = Character(**profile, embedding=embedding)
    db.add(char)
    await db.flush()
    existing_characters.append(char)
    _refresh_character_key_cache(character_key_cache, char)
    await record_character_candidate(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        raw_name=str(entity.get("name") or ""),
        proposed_name=str(entity.get("name") or ""),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        matched_character_id=char.id,
        status="promoted",
        confidence=entity.get("confidence"),
        reason_codes=["new_character_promoted"],
        evidence=_candidate_record_evidence(entity),
        source_batch_key=source_batch_key,
    )
    pending_first_chapter_candidates[char.id] = _first_chapter_lookup_candidates(
        profile["name"],
        profile["aliases"],
    )
    pending_first_chapter_updates[char.id] = char
    return char


async def _record_entity_cluster_mentions(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    matched_character_id: uuid.UUID | None,
    resolver_status: str,
    resolver_reasons: list[str],
) -> None:
    cluster_key = build_character_mention_cluster_key(
        str(entity.get("name") or ""),
        entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
    )
    members = (
        entity.get("cluster_members") if isinstance(entity.get("cluster_members"), list) else []
    )
    if not members:
        members = [
            {
                "name": entity.get("name"),
                "aliases": entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
                "source_batch_key": entity.get("_source_batch_key"),
                "source_text": entity.get("_source_text"),
                "evidence": _entity_evidence(entity),
            }
        ]

    for member in members:
        raw_name = " ".join(str(member.get("name") or "").split()).strip()
        normalized_name = normalize_character_name(raw_name)
        if not raw_name or not normalized_name:
            continue
        await record_character_mention(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            raw_name=raw_name,
            normalized_name=normalized_name,
            source_batch_key=str(member.get("source_batch_key") or "") or None,
            cluster_key=cluster_key or normalized_name,
            mention_text=str(member.get("source_text") or "")[:1800] or None,
            matched_character_id=matched_character_id,
            resolver_status=resolver_status,
            resolver_reasons=resolver_reasons,
            evidence=member.get("evidence") if isinstance(member.get("evidence"), dict) else {},
        )


async def _record_cluster_member_candidates(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    matched_character_id: uuid.UUID | None,
    reason_code: str,
    status: str = "accepted",
) -> None:
    members = (
        entity.get("cluster_members") if isinstance(entity.get("cluster_members"), list) else []
    )
    if not members:
        return

    primary_name = normalize_character_name(str(entity.get("name") or ""))
    seen: set[tuple[str, str | None]] = set()
    for member in members:
        raw_name = " ".join(str(member.get("name") or "").split()).strip()
        normalized_name = normalize_character_name(raw_name)
        source_batch_key = str(member.get("source_batch_key") or "") or None
        if not raw_name or not normalized_name:
            continue
        if normalized_name == primary_name:
            continue
        dedupe_key = (normalized_name, source_batch_key)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        await record_character_candidate(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            raw_name=raw_name,
            proposed_name=raw_name,
            aliases=member.get("aliases") if isinstance(member.get("aliases"), list) else [],
            matched_character_id=matched_character_id,
            status=status,
            confidence=entity.get("confidence"),
            reason_codes=[reason_code],
            evidence={
                **(member.get("evidence") if isinstance(member.get("evidence"), dict) else {}),
                "entity": {
                    "name": raw_name,
                    "canonical_name": entity.get("name"),
                    "aliases": member.get("aliases")
                    if isinstance(member.get("aliases"), list)
                    else [],
                    "confidence": entity.get("confidence"),
                },
            },
            source_batch_key=source_batch_key,
        )


def _blocked_character_ids(
    chars: list[Character],
    entity: dict,
    *,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> set[uuid.UUID]:
    blocked_ids: set[uuid.UUID] = set()
    blocked_names = [
        name
        for name in (entity.get("anti_merge_names") or [])
        if isinstance(name, str) and name.strip()
    ]
    if not blocked_names:
        return blocked_ids

    for blocked_name in blocked_names:
        blocked_keys = character_name_keys(blocked_name, [])
        for char in chars:
            char_keys = _character_keys_for_cache(char, key_cache)
            if blocked_keys & char_keys:
                blocked_ids.add(char.id)
                continue
            if names_equivalent(blocked_name, [], char.name, char.aliases or []):
                blocked_ids.add(char.id)
    return blocked_ids


def _apply_character_update(char: Character, updated: dict[str, Any]) -> None:
    for key, value in updated.items():
        setattr(char, key, value)


def _merge_alias_in_memory(char: Character | None, alias: str | None) -> None:
    if char is None or not is_valid_alias(alias):
        return
    safe_aliases = filter_character_identity_aliases(char.name, [alias])
    if not safe_aliases:
        return
    cleaned_alias = safe_aliases[0]
    if not cleaned_alias or cleaned_alias.casefold() == str(char.name or "").strip().casefold():
        return
    aliases = list(char.aliases or [])
    if any(existing.casefold() == cleaned_alias.casefold() for existing in aliases):
        return
    char.aliases = [*aliases, cleaned_alias]


def _changed(old: dict, new: dict, delta: float = 0.15) -> bool:
    for key, value in new.items():
        if not isinstance(value, dict):
            continue
        old_conf = old.get(key, {}).get("confidence", 0) if isinstance(old.get(key), dict) else 0
        if value.get("confidence", 0) - old_conf >= delta:
            return True
    return False


def _diff(old: dict, new: dict) -> str:
    changes = []
    for key, value in new.items():
        if not isinstance(value, dict):
            continue
        old_v = old.get(key, {}).get("value") if isinstance(old.get(key), dict) else None
        new_v = value.get("value")
        if old_v and new_v and old_v != new_v:
            changes.append(f"{key}: {old_v}->{new_v}")
        elif not old_v and new_v:
            changes.append(f"+{key}: {new_v}")
    return "; ".join(changes[:5]) or "minor update"
