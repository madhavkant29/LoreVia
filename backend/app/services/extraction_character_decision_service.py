from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.engine.character.entity_filters import (
    CharacterPersistenceDecision,
    character_persistence_decision,
    entity_words,
)
from app.models.character import CharacterCandidate
from app.models.operations import AiQualityEvent
from app.services.character_identity.classification import CandidateKind, classify_candidate_kind
from app.utils.characters.candidates import (
    can_auto_persist_character_candidate,
    decide_character_candidate_disposition,
)
from app.utils.characters.identity import is_role_only_character_name, normalize_character_name
from app.utils.characters.presentation import build_character_dossier_summary
from app.utils.characters.profile_evidence import profile_claim_records
from app.utils.characters.review import record_character_candidate

AUTO_SAVE_CONFIDENCE = 0.78
MIN_EXISTING_UPDATE_CONFIDENCE = 0.55


async def load_author_review_holds(
    db, *, book_id: uuid.UUID, chapter_number: int | None
) -> dict[str, str]:
    """Find names the author rejected, marked as places, or demoted for review."""
    filters = [
        CharacterCandidate.book_id == book_id,
        CharacterCandidate.status.in_(("pending", "suppressed", "rejected")),
    ]
    if chapter_number is not None:
        filters.append(CharacterCandidate.chapter_number == chapter_number)
    candidates = (await db.execute(select(CharacterCandidate).where(*filters))).scalars().all()
    rejected_ids = [str(candidate.id) for candidate in candidates if candidate.status == "rejected"]
    historical_rejections = (
        set(
            (
                await db.scalars(
                    select(AiQualityEvent.entity_id).where(
                        AiQualityEvent.book_id == book_id,
                        AiQualityEvent.entity_type == "character_candidate",
                        AiQualityEvent.entity_id.in_(rejected_ids),
                        AiQualityEvent.actor_user_id.is_not(None),
                        AiQualityEvent.outcome == "rejected",
                    )
                )
            ).all()
        )
        if rejected_ids
        else set()
    )
    holds: dict[str, str] = {}
    for candidate in candidates:
        name = normalize_character_name(candidate.proposed_name)
        if not name:
            continue
        if candidate.rejection_reason == "author_marked_place":
            holds[name] = "author_marked_place"
        elif str(candidate.source_batch_key or "").startswith("manual-demote:"):
            holds[name] = "manual_demoted_for_review"
        elif candidate.status == "rejected" and (
            "author_rejected_candidate" in (candidate.reason_codes or [])
            or str(candidate.id) in historical_rejections
        ):
            holds[name] = "author_rejected_candidate"
    return holds


def _entity_evidence(entity: dict) -> dict:
    evidence = entity.get("evidence")
    return evidence if isinstance(evidence, dict) else {}


def _entity_dossier_summary(entity: dict) -> dict[str, Any]:
    evidence = _entity_evidence(entity)
    verifier = evidence.get("verifier") if isinstance(evidence.get("verifier"), dict) else {}
    final = (
        verifier.get("final")
        if isinstance(verifier, dict) and isinstance(verifier.get("final"), dict)
        else {}
    )
    return build_character_dossier_summary(
        name=entity.get("name"),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        evidence=evidence,
        reason_codes=[
            *(final.get("reasons") if isinstance(final.get("reasons"), list) else []),
            *(
                evidence.get("resolver_reasons")
                if isinstance(evidence.get("resolver_reasons"), list)
                else []
            ),
        ],
    )


def _candidate_record_evidence(entity: dict) -> dict[str, Any]:
    evidence = dict(_entity_evidence(entity))
    evidence["dossier_summary"] = _entity_dossier_summary(entity)
    evidence["entity"] = {
        "name": entity.get("name"),
        "canonical_name": entity.get("canonical_name"),
        "aliases": entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        "role": entity.get("role"),
        "traits": entity.get("traits") if isinstance(entity.get("traits"), dict) else {},
        "personality_tags": entity.get("personality_tags")
        if isinstance(entity.get("personality_tags"), list)
        else [],
        "motivations": entity.get("motivations")
        if isinstance(entity.get("motivations"), list)
        else [],
        "fears": entity.get("fears") if isinstance(entity.get("fears"), list) else [],
        "goal": entity.get("goal"),
        "lie_they_believe": entity.get("lie_they_believe"),
        "backstory_wound": entity.get("backstory_wound"),
        "arc_type": entity.get("arc_type"),
        "arc_summary": entity.get("arc_summary"),
        "archetype": entity.get("archetype"),
        "growth_event": entity.get("growth_event")
        if isinstance(entity.get("growth_event"), dict)
        else None,
        "confidence": entity.get("confidence"),
    }
    return evidence


async def _record_character_disposition_candidate(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    matched_character_id: uuid.UUID | None,
    reason_codes: list[str],
    source_batch_key: str | None,
) -> tuple[str, list[str], dict[str, Any]]:
    evidence = _candidate_record_evidence(entity)
    disposition = decide_character_candidate_disposition(
        name=str(entity.get("name") or ""),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        confidence=entity.get("confidence"),
        reason_codes=reason_codes,
        evidence=evidence,
        matched_character_id=matched_character_id,
    )
    await record_character_candidate(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        raw_name=str(entity.get("name") or ""),
        proposed_name=str(entity.get("name") or ""),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        matched_character_id=matched_character_id,
        status=disposition.status,
        confidence=entity.get("confidence"),
        reason_codes=disposition.reason_codes,
        evidence=disposition.evidence,
        source_batch_key=source_batch_key,
    )
    return disposition.status, list(disposition.reason_codes), disposition.evidence


def _entity_verifier_summary(entity: dict) -> dict[str, Any]:
    evidence = _entity_evidence(entity)
    verifier = evidence.get("verifier") if isinstance(evidence.get("verifier"), dict) else {}
    final = verifier.get("final") if isinstance(verifier, dict) else {}
    return final if isinstance(final, dict) else {}


def _entity_verifier_band(entity: dict) -> str | None:
    final = _entity_verifier_summary(entity)
    band = str(final.get("confidence_band") or "").strip()
    return band or None


def _should_update_existing_character(entity: dict) -> bool:
    verifier_band = _entity_verifier_band(entity)
    if verifier_band == "reject":
        return False
    if verifier_band == "review":
        return False
    dossier_summary = _entity_dossier_summary(entity)
    if dossier_summary.get("resolver_ambiguity_count") or dossier_summary.get(
        "conflict_signal_count"
    ):
        return False
    if verifier_band == "accept":
        return bool(
            dossier_summary.get("strict_auto_eligible")
            or (
                not dossier_summary.get("single_token")
                and dossier_summary.get("person_ner_support", 0) >= 1
                and (
                    _entity_evidence(entity).get("has_dialogue_or_action")
                    or _has_character_profile_signal(entity)
                )
            )
        )
    confidence = float(entity.get("confidence") or 0.0)
    if confidence >= AUTO_SAVE_CONFIDENCE:
        return True
    evidence = _entity_evidence(entity)
    return bool(
        confidence >= MIN_EXISTING_UPDATE_CONFIDENCE
        and (
            evidence.get("has_dialogue_or_action")
            or evidence.get("has_physical_description")
            or evidence.get("appears_multiple_times")
            or _has_character_profile_signal(entity)
        )
    )


def _can_update_exact_existing_profile(entity: dict, existing_name: str) -> bool:
    """Allow cited profile evidence for a unique exact full-name roster match."""
    name = str(entity.get("name") or "")
    normalized_name = normalize_character_name(name)
    if (
        len(entity_words(name)) < 2
        or normalized_name != normalize_character_name(existing_name)
        or is_role_only_character_name(name)
        or classify_candidate_kind(name) == CandidateKind.TITLE_NAME
        or _entity_verifier_band(entity) != "accept"
        or float(entity.get("confidence") or 0) < MIN_EXISTING_UPDATE_CONFIDENCE
    ):
        return False
    evidence = _entity_evidence(entity)
    if (
        evidence.get("profile_enrichment_status") != "complete"
        or evidence.get("source_mention_count_verified") is not True
        or int(evidence.get("mention_count") or 0) < 1
        or evidence.get("ambiguous_full_name_fragment") is True
        or entity.get("anti_merge_names")
    ):
        return False
    if any(
        normalize_character_name(str(candidate)) != normalized_name
        for candidate in [*(entity.get("aliases") or []), *(evidence.get("cluster_names") or [])]
    ):
        return False
    dossier = _entity_dossier_summary(entity)
    return bool(
        not dossier.get("resolver_ambiguity_count")
        and not dossier.get("conflict_signal_count")
        and not dossier.get("non_person_signal_count")
        and profile_claim_records(entity)
    )


def _has_character_profile_signal(entity: dict) -> bool:
    traits = entity.get("traits")
    if isinstance(traits, dict) and any(
        isinstance(value, dict) and str(value.get("value") or "").strip()
        for value in traits.values()
    ):
        return True
    if any(
        str(entity.get(field) or "").strip()
        for field in ("goal", "lie_they_believe", "backstory_wound", "arc_type", "archetype")
    ):
        return True
    if any(entity.get(field) for field in ("personality_tags", "motivations", "fears")):
        return True
    arc_summary = str(entity.get("arc_summary") or "").strip().casefold()
    if arc_summary and arc_summary not in {
        "appearance not yet described",
        "background character",
        "is a character",
        "mysterious figure",
        "normal character",
        "plain character",
        "supporting character",
        "this character is a character",
        "protagonist",
        "antagonist",
        "puppet master",
        "tragic figure",
        "unknown character",
    }:
        return True
    growth_event = entity.get("growth_event")
    return isinstance(growth_event, dict) and bool(str(growth_event.get("event") or "").strip())


def _entity_requires_manual_review(entity: dict) -> str | None:
    verifier_band = _entity_verifier_band(entity)
    if verifier_band == "review":
        return "mention_verifier_review"
    if verifier_band == "reject":
        return "mention_verifier_rejected"
    if classify_candidate_kind(entity.get("name")) == CandidateKind.TITLE_NAME:
        return "title_name_requires_review"
    if classify_candidate_kind(entity.get("name")) == CandidateKind.ROLE_DESCRIPTOR:
        return "role_descriptor_requires_review"

    evidence = _entity_evidence(entity)
    cluster_names = [
        str(item).strip() for item in (evidence.get("cluster_names") or []) if str(item).strip()
    ]
    confidence = float(entity.get("confidence") or 0.0)
    if is_role_only_character_name(entity.get("name")) and not any(
        not is_role_only_character_name(name) for name in cluster_names
    ):
        return "role_only_reference_requires_review"

    mention_count = int(evidence.get("mention_count") or 0)
    strong_mentions = int(evidence.get("strong_mention_count") or 0)
    confidence = float(entity.get("confidence") or 0.0)
    if (
        mention_count <= 1
        and strong_mentions >= 1
        and confidence >= 0.9
        and (evidence.get("has_dialogue_or_action") or evidence.get("has_physical_description"))
    ):
        return None
    if confidence < 0.45 and strong_mentions <= 1:
        return "low_confidence_requires_review"
    if mention_count <= 1 and strong_mentions <= 1 and not _has_character_profile_signal(entity):
        return "single_mention_requires_review"
    return None


def _can_auto_save_character(entity: dict) -> bool:
    verifier_band = str(_entity_verifier_band(entity) or "").casefold()
    if verifier_band not in {"", "accept"}:
        return False
    if _entity_requires_manual_review(entity):
        return False
    return _character_save_decision(entity).allowed


def _character_save_decision(entity: dict):
    evidence = _entity_evidence(entity)
    traits = entity.get("traits")
    trait_state = traits if isinstance(traits, dict) else {}
    decision = character_persistence_decision(
        entity.get("name"),
        role=entity.get("role"),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else None,
        personality_tags=entity.get("personality_tags")
        if isinstance(entity.get("personality_tags"), list)
        else None,
        motivations=entity.get("motivations")
        if isinstance(entity.get("motivations"), list)
        else None,
        fears=entity.get("fears") if isinstance(entity.get("fears"), list) else None,
        archetype=entity.get("archetype"),
        trait_state=trait_state,
        relationship_count=int(entity.get("relationship_count") or 0),
        arc_summary=entity.get("arc_summary"),
        evidence=evidence,
        entity_type=str(entity.get("entity_type") or "person"),
    )
    verifier_band = _entity_verifier_band(entity)
    verifier_reasons = [
        str(reason).strip()
        for reason in (_entity_verifier_summary(entity).get("reasons") or [])
        if str(reason).strip()
    ]
    dossier_summary = _entity_dossier_summary(entity)
    if verifier_band == "reject":
        return CharacterPersistenceDecision(
            allowed=False,
            score=decision.score,
            reasons=tuple(["mention_verifier_rejected", *verifier_reasons]),
        )
    if verifier_band == "review":
        return CharacterPersistenceDecision(
            allowed=False,
            score=decision.score,
            reasons=tuple(["mention_verifier_review", *verifier_reasons]),
        )
    if verifier_band == "accept":
        if not dossier_summary.get("strict_auto_eligible"):
            return CharacterPersistenceDecision(
                allowed=False,
                score=decision.score,
                reasons=tuple(
                    [
                        "candidate_dossier_needs_review",
                        *[
                            str(reason).strip()
                            for reason in (dossier_summary.get("strict_auto_reason_codes") or [])
                            if str(reason).strip()
                        ],
                        *decision.reasons,
                    ]
                ),
            )
        if not can_auto_persist_character_candidate(
            name=entity.get("name"),
            aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
            evidence=evidence,
        ):
            return CharacterPersistenceDecision(
                allowed=False,
                score=decision.score,
                reasons=tuple(
                    [
                        "initial_auto_persist_requires_stronger_grounding",
                        *[
                            str(reason).strip()
                            for reason in (dossier_summary.get("strict_auto_reason_codes") or [])
                            if str(reason).strip()
                        ],
                        *decision.reasons,
                    ]
                ),
            )
        return CharacterPersistenceDecision(
            allowed=decision.allowed,
            score=decision.score,
            reasons=tuple(decision.reasons),
        )
    confidence = float(entity.get("confidence") or 0.0)
    if confidence >= AUTO_SAVE_CONFIDENCE and not dossier_summary.get("strict_auto_eligible"):
        return CharacterPersistenceDecision(
            allowed=False,
            score=decision.score,
            reasons=tuple(
                [
                    "candidate_dossier_needs_review",
                    *[
                        str(reason).strip()
                        for reason in (dossier_summary.get("strict_auto_reason_codes") or [])
                        if str(reason).strip()
                    ],
                    *decision.reasons,
                ]
            ),
        )
    return decision
