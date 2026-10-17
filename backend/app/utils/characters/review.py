"""Focused character review workflows."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import object_session
from sqlalchemy.orm.exc import UnmappedInstanceError

from app.engine.character.profile_builder import (
    build_character_profile,
    merge_profile_fields,
)
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDecisionEvent,
    CharacterMention,
    CharacterRelationshipCandidate,
)
from app.utils.characters.constants import (
    CHARACTER_ADJUDICATION_MERGED_ALIAS,
    CHARACTER_ADJUDICATION_PLACE,
    CHARACTER_ADJUDICATION_PROMOTED_CHARACTER,
    CHARACTER_ADJUDICATION_REJECTED,
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_PROTECTED,
    CHARACTER_APPROVAL_REJECTED,
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
    CHARACTER_CANDIDATE_ACCEPTED,
    CHARACTER_CANDIDATE_MERGED,
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_CANDIDATE_PROMOTED,
    CHARACTER_CANDIDATE_REJECTED,
    CHARACTER_CANDIDATE_SUPPRESSED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_TRUST_TIER_REPAIRED_NOISE,
    CHARACTER_TRUST_TIER_REVIEW_ONLY,
    CHARACTER_TRUST_TIER_VISIBLE,
    CHARACTER_VISIBILITY_NOISE,
    CHARACTER_VISIBILITY_QUARANTINED,
    CHARACTER_VISIBILITY_VISIBLE,
)
from app.utils.characters.governance import (
    _clean_reason_code_values,
    character_governance,
    normalize_character_approval_source,
    normalize_character_approval_state,
    normalize_character_visibility_state,
)
from app.utils.characters.identity import (
    normalize_character_name,
)
from app.utils.characters.presentation import dedupe_preserve_order
from app.utils.characters.review_serialization import (
    _clean_candidate_aliases,
    _coerce_int,
    _normalize_candidate_confidence,
)
from app.utils.characters.text import _clean_reason_codes, clean_optional_text


async def record_character_candidate(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_id: uuid.UUID | None = None,
    scene_id: uuid.UUID | None = None,
    chapter_number: int,
    raw_name: str,
    proposed_name: str,
    aliases: Sequence[object] | None = None,
    matched_character_id: uuid.UUID | None = None,
    status: str = CHARACTER_CANDIDATE_PENDING,
    confidence: object | None = None,
    reason_codes: Sequence[object] | None = None,
    evidence: Mapping[str, Any] | None = None,
    source_batch_key: str | None = None,
) -> CharacterCandidate:
    from app.engine.character.adjudicator import adjudicate_character_candidate

    normalized_name = normalize_character_name(proposed_name)
    stmt = select(CharacterCandidate).where(
        CharacterCandidate.book_id == book_id,
        CharacterCandidate.chapter_number == chapter_number,
        CharacterCandidate.normalized_name == normalized_name,
        CharacterCandidate.source_batch_key == source_batch_key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    candidate = existing or CharacterCandidate(
        book_id=book_id,
        chapter_number=chapter_number,
        raw_name=raw_name,
        proposed_name=proposed_name,
        normalized_name=normalized_name,
        source_batch_key=source_batch_key,
    )
    candidate.raw_name = clean_optional_text(raw_name) or raw_name
    candidate.proposed_name = clean_optional_text(proposed_name) or proposed_name
    candidate.display_name = clean_optional_text(candidate.proposed_name) or candidate.proposed_name
    candidate.normalized_name = normalized_name
    candidate.chapter_id = chapter_id
    candidate.scene_id = scene_id
    candidate.aliases = _clean_candidate_aliases(aliases, candidate.proposed_name)
    candidate.matched_character_id = matched_character_id
    candidate.status = status
    candidate.confidence = _normalize_candidate_confidence(confidence)
    candidate.reason_codes = _clean_reason_codes(reason_codes)
    merged_evidence = dict(candidate.evidence or {})
    if evidence:
        merged_evidence.update(dict(evidence))
    adjudication = adjudicate_character_candidate(
        candidate.proposed_name,
        aliases=candidate.aliases or [],
        confidence=candidate.confidence,
        evidence=merged_evidence,
        reason_codes=candidate.reason_codes or [],
        matched_character_id=matched_character_id,
    )
    existing_adjudication = merged_evidence.get("adjudication")
    merged_evidence["adjudication"] = {
        **(dict(existing_adjudication) if isinstance(existing_adjudication, Mapping) else {}),
        "display_name": adjudication.display_name,
        "normalized_name": adjudication.normalized_name,
        "entity_type": adjudication.entity_type,
        "adjudication_status": adjudication.adjudication_status,
        "character_score": adjudication.character_score,
        "confidence": adjudication.confidence,
        "rejection_reason": adjudication.rejection_reason,
        "reason_codes": list(adjudication.reason_codes),
    }
    candidate.evidence = merged_evidence
    candidate.mention_count = _coerce_int(
        merged_evidence.get("mention_count"),
        fallback=_coerce_int(merged_evidence.get("cluster_mention_count")),
    )
    candidate.chapter_count = max(
        0,
        len(
            {
                _coerce_int(chapter, fallback=0)
                for chapter in cast(Sequence[object], merged_evidence.get("chapter_numbers") or [])
                if _coerce_int(chapter, fallback=0) > 0
            }
        ),
    )
    candidate.evidence_windows = list(adjudication.evidence_windows)
    candidate.entity_type = adjudication.entity_type
    candidate.adjudication_status = adjudication.adjudication_status
    candidate.character_score = adjudication.character_score
    candidate.rejection_reason = adjudication.rejection_reason
    candidate.source_batch_key = source_batch_key
    if existing is None:
        db.add(candidate)
    await db.flush()
    return candidate


async def record_relationship_candidate(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    raw_character_a: str,
    raw_character_b: str,
    matched_character_a_id: uuid.UUID | None = None,
    matched_character_b_id: uuid.UUID | None = None,
    rel_type: str | None = None,
    sentiment: float | None = None,
    description: str | None = None,
    status: str = CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    reason_codes: Sequence[object] | None = None,
    evidence: Mapping[str, Any] | None = None,
    source_batch_key: str | None = None,
) -> CharacterRelationshipCandidate:
    stmt = select(CharacterRelationshipCandidate).where(
        CharacterRelationshipCandidate.book_id == book_id,
        CharacterRelationshipCandidate.chapter_number == chapter_number,
        CharacterRelationshipCandidate.raw_character_a == raw_character_a,
        CharacterRelationshipCandidate.raw_character_b == raw_character_b,
        CharacterRelationshipCandidate.source_batch_key == source_batch_key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    candidate = existing or CharacterRelationshipCandidate(
        book_id=book_id,
        chapter_number=chapter_number,
        raw_character_a=raw_character_a,
        raw_character_b=raw_character_b,
        source_batch_key=source_batch_key,
    )
    candidate.raw_character_a = clean_optional_text(raw_character_a) or raw_character_a
    candidate.raw_character_b = clean_optional_text(raw_character_b) or raw_character_b
    candidate.matched_character_a_id = matched_character_a_id
    candidate.matched_character_b_id = matched_character_b_id
    candidate.rel_type = clean_optional_text(rel_type)
    candidate.sentiment = sentiment
    candidate.description = clean_optional_text(description)
    candidate.status = status
    candidate.reason_codes = _clean_reason_codes(reason_codes)
    merged_evidence = dict(candidate.evidence or {})
    if evidence:
        merged_evidence.update(dict(evidence))
    candidate.evidence = merged_evidence
    candidate.source_batch_key = source_batch_key
    if existing is None:
        db.add(candidate)
    await db.flush()
    return candidate


def append_character_review_audit_entry(
    character: Character,
    *,
    action: str,
    details: Mapping[str, Any] | None = None,
    actor_user_id: uuid.UUID | None = None,
    reason_codes: Sequence[object] | None = None,
) -> None:
    metadata = dict(character.analysis_metadata or {})
    entries = list(metadata.get("review_audit") or [])
    entries.append(
        {
            "action": action,
            "details": dict(details or {}),
        }
    )
    metadata["review_audit"] = entries[-12:]
    metadata["user_reviewed"] = True
    character.analysis_metadata = metadata
    try:
        session = object_session(character)
    except UnmappedInstanceError:
        session = None
    if session is not None and character.id is not None:
        visibility_state, approval_state, approval_source, _approval_reason_codes = (
            character_governance(character)
        )
        session.add(
            CharacterDecisionEvent(
                book_id=character.book_id,
                character_id=character.id,
                actor_user_id=actor_user_id,
                action=action,
                visibility_state=visibility_state,
                approval_state=approval_state,
                approval_source=approval_source,
                reason_codes=_clean_reason_code_values(reason_codes),
                evidence=dict(details or {}),
            )
        )


def set_character_review_state(
    character: Character,
    *,
    visibility_state: str,
    approval_state: str,
    approval_source: str | None,
    reason_codes: Sequence[object] | None = None,
    action: str | None = None,
    details: Mapping[str, Any] | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    normalized_visibility = (
        normalize_character_visibility_state(visibility_state) or CHARACTER_VISIBILITY_QUARANTINED
    )
    normalized_approval = (
        normalize_character_approval_state(approval_state) or CHARACTER_APPROVAL_PENDING_REVIEW
    )
    normalized_source = (
        normalize_character_approval_source(approval_source)
        or CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW
    )
    character.visibility_state = normalized_visibility
    character.approval_state = normalized_approval
    character.approval_source = normalized_source
    character.approval_reason_codes = _clean_reason_code_values(reason_codes)
    character.approval_updated_at = datetime.now(UTC)
    metadata = dict(character.analysis_metadata or {})
    metadata["user_reviewed"] = True
    metadata["trust_tier"] = (
        CHARACTER_TRUST_TIER_VISIBLE
        if normalized_visibility == CHARACTER_VISIBILITY_VISIBLE
        and normalized_approval in {CHARACTER_APPROVAL_APPROVED, CHARACTER_APPROVAL_PROTECTED}
        else CHARACTER_TRUST_TIER_REPAIRED_NOISE
        if normalized_visibility == CHARACTER_VISIBILITY_NOISE
        or normalized_approval == CHARACTER_APPROVAL_REJECTED
        else CHARACTER_TRUST_TIER_REVIEW_ONLY
    )
    metadata["trust_reasons"] = _clean_reason_code_values(reason_codes)
    character.analysis_metadata = metadata
    if action:
        append_character_review_audit_entry(
            character,
            action=action,
            details=details,
            actor_user_id=actor_user_id,
            reason_codes=reason_codes,
        )


def mark_character_curated(
    character: Character,
    *,
    protected_from_repair: bool | None = None,
    review_note: str | None = None,
) -> None:
    metadata = dict(character.analysis_metadata or {})
    metadata["user_curated"] = True
    metadata["user_reviewed"] = True
    if protected_from_repair is not None:
        metadata["protected_from_repair"] = bool(protected_from_repair)
    if review_note is not None:
        cleaned_note = clean_optional_text(review_note)
        if cleaned_note:
            metadata["review_note"] = cleaned_note
        else:
            metadata.pop("review_note", None)
    character.analysis_metadata = metadata
    set_character_review_state(
        character,
        visibility_state=CHARACTER_VISIBILITY_VISIBLE,
        approval_state=CHARACTER_APPROVAL_PROTECTED,
        approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
        reason_codes=["manual_or_curated"],
        action="character_curated",
        details={"protected_from_repair": bool(metadata.get("protected_from_repair"))},
    )


async def mark_character_candidates_merged(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    primary_character_id: uuid.UUID,
    secondary_character_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(CharacterCandidate).where(
            CharacterCandidate.book_id == book_id,
            CharacterCandidate.matched_character_id.in_(
                (primary_character_id, secondary_character_id)
            ),
        )
    )
    candidates = result.scalars().all()
    for candidate in candidates:
        candidate.generation_id = None
        candidate.matched_character_id = primary_character_id
        candidate.status = CHARACTER_CANDIDATE_MERGED
        candidate.adjudication_status = CHARACTER_ADJUDICATION_MERGED_ALIAS


def _candidate_entity_payload(candidate: CharacterCandidate) -> dict[str, Any]:
    evidence = dict(candidate.evidence or {})
    entity = evidence.get("entity") if isinstance(evidence.get("entity"), dict) else {}
    payload = dict(entity)
    payload["name"] = clean_optional_text(payload.get("name")) or candidate.proposed_name
    payload["aliases"] = (
        payload.get("aliases")
        if isinstance(payload.get("aliases"), list)
        else list(candidate.aliases or [])
    )
    payload["confidence"] = float(payload.get("confidence") or (candidate.confidence or 0) / 100)
    payload["evidence"] = evidence
    return payload


def _approve_character_from_review(
    character: Character,
    *,
    reason_codes: Sequence[object] | None = None,
    action: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    character.generation_id = None
    set_character_review_state(
        character,
        visibility_state=CHARACTER_VISIBILITY_VISIBLE,
        approval_state=CHARACTER_APPROVAL_APPROVED,
        approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
        reason_codes=reason_codes,
        action=action,
        details=details,
    )


def _quarantine_character_for_review(
    character: Character,
    *,
    reason_codes: Sequence[object] | None = None,
    action: str,
    details: Mapping[str, Any] | None = None,
    approval_source: str = CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
) -> None:
    character.generation_id = None
    set_character_review_state(
        character,
        visibility_state=CHARACTER_VISIBILITY_QUARANTINED,
        approval_state=CHARACTER_APPROVAL_PENDING_REVIEW,
        approval_source=approval_source,
        reason_codes=reason_codes,
        action=action,
        details=details,
    )


def reject_character_as_noise(
    character: Character,
    *,
    reason_codes: Sequence[object] | None = None,
    action: str,
    details: Mapping[str, Any] | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    character.generation_id = None
    set_character_review_state(
        character,
        visibility_state=CHARACTER_VISIBILITY_NOISE,
        approval_state=CHARACTER_APPROVAL_REJECTED,
        approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
        reason_codes=reason_codes,
        action=action,
        details=details,
        actor_user_id=actor_user_id,
    )


def reject_character_candidate(
    candidate: CharacterCandidate,
    *,
    reason_codes: Sequence[object] | None = None,
) -> None:
    candidate.generation_id = None
    candidate.status = CHARACTER_CANDIDATE_REJECTED
    candidate.adjudication_status = CHARACTER_ADJUDICATION_REJECTED
    candidate.entity_type = candidate.entity_type or "unknown"
    candidate.rejection_reason = "candidate_rejected"
    candidate.reason_codes = _clean_reason_codes(
        [
            *(candidate.reason_codes or []),
            *(reason_codes or []),
            "candidate_rejected",
        ]
    )


def mark_character_candidate_as_place(
    candidate: CharacterCandidate,
    *,
    reason_codes: Sequence[object] | None = None,
) -> None:
    candidate.generation_id = None
    candidate.status = CHARACTER_CANDIDATE_SUPPRESSED
    candidate.entity_type = "place"
    candidate.adjudication_status = CHARACTER_ADJUDICATION_PLACE
    candidate.rejection_reason = "author_marked_place"
    candidate.reason_codes = _clean_reason_codes(
        [
            *(candidate.reason_codes or []),
            *(reason_codes or []),
            "author_marked_place",
        ]
    )


async def promote_character_candidate(
    db: AsyncSession,
    *,
    candidate: CharacterCandidate,
) -> Character:
    candidate.generation_id = None
    entity = _candidate_entity_payload(candidate)
    if candidate.matched_character_id is not None:
        existing = await db.get(Character, candidate.matched_character_id)
        if existing is not None and existing.book_id == candidate.book_id:
            updated = merge_profile_fields(
                existing,
                {
                    **entity,
                    "first_chapter": min(
                        int(candidate.chapter_number or 1), int(existing.first_chapter or 1)
                    ),
                    "last_seen_chapter": max(
                        int(existing.last_seen_chapter or existing.first_chapter or 1),
                        int(candidate.chapter_number or 1),
                    ),
                },
            )
            for key, value in updated.items():
                setattr(existing, key, value)
            _approve_character_from_review(
                existing,
                reason_codes=["review_candidate_promoted", *list(candidate.reason_codes or [])],
                action="character_review_promoted",
                details={"candidate_id": str(candidate.id)},
            )
            candidate.status = CHARACTER_CANDIDATE_ACCEPTED
            candidate.adjudication_status = CHARACTER_ADJUDICATION_MERGED_ALIAS
            return existing

    character = Character(
        **build_character_profile(entity, candidate.book_id, int(candidate.chapter_number or 1))
    )
    db.add(character)
    await db.flush()
    _approve_character_from_review(
        character,
        reason_codes=["review_candidate_promoted", *list(candidate.reason_codes or [])],
        action="character_review_promoted",
        details={"candidate_id": str(candidate.id)},
    )
    candidate.matched_character_id = character.id
    candidate.status = CHARACTER_CANDIDATE_PROMOTED
    candidate.adjudication_status = CHARACTER_ADJUDICATION_PROMOTED_CHARACTER
    return character


async def attach_character_candidate(
    db: AsyncSession,
    *,
    candidate: CharacterCandidate,
    character: Character,
) -> Character:
    candidate.generation_id = None
    updated = merge_profile_fields(
        character,
        {
            **_candidate_entity_payload(candidate),
            "first_chapter": min(
                int(candidate.chapter_number or 1), int(character.first_chapter or 1)
            ),
            "last_seen_chapter": max(
                int(character.last_seen_chapter or character.first_chapter or 1),
                int(candidate.chapter_number or 1),
            ),
        },
    )
    for key, value in updated.items():
        setattr(character, key, value)
    candidate.matched_character_id = character.id
    candidate.status = CHARACTER_CANDIDATE_ACCEPTED
    candidate.adjudication_status = CHARACTER_ADJUDICATION_MERGED_ALIAS
    if (
        character.approval_state == CHARACTER_APPROVAL_PENDING_REVIEW
        or character.visibility_state != CHARACTER_VISIBILITY_VISIBLE
    ):
        _approve_character_from_review(
            character,
            reason_codes=["review_candidate_attached", *list(candidate.reason_codes or [])],
            action="character_review_attached",
            details={"candidate_id": str(candidate.id)},
        )
    else:
        append_character_review_audit_entry(
            character,
            action="character_candidate_attached",
            details={"candidate_id": str(candidate.id)},
            reason_codes=["review_candidate_attached", *list(candidate.reason_codes or [])],
        )
    return character


async def demote_character_to_review_candidate(
    db: AsyncSession,
    *,
    character: Character,
    reason_codes: Sequence[object] | None = None,
    review_note: str | None = None,
) -> CharacterCandidate:
    mention_rows = (
        (
            await db.execute(
                select(CharacterMention)
                .where(
                    CharacterMention.book_id == character.book_id,
                    CharacterMention.matched_character_id == character.id,
                )
                .order_by(CharacterMention.chapter_number, CharacterMention.created_at)
            )
        )
        .scalars()
        .all()
    )
    cluster_names = dedupe_preserve_order(
        [
            *[row.cluster_key for row in mention_rows if clean_optional_text(row.cluster_key)],
            character.name,
            *(character.aliases or []),
        ]
    )
    snippets = dedupe_preserve_order(
        [row.mention_text for row in mention_rows if clean_optional_text(row.mention_text)]
    )[:6]
    metadata = dict(character.analysis_metadata or {})
    _quarantine_character_for_review(
        character,
        reason_codes=["manual_demoted_for_review", *list(reason_codes or [])],
        action="character_demoted_for_review",
        details={"review_note": clean_optional_text(review_note)},
    )
    candidate = await record_character_candidate(
        db,
        book_id=character.book_id,
        chapter_number=int(character.first_chapter or 1),
        raw_name=character.name,
        proposed_name=character.name,
        aliases=character.aliases or [],
        matched_character_id=character.id,
        status=CHARACTER_CANDIDATE_PENDING,
        confidence=max(
            0, min(100, int(round(float(metadata.get("canonical_confidence") or 0) * 100)))
        ),
        reason_codes=["manual_demoted_for_review", *list(reason_codes or [])],
        evidence={
            "cluster_names": cluster_names,
            "cluster_size": max(1, int(metadata.get("cluster_size") or len(cluster_names) or 1)),
            "cluster_mention_count": max(
                0,
                int(
                    metadata.get("cluster_mention_count")
                    or character.mention_count
                    or len(mention_rows)
                ),
            ),
            "resolver_status": "manual_demoted_for_review",
            "resolver_reasons": [
                "manual_demoted_for_review",
                *[str(code).strip() for code in (reason_codes or []) if str(code).strip()],
            ],
            "canonical_confidence": metadata.get("canonical_confidence"),
            "grounding_coverage": metadata.get("grounding_coverage"),
            "snippets": snippets,
            "repair_source": {
                "character_id": str(character.id),
                "mention_count": int(character.mention_count or 0),
                "first_chapter": int(character.first_chapter or 0),
                "last_seen_chapter": int(character.last_seen_chapter or 0)
                if character.last_seen_chapter
                else None,
                "review_note": clean_optional_text(review_note),
            },
        },
        source_batch_key=f"manual-demote:{character.book_id}:{character.id}",
    )
    await db.flush()
    return candidate
