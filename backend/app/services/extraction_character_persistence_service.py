from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

from sqlalchemy import select

from app.engine.character.deduplicator import (
    character_name_keys,
    is_valid_alias,
    names_equivalent,
)
from app.engine.character.profile_builder import build_character_profile, update_profile
from app.models.character import Character, CharacterCandidate, CharacterMention, CharacterState
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
from app.utils.characters.governance import is_author_curated_character
from app.utils.characters.identity import (
    filter_character_identity_aliases,
    normalize_character_name,
)
from app.utils.characters.review import record_character_candidate
from app.utils.characters.text import unique_source_mention_spans


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
    previous_trait_state = deepcopy(char.trait_state or {})
    state_snapshot = _build_observed_state_snapshot(
        updated["trait_state"],
        entity.get("traits"),
    )
    changed = _changed(previous_trait_state, state_snapshot)
    prompt_delta = _diff(previous_trait_state, state_snapshot)
    _apply_character_update(char, updated)
    _refresh_character_key_cache(character_key_cache, char)
    pending_first_chapter_candidates[existing_id] = _first_chapter_lookup_candidates(
        char.name,
        updated.get("aliases") or char.aliases or [],
    )
    pending_first_chapter_updates[existing_id] = char
    if changed and not is_author_curated_character(char):
        growth_event = entity.get("growth_event")
        if isinstance(growth_event, dict):
            growth_event = {**growth_event, "chapter": chapter_number}
        db.add(
            CharacterState(
                character_id=existing_id,
                at_chapter=chapter_number,
                trait_snapshot=state_snapshot,
                observed_trait_keys=_observed_trait_keys(entity.get("traits")),
                motivations_snapshot=updated.get("motivations") or [],
                fears_snapshot=updated.get("fears") or [],
                prompt_delta=prompt_delta,
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
    if not is_author_curated_character(char):
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
    cross_chapter_ids = _entity_evidence(entity).get("cross_chapter_candidate_ids")
    if isinstance(cross_chapter_ids, list) and cross_chapter_ids:
        chapter_numbers = [
            number
            for number in (_entity_evidence(entity).get("shared_chapters") or [])
            if isinstance(number, int) and number > 0
        ]
        if chapter_numbers:
            profile["first_chapter"] = min(chapter_numbers)
            profile["last_seen_chapter"] = max(chapter_numbers)
    profile["normalized_name"] = normalize_character_name(str(profile.get("name") or "")) or None
    char = Character(**profile, embedding=embedding)
    db.add(char)
    await db.flush()
    baseline_snapshot = deepcopy(profile.get("trait_state") or {})
    db.add(
        CharacterState(
            character_id=char.id,
            at_chapter=profile["last_seen_chapter"],
            trait_snapshot=baseline_snapshot,
            observed_trait_keys=sorted(baseline_snapshot),
            motivations_snapshot=list(profile.get("motivations") or []),
            fears_snapshot=list(profile.get("fears") or []),
            prompt_delta=_diff({}, baseline_snapshot),
            arc_note=profile.get("arc_summary"),
            growth_event=(
                deepcopy(profile.get("growth_events")[0])
                if isinstance(profile.get("growth_events"), list)
                and profile.get("growth_events")
                and isinstance(profile.get("growth_events")[0], dict)
                else None
            ),
        )
    )
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


async def reconcile_cross_chapter_candidates(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    character_id: uuid.UUID,
) -> int:
    """Attach verified mentions from other chapters that justified promotion."""
    evidence = _entity_evidence(entity)
    raw_ids = evidence.get("cross_chapter_candidate_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return 0
    candidate_ids: list[uuid.UUID] = []
    for raw_id in raw_ids:
        try:
            candidate_ids.append(uuid.UUID(str(raw_id)))
        except (TypeError, ValueError):
            continue
    if not candidate_ids:
        return 0
    candidates = (
        (
            await db.execute(
                select(CharacterCandidate).where(
                    CharacterCandidate.id.in_(candidate_ids),
                    CharacterCandidate.book_id == book_id,
                    CharacterCandidate.status == "pending",
                    CharacterCandidate.matched_character_id.is_(None),
                    CharacterCandidate.chapter_number != chapter_number,
                    CharacterCandidate.normalized_name
                    == normalize_character_name(str(entity.get("name") or "")),
                )
            )
        )
        .scalars()
        .all()
    )
    candidates = [
        candidate
        for candidate in candidates
        if isinstance(candidate.evidence, dict)
        and candidate.evidence.get("source_mention_count_verified") is True
        and isinstance(candidate.evidence.get("mention_count"), int)
        and not isinstance(candidate.evidence.get("mention_count"), bool)
        and candidate.evidence["mention_count"] > 0
        and candidate.evidence.get("profile_enrichment_status") != "unanchored_reference"
        and not candidate.evidence.get("anti_merge_names")
        and candidate.evidence.get("resolver_status") not in {"ambiguous", "matched_needs_review"}
        and isinstance(candidate.evidence.get("verifier"), dict)
        and isinstance(candidate.evidence["verifier"].get("final"), dict)
        and candidate.evidence["verifier"]["final"].get("confidence_band") == "accept"
        and candidate.rejection_reason is None
        and candidate.entity_type in (None, "person", "alias_candidate")
        and not str(candidate.source_batch_key or "").startswith("manual-demote:")
        and not any(
            str(reason).startswith("author_") or "conflict" in str(reason)
            for reason in candidate.reason_codes or []
        )
    ]
    for candidate in candidates:
        candidate.status = "accepted"
        candidate.matched_character_id = character_id
        candidate.reason_codes = [
            *list(candidate.reason_codes or []),
            "cross_chapter_evidence_reconciled",
        ]
        if not candidate.source_batch_key:
            continue
        mentions = (
            (
                await db.execute(
                    select(CharacterMention).where(
                        CharacterMention.book_id == book_id,
                        CharacterMention.chapter_number == candidate.chapter_number,
                        CharacterMention.normalized_name == candidate.normalized_name,
                        CharacterMention.source_batch_key == candidate.source_batch_key,
                        CharacterMention.matched_character_id.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for mention in mentions:
            mention.matched_character_id = character_id
            mention.resolver_status = "matched_existing"
            mention.resolver_reasons = ["cross_chapter_evidence_reconciled"]
    return len(candidates)


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

    source_spans = [
        span
        for member in members
        for span in member.get("source_mentions") or []
        if isinstance(span, dict)
        and all(isinstance(span.get(key), int) for key in ("chunk_index", "start", "end"))
    ]
    unique_positions = {
        (span["chunk_index"], span["start"], span["end"])
        for span in unique_source_mention_spans(source_spans)
    }
    seen_source_mentions: set[tuple[int, int, int]] = set()
    for member in members:
        raw_name = " ".join(str(member.get("name") or "").split()).strip()
        normalized_name = normalize_character_name(raw_name)
        if not raw_name or not normalized_name:
            continue
        spans = {
            (span["chunk_index"], span["start"], span["end"])
            for span in member.get("source_mentions") or []
            if isinstance(span, dict)
            and all(isinstance(span.get(key), int) for key in ("chunk_index", "start", "end"))
        }
        new_spans = spans & unique_positions - seen_source_mentions
        if spans and not new_spans:
            continue
        seen_source_mentions.update(new_spans)
        member_evidence = (
            dict(member["evidence"]) if isinstance(member.get("evidence"), dict) else {}
        )
        if spans:
            member_evidence["mention_count"] = len(new_spans)
            member_evidence["strong_mention_count"] = min(
                int(member_evidence.get("strong_mention_count") or 0), len(new_spans)
            )
            member_evidence["source_mentions"] = [
                {"chunk_index": chunk_index, "start": start, "end": end}
                for chunk_index, start, end in sorted(new_spans)
            ]
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
            evidence=member_evidence,
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


def _build_observed_state_snapshot(
    merged_trait_state: dict[str, Any] | None,
    observed_traits: object,
) -> dict[str, Any]:
    snapshot = deepcopy(merged_trait_state or {})
    if not isinstance(observed_traits, dict):
        return snapshot
    for key, value in observed_traits.items():
        if isinstance(value, dict) and value.get("value") not in (None, ""):
            snapshot[key] = deepcopy(value)
    return snapshot


def _observed_trait_keys(observed_traits: object) -> list[str]:
    if not isinstance(observed_traits, dict):
        return []
    return sorted(
        str(key)
        for key, value in observed_traits.items()
        if isinstance(value, dict) and value.get("value") not in (None, "")
    )


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
        old_value = old.get(key) if isinstance(old.get(key), dict) else {}
        old_normalized = _normalized_trait_value(old_value.get("value"))
        new_normalized = _normalized_trait_value(value.get("value"))
        if new_normalized and new_normalized != old_normalized:
            return True
        old_conf = float(old_value.get("confidence") or 0)
        if float(value.get("confidence") or 0) - old_conf >= delta:
            return True
    return False


def _diff(old: dict, new: dict) -> str:
    changes = []
    for key, value in new.items():
        if not isinstance(value, dict):
            continue
        old_v = old.get(key, {}).get("value") if isinstance(old.get(key), dict) else None
        new_v = value.get("value")
        if old_v and new_v and _normalized_trait_value(old_v) != _normalized_trait_value(new_v):
            changes.append(f"{key}: {old_v}->{new_v}")
        elif not old_v and new_v:
            changes.append(f"+{key}: {new_v}")
    return "; ".join(changes[:5]) or "minor update"


def _normalized_trait_value(value: object) -> str:
    return " ".join(str(value or "").split()).strip().casefold()
