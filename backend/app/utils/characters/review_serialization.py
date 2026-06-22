"""Character review serialization and query workflows."""

from __future__ import annotations

import math
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDecisionEvent,
    CharacterDuplicateSuggestion,
    CharacterIdentityAction,
    CharacterRelationshipCandidate,
)
from app.utils.characters.candidates import build_candidate_dossier_summary
from app.utils.characters.constants import (
    CHARACTER_ADJUDICATION_OBJECT,
    CHARACTER_ADJUDICATION_ORGANIZATION,
    CHARACTER_ADJUDICATION_PLACE,
    CHARACTER_ADJUDICATION_QUARANTINED,
    CHARACTER_ADJUDICATION_REJECTED,
    CHARACTER_ADJUDICATION_TITLE_OR_ROLE,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_CANDIDATE_ACCEPTED,
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_CANDIDATE_PROMOTED,
    CHARACTER_CANDIDATE_REJECTED,
    CHARACTER_CANDIDATE_SUPPRESSED,
    CHARACTER_DUPLICATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED,
)
from app.utils.characters.governance import character_governance, is_cast_visible_character
from app.utils.characters.identity import normalize_character_name
from app.utils.characters.presentation import dedupe_preserve_order
from app.utils.characters.serialization import is_protected_character, serialize_character_detail
from app.utils.characters.text import _clean_reason_codes, clean_optional_text, clean_string_list
from app.utils.db_utils import run_read_with_retry


def _character_candidate_identity_key(
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    source_batch_key: str | None,
    normalized_name: str,
) -> tuple[str, int, str, str]:
    return (str(book_id), chapter_number, str(source_batch_key or ""), normalized_name)


def _clean_candidate_aliases(values: Sequence[object] | None, proposed_name: str) -> list[str]:
    normalized_proposed = normalize_character_name(proposed_name)
    aliases: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = clean_optional_text(str(raw or ""))
        if not item:
            continue
        normalized = normalize_character_name(item)
        if not normalized or normalized == normalized_proposed or normalized in seen:
            continue
        seen.add(normalized)
        aliases.append(item)
    return aliases


def _normalize_candidate_confidence(value: object | None) -> int:
    try:
        confidence = float(value or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0, min(100, int(round(confidence * 100 if confidence <= 1 else confidence))))


def serialize_character_candidate(candidate: CharacterCandidate) -> dict[str, Any]:
    normalized_evidence = _normalize_candidate_evidence(candidate)
    return {
        "id": str(candidate.id),
        "book_id": str(candidate.book_id),
        "chapter_id": str(candidate.chapter_id) if getattr(candidate, "chapter_id", None) else None,
        "scene_id": str(candidate.scene_id) if getattr(candidate, "scene_id", None) else None,
        "chapter_number": int(candidate.chapter_number or 0),
        "raw_name": candidate.raw_name,
        "proposed_name": candidate.proposed_name,
        "display_name": getattr(candidate, "display_name", None) or candidate.proposed_name,
        "normalized_name": candidate.normalized_name,
        "aliases": clean_string_list(candidate.aliases or []),
        "matched_character_id": str(candidate.matched_character_id)
        if candidate.matched_character_id
        else None,
        "status": candidate.status,
        "confidence": int(candidate.confidence or 0),
        "reason_codes": _clean_reason_codes(candidate.reason_codes or []),
        "evidence": normalized_evidence,
        "mention_count": getattr(candidate, "mention_count", None),
        "chapter_count": getattr(candidate, "chapter_count", None),
        "evidence_windows": list(getattr(candidate, "evidence_windows", None) or []),
        "entity_type": getattr(candidate, "entity_type", None),
        "adjudication_status": getattr(candidate, "adjudication_status", None),
        "character_score": getattr(candidate, "character_score", None),
        "rejection_reason": getattr(candidate, "rejection_reason", None),
        "cluster_names": _coerce_string_list(normalized_evidence.get("cluster_names")),
        "cluster_size": _coerce_int(normalized_evidence.get("cluster_size"), fallback=1),
        "cluster_mention_count": _coerce_int(normalized_evidence.get("cluster_mention_count")),
        "resolver_status": clean_optional_text(normalized_evidence.get("resolver_status")),
        "resolver_reasons": _coerce_string_list(normalized_evidence.get("resolver_reasons")),
        "canonical_confidence": _coerce_float(normalized_evidence.get("canonical_confidence")),
        "grounding_coverage": _coerce_float(normalized_evidence.get("grounding_coverage")),
        "dossier_summary": build_candidate_dossier_summary(candidate),
        "snippets": _coerce_string_list(normalized_evidence.get("snippets")),
        "source_batch_key": candidate.source_batch_key,
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


def serialize_character_duplicate_suggestion(
    suggestion: CharacterDuplicateSuggestion,
    *,
    primary: Character | None = None,
    secondary: Character | None = None,
) -> dict[str, Any]:
    shared_evidence = _normalize_duplicate_shared_evidence(
        suggestion,
        primary=primary,
        secondary=secondary,
    )
    return {
        "id": str(suggestion.id),
        "book_id": str(suggestion.book_id),
        "primary_character_id": str(suggestion.primary_character_id),
        "secondary_character_id": str(suggestion.secondary_character_id),
        "confidence": int(suggestion.confidence or 0),
        "reasons": _clean_reason_codes(suggestion.reasons or []),
        "shared_evidence": shared_evidence,
        "shared_cluster_keys": _coerce_string_list(shared_evidence.get("shared_cluster_keys")),
        "shared_chapters": [
            chapter
            for chapter in (
                _coerce_int(value, fallback=0)
                for value in cast(Sequence[object], shared_evidence.get("shared_chapters") or [])
            )
            if chapter > 0
        ],
        "embedding_similarity": _coerce_float(shared_evidence.get("embedding_similarity")),
        "primary_is_protected": bool(shared_evidence.get("primary_is_protected")),
        "secondary_is_protected": bool(shared_evidence.get("secondary_is_protected")),
        "primary_is_manual": bool(shared_evidence.get("primary_is_manual")),
        "secondary_is_manual": bool(shared_evidence.get("secondary_is_manual")),
        "primary_is_curated": bool(shared_evidence.get("primary_is_curated")),
        "secondary_is_curated": bool(shared_evidence.get("secondary_is_curated")),
        "status": suggestion.status,
        "dismissal_reason": getattr(suggestion, "dismissal_reason", None),
        "auto_dismissed": bool(getattr(suggestion, "auto_dismissed", False)),
        "created_at": suggestion.created_at,
        "updated_at": suggestion.updated_at,
    }


def serialize_character_relationship_candidate(
    candidate: CharacterRelationshipCandidate,
) -> dict[str, Any]:
    return {
        "id": str(candidate.id),
        "book_id": str(candidate.book_id),
        "chapter_number": int(candidate.chapter_number or 0),
        "raw_character_a": candidate.raw_character_a,
        "raw_character_b": candidate.raw_character_b,
        "matched_character_a_id": str(candidate.matched_character_a_id)
        if candidate.matched_character_a_id
        else None,
        "matched_character_b_id": str(candidate.matched_character_b_id)
        if candidate.matched_character_b_id
        else None,
        "rel_type": clean_optional_text(candidate.rel_type),
        "sentiment": candidate.sentiment,
        "description": clean_optional_text(candidate.description),
        "status": candidate.status,
        "reason_codes": _clean_reason_codes(candidate.reason_codes or []),
        "evidence": dict(candidate.evidence or {}),
        "source_batch_key": candidate.source_batch_key,
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


def serialize_character_decision_event(event: CharacterDecisionEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "book_id": str(event.book_id),
        "character_id": str(event.character_id),
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "action": event.action,
        "visibility_state": event.visibility_state,
        "approval_state": event.approval_state,
        "approval_source": event.approval_source,
        "reason_codes": _clean_reason_codes(event.reason_codes or []),
        "evidence": dict(event.evidence or {}),
        "created_at": event.created_at,
    }


def build_character_review_payload(
    candidates: Sequence[CharacterCandidate],
    duplicate_suggestions: Sequence[CharacterDuplicateSuggestion],
    relationship_candidates: Sequence[CharacterRelationshipCandidate] | None = None,
    *,
    character_map: Mapping[uuid.UUID, Character] | None = None,
    shadow_characters: Sequence[Character] | None = None,
    decision_events: Sequence[CharacterDecisionEvent] | None = None,
) -> dict[str, Any]:
    relationship_candidates = relationship_candidates or []
    serialized_candidates = [serialize_character_candidate(candidate) for candidate in candidates]
    visible_duplicate_suggestions = [
        suggestion
        for suggestion in duplicate_suggestions
        if str(suggestion.status or "") == CHARACTER_DUPLICATE_PENDING
        and int(suggestion.confidence or 0) >= 75
        and not bool(getattr(suggestion, "auto_dismissed", False))
    ]
    serialized_duplicates = [
        serialize_character_duplicate_suggestion(
            suggestion,
            primary=(character_map or {}).get(suggestion.primary_character_id),
            secondary=(character_map or {}).get(suggestion.secondary_character_id),
        )
        for suggestion in visible_duplicate_suggestions
    ]
    serialized_relationship_candidates = [
        serialize_character_relationship_candidate(candidate)
        for candidate in relationship_candidates
    ]
    serialized_shadow_characters = [
        serialize_character_detail(character) for character in shadow_characters or []
    ]
    serialized_decision_events = [
        serialize_character_decision_event(event) for event in decision_events or []
    ]
    return {
        "candidates": serialized_candidates,
        "duplicate_suggestions": serialized_duplicates,
        "relationship_candidates": serialized_relationship_candidates,
        "shadow_characters": serialized_shadow_characters,
        "decision_events": serialized_decision_events,
        "counts": {
            "pending_candidates": sum(
                1 for item in candidates if str(item.status or "") == CHARACTER_CANDIDATE_PENDING
            ),
            "pending_duplicate_suggestions": sum(
                1
                for item in visible_duplicate_suggestions
                if str(item.status or "") == CHARACTER_DUPLICATE_PENDING
            ),
            "pending_relationship_candidates": sum(
                1
                for item in relationship_candidates
                if str(item.status or "") == CHARACTER_RELATIONSHIP_CANDIDATE_PENDING
            ),
        },
        "auto_actions_summary": {},
    }


async def list_character_review_data(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    include_quarantined: bool = True,
    include_places: bool = False,
    include_rejected: bool = False,
) -> dict[str, Any]:
    return await run_read_with_retry(
        db,
        lambda: _list_character_review_data_once(
            db,
            book_id=book_id,
            include_quarantined=include_quarantined,
            include_places=include_places,
            include_rejected=include_rejected,
        ),
    )


async def _list_character_review_data_once(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    include_quarantined: bool,
    include_places: bool,
    include_rejected: bool,
) -> dict[str, Any]:
    candidate_statuses = {
        CHARACTER_CANDIDATE_PENDING,
        CHARACTER_CANDIDATE_ACCEPTED,
        CHARACTER_CANDIDATE_PROMOTED,
    }
    adjudication_statuses: set[str] = set()
    if include_quarantined:
        adjudication_statuses.add(CHARACTER_ADJUDICATION_QUARANTINED)
    if include_places:
        candidate_statuses.add(CHARACTER_CANDIDATE_SUPPRESSED)
        adjudication_statuses.update(
            {
                CHARACTER_ADJUDICATION_PLACE,
                CHARACTER_ADJUDICATION_ORGANIZATION,
                CHARACTER_ADJUDICATION_OBJECT,
                CHARACTER_ADJUDICATION_TITLE_OR_ROLE,
            }
        )
    if include_rejected:
        candidate_statuses.add(CHARACTER_CANDIDATE_REJECTED)
        adjudication_statuses.add(CHARACTER_ADJUDICATION_REJECTED)
    candidate_filters = [
        CharacterCandidate.book_id == book_id,
        CharacterCandidate.status.in_(tuple(sorted(candidate_statuses))),
    ]
    if adjudication_statuses:
        candidate_filters.append(
            CharacterCandidate.adjudication_status.in_(tuple(sorted(adjudication_statuses)))
            | CharacterCandidate.status.in_(
                (
                    CHARACTER_CANDIDATE_PENDING,
                    CHARACTER_CANDIDATE_ACCEPTED,
                    CHARACTER_CANDIDATE_PROMOTED,
                )
            )
        )
    candidates = (
        (
            await db.execute(
                select(CharacterCandidate)
                .where(*candidate_filters)
                .order_by(CharacterCandidate.chapter_number, CharacterCandidate.created_at)
            )
        )
        .scalars()
        .all()
    )
    duplicate_suggestions = (
        (
            await db.execute(
                select(CharacterDuplicateSuggestion)
                .where(
                    CharacterDuplicateSuggestion.book_id == book_id,
                    CharacterDuplicateSuggestion.status == CHARACTER_DUPLICATE_PENDING,
                    CharacterDuplicateSuggestion.confidence >= 75,
                )
                .order_by(
                    CharacterDuplicateSuggestion.confidence.desc(),
                    CharacterDuplicateSuggestion.created_at,
                )
            )
        )
        .scalars()
        .all()
    )
    relationship_candidates = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate)
                .where(
                    CharacterRelationshipCandidate.book_id == book_id,
                    CharacterRelationshipCandidate.status.in_(
                        (
                            CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
                            CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED,
                            CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED,
                        )
                    ),
                )
                .order_by(
                    CharacterRelationshipCandidate.chapter_number,
                    CharacterRelationshipCandidate.created_at,
                )
            )
        )
        .scalars()
        .all()
    )
    character_rows = (
        (
            await db.execute(
                select(Character)
                .options(selectinload(Character.alias_records))
                .where(Character.book_id == book_id)
            )
        )
        .scalars()
        .all()
    )
    character_map = {item.id: item for item in character_rows if item.id is not None}
    shadow_characters = [
        item
        for item in character_rows
        if item.id is not None
        and getattr(item, "merged_into_character_id", None) is None
        and not is_cast_visible_character(item)
        and character_governance(item)[1] == CHARACTER_APPROVAL_PENDING_REVIEW
    ]
    identity_actions = (
        (
            await db.execute(
                select(CharacterIdentityAction.action_type).where(
                    CharacterIdentityAction.book_id == book_id
                )
            )
        )
        .scalars()
        .all()
    )
    auto_actions_summary = dict(Counter(identity_actions))
    decision_events = (
        (
            await db.execute(
                select(CharacterDecisionEvent)
                .where(CharacterDecisionEvent.book_id == book_id)
                .order_by(CharacterDecisionEvent.created_at.desc())
                .limit(40)
            )
        )
        .scalars()
        .all()
    )
    payload = build_character_review_payload(
        candidates,
        duplicate_suggestions,
        relationship_candidates,
        character_map=character_map,
        shadow_characters=shadow_characters,
        decision_events=decision_events,
    )
    payload["auto_actions_summary"] = auto_actions_summary
    return payload


def _clean_text_list(values: Sequence[object] | None) -> list[str]:
    cleaned: list[str] = []
    for value in values or []:
        text = clean_optional_text(value)
        if text:
            cleaned.append(text)
    return dedupe_preserve_order(cleaned)


def _coerce_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return _clean_text_list([value])
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return _clean_text_list(list(value))
    return []


def _coerce_int(value: object, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_float(value: object) -> float | None:
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(coerced) or math.isinf(coerced):
        return None
    return coerced


def _extract_candidate_snippets(
    evidence: Mapping[str, Any], candidate: CharacterCandidate
) -> list[str]:
    snippets = _coerce_string_list(evidence.get("snippets"))
    snippets.extend(_coerce_string_list(evidence.get("mention_texts")))
    snippets.extend(_coerce_string_list(evidence.get("passages")))
    snippets.extend(_coerce_string_list(evidence.get("local_passages")))
    mention_text = clean_optional_text(evidence.get("mention_text"))
    if mention_text:
        snippets.append(mention_text)
    local_passage = clean_optional_text(evidence.get("local_passage"))
    if local_passage:
        snippets.append(local_passage)
    repair_source = evidence.get("repair_source")
    if isinstance(repair_source, Mapping):
        summary = (
            f"Existing character demoted from canonical roster. "
            f"Mentions: {_coerce_int(repair_source.get('mention_count'))}. "
            f"First chapter: {_coerce_int(repair_source.get('first_chapter'))}."
        )
        snippets.append(summary)
    if not snippets:
        snippets.append(
            f"{candidate.proposed_name} review candidate from chapter {int(candidate.chapter_number or 0)}."
        )
    return dedupe_preserve_order(snippets)[:6]


def _normalize_candidate_evidence(candidate: CharacterCandidate) -> dict[str, Any]:
    evidence = dict(candidate.evidence or {})
    cluster_names = _coerce_string_list(evidence.get("cluster_names"))
    if not cluster_names:
        cluster_names = _coerce_string_list(evidence.get("cluster_key"))
    if not cluster_names:
        cluster_names = _clean_text_list(
            [candidate.proposed_name, candidate.raw_name, *(candidate.aliases or [])]
        )
    cluster_size = max(
        1, _coerce_int(evidence.get("cluster_size"), fallback=len(cluster_names) or 1)
    )
    cluster_mention_count = max(
        0,
        _coerce_int(
            evidence.get("cluster_mention_count"),
            fallback=_coerce_int(
                evidence.get("mention_count"),
                fallback=_coerce_int(evidence.get("strong_mention_count"), fallback=0),
            ),
        ),
    )
    resolver_status = clean_optional_text(evidence.get("resolver_status")) or "needs_review"
    resolver_reasons = _coerce_string_list(evidence.get("resolver_reasons")) or _clean_reason_codes(
        candidate.reason_codes or []
    )
    canonical_confidence = _coerce_float(evidence.get("canonical_confidence"))
    if canonical_confidence is None:
        canonical_confidence = round(
            max(0.0, min(1.0, float(candidate.confidence or 0) / 100.0)), 2
        )
    grounding_coverage = _coerce_float(evidence.get("grounding_coverage"))
    if grounding_coverage is None:
        denominator = max(1, cluster_size)
        grounding_coverage = (
            round(min(1.0, cluster_mention_count / denominator), 2)
            if cluster_mention_count > 0
            else 0.0
        )
    snippets = _extract_candidate_snippets(evidence, candidate)
    normalized = dict(evidence)
    normalized.update(
        {
            "cluster_names": cluster_names,
            "cluster_size": cluster_size,
            "cluster_mention_count": cluster_mention_count,
            "resolver_status": resolver_status,
            "resolver_reasons": resolver_reasons,
            "canonical_confidence": canonical_confidence,
            "grounding_coverage": grounding_coverage,
            "snippets": snippets,
        }
    )
    return normalized


def _normalize_duplicate_shared_evidence(
    suggestion: CharacterDuplicateSuggestion,
    *,
    primary: Character | None = None,
    secondary: Character | None = None,
) -> dict[str, Any]:
    shared = dict(suggestion.shared_evidence or {})
    shared_cluster_keys = _coerce_string_list(shared.get("shared_cluster_keys"))
    shared_chapters = sorted(
        {
            chapter
            for chapter in (
                _coerce_int(value, fallback=0)
                for value in _coerce_string_list(shared.get("shared_chapters"))
            )
            if chapter > 0
        }
    )
    shared["shared_cluster_keys"] = shared_cluster_keys
    shared["shared_chapters"] = shared_chapters
    shared["embedding_similarity"] = _coerce_float(shared.get("embedding_similarity"))
    shared["primary_is_protected"] = bool(primary and is_protected_character(primary))
    shared["secondary_is_protected"] = bool(secondary and is_protected_character(secondary))
    shared["primary_is_manual"] = bool(primary and getattr(primary, "is_manual", False))
    shared["secondary_is_manual"] = bool(secondary and getattr(secondary, "is_manual", False))
    shared["primary_is_curated"] = bool(
        primary and bool((primary.analysis_metadata or {}).get("user_curated"))
    )
    shared["secondary_is_curated"] = bool(
        secondary and bool((secondary.analysis_metadata or {}).get("user_curated"))
    )
    return shared
