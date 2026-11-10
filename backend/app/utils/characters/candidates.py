"""
Character utility helpers — shared across route modules.
Covers display filtering, status derivation, relationship summaries,
and text-sanitization helpers used on character data.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from app.engine.character.entity_filters import (
    entity_words,
)
from app.engine.character.extractor import _is_title_only_name
from app.models.character import (
    Character,
    CharacterCandidate,
)
from app.services.character_identity.classification import CandidateKind, classify_candidate_kind
from app.utils.characters.constants import (
    CHARACTER_ADJUDICATION_OBJECT,
    CHARACTER_ADJUDICATION_ORGANIZATION,
    CHARACTER_ADJUDICATION_PLACE,
    CHARACTER_ADJUDICATION_REJECTED,
    CHARACTER_ADJUDICATION_TITLE_OR_ROLE,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_CANDIDATE_ACCEPTED,
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_CANDIDATE_PROMOTED,
    CHARACTER_CANDIDATE_REJECTED,
    CHARACTER_CANDIDATE_SUPPRESSED,
    CHARACTER_DISPOSITION_PROMOTE_UPDATE,
    CHARACTER_DISPOSITION_QUEUE_REVIEW,
    CHARACTER_DISPOSITION_REJECT,
    CHARACTER_DISPOSITION_SUPPRESS,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED,
    CharacterCandidateDisposition,
)
from app.utils.characters.governance import (
    _clean_reason_code_values,
    character_governance,
    infer_character_trust_tier,
)
from app.utils.characters.identity import family_role_reference
from app.utils.characters.presentation import (
    build_character_dossier_summary,
    dedupe_preserve_order,
)
from app.utils.characters.text import clean_string_list


def build_candidate_dossier_summary(candidate: CharacterCandidate) -> dict[str, Any]:
    summary = build_character_dossier_summary(
        name=candidate.proposed_name,
        aliases=candidate.aliases or [],
        evidence=candidate.evidence or {},
        fallback_chapter_numbers=[int(candidate.chapter_number or 0)],
        reason_codes=candidate.reason_codes or [],
    )
    summary.update(
        {
            "entity_type": getattr(candidate, "entity_type", None),
            "adjudication_status": getattr(candidate, "adjudication_status", None),
            "character_score": getattr(candidate, "character_score", None),
            "rejection_reason": getattr(candidate, "rejection_reason", None),
        }
    )
    return summary


def _verifier_final_from_evidence(evidence: Mapping[str, Any] | None) -> Mapping[str, Any]:
    verifier = (evidence or {}).get("verifier")
    if not isinstance(verifier, Mapping):
        return {}
    final = verifier.get("final")
    return final if isinstance(final, Mapping) else {}


def _verifier_llm_from_evidence(evidence: Mapping[str, Any] | None) -> Mapping[str, Any]:
    verifier = (evidence or {}).get("verifier")
    if not isinstance(verifier, Mapping):
        return {}
    llm = verifier.get("llm")
    return llm if isinstance(llm, Mapping) else {}


def _candidate_llm_confirmed_person(evidence: Mapping[str, Any] | None) -> bool:
    llm = _verifier_llm_from_evidence(evidence)
    final = _verifier_final_from_evidence(evidence)
    return bool(
        llm.get("is_person_like") is True
        or "llm_confirmed_person"
        in {str(reason).strip() for reason in (final.get("reasons") or []) if str(reason).strip()}
    )


def recurring_role_review_supported(name: str | None, evidence: Mapping[str, Any] | None) -> bool:
    """Retain a repeated, source-backed unnamed person for author review."""
    if classify_candidate_kind(name) != CandidateKind.ROLE_DESCRIPTOR:
        return False
    details = evidence if isinstance(evidence, Mapping) else {}
    final = _verifier_final_from_evidence(details)
    return bool(
        details.get("source_mention_count_verified") is True
        and str(final.get("confidence_band") or "").casefold() == "accept"
        and int(details.get("mention_count") or 0) >= 3
        and int(details.get("strong_mention_count") or 0) >= 2
        and (
            details.get("has_attributed_speech") is True
            or details.get("has_human_self_action") is True
            or details.get("has_direct_communication") is True
        )
    )


def _candidate_strongly_grounded(summary: Mapping[str, Any], evidence: Mapping[str, Any]) -> bool:
    if bool(summary.get("common_single_token")) or bool(summary.get("role_only_single_token")):
        return False
    if int(summary.get("non_person_signal_count") or 0) > 0:
        return False
    mention_count = int(summary.get("mention_count") or 0)
    strong_mentions = int(evidence.get("strong_mention_count") or 0)
    person_ner_support = int(summary.get("person_ner_support") or 0)
    dialogue_support = int(summary.get("dialogue_attribution_support") or 0)
    distinct_chapters = int(summary.get("distinct_chapter_count") or 0)
    mid_sentence = int(summary.get("mid_sentence_mentions") or 0)
    single_token = bool(summary.get("single_token"))
    if bool(summary.get("strict_auto_eligible")):
        return True
    if single_token:
        return bool(
            (
                mention_count >= 3
                and strong_mentions >= 2
                and mid_sentence >= 1
                and (person_ner_support >= 1 or dialogue_support >= 1 or distinct_chapters >= 2)
            )
            or (
                mention_count >= 2
                and strong_mentions >= 1
                and (
                    dialogue_support >= 1
                    or bool(evidence.get("has_physical_description"))
                    or bool(evidence.get("appears_multiple_times"))
                    or person_ner_support >= 1
                )
            )
        )
    return bool(
        mention_count >= 2
        and (
            person_ner_support >= 1
            or strong_mentions >= 2
            or dialogue_support >= 1
            or distinct_chapters >= 2
            or int(summary.get("alias_link_support") or 0) >= 1
            or int(summary.get("full_name_link_support") or 0) >= 1
        )
    )


def can_auto_persist_character_candidate(
    *,
    name: str | None,
    aliases: Sequence[object] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> bool:
    if classify_candidate_kind(name) == CandidateKind.ROLE_DESCRIPTOR:
        return False
    evidence_map = dict(evidence or {})
    cluster_names = clean_string_list(
        evidence_map.get("cluster_names")
        if isinstance(evidence_map.get("cluster_names"), list)
        else []
    )
    alias_names = [str(alias).strip() for alias in (aliases or []) if str(alias).strip()]
    summary = build_character_dossier_summary(
        name=name,
        aliases=aliases,
        evidence=evidence_map,
        reason_codes=_clean_reason_code_values(evidence_map.get("resolver_reasons") or []),
    )
    if not bool(summary.get("strict_auto_eligible")):
        return False
    if not _candidate_strongly_grounded(summary, evidence_map):
        return False

    llm_confirmed = _candidate_llm_confirmed_person(evidence_map)
    mention_count = int(summary.get("mention_count") or 0)
    distinct_chapters = int(summary.get("distinct_chapter_count") or 0)
    single_token = bool(summary.get("single_token"))
    person_ner_support = int(summary.get("person_ner_support") or 0)
    alias_link_support = int(summary.get("alias_link_support") or 0)
    full_name_link_support = int(summary.get("full_name_link_support") or 0)
    dialogue_support = int(summary.get("dialogue_attribution_support") or 0)
    strong_mentions = int(evidence_map.get("strong_mention_count") or 0)
    has_physical_description = bool(evidence_map.get("has_physical_description"))
    deterministic_fallback = bool(evidence_map.get("deterministic_fallback"))
    full_name_alias_support = bool(
        any(len(entity_words(alias)) >= 2 for alias in [*alias_names, *cluster_names])
    )
    shared_identity_support = bool(
        person_ner_support >= 1 or alias_link_support >= 1 or full_name_link_support >= 1
    )

    if single_token:
        if bool(summary.get("explicit_speech_single_name_eligible")):
            return True
        if bool(summary.get("direct_communication_single_name_eligible")):
            return True
        if bool(summary.get("human_self_action_single_name_eligible")):
            return True
        if bool(summary.get("recurring_single_name_eligible")):
            return True
        if deterministic_fallback and full_name_alias_support:
            return bool(
                mention_count >= 3
                and strong_mentions >= 2
                and dialogue_support >= 1
                and shared_identity_support
            )
        return bool(
            llm_confirmed
            and mention_count >= 3
            and distinct_chapters >= 2
            and strong_mentions >= 2
            and dialogue_support >= 1
            and shared_identity_support
        )

    if bool(summary.get("first_pass_full_name_eligible")) or bool(
        summary.get("explicit_narrator_full_name_eligible")
    ):
        return True

    if llm_confirmed:
        return bool(
            mention_count >= 2
            and strong_mentions >= 1
            and (
                shared_identity_support
                or dialogue_support >= 1
                or has_physical_description
                or distinct_chapters >= 2
            )
        )

    if (
        distinct_chapters >= 2
        and mention_count >= 2
        and (shared_identity_support or dialogue_support >= 1 or has_physical_description)
    ):
        return True

    return bool(
        deterministic_fallback
        and mention_count >= 2
        and strong_mentions >= 1
        and dialogue_support >= 1
        and (shared_identity_support or has_physical_description)
    )


def decide_character_candidate_disposition(
    *,
    name: str | None,
    aliases: Sequence[object] | None = None,
    confidence: object | None = None,
    reason_codes: Sequence[object] | None = None,
    evidence: Mapping[str, Any] | None = None,
    matched_character_id: uuid.UUID | None = None,
    intended_action: str | None = None,
) -> CharacterCandidateDisposition:
    from app.engine.character.adjudicator import adjudicate_character_candidate

    evidence_map = dict(evidence or {})
    reasons = _clean_reason_code_values(reason_codes)
    adjudication = adjudicate_character_candidate(
        name=name,
        aliases=aliases,
        confidence=confidence,
        evidence=evidence_map,
        reason_codes=reasons,
        matched_character_id=matched_character_id,
    )
    evidence_map["adjudication"] = {
        "display_name": adjudication.display_name,
        "normalized_name": adjudication.normalized_name,
        "entity_type": adjudication.entity_type,
        "adjudication_status": adjudication.adjudication_status,
        "character_score": adjudication.character_score,
        "confidence": adjudication.confidence,
        "rejection_reason": adjudication.rejection_reason,
        "reason_codes": list(adjudication.reason_codes),
    }
    if adjudication.evidence_windows:
        evidence_map["evidence_windows"] = list(adjudication.evidence_windows)
    reasons = dedupe_preserve_order([*reasons, *adjudication.reason_codes])
    final = _verifier_final_from_evidence(evidence_map)
    final_band = str(final.get("confidence_band") or "").strip().casefold()
    final_reasons = _clean_reason_code_values(
        final.get("reasons") if isinstance(final, Mapping) else []
    )
    all_reasons = dedupe_preserve_order([*reasons, *final_reasons])
    summary = build_character_dossier_summary(
        name=name,
        aliases=aliases,
        evidence=evidence_map,
        reason_codes=all_reasons,
    )
    evidence_map["disposition_summary"] = dict(summary)
    normalized_reasons = {reason.casefold() for reason in all_reasons}
    llm_confirmed = _candidate_llm_confirmed_person(evidence_map)
    strongly_grounded = _candidate_strongly_grounded(summary, evidence_map)
    recurring_role_review = recurring_role_review_supported(name, evidence_map)
    visible_review_allowed = bool(llm_confirmed or strongly_grounded or recurring_role_review)

    suppress_reasons: list[str] = []
    if "unanchored_character_reference" in normalized_reasons:
        suppress_reasons.append("unanchored_character_reference")
    if final_band == "review" or "mention_verifier_review" in normalized_reasons:
        suppress_reasons.append("mention_verifier_review_suppressed")
    if adjudication.adjudication_status in {
        CHARACTER_ADJUDICATION_PLACE,
        CHARACTER_ADJUDICATION_ORGANIZATION,
        CHARACTER_ADJUDICATION_OBJECT,
        CHARACTER_ADJUDICATION_TITLE_OR_ROLE,
        CHARACTER_ADJUDICATION_REJECTED,
    }:
        suppress_reasons.append(f"{adjudication.adjudication_status}_adjudicated")
    if "fallback_review_candidate_unconfirmed" in normalized_reasons:
        suppress_reasons.append("fallback_review_candidate_unconfirmed")
    if bool(summary.get("common_single_token")):
        suppress_reasons.append("common_single_token_suppressed")
    if _is_title_only_name(name or ""):
        suppress_reasons.append("title_only_fragment_suppressed")
    family_anchor, family_role = family_role_reference(name or "")
    if (
        family_anchor
        and family_role
        and matched_character_id is None
        and not visible_review_allowed
    ):
        suppress_reasons.append("kinship_descriptor_unresolved_suppressed")
    if bool(summary.get("role_only_single_token")) and not visible_review_allowed:
        suppress_reasons.append("role_only_single_token_suppressed")
    if (
        bool(summary.get("single_token"))
        and int(summary.get("sentence_start_mentions") or 0)
        >= int(summary.get("mention_count") or 0)
        and int(summary.get("mid_sentence_mentions") or 0) <= 0
        and not visible_review_allowed
    ):
        suppress_reasons.append("sentence_start_capitalization_suppressed")
    if (
        "single_token_ambiguous"
        in {str(reason).casefold() for reason in summary.get("strict_auto_reason_codes") or []}
        and not visible_review_allowed
    ):
        suppress_reasons.append("weak_single_token_suppressed")
    if final_band == "reject" or "mention_verifier_rejected" in normalized_reasons:
        action = CHARACTER_DISPOSITION_REJECT
        status = (
            CHARACTER_CANDIDATE_SUPPRESSED
            if intended_action != CHARACTER_DISPOSITION_REJECT
            else CHARACTER_CANDIDATE_REJECTED
        )
        disposition_reasons = dedupe_preserve_order(["mention_verifier_rejected", *all_reasons])
    elif "unanchored_character_reference" in normalized_reasons or (
        suppress_reasons and not visible_review_allowed
    ):
        action = CHARACTER_DISPOSITION_SUPPRESS
        status = CHARACTER_CANDIDATE_SUPPRESSED
        disposition_reasons = dedupe_preserve_order([*suppress_reasons, *all_reasons])
    elif intended_action == CHARACTER_DISPOSITION_PROMOTE_UPDATE:
        action = CHARACTER_DISPOSITION_PROMOTE_UPDATE
        status = (
            CHARACTER_CANDIDATE_ACCEPTED if matched_character_id else CHARACTER_CANDIDATE_PROMOTED
        )
        disposition_reasons = all_reasons or ["candidate_strongly_grounded"]
    elif visible_review_allowed:
        action = CHARACTER_DISPOSITION_QUEUE_REVIEW
        status = CHARACTER_CANDIDATE_PENDING
        disposition_reasons = all_reasons or ["candidate_visible_review_allowed"]
    else:
        action = CHARACTER_DISPOSITION_SUPPRESS
        status = CHARACTER_CANDIDATE_SUPPRESSED
        disposition_reasons = dedupe_preserve_order(
            ["insufficient_visible_review_grounding", *all_reasons]
        )

    evidence_map["candidate_disposition"] = {
        "action": action,
        "status": status,
        "visible_review_allowed": visible_review_allowed,
        "llm_confirmed_person": llm_confirmed,
        "strongly_grounded": strongly_grounded,
        "reasons": disposition_reasons,
    }
    return CharacterCandidateDisposition(
        action=action,
        status=status,
        reason_codes=tuple(disposition_reasons),
        evidence=evidence_map,
        visible_review_allowed=visible_review_allowed,
    )


def decide_relationship_candidate_disposition(
    *,
    raw_character_a: str | None,
    raw_character_b: str | None,
    left_resolved: bool,
    right_resolved: bool,
    reason_codes: Sequence[object] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> CharacterCandidateDisposition:
    evidence_map = dict(evidence or {})
    reasons = _clean_reason_code_values(reason_codes)
    suppress_reasons: list[str] = []
    for label, raw_name, resolved in (
        ("character_a", raw_character_a, left_resolved),
        ("character_b", raw_character_b, right_resolved),
    ):
        if resolved:
            continue
        disposition = decide_character_candidate_disposition(
            name=raw_name,
            aliases=[],
            confidence=0,
            reason_codes=[*reasons, f"{label}_unresolved"],
            evidence={"mention_count": 1, "resolver_reasons": reasons},
        )
        if disposition.status == CHARACTER_CANDIDATE_SUPPRESSED:
            suppress_reasons.append(f"{label}_suppressed")
    if suppress_reasons:
        status = CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED
        action = CHARACTER_DISPOSITION_SUPPRESS
        disposition_reasons = dedupe_preserve_order([*suppress_reasons, *reasons])
    else:
        status = CHARACTER_RELATIONSHIP_CANDIDATE_PENDING
        action = CHARACTER_DISPOSITION_QUEUE_REVIEW
        disposition_reasons = reasons or ["relationship_unresolved"]
    evidence_map["relationship_candidate_disposition"] = {
        "action": action,
        "status": status,
        "reasons": disposition_reasons,
    }
    return CharacterCandidateDisposition(
        action=action,
        status=status,
        reason_codes=tuple(disposition_reasons),
        evidence=evidence_map,
        visible_review_allowed=status == CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    )


def build_character_record_dossier_summary(char: Character) -> dict[str, Any]:
    metadata = dict(getattr(char, "analysis_metadata", None) or {})
    evidence: dict[str, Any] = {
        "cluster_mention_count": int(getattr(char, "mention_count", 0) or 0),
        "chapter_numbers": [
            chapter
            for chapter in [
                int(getattr(char, "first_chapter", 0) or 0),
                int(getattr(char, "last_seen_chapter", 0) or 0),
            ]
            if chapter > 0
        ],
        "resolver_reasons": metadata.get("trust_reasons") or [],
    }
    return build_character_dossier_summary(
        name=char.name,
        aliases=char.aliases or [],
        evidence=evidence,
        fallback_chapter_numbers=[
            int(getattr(char, "first_chapter", 0) or 0),
            int(getattr(char, "last_seen_chapter", 0) or 0),
        ],
        reason_codes=getattr(char, "approval_reason_codes", None)
        or metadata.get("trust_reasons")
        or [],
    )


def build_character_analysis_payload(char: Character) -> dict[str, Any]:
    metadata = dict(getattr(char, "analysis_metadata", None) or {})
    mention_count = int(getattr(char, "mention_count", 0) or 0)
    is_manual = bool(getattr(char, "is_manual", False))
    trust_tier, trust_reasons = infer_character_trust_tier(char)
    visibility_state, approval_state, approval_source, approval_reason_codes = character_governance(
        char
    )
    dossier_summary = build_character_record_dossier_summary(char)

    if (
        "grounding_passage_count" in metadata
        and metadata.get("grounding_passage_count") is not None
    ):
        grounding_passage_count = int(metadata.get("grounding_passage_count") or 0)
    elif "evidence_count" in metadata and metadata.get("evidence_count") is not None:
        grounding_passage_count = int(metadata.get("evidence_count") or 0)
    else:
        grounding_passage_count = mention_count
    quality_flags = [
        str(flag).strip() for flag in (metadata.get("quality_flags") or []) if str(flag).strip()
    ]
    if grounding_passage_count <= 1 and not is_manual and "light_grounding" not in quality_flags:
        quality_flags.append("light_grounding")

    if "evidence_count" in metadata and metadata.get("evidence_count") is not None:
        evidence_count = int(metadata.get("evidence_count") or 0)
    else:
        evidence_count = grounding_passage_count

    confidence_band = str(metadata.get("confidence_band") or "").strip() or None
    if confidence_band not in {"high", "medium", "low", None}:
        confidence_band = None
    if confidence_band is None:
        if grounding_passage_count >= 3:
            confidence_band = "high"
        elif grounding_passage_count >= 1 or evidence_count >= 1 or is_manual:
            confidence_band = "medium"
        else:
            confidence_band = "low"

    summary_quality = str(metadata.get("summary_quality") or "").strip() or None
    if summary_quality is None:
        if "generic_summary" in quality_flags:
            summary_quality = "generic"
        elif grounding_passage_count >= 2:
            summary_quality = "grounded"
        else:
            summary_quality = "thin"

    persistence_reason = str(metadata.get("persistence_reason") or "").strip() or None
    if persistence_reason is None and is_manual:
        persistence_reason = "manual_character"

    rejected_duplicate_candidates = [
        str(item).strip()
        for item in (metadata.get("rejected_duplicate_candidates") or [])
        if str(item).strip()
    ]

    return {
        "persistence_reason": persistence_reason,
        "evidence_count": evidence_count,
        "summary_quality": summary_quality,
        "needs_review": bool(metadata.get("needs_review"))
        or bool(quality_flags)
        or approval_state == CHARACTER_APPROVAL_PENDING_REVIEW,
        "rejected_duplicate_candidates": rejected_duplicate_candidates,
        "quality_flags": quality_flags,
        "grounding_passage_count": grounding_passage_count,
        "confidence_band": confidence_band,
        "user_curated": bool(metadata.get("user_curated")),
        "protected_from_repair": bool(metadata.get("protected_from_repair")),
        "canonical_confidence": (
            float(metadata.get("canonical_confidence"))
            if metadata.get("canonical_confidence") is not None
            else None
        ),
        "grounding_coverage": (
            float(metadata.get("grounding_coverage"))
            if metadata.get("grounding_coverage") is not None
            else None
        ),
        "cluster_size": int(metadata.get("cluster_size") or 0),
        "cluster_mention_count": int(metadata.get("cluster_mention_count") or 0),
        "resolver_status": str(metadata.get("resolver_status") or "").strip() or None,
        "review_note": str(metadata.get("review_note") or "").strip() or None,
        "first_person_self_identification": (
            metadata.get("first_person_self_identification")
            if isinstance(metadata.get("first_person_self_identification"), dict)
            else None
        ),
        "first_person_addressed_as": (
            metadata.get("first_person_addressed_as")
            if isinstance(metadata.get("first_person_addressed_as"), dict)
            else None
        ),
        "visibility_state": visibility_state,
        "approval_state": approval_state,
        "approval_source": approval_source,
        "approval_reason_codes": approval_reason_codes,
        "dossier_summary": dossier_summary,
        "trust_tier": trust_tier,
        "trust_reasons": trust_reasons,
        "profile_claims": [
            claim for claim in metadata.get("profile_claims") or [] if isinstance(claim, dict)
        ],
    }
