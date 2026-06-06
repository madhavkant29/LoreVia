"""
Character utility helpers — shared across route modules.
Covers display filtering, status derivation, relationship summaries,
and text-sanitization helpers used on character data.
"""
from __future__ import annotations

import math
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, cast

import bleach  # type: ignore[import-untyped]
from sqlalchemy import inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import UnmappedInstanceError
from sqlalchemy.orm import object_session, selectinload

from app.engine.character.entity_filters import (
    COMMON_NON_NAME_WORDS,
    VISIBILITY_THRESHOLD,
    character_visibility_score,
    complex_character_score,
    compute_all_subtype_scores,
    entity_words,
    gag_character_score,
    is_displayable_character_entity,
)
from app.engine.character.extractor import extract_characters_and_relationships
from app.engine.character.extractor import _is_title_only_name
from app.engine.character.profile_builder import (
    build_character_profile,
    build_description,
    choose_richer_text,
    flat,
    merge_growth_events,
    merge_list_values,
    merge_profile_fields,
    merge_trait_states,
)
from app.models.book import Chapter
from app.models.character import (
    Character,
    CharacterAlias,
    CharacterCandidate,
    CharacterDecisionEvent,
    CharacterDuplicateSuggestion,
    CharacterIdentityAction,
    CharacterIdentityConstraint,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterState,
    CharacterSuppression,
    CharacterVoiceProfile,
)
from app.services.character_identity.constraints import (
    has_blocking_identity_constraint,
)
from app.services.character_identity.merge import add_character_alias, record_identity_action
from app.services.character_identity.normalization import assign_unique_active_normalized_names, first_name_token
from app.services.character_identity.suppression import suppress_candidate
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    QuoteEntry,
    WikiEntry,
)
from app.utils.db_utils import run_read_with_retry
from app.utils.relationship_utils import repair_relationship_timelines

BLEACH_EMPTY_TAGS: Any = frozenset()
CHARACTER_CANDIDATE_PENDING = "pending"
CHARACTER_CANDIDATE_ACCEPTED = "accepted"
CHARACTER_CANDIDATE_REJECTED = "rejected"
CHARACTER_CANDIDATE_PROMOTED = "promoted"
CHARACTER_CANDIDATE_MERGED = "merged"
CHARACTER_CANDIDATE_SUPPRESSED = "suppressed"
CHARACTER_DUPLICATE_PENDING = "pending"
CHARACTER_DUPLICATE_ACCEPTED = "accepted"
CHARACTER_DUPLICATE_DISMISSED = "dismissed"
CHARACTER_RELATIONSHIP_CANDIDATE_PENDING = "pending"
CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED = "accepted"
CHARACTER_RELATIONSHIP_CANDIDATE_REJECTED = "rejected"
CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED = "resolved"
CHARACTER_RELATIONSHIP_CANDIDATE_MERGED = "merged"
CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED = "suppressed"
CHARACTER_VISIBILITY_VISIBLE = "visible"
CHARACTER_VISIBILITY_QUARANTINED = "quarantined"
CHARACTER_VISIBILITY_NOISE = "noise"
VALID_CHARACTER_VISIBILITY_STATES = {
    CHARACTER_VISIBILITY_VISIBLE,
    CHARACTER_VISIBILITY_QUARANTINED,
    CHARACTER_VISIBILITY_NOISE,
}
CHARACTER_APPROVAL_APPROVED = "approved"
CHARACTER_APPROVAL_PENDING_REVIEW = "pending_review"
CHARACTER_APPROVAL_REJECTED = "rejected"
CHARACTER_APPROVAL_PROTECTED = "protected"
VALID_CHARACTER_APPROVAL_STATES = {
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_REJECTED,
    CHARACTER_APPROVAL_PROTECTED,
}
CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW = "manual_review"
CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO = "deterministic_auto"
CHARACTER_APPROVAL_SOURCE_BACKFILL_REVIEW = "backfill_review"
CHARACTER_APPROVAL_SOURCE_LEGACY_IMPORT = "legacy_import"
VALID_CHARACTER_APPROVAL_SOURCES = {
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
    CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
    CHARACTER_APPROVAL_SOURCE_BACKFILL_REVIEW,
    CHARACTER_APPROVAL_SOURCE_LEGACY_IMPORT,
}
CHARACTER_TRUST_TIER_VISIBLE = "visible"
CHARACTER_TRUST_TIER_REVIEW_ONLY = "review_only"
CHARACTER_TRUST_TIER_REPAIRED_NOISE = "repaired_noise"
VALID_CHARACTER_TRUST_TIERS = {
    CHARACTER_TRUST_TIER_VISIBLE,
    CHARACTER_TRUST_TIER_REVIEW_ONLY,
    CHARACTER_TRUST_TIER_REPAIRED_NOISE,
}
ROLE_ONLY_REFERENCE_WORDS = {
    "aunt", "brother", "captain", "chief", "chief clerk", "clerk", "doctor", "father", "headmaster",
    "lady", "lord", "master", "mentor", "mother", "mr", "mrs", "ms", "nurse", "professor", "servant",
    "sister", "teacher", "uncle",
}
FAMILY_ROLE_WORDS = {"aunt", "brother", "father", "mother", "sister", "uncle"}

CHARACTER_DISPOSITION_PROMOTE_UPDATE = "promote/update"
CHARACTER_DISPOSITION_QUEUE_REVIEW = "queue_review"
CHARACTER_DISPOSITION_SUPPRESS = "suppress"
CHARACTER_DISPOSITION_REJECT = "reject"


@dataclass(frozen=True)
class CharacterCandidateDisposition:
    action: str
    status: str
    reason_codes: tuple[str, ...]
    evidence: dict[str, Any]
    visible_review_allowed: bool = False


def normalize_character_trust_tier(value: object | None) -> str | None:
    cleaned = str(value or "").strip().casefold()
    return cleaned if cleaned in VALID_CHARACTER_TRUST_TIERS else None


def normalize_character_visibility_state(value: object | None) -> str | None:
    cleaned = str(value or "").strip().casefold()
    return cleaned if cleaned in VALID_CHARACTER_VISIBILITY_STATES else None


def normalize_character_approval_state(value: object | None) -> str | None:
    cleaned = str(value or "").strip().casefold()
    return cleaned if cleaned in VALID_CHARACTER_APPROVAL_STATES else None


def normalize_character_approval_source(value: object | None) -> str | None:
    cleaned = str(value or "").strip().casefold()
    return cleaned if cleaned in VALID_CHARACTER_APPROVAL_SOURCES else None


def _clean_reason_code_values(values: Sequence[object] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = str(raw or "").strip()
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def character_governance(char: Character) -> tuple[str, str, str | None, list[str]]:
    metadata = dict(getattr(char, "analysis_metadata", None) or {})
    visibility_state = normalize_character_visibility_state(getattr(char, "visibility_state", None))
    approval_state = normalize_character_approval_state(getattr(char, "approval_state", None))
    approval_source = normalize_character_approval_source(getattr(char, "approval_source", None))
    approval_reason_codes = _clean_reason_code_values(getattr(char, "approval_reason_codes", None))
    if visibility_state and approval_state:
        return visibility_state, approval_state, approval_source, approval_reason_codes

    explicit_tier = normalize_character_trust_tier(metadata.get("trust_tier"))
    explicit_reasons = clean_string_list(cast(list[str] | None, metadata.get("trust_reasons")))
    if getattr(char, "is_manual", False) or metadata.get("user_curated") or metadata.get("protected_from_repair"):
        return (
            CHARACTER_VISIBILITY_VISIBLE,
            CHARACTER_APPROVAL_PROTECTED,
            CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
            ["manual_or_curated"],
        )
    if explicit_tier == CHARACTER_TRUST_TIER_REVIEW_ONLY:
        return (
            CHARACTER_VISIBILITY_QUARANTINED,
            CHARACTER_APPROVAL_PENDING_REVIEW,
            CHARACTER_APPROVAL_SOURCE_LEGACY_IMPORT,
            explicit_reasons,
        )
    if explicit_tier == CHARACTER_TRUST_TIER_REPAIRED_NOISE:
        return (
            CHARACTER_VISIBILITY_NOISE,
            CHARACTER_APPROVAL_REJECTED,
            CHARACTER_APPROVAL_SOURCE_LEGACY_IMPORT,
            explicit_reasons,
        )
    name = " ".join((char.name or "").split())
    words = entity_words(name)
    normalized_words = [word.casefold() for word in words]
    single_token = len(normalized_words) == 1
    common_single_token = single_token and normalized_words[0] in COMMON_NON_NAME_WORDS
    role_only_single_token = single_token and normalized_words[0] in ROLE_ONLY_REFERENCE_WORDS
    mention_count = int(getattr(char, "mention_count", 0) or 0)
    grounding_passage_count = int(metadata.get("grounding_passage_count") or metadata.get("evidence_count") or mention_count or 0)
    quality_flags = {str(flag).strip() for flag in (metadata.get("quality_flags") or []) if str(flag).strip()}
    has_profile = _character_has_meaningful_profile_data(char)
    score = character_visibility_score(
        name,
        role=char.role,
        aliases=char.aliases or [],
        arc_summary=char.arc_summary,
        personality_tags=char.personality_tags or [],
        motivations=char.motivations or [],
        fears=char.fears or [],
        archetype=char.archetype or char.arc_summary,
        trait_state=char.trait_state or {},
        relationship_count=0,
    )
    legacy_reasons: list[str] = []
    if score < VISIBILITY_THRESHOLD:
        legacy_reasons.append("visibility_score_below_threshold")
    if common_single_token:
        legacy_reasons.append("common_single_token")
    if role_only_single_token and not has_profile:
        legacy_reasons.append("role_only_single_token")
    if single_token and grounding_passage_count <= 1 and mention_count <= 1 and not has_profile:
        legacy_reasons.append("thin_single_token_grounding")
    if "generic_summary" in quality_flags and grounding_passage_count <= 1 and not has_profile:
        legacy_reasons.append("generic_low_grounding")
    if legacy_reasons and (
        common_single_token
        or role_only_single_token
        or score < VISIBILITY_THRESHOLD
        or "thin_single_token_grounding" in legacy_reasons
    ):
        return (
            CHARACTER_VISIBILITY_QUARANTINED,
            CHARACTER_APPROVAL_PENDING_REVIEW,
            CHARACTER_APPROVAL_SOURCE_LEGACY_IMPORT,
            legacy_reasons,
        )
    return (
        CHARACTER_VISIBILITY_VISIBLE,
        CHARACTER_APPROVAL_APPROVED,
        approval_source or CHARACTER_APPROVAL_SOURCE_LEGACY_IMPORT,
        explicit_reasons or ["legacy_visible"],
    )


def _character_has_meaningful_profile_data(char: Character) -> bool:
    if any(
        isinstance(value, dict) and str(value.get("value") or "").strip()
        for value in (char.trait_state or {}).values()
    ):
        return True
    if any(
        str(getattr(char, field, "") or "").strip()
        for field in ("goal", "lie_they_believe", "backstory_wound", "arc_type", "archetype")
    ):
        return True
    if any(getattr(char, field, None) for field in ("personality_tags", "motivations", "fears", "growth_events")):
        return True
    arc_summary = clean_optional_text(getattr(char, "arc_summary", None))
    return bool(arc_summary and arc_summary.casefold() not in {"appearance not yet described", "background character", "is a character", "mysterious figure", "normal character", "plain character", "supporting character", "this character is a character", "protagonist", "antagonist", "puppet master", "tragic figure", "unknown character"})


def infer_character_trust_tier(char: Character) -> tuple[str, list[str]]:
    visibility_state, approval_state, _approval_source, approval_reason_codes = character_governance(char)
    if visibility_state == CHARACTER_VISIBILITY_VISIBLE and approval_state in {
        CHARACTER_APPROVAL_APPROVED,
        CHARACTER_APPROVAL_PROTECTED,
    }:
        return CHARACTER_TRUST_TIER_VISIBLE, approval_reason_codes or ["approval_visible"]
    if visibility_state == CHARACTER_VISIBILITY_NOISE or approval_state == CHARACTER_APPROVAL_REJECTED:
        return CHARACTER_TRUST_TIER_REPAIRED_NOISE, approval_reason_codes or ["approval_rejected"]
    if visibility_state == CHARACTER_VISIBILITY_QUARANTINED or approval_state == CHARACTER_APPROVAL_PENDING_REVIEW:
        return CHARACTER_TRUST_TIER_REVIEW_ONLY, approval_reason_codes or ["approval_pending_review"]

    metadata = dict(getattr(char, "analysis_metadata", None) or {})
    explicit_tier = normalize_character_trust_tier(metadata.get("trust_tier"))
    explicit_reasons = clean_string_list(cast(list[str] | None, metadata.get("trust_reasons")))
    if getattr(char, "is_manual", False) or metadata.get("user_curated") or metadata.get("protected_from_repair"):
        return CHARACTER_TRUST_TIER_VISIBLE, ["manual_or_curated"]
    if explicit_tier is not None:
        return explicit_tier, explicit_reasons

    name = " ".join((char.name or "").split())
    words = entity_words(name)
    normalized_words = [word.casefold() for word in words]
    single_token = len(normalized_words) == 1
    common_single_token = single_token and normalized_words[0] in COMMON_NON_NAME_WORDS
    role_only_single_token = single_token and normalized_words[0] in ROLE_ONLY_REFERENCE_WORDS
    mention_count = int(getattr(char, "mention_count", 0) or 0)
    grounding_passage_count = int(metadata.get("grounding_passage_count") or metadata.get("evidence_count") or mention_count or 0)
    quality_flags = {str(flag).strip() for flag in (metadata.get("quality_flags") or []) if str(flag).strip()}
    has_profile = _character_has_meaningful_profile_data(char)
    score = character_visibility_score(
        name,
        role=char.role,
        aliases=char.aliases or [],
        arc_summary=char.arc_summary,
        personality_tags=char.personality_tags or [],
        motivations=char.motivations or [],
        fears=char.fears or [],
        archetype=char.archetype or char.arc_summary,
        trait_state=char.trait_state or {},
        relationship_count=0,
    )

    reasons: list[str] = []
    if score < VISIBILITY_THRESHOLD:
        reasons.append("visibility_score_below_threshold")
    if common_single_token:
        reasons.append("common_single_token")
    if role_only_single_token and not has_profile:
        reasons.append("role_only_single_token")
    if single_token and grounding_passage_count <= 1 and mention_count <= 1 and not has_profile:
        reasons.append("thin_single_token_grounding")
    if "generic_summary" in quality_flags and grounding_passage_count <= 1 and not has_profile:
        reasons.append("generic_low_grounding")

    if reasons and (common_single_token or role_only_single_token or score < VISIBILITY_THRESHOLD or "thin_single_token_grounding" in reasons):
        return CHARACTER_TRUST_TIER_REVIEW_ONLY, reasons
    return CHARACTER_TRUST_TIER_VISIBLE, reasons


def is_cast_visible_character(char: Character) -> bool:
    if getattr(char, "merged_into_character_id", None) is not None:
        return False
    visibility_state, approval_state, _approval_source, _reasons = character_governance(char)
    return visibility_state == CHARACTER_VISIBILITY_VISIBLE and approval_state in {
        CHARACTER_APPROVAL_APPROVED,
        CHARACTER_APPROVAL_PROTECTED,
    }

# ─── Display filter ───────────────────────────────────────────────────────────

def is_displayable_character(char: Character) -> bool:
    name = " ".join((char.name or "").split())
    if not name:
        return False
    if getattr(char, "merged_into_character_id", None) is not None:
        return False
    if getattr(char, "is_manual", False):
        return True
    if not is_cast_visible_character(char):
        return False
    return True


# ─── Status derivation ────────────────────────────────────────────────────────

def character_status(char: Character) -> str:
    text = " ".join(
        part
        for part in [
            char.arc_summary or "",
            " ".join(event.get("event", "") for event in (char.growth_events or []) if isinstance(event, dict)),
        ]
        if part
    ).lower()
    deceased_markers = ("deceased", "dead", "dies", "died", "killed", "murdered", "executed", "buried")
    return "deceased" if any(marker in text for marker in deceased_markers) else "alive"


# ─── Relationship summary helpers ─────────────────────────────────────────────

def relationship_summary_for_character(
    rel: CharacterRelationship,
    name_a: str,
    name_b: str,
    perspective_name: str,
) -> str | None:
    counterpart = name_b if perspective_name == name_a else name_a
    rel_type = (rel.rel_type or "connection").replace("_", " ").strip()
    if not rel_type:
        rel_type = "connection"
    return f"{rel_type.capitalize()} connection with {counterpart}."


def relationship_summary(
    description: str | None,
    rel_type: str | None,
    name_a: str,
    name_b: str,
) -> str | None:
    if description:
        return " ".join(description.split())
    if rel_type:
        return f"{name_a} has a {rel_type} relationship with {name_b}."
    return None


def append_unique_summary(
    rel_summaries: dict[str, list[str]],
    rel_keys: dict[str, set[str]],
    char_id: str,
    signature: str,
    summary: str,
) -> None:
    bucket = rel_keys.setdefault(char_id, set())
    if signature in bucket:
        return
    bucket.add(signature)
    rel_summaries.setdefault(char_id, []).append(summary)


# ─── List / string deduplication helpers ─────────────────────────────────────

def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def merge_description_with_relationships(
    description: str | None,
    relationship_summaries: list[str],
) -> str:
    preview = clean_string_list(relationship_summaries)[:2]
    base = clean_optional_text(description)
    if not preview:
        return base or ""
    if not base:
        return " ".join(preview)
    return f"{base}. {' '.join(preview)}"


def _ensure_sentence(text: str) -> str:
    cleaned = clean_optional_text(text)
    if not cleaned:
        return ""
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def compose_character_description(
    *,
    trait_state: dict[str, Any] | None,
    archetype: str | None,
    arc_summary: str | None = None,
    personality_tags: list[str] | None = None,
    motivations: list[str] | None = None,
    relationship_summaries: list[str] | None = None,
) -> str | None:
    segments: list[str] = []
    base = clean_optional_text(build_description(trait_state or {}, archetype))
    if base and base.casefold() != "appearance not yet described":
        segments.append(_ensure_sentence(base))

    arc = clean_optional_text(arc_summary)
    if arc and (not base or arc.casefold() != base.casefold()):
        segments.append(_ensure_sentence(arc))

    if not segments:
        cleaned_tags = clean_string_list(personality_tags)
        if cleaned_tags:
            segments.append(f"Disposition: {', '.join(cleaned_tags[:3])}.")
        cleaned_motivations = clean_string_list(motivations)
        if cleaned_motivations:
            segments.append(f"Wants: {', '.join(cleaned_motivations[:2])}.")

    relationship_preview = clean_string_list(relationship_summaries)[:2]
    if relationship_preview:
        segments.append(" ".join(_ensure_sentence(summary) for summary in relationship_preview if summary))

    composed = " ".join(segment for segment in segments if segment).strip()
    return composed or None


# ─── Text-cleaning helpers ────────────────────────────────────────────────────

def clean_optional_text(value: object | None) -> str | None:
    cleaned = str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))
    return cleaned or None


def clean_string_list(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = str(bleach.clean(str(raw or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _clean_int_list(values: Sequence[object] | None) -> list[int]:
    cleaned: list[int] = []
    seen: set[int] = set()
    for raw in values or []:
        try:
            item = int(raw)
        except (TypeError, ValueError):
            continue
        if item <= 0 or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    return cleaned


def build_character_dossier_summary(
    *,
    name: str | None,
    aliases: Sequence[object] | None = None,
    evidence: Mapping[str, Any] | None = None,
    fallback_chapter_numbers: Sequence[int] | None = None,
    reason_codes: Sequence[object] | None = None,
) -> dict[str, Any]:
    clean_name = clean_optional_text(name) or ""
    clean_aliases = clean_string_list([str(alias) for alias in aliases or []])
    entity_aliases = clean_string_list(
        [str(alias) for alias in ((evidence or {}).get("entity") or {}).get("aliases") or []]
    ) if isinstance((evidence or {}).get("entity"), Mapping) else []
    merged_aliases = dedupe_preserve_order([*clean_aliases, *entity_aliases])
    words = entity_words(clean_name)
    single_token = len(words) == 1
    common_single_token = single_token and words[0].casefold() in COMMON_NON_NAME_WORDS
    role_only_single_token = single_token and words[0].casefold() in ROLE_ONLY_REFERENCE_WORDS
    evidence_map = dict(evidence or {})
    verifier = evidence_map.get("verifier") if isinstance(evidence_map.get("verifier"), Mapping) else {}
    local = verifier.get("local") if isinstance(verifier, Mapping) and isinstance(verifier.get("local"), Mapping) else {}
    final = verifier.get("final") if isinstance(verifier, Mapping) and isinstance(verifier.get("final"), Mapping) else {}
    cluster_names = clean_string_list([str(item) for item in evidence_map.get("cluster_names") or []])
    chapter_numbers = _clean_int_list(
        [
            *(evidence_map.get("shared_chapters") or []),
            *(evidence_map.get("chapter_numbers") or []),
            *(fallback_chapter_numbers or []),
        ]
    )
    mention_count = max(
        1 if clean_name else 0,
        int(evidence_map.get("cluster_mention_count") or 0),
        int(evidence_map.get("mention_count") or 0),
        int(evidence_map.get("strong_mention_count") or 0),
        len(chapter_numbers),
    )
    strong_mention_count = int(evidence_map.get("strong_mention_count") or 0)
    person_ner_support = int(local.get("person_ner_mentions") or 0)
    raw_non_person_signal_count = int(local.get("non_person_ner_mentions") or 0)
    sentence_start_mentions = int(local.get("sentence_start_mentions") or 0)
    mid_sentence_mentions = int(local.get("mid_sentence_mentions") or 0)
    dialogue_attribution_support = 1 if evidence_map.get("has_dialogue_or_action") else 0
    resolver_status = clean_optional_text(evidence_map.get("resolver_status")) or ""
    resolved_reason_codes = _clean_reason_code_values(reason_codes or evidence_map.get("resolver_reasons") or [])
    resolver_ambiguity_count = int(
        resolver_status in {"ambiguous", "matched_needs_review", "held_for_review"}
        or any(
            "conflict" in reason.casefold()
            or "needs_review" in reason.casefold()
            or reason.casefold() in {"ambiguous_identity_match", "ambiguous_roster_match"}
            for reason in resolved_reason_codes
        )
    )
    alias_link_support = int(bool(merged_aliases or len(cluster_names) > 1))
    full_name_alias_support = int(any(len(entity_words(alias)) >= 2 for alias in [*merged_aliases, *cluster_names]))
    canonical_name = clean_optional_text(((evidence_map.get("entity") or {}) if isinstance(evidence_map.get("entity"), Mapping) else {}).get("canonical_name"))
    full_name_link_support = int(bool(canonical_name and canonical_name.casefold() != clean_name.casefold()))
    conflict_signal_count = int(
        bool(evidence_map.get("anti_merge_names"))
        or any("conflict" in reason.casefold() for reason in resolved_reason_codes)
    )
    final_band = str(final.get("confidence_band") or "").strip().casefold()
    non_person_signal_count = (
        max(0, raw_non_person_signal_count - person_ner_support)
        if final_band == "accept"
        else raw_non_person_signal_count
    )
    deterministic_fallback = bool(evidence_map.get("deterministic_fallback"))
    strong_fallback_support = bool(
        deterministic_fallback
        and final_band == "accept"
        and mention_count >= 3
        and strong_mention_count >= 2
        and dialogue_attribution_support >= 1
        and (
            person_ner_support >= 1
            or (single_token and full_name_alias_support >= 1)
            or not single_token
        )
    )
    first_pass_full_name_eligible = bool(
        not single_token
        and final_band in {"", "accept"}
        and mention_count >= 2
        and strong_mention_count >= 1
        and non_person_signal_count <= 0
        and resolver_ambiguity_count <= 0
        and (
            person_ner_support >= 1
            or dialogue_attribution_support >= 1
            or bool(evidence_map.get("has_physical_description"))
        )
    )

    strict_auto_reason_codes: list[str] = []
    if role_only_single_token:
        strict_auto_reason_codes.append("role_only_reference")
    if common_single_token:
        strict_auto_reason_codes.append("sentence_start_common_word")
    if non_person_signal_count > 0:
        strict_auto_reason_codes.append("non_person_ner_signal")
    if resolver_ambiguity_count > 0:
        strict_auto_reason_codes.append("conflicts_with_existing_character")
    if single_token and person_ner_support <= 0 and not strong_fallback_support:
        strict_auto_reason_codes.append("single_token_ambiguous")
    if len(chapter_numbers) < 2 and mention_count < 3:
        strict_auto_reason_codes.append("insufficient_cross_chapter_support")
    strict_auto_reason_codes = dedupe_preserve_order(strict_auto_reason_codes)

    strict_auto_eligible = False
    if clean_name:
        if strong_fallback_support or first_pass_full_name_eligible:
            strict_auto_eligible = True
        elif not strict_auto_reason_codes:
            if single_token:
                strict_auto_eligible = (
                    final_band == "accept"
                    and len(chapter_numbers) >= 2
                    and mention_count >= 3
                    and person_ner_support >= 1
                    and mid_sentence_mentions >= 1
                    and dialogue_attribution_support >= 1
                )
            else:
                strict_auto_eligible = (
                    final_band == "accept"
                    and (
                        (len(chapter_numbers) >= 2 and person_ner_support >= 1)
                        or (mention_count >= 2 and person_ner_support >= 1 and (alias_link_support >= 1 or full_name_link_support >= 1 or dialogue_attribution_support >= 1))
                    )
                )
        if not strict_auto_eligible:
            strict_auto_reason_codes.append("insufficient_cross_chapter_support")

    return {
        "normalized_name": normalize_character_name(clean_name),
        "single_token": single_token,
        "common_single_token": common_single_token,
        "role_only_single_token": role_only_single_token,
        "mention_count": mention_count,
        "distinct_chapter_count": len(chapter_numbers),
        "chapter_numbers": chapter_numbers,
        "sentence_start_mentions": sentence_start_mentions,
        "mid_sentence_mentions": mid_sentence_mentions,
        "dialogue_attribution_support": dialogue_attribution_support,
        "person_ner_support": person_ner_support,
        "alias_link_support": alias_link_support,
        "full_name_link_support": full_name_link_support,
        "resolver_ambiguity_count": resolver_ambiguity_count,
        "conflict_signal_count": conflict_signal_count,
        "raw_non_person_signal_count": raw_non_person_signal_count,
        "non_person_signal_count": non_person_signal_count,
        "first_pass_full_name_eligible": first_pass_full_name_eligible,
        "strict_auto_eligible": strict_auto_eligible,
        "strict_auto_reason_codes": dedupe_preserve_order(strict_auto_reason_codes),
        "summary_reason_codes": dedupe_preserve_order([*resolved_reason_codes, *strict_auto_reason_codes]),
    }


def build_candidate_dossier_summary(candidate: CharacterCandidate) -> dict[str, Any]:
    return build_character_dossier_summary(
        name=candidate.proposed_name,
        aliases=candidate.aliases or [],
        evidence=candidate.evidence or {},
        fallback_chapter_numbers=[int(candidate.chapter_number or 0)],
        reason_codes=candidate.reason_codes or [],
    )


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
        or "llm_confirmed_person" in {
            str(reason).strip()
            for reason in (final.get("reasons") or [])
            if str(reason).strip()
        }
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
    evidence_map = dict(evidence or {})
    cluster_names = clean_string_list(evidence_map.get("cluster_names") if isinstance(evidence_map.get("cluster_names"), list) else [])
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

    if bool(summary.get("first_pass_full_name_eligible")):
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

    if distinct_chapters >= 2 and mention_count >= 2 and (
        shared_identity_support
        or dialogue_support >= 1
        or has_physical_description
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
    evidence_map = dict(evidence or {})
    reasons = _clean_reason_code_values(reason_codes)
    final = _verifier_final_from_evidence(evidence_map)
    final_band = str(final.get("confidence_band") or "").strip().casefold()
    final_reasons = _clean_reason_code_values(final.get("reasons") if isinstance(final, Mapping) else [])
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
    visible_review_allowed = bool(llm_confirmed or strongly_grounded)

    suppress_reasons: list[str] = []
    if final_band == "review" or "mention_verifier_review" in normalized_reasons:
        suppress_reasons.append("mention_verifier_review_suppressed")
    if "fallback_review_candidate_unconfirmed" in normalized_reasons:
        suppress_reasons.append("fallback_review_candidate_unconfirmed")
    if bool(summary.get("common_single_token")):
        suppress_reasons.append("common_single_token_suppressed")
    if _is_title_only_name(name or ""):
        suppress_reasons.append("title_only_fragment_suppressed")
    family_anchor, family_role = family_role_reference(name or "")
    if family_anchor and family_role and matched_character_id is None and not visible_review_allowed:
        suppress_reasons.append("kinship_descriptor_unresolved_suppressed")
    if bool(summary.get("role_only_single_token")) and not visible_review_allowed:
        suppress_reasons.append("role_only_single_token_suppressed")
    if (
        bool(summary.get("single_token"))
        and int(summary.get("sentence_start_mentions") or 0) >= int(summary.get("mention_count") or 0)
        and int(summary.get("mid_sentence_mentions") or 0) <= 0
        and not visible_review_allowed
    ):
        suppress_reasons.append("sentence_start_capitalization_suppressed")
    if "single_token_ambiguous" in {
        str(reason).casefold()
        for reason in summary.get("strict_auto_reason_codes") or []
    } and not visible_review_allowed:
        suppress_reasons.append("weak_single_token_suppressed")
    if final_band == "reject" or "mention_verifier_rejected" in normalized_reasons:
        action = CHARACTER_DISPOSITION_REJECT
        status = CHARACTER_CANDIDATE_SUPPRESSED if intended_action != CHARACTER_DISPOSITION_REJECT else CHARACTER_CANDIDATE_REJECTED
        disposition_reasons = dedupe_preserve_order(["mention_verifier_rejected", *all_reasons])
    elif suppress_reasons and not visible_review_allowed:
        action = CHARACTER_DISPOSITION_SUPPRESS
        status = CHARACTER_CANDIDATE_SUPPRESSED
        disposition_reasons = dedupe_preserve_order([*suppress_reasons, *all_reasons])
    elif intended_action == CHARACTER_DISPOSITION_PROMOTE_UPDATE:
        action = CHARACTER_DISPOSITION_PROMOTE_UPDATE
        status = CHARACTER_CANDIDATE_ACCEPTED if matched_character_id else CHARACTER_CANDIDATE_PROMOTED
        disposition_reasons = all_reasons or ["candidate_strongly_grounded"]
    elif visible_review_allowed:
        action = CHARACTER_DISPOSITION_QUEUE_REVIEW
        status = CHARACTER_CANDIDATE_PENDING
        disposition_reasons = all_reasons or ["candidate_visible_review_allowed"]
    else:
        action = CHARACTER_DISPOSITION_SUPPRESS
        status = CHARACTER_CANDIDATE_SUPPRESSED
        disposition_reasons = dedupe_preserve_order(["insufficient_visible_review_grounding", *all_reasons])

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
            for chapter in [int(getattr(char, "first_chapter", 0) or 0), int(getattr(char, "last_seen_chapter", 0) or 0)]
            if chapter > 0
        ],
        "resolver_reasons": metadata.get("trust_reasons") or [],
    }
    return build_character_dossier_summary(
        name=char.name,
        aliases=char.aliases or [],
        evidence=evidence,
        fallback_chapter_numbers=[int(getattr(char, "first_chapter", 0) or 0), int(getattr(char, "last_seen_chapter", 0) or 0)],
        reason_codes=getattr(char, "approval_reason_codes", None) or metadata.get("trust_reasons") or [],
    )


def build_character_analysis_payload(char: Character) -> dict[str, Any]:
    metadata = dict(getattr(char, "analysis_metadata", None) or {})
    mention_count = int(getattr(char, "mention_count", 0) or 0)
    is_manual = bool(getattr(char, "is_manual", False))
    trust_tier, trust_reasons = infer_character_trust_tier(char)
    visibility_state, approval_state, approval_source, approval_reason_codes = character_governance(char)
    dossier_summary = build_character_record_dossier_summary(char)

    if "grounding_passage_count" in metadata and metadata.get("grounding_passage_count") is not None:
        grounding_passage_count = int(metadata.get("grounding_passage_count") or 0)
    elif "evidence_count" in metadata and metadata.get("evidence_count") is not None:
        grounding_passage_count = int(metadata.get("evidence_count") or 0)
    else:
        grounding_passage_count = mention_count
    quality_flags = [
        str(flag).strip()
        for flag in (metadata.get("quality_flags") or [])
        if str(flag).strip()
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
        "needs_review": bool(metadata.get("needs_review")) or bool(quality_flags) or approval_state == CHARACTER_APPROVAL_PENDING_REVIEW,
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
        "visibility_state": visibility_state,
        "approval_state": approval_state,
        "approval_source": approval_source,
        "approval_reason_codes": approval_reason_codes,
        "dossier_summary": dossier_summary,
        "trust_tier": trust_tier,
        "trust_reasons": trust_reasons,
    }


def is_protected_character(char: Character | None) -> bool:
    if char is None:
        return False
    _visibility_state, approval_state, _approval_source, _reason_codes = character_governance(char)
    if approval_state == CHARACTER_APPROVAL_PROTECTED:
        return True
    metadata = dict(getattr(char, "analysis_metadata", None) or {})
    return bool(getattr(char, "is_manual", False) or metadata.get("protected_from_repair"))


def serialize_character_alias_record(alias: CharacterAlias) -> dict[str, Any]:
    return {
        "id": str(alias.id),
        "book_id": str(alias.book_id),
        "character_id": str(alias.character_id),
        "alias_text": alias.alias_text,
        "normalized_alias": alias.normalized_alias,
        "alias_kind": alias.alias_kind,
        "source": alias.source,
        "confidence": float(alias.confidence or 0.0),
        "created_at": alias.created_at,
    }


def serialize_character_alias_records(char: Character) -> list[dict[str, Any]]:
    try:
        if "alias_records" in inspect(char).unloaded:
            return []
    except Exception:
        return []
    records = getattr(char, "alias_records", None) or []
    return [
        serialize_character_alias_record(alias)
        for alias in sorted(
            records,
            key=lambda item: (str(item.alias_kind or ""), str(item.alias_text or "").casefold()),
        )
    ]


def serialize_character_detail(char: Character, *, skip_analysis_metadata: bool = False) -> dict[str, Any]:
    visibility_state, approval_state, approval_source, approval_reason_codes = character_governance(char)
    return {
        "id": char.id,
        "book_id": char.book_id,
        "name": char.name,
        "aliases": getattr(char, "aliases", None) or [],
        "alias_records": serialize_character_alias_records(char),
        "role": getattr(char, "role", None),
        "first_chapter": getattr(char, "first_chapter", 0),
        "trait_state": getattr(char, "trait_state", None) or {},
        "hair": getattr(char, "hair", None),
        "eyes": getattr(char, "eyes", None),
        "build": getattr(char, "build", None),
        "age_descriptor": getattr(char, "age_descriptor", None),
        "distinguishing": getattr(char, "distinguishing", None),
        "personality_tags": getattr(char, "personality_tags", None) or [],
        "motivations": getattr(char, "motivations", None) or [],
        "fears": getattr(char, "fears", None) or [],
        "archetype": getattr(char, "archetype", None),
        "arc_summary": getattr(char, "arc_summary", None),
        "last_seen_chapter": getattr(char, "last_seen_chapter", None),
        "mention_count": getattr(char, "mention_count", None) or 0,
        "growth_events": getattr(char, "growth_events", None) or [],
        "character_type": getattr(char, "character_type", None),
        "character_type_score": getattr(char, "character_type_score", None),
        "subtype_scores": getattr(char, "subtype_scores", None) or {},
        "analysis_metadata": None if skip_analysis_metadata else build_character_analysis_payload(char),
        "visibility_state": visibility_state,
        "approval_state": approval_state,
        "approval_source": approval_source,
        "approval_reason_codes": approval_reason_codes,
        "approval_updated_at": getattr(char, "approval_updated_at", None),
        "is_manual": getattr(char, "is_manual", False),
        "created_at": getattr(char, "created_at"),
    }


def serialize_book_character(
    char: Character,
    *,
    rel_summaries: dict[str, list[str]],
    states: list[CharacterState],
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
    voice_profile: CharacterVoiceProfile | None,
    total_chapters: int | None,
    tags: list[str] | None = None,
    skip_arc_tracker: bool = False,
    skip_analysis_metadata: bool = False,
    skip_tags: bool = False,
) -> dict[str, Any]:
    relationship_summaries = dedupe_preserve_order(rel_summaries.get(str(char.id), []))
    visibility_state, approval_state, approval_source, approval_reason_codes = character_governance(char)
    result: dict[str, Any] = {
        "id": str(char.id),
        "book_id": str(char.book_id),
        "name": char.name,
        "aliases": char.aliases or [],
        "role": char.role,
        "first_chapter": char.first_chapter,
        "last_seen_chapter": char.last_seen_chapter,
        "mention_count": char.mention_count or 0,
        "status": character_status(char),
        "trait_state": char.trait_state or {},
        "description": compose_character_description(
            trait_state=char.trait_state or {},
            archetype=char.archetype,
            arc_summary=char.arc_summary,
            personality_tags=char.personality_tags or [],
            motivations=char.motivations or [],
            relationship_summaries=relationship_summaries,
        ),
        "personality_tags": char.personality_tags or [],
        "goal": char.goal,
        "motivations": char.motivations or [],
        "fears": char.fears or [],
        "lie_they_believe": char.lie_they_believe,
        "backstory_wound": char.backstory_wound,
        "arc_type": char.arc_type,
        "archetype": char.archetype,
        "arc_summary": char.arc_summary,
        "growth_events": char.growth_events or [],
        "relationship_summaries": relationship_summaries,
        "character_type": char.character_type,
        "character_type_score": char.character_type_score,
        "subtype_scores": char.subtype_scores or {},
        "visibility_state": visibility_state,
        "approval_state": approval_state,
        "approval_source": approval_source,
        "approval_reason_codes": approval_reason_codes,
        "approval_updated_at": getattr(char, "approval_updated_at", None),
        "is_manual": getattr(char, "is_manual", False),
        "graph_visibility_override": get_graph_visibility_override(char),
    }
    if skip_analysis_metadata:
        result["analysis_metadata"] = None
    else:
        result["analysis_metadata"] = build_character_analysis_payload(char)
    result["tags"] = [] if skip_tags else (tags or [])
    if skip_arc_tracker:
        result["arc_tracker"] = None
    else:
        result["arc_tracker"] = build_character_arc_tracker(
            char,
            states=states,
            relationships=relationships,
            counterpart_names=counterpart_names,
            voice_profile=voice_profile,
            total_chapters=total_chapters,
        )
    return result


def serialize_reader_character(
    char: Character,
    *,
    trait_snapshot: dict[str, Any] | None = None,
    relationship_summaries: list[str] | None = None,
) -> dict[str, Any]:
    resolved_traits = dict(cast(dict[str, Any], trait_snapshot or char.trait_state or {}))
    visibility_state, approval_state, approval_source, approval_reason_codes = character_governance(char)
    return {
        "id": str(char.id),
        "name": char.name,
        "aliases": char.aliases or [],
        "alias_records": serialize_character_alias_records(char),
        "role": char.role,
        "first_chapter": char.first_chapter,
        "last_seen_chapter": char.last_seen_chapter,
        "status": character_status(char),
        "description": compose_character_description(
            trait_state=resolved_traits,
            archetype=char.archetype,
            arc_summary=char.arc_summary,
            personality_tags=char.personality_tags or [],
            motivations=char.motivations or [],
            relationship_summaries=relationship_summaries or [],
        ),
        "trait_state": resolved_traits,
        "personality_tags": char.personality_tags or [],
        "motivations": char.motivations or [],
        "fears": char.fears or [],
        "archetype": char.archetype,
        "arc_summary": char.arc_summary,
        "mention_count": char.mention_count or 0,
        "is_manual": getattr(char, "is_manual", False),
        "analysis_metadata": build_character_analysis_payload(char),
        "visibility_state": visibility_state,
        "approval_state": approval_state,
        "approval_source": approval_source,
        "approval_reason_codes": approval_reason_codes,
        "approval_updated_at": getattr(char, "approval_updated_at", None),
        "goal": char.goal,
        "lie_they_believe": char.lie_they_believe,
        "backstory_wound": char.backstory_wound,
        "arc_type": char.arc_type,
        "growth_events": char.growth_events or [],
        "graph_visibility_override": get_graph_visibility_override(char),
        "relationship_summaries": clean_string_list(relationship_summaries or []),
    }


def build_character_roster_snapshot(characters: Sequence[Character]) -> list[dict[str, Any]]:
    roster: list[dict[str, Any]] = []
    for character in characters:
        roster.append(
            {
                "id": str(character.id),
                "name": character.name,
                "aliases": clean_string_list(character.aliases or []),
                "role": character.role,
                "summary": clean_optional_text(
                    compose_character_description(
                        trait_state=character.trait_state or {},
                        archetype=character.archetype,
                        arc_summary=character.arc_summary,
                        personality_tags=character.personality_tags or [],
                        motivations=character.motivations or [],
                    )
                ),
                "is_manual": bool(getattr(character, "is_manual", False)),
            }
        )
    return roster


def is_role_only_character_name(name: str | None) -> bool:
    normalized = normalize_character_name(name)
    if not normalized:
        return False
    if normalized in ROLE_ONLY_REFERENCE_WORDS:
        return True
    tokens = normalized.split()
    return bool(tokens and all(token in ROLE_ONLY_REFERENCE_WORDS for token in tokens))


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


def build_character_mention_cluster_key(name: str | None, aliases: Sequence[str] | None = None) -> str:
    parts = [normalize_character_name(name), *(normalize_character_name(alias) for alias in aliases or [])]
    parts = sorted({part for part in parts if part})
    if not parts:
        return ""
    return parts[0]


def _context_links_family_role_to_name(role_name: str, proper_name: str, text: str) -> bool:
    anchor, role = family_role_reference(role_name)
    normalized_proper = normalize_character_name(proper_name)
    if not anchor or not role or not normalized_proper or not text:
        return False
    anchor_phrase = rf"\b{re.escape(anchor)}(?:'s|\u2019s) {re.escape(role)}\b"
    proper_phrase = rf"\b{re.escape(normalized_proper)}\b"
    patterns = (
        rf"{anchor_phrase}[^.?!\n]{{0,80}}{proper_phrase}",
        rf"{proper_phrase}[^.?!\n]{{0,80}}{anchor_phrase}",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _entity_display_name(entity: Mapping[str, Any]) -> str:
    return " ".join(str(entity.get("name") or "").split()).strip()


def _entity_source_text(entity: Mapping[str, Any]) -> str:
    return " ".join(str(entity.get("_source_text") or "").split()).strip()


def _entity_aliases(entity: Mapping[str, Any]) -> list[str]:
    return clean_string_list(entity.get("aliases") if isinstance(entity.get("aliases"), list) else [])


def _mention_entity_evidence(entity: Mapping[str, Any]) -> dict[str, Any]:
    evidence = entity.get("evidence")
    return dict(evidence) if isinstance(evidence, dict) else {}


def _entity_mentions_linked_in_text(left_name: str, right_name: str, text: str) -> bool:
    if not left_name or not right_name or not text:
        return False

    left_anchor, left_role = family_role_reference(left_name)
    right_anchor, right_role = family_role_reference(right_name)
    normalized_left = normalize_character_name(left_name)
    normalized_right = normalize_character_name(right_name)

    def _phrase(name: str, role: str | None) -> str:
        return role or normalize_character_name(name)

    left_phrase = _phrase(left_name, left_role if left_role else ("chief clerk" if normalized_left.endswith("chief clerk") else None))
    right_phrase = _phrase(right_name, right_role if right_role else ("chief clerk" if normalized_right.endswith("chief clerk") else None))
    escaped_left = re.escape(left_phrase)
    escaped_right = re.escape(right_phrase)
    if not escaped_left or not escaped_right:
        return False

    patterns = (
        rf"\b{escaped_left}\b[^.?!\n]{{0,80}}\b{escaped_right}\b",
        rf"\b{escaped_right}\b[^.?!\n]{{0,80}}\b{escaped_left}\b",
    )
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True

    if left_role and left_anchor:
        anchor_patterns = (
            rf"\b{re.escape(left_anchor)}['’]s {re.escape(left_role)}\b[^.?!\n]{{0,80}}\b{re.escape(normalized_right)}\b",
            rf"\b{re.escape(normalized_right)}\b[^.?!\n]{{0,80}}\b{re.escape(left_anchor)}['’]s {re.escape(left_role)}\b",
        )
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in anchor_patterns):
            return True
    if right_role and right_anchor:
        anchor_patterns = (
            rf"\b{re.escape(right_anchor)}['’]s {re.escape(right_role)}\b[^.?!\n]{{0,80}}\b{re.escape(normalized_left)}\b",
            rf"\b{re.escape(normalized_left)}\b[^.?!\n]{{0,80}}\b{re.escape(right_anchor)}['’]s {re.escape(right_role)}\b",
        )
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in anchor_patterns):
            return True

    return False


def _character_entity_matches_cluster(candidate: Mapping[str, Any], cluster: Mapping[str, Any]) -> bool:
    from app.engine.character.deduplicator import names_equivalent

    candidate_name = _entity_display_name(candidate)
    cluster_name = _entity_display_name(cluster)
    candidate_aliases = _entity_aliases(candidate)
    cluster_aliases = _entity_aliases(cluster)
    if not candidate_name or not cluster_name:
        return False
    candidate_title = _leading_title(candidate_name)
    cluster_title = _leading_title(cluster_name)
    if (candidate_title or cluster_title) and partition_identity_key(candidate_name) != partition_identity_key(cluster_name):
        return False
    candidate_family_role = family_role_reference(candidate_name)[1]
    cluster_family_role = family_role_reference(cluster_name)[1]
    if candidate_family_role or cluster_family_role:
        return normalize_character_name(candidate_name) == normalize_character_name(cluster_name)
    if is_role_only_character_name(candidate_name) or is_role_only_character_name(cluster_name):
        return normalize_character_name(candidate_name) == normalize_character_name(cluster_name)
    if names_equivalent(candidate_name, candidate_aliases, cluster_name, cluster_aliases):
        return True

    source_text = " ".join(filter(None, [_entity_source_text(candidate), _entity_source_text(cluster)]))
    if _context_links_family_role_to_name(candidate_name, cluster_name, source_text):
        return True
    if _context_links_family_role_to_name(cluster_name, candidate_name, source_text):
        return True

    candidate_keys = {build_character_mention_cluster_key(candidate_name, candidate_aliases), *(normalize_character_name(alias) for alias in candidate_aliases)}
    cluster_keys = {build_character_mention_cluster_key(cluster_name, cluster_aliases), *(normalize_character_name(alias) for alias in cluster_aliases)}
    candidate_keys.discard("")
    cluster_keys.discard("")
    return bool(candidate_keys & cluster_keys)


def _cluster_verifier_summary(cluster: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    verdicts: list[str] = []
    reasons: list[str] = []
    local_totals = {
        "mention_count": 0,
        "person_context_mentions": 0,
        "mid_sentence_mentions": 0,
        "sentence_start_mentions": 0,
        "subject_action_mentions": 0,
        "person_ner_mentions": 0,
        "non_person_ner_mentions": 0,
        "interjection_like_mentions": 0,
    }
    local_windows: list[dict[str, Any]] = []
    for item in cluster:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        verifier = evidence.get("verifier") if isinstance(evidence, dict) else {}
        local = verifier.get("local") if isinstance(verifier, dict) else {}
        final = verifier.get("final") if isinstance(verifier, dict) else {}
        if isinstance(local, dict):
            for field in local_totals:
                local_totals[field] += int(local.get(field) or 0)
            for window in local.get("windows") or []:
                if isinstance(window, dict):
                    local_windows.append(dict(window))
        if not isinstance(final, dict):
            continue
        verdict = str(final.get("confidence_band") or "").strip()
        if verdict:
            verdicts.append(verdict)
        for reason in final.get("reasons") or []:
            cleaned = str(reason or "").strip()
            if cleaned and cleaned not in reasons:
                reasons.append(cleaned)
    if not verdicts:
        return None
    unique = set(verdicts)
    if unique == {"accept"}:
        band = "accept"
        is_person_like = True
    elif unique == {"reject"}:
        band = "reject"
        is_person_like = False
    else:
        band = "review"
        is_person_like = False
    return {
        "local": {
            **local_totals,
            "windows": local_windows[:8],
        },
        "local_summary": {
            "member_verdicts": verdicts,
        },
        "llm": {"used": any("llm_" in reason for reason in reasons)},
        "final": {
            "confidence_band": band,
            "is_person_like": is_person_like,
            "reasons": reasons,
        },
    }


def cluster_character_entities(entities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[list[dict[str, Any]]] = []
    for raw in entities:
        entity = dict(raw)
        if not _entity_display_name(entity):
            continue
        matched_cluster: list[dict[str, Any]] | None = None
        for cluster in clusters:
            if any(_character_entity_matches_cluster(entity, member) for member in cluster):
                matched_cluster = cluster
                break
        if matched_cluster is None:
            clusters.append([entity])
            continue
        matched_cluster.append(entity)

    aggregated: list[dict[str, Any]] = []
    for cluster in clusters:
        def _family_role_like_display(display_name: str) -> bool:
            _family_anchor, family_role = family_role_reference(display_name)
            return bool(
                family_role
                or re.search(
                    r"(?:'s|\u2019s|\bs\b)\s+(?:aunt|brother|father|mother|sister|uncle)\b",
                    display_name.casefold(),
                )
            )

        def _cluster_primary_rank(item: Mapping[str, Any]) -> tuple[int, int, int, int, float]:
            display_name = _entity_display_name(item)
            family_role_like = _family_role_like_display(display_name)
            proper_name = (
                not is_role_only_character_name(display_name)
                and not family_role_like
            )
            return (
                1 if proper_name else 0,
                int(len(entity_words(display_name)) >= 2 and not family_role_like),
                int((_mention_entity_evidence(item).get("strong_mention_count") or 0)),
                int((_mention_entity_evidence(item).get("mention_count") or 0)),
                float(item.get("confidence") or 0.0),
            )

        ranked = sorted(
            cluster,
            key=_cluster_primary_rank,
            reverse=True,
        )
        primary = dict(ranked[0])
        if _family_role_like_display(_entity_display_name(primary)):
            proper_ranked = [
                item
                for item in ranked
                if not _family_role_like_display(_entity_display_name(item))
                and not is_role_only_character_name(_entity_display_name(item))
            ]
            if proper_ranked:
                primary = dict(proper_ranked[0])
        cluster_names = clean_string_list([_entity_display_name(item) for item in cluster])
        cluster_aliases = merge_list_values(*(item.get("aliases") if isinstance(item.get("aliases"), list) else [] for item in cluster))
        merged_traits: dict[str, Any] = {}
        evidence = dict(_mention_entity_evidence(primary))
        passages: list[str] = []
        total_mentions = 0
        strong_mentions = 0
        for item in cluster:
            merged_traits = merge_trait_states(merged_traits, item.get("traits") if isinstance(item.get("traits"), dict) else {})
            item_evidence = _mention_entity_evidence(item)
            total_mentions += int(item_evidence.get("mention_count") or 0)
            strong_mentions += int(item_evidence.get("strong_mention_count") or 0)
            passages.extend(clean_string_list(item_evidence.get("snippets") if isinstance(item_evidence.get("snippets"), list) else []))

        primary["aliases"] = filter_character_identity_aliases(
            primary.get("name"),
            merge_list_values(cluster_aliases, cluster_names),
        )
        primary["traits"] = merged_traits
        primary["confidence"] = max(float(item.get("confidence") or 0.0) for item in cluster)
        evidence.update(
            {
                "mention_count": total_mentions or int(evidence.get("mention_count") or 0),
                "strong_mention_count": strong_mentions or int(evidence.get("strong_mention_count") or 0),
                "cluster_size": len(cluster),
                "cluster_mention_count": total_mentions or int(evidence.get("mention_count") or 0),
                "cluster_names": cluster_names,
                "resolver_status": "clustered" if len(cluster) > 1 else "single",
                "snippets": clean_string_list(passages)[:6],
            }
        )
        verifier_summary = _cluster_verifier_summary(cluster)
        if verifier_summary is not None:
            evidence["verifier"] = verifier_summary
        primary["evidence"] = evidence
        primary["resolver_status"] = str(evidence.get("resolver_status") or "single")
        primary["canonical_confidence"] = max(
            float(primary.get("confidence") or 0.0),
            min(0.99, 0.35 + (0.1 * len(cluster)) + (0.08 * min(strong_mentions, 4))),
        )
        primary["cluster_members"] = [
            {
                "name": _entity_display_name(item),
                "aliases": _entity_aliases(item),
                "source_batch_key": item.get("_source_batch_key"),
                "source_text": _entity_source_text(item),
                "evidence": _mention_entity_evidence(item),
            }
            for item in cluster
        ]
        aggregated.append(primary)

    return aggregated


async def record_character_mention(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    raw_name: str,
    normalized_name: str,
    source_batch_key: str | None = None,
    cluster_key: str | None = None,
    mention_text: str | None = None,
    matched_character_id: uuid.UUID | None = None,
    resolver_status: str = "unresolved",
    resolver_reasons: Sequence[object] | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> CharacterMention:
    cleaned_mention_text = clean_optional_text(mention_text)
    stmt = select(CharacterMention).where(
        CharacterMention.book_id == book_id,
        CharacterMention.chapter_number == chapter_number,
        CharacterMention.normalized_name == normalized_name,
        CharacterMention.source_batch_key == source_batch_key,
        CharacterMention.cluster_key == cluster_key,
        CharacterMention.mention_text == cleaned_mention_text,
    )
    mention = (await db.execute(stmt)).scalar_one_or_none()
    if mention is None:
        mention = CharacterMention(
            book_id=book_id,
            chapter_number=chapter_number,
            raw_name=raw_name,
            normalized_name=normalized_name,
            source_batch_key=source_batch_key,
            cluster_key=cluster_key,
        )
        db.add(mention)
    mention.raw_name = clean_optional_text(raw_name) or raw_name
    mention.normalized_name = normalized_name
    mention.source_batch_key = source_batch_key
    mention.cluster_key = cluster_key
    mention.mention_text = cleaned_mention_text
    mention.matched_character_id = matched_character_id
    mention.resolver_status = clean_optional_text(resolver_status) or "unresolved"
    mention.resolver_reasons = _clean_reason_codes(resolver_reasons)
    merged_evidence = dict(mention.evidence or {})
    if evidence:
        merged_evidence.update(dict(evidence))
    mention.evidence = merged_evidence
    await db.flush()
    return mention


def resolve_character_reference_from_roster(
    characters: Sequence[Character],
    raw_name: str | None,
    *,
    context_text: str | None = None,
) -> Character | None:
    from app.engine.character.deduplicator import names_equivalent

    candidate_name = " ".join(str(raw_name or "").split()).strip()
    if not candidate_name:
        return None

    scored: list[tuple[int, Character]] = []
    normalized_candidate = normalize_character_name(candidate_name)
    candidate_anchor, candidate_role = family_role_reference(candidate_name)
    for character in characters:
        aliases = clean_string_list(character.aliases or [])
        score = 0
        if not candidate_role:
            if names_equivalent(candidate_name, [], character.name, aliases):
                score += 90
            elif normalized_candidate == normalize_character_name(character.name):
                score += 85
            elif normalized_candidate and normalized_candidate in {normalize_character_name(alias) for alias in aliases}:
                score += 82

        joined_names = [character.name, *aliases]
        if context_text and any(
            _entity_mentions_linked_in_text(candidate_name, value, context_text)
            for value in joined_names
            if value
        ):
            score += 24
        if context_text and any(
            _context_links_family_role_to_name(candidate_name, value, context_text)
            or _context_links_family_role_to_name(value, candidate_name, context_text)
            for value in joined_names
            if value
        ):
            score += 72

        if candidate_anchor and candidate_role and normalize_character_name(character.name) == candidate_anchor:
            score -= 32

        if is_role_only_character_name(candidate_name) and not is_role_only_character_name(character.name):
            score -= 12

        if score > 0:
            scored.append((score, character))

    if not scored:
        return None

    scored.sort(key=lambda item: (item[0], int(item[1].mention_count or 0)), reverse=True)
    best_score, best_character = scored[0]
    if best_score < 60:
        return None
    if len(scored) > 1 and scored[1][0] >= best_score - 8:
        return None
    return best_character


def _character_candidate_identity_key(
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    source_batch_key: str | None,
    normalized_name: str,
) -> tuple[str, int, str, str]:
    return (str(book_id), chapter_number, str(source_batch_key or ""), normalized_name)


def _clean_reason_codes(values: Sequence[object] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        item = str(raw or "").strip()
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


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
        "chapter_number": int(candidate.chapter_number or 0),
        "raw_name": candidate.raw_name,
        "proposed_name": candidate.proposed_name,
        "normalized_name": candidate.normalized_name,
        "aliases": clean_string_list(candidate.aliases or []),
        "matched_character_id": str(candidate.matched_character_id) if candidate.matched_character_id else None,
        "status": candidate.status,
        "confidence": int(candidate.confidence or 0),
        "reason_codes": _clean_reason_codes(candidate.reason_codes or []),
        "evidence": normalized_evidence,
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
        "matched_character_a_id": str(candidate.matched_character_a_id) if candidate.matched_character_a_id else None,
        "matched_character_b_id": str(candidate.matched_character_b_id) if candidate.matched_character_b_id else None,
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
        serialize_character_detail(character)
        for character in shadow_characters or []
    ]
    serialized_decision_events = [
        serialize_character_decision_event(event)
        for event in decision_events or []
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
) -> dict[str, Any]:
    return await run_read_with_retry(
        db,
        lambda: _list_character_review_data_once(db, book_id=book_id),
    )


async def _list_character_review_data_once(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[str, Any]:
    candidates = (
        await db.execute(
            select(CharacterCandidate)
            .where(
                CharacterCandidate.book_id == book_id,
                CharacterCandidate.status.in_(
                    (
                        CHARACTER_CANDIDATE_PENDING,
                        CHARACTER_CANDIDATE_ACCEPTED,
                        CHARACTER_CANDIDATE_PROMOTED,
                    )
                ),
            )
            .order_by(CharacterCandidate.chapter_number, CharacterCandidate.created_at)
        )
    ).scalars().all()
    duplicate_suggestions = (
        await db.execute(
            select(CharacterDuplicateSuggestion)
            .where(
                CharacterDuplicateSuggestion.book_id == book_id,
                CharacterDuplicateSuggestion.status == CHARACTER_DUPLICATE_PENDING,
                CharacterDuplicateSuggestion.confidence >= 75,
            )
            .order_by(CharacterDuplicateSuggestion.confidence.desc(), CharacterDuplicateSuggestion.created_at)
        )
    ).scalars().all()
    relationship_candidates = (
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
            .order_by(CharacterRelationshipCandidate.chapter_number, CharacterRelationshipCandidate.created_at)
        )
    ).scalars().all()
    character_rows = (
        await db.execute(
            select(Character)
            .options(selectinload(Character.alias_records))
            .where(Character.book_id == book_id)
        )
    ).scalars().all()
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
        await db.execute(
            select(CharacterIdentityAction.action_type).where(CharacterIdentityAction.book_id == book_id)
        )
    ).scalars().all()
    auto_actions_summary = dict(Counter(identity_actions))
    decision_events = (
        await db.execute(
            select(CharacterDecisionEvent)
            .where(CharacterDecisionEvent.book_id == book_id)
            .order_by(CharacterDecisionEvent.created_at.desc())
            .limit(40)
        )
    ).scalars().all()
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


async def record_character_candidate(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
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
    candidate.normalized_name = normalized_name
    candidate.aliases = _clean_candidate_aliases(aliases, candidate.proposed_name)
    candidate.matched_character_id = matched_character_id
    candidate.status = status
    candidate.confidence = _normalize_candidate_confidence(confidence)
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
        visibility_state, approval_state, approval_source, _approval_reason_codes = character_governance(character)
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
    normalized_visibility = normalize_character_visibility_state(visibility_state) or CHARACTER_VISIBILITY_QUARANTINED
    normalized_approval = normalize_character_approval_state(approval_state) or CHARACTER_APPROVAL_PENDING_REVIEW
    normalized_source = normalize_character_approval_source(approval_source) or CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW
    character.visibility_state = normalized_visibility
    character.approval_state = normalized_approval
    character.approval_source = normalized_source
    character.approval_reason_codes = _clean_reason_code_values(reason_codes)
    character.approval_updated_at = datetime.now(UTC)
    metadata = dict(character.analysis_metadata or {})
    metadata["user_reviewed"] = True
    metadata["trust_tier"] = (
        CHARACTER_TRUST_TIER_VISIBLE
        if normalized_visibility == CHARACTER_VISIBILITY_VISIBLE and normalized_approval in {CHARACTER_APPROVAL_APPROVED, CHARACTER_APPROVAL_PROTECTED}
        else CHARACTER_TRUST_TIER_REPAIRED_NOISE
        if normalized_visibility == CHARACTER_VISIBILITY_NOISE or normalized_approval == CHARACTER_APPROVAL_REJECTED
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


def _extract_candidate_snippets(evidence: Mapping[str, Any], candidate: CharacterCandidate) -> list[str]:
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
        snippets.append(f"{candidate.proposed_name} review candidate from chapter {int(candidate.chapter_number or 0)}.")
    return dedupe_preserve_order(snippets)[:6]


def _normalize_candidate_evidence(candidate: CharacterCandidate) -> dict[str, Any]:
    evidence = dict(candidate.evidence or {})
    cluster_names = _coerce_string_list(evidence.get("cluster_names"))
    if not cluster_names:
        cluster_names = _coerce_string_list(evidence.get("cluster_key"))
    if not cluster_names:
        cluster_names = _clean_text_list([candidate.proposed_name, candidate.raw_name, *(candidate.aliases or [])])
    cluster_size = max(1, _coerce_int(evidence.get("cluster_size"), fallback=len(cluster_names) or 1))
    cluster_mention_count = max(
        0,
        _coerce_int(
            evidence.get("cluster_mention_count"),
            fallback=_coerce_int(evidence.get("mention_count"), fallback=_coerce_int(evidence.get("strong_mention_count"), fallback=0)),
        ),
    )
    resolver_status = clean_optional_text(evidence.get("resolver_status")) or "needs_review"
    resolver_reasons = _coerce_string_list(evidence.get("resolver_reasons")) or _clean_reason_codes(candidate.reason_codes or [])
    canonical_confidence = _coerce_float(evidence.get("canonical_confidence"))
    if canonical_confidence is None:
        canonical_confidence = round(max(0.0, min(1.0, float(candidate.confidence or 0) / 100.0)), 2)
    grounding_coverage = _coerce_float(evidence.get("grounding_coverage"))
    if grounding_coverage is None:
        denominator = max(1, cluster_size)
        grounding_coverage = round(min(1.0, cluster_mention_count / denominator), 2) if cluster_mention_count > 0 else 0.0
    snippets = _extract_candidate_snippets(evidence, candidate)
    normalized = dict(evidence)
    normalized.update({
        "cluster_names": cluster_names,
        "cluster_size": cluster_size,
        "cluster_mention_count": cluster_mention_count,
        "resolver_status": resolver_status,
        "resolver_reasons": resolver_reasons,
        "canonical_confidence": canonical_confidence,
        "grounding_coverage": grounding_coverage,
        "snippets": snippets,
    })
    return normalized


def _normalize_duplicate_shared_evidence(
    suggestion: CharacterDuplicateSuggestion,
    *,
    primary: Character | None = None,
    secondary: Character | None = None,
) -> dict[str, Any]:
    shared = dict(suggestion.shared_evidence or {})
    shared_cluster_keys = _coerce_string_list(shared.get("shared_cluster_keys"))
    shared_chapters = sorted({
        chapter
        for chapter in (_coerce_int(value, fallback=0) for value in _coerce_string_list(shared.get("shared_chapters")))
        if chapter > 0
    })
    shared["shared_cluster_keys"] = shared_cluster_keys
    shared["shared_chapters"] = shared_chapters
    shared["embedding_similarity"] = _coerce_float(shared.get("embedding_similarity"))
    shared["primary_is_protected"] = bool(primary and is_protected_character(primary))
    shared["secondary_is_protected"] = bool(secondary and is_protected_character(secondary))
    shared["primary_is_manual"] = bool(primary and getattr(primary, "is_manual", False))
    shared["secondary_is_manual"] = bool(secondary and getattr(secondary, "is_manual", False))
    shared["primary_is_curated"] = bool(primary and bool((primary.analysis_metadata or {}).get("user_curated")))
    shared["secondary_is_curated"] = bool(secondary and bool((secondary.analysis_metadata or {}).get("user_curated")))
    return shared


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
            CharacterCandidate.matched_character_id.in_((primary_character_id, secondary_character_id)),
        )
    )
    candidates = result.scalars().all()
    for candidate in candidates:
        candidate.matched_character_id = primary_character_id
        candidate.status = CHARACTER_CANDIDATE_MERGED


def _candidate_entity_payload(candidate: CharacterCandidate) -> dict[str, Any]:
    evidence = dict(candidate.evidence or {})
    entity = evidence.get("entity") if isinstance(evidence.get("entity"), dict) else {}
    payload = dict(entity)
    payload["name"] = clean_optional_text(payload.get("name")) or candidate.proposed_name
    payload["aliases"] = payload.get("aliases") if isinstance(payload.get("aliases"), list) else list(candidate.aliases or [])
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


async def promote_character_candidate(
    db: AsyncSession,
    *,
    candidate: CharacterCandidate,
) -> Character:
    entity = _candidate_entity_payload(candidate)
    if candidate.matched_character_id is not None:
        existing = await db.get(Character, candidate.matched_character_id)
        if existing is not None and existing.book_id == candidate.book_id:
            updated = merge_profile_fields(existing, {
                **entity,
                "first_chapter": min(int(candidate.chapter_number or 1), int(existing.first_chapter or 1)),
                "last_seen_chapter": max(int(existing.last_seen_chapter or existing.first_chapter or 1), int(candidate.chapter_number or 1)),
            })
            for key, value in updated.items():
                setattr(existing, key, value)
            _approve_character_from_review(
                existing,
                reason_codes=["review_candidate_promoted", *list(candidate.reason_codes or [])],
                action="character_review_promoted",
                details={"candidate_id": str(candidate.id)},
            )
            candidate.status = CHARACTER_CANDIDATE_ACCEPTED
            return existing

    character = Character(**build_character_profile(entity, candidate.book_id, int(candidate.chapter_number or 1)))
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
    return character


async def attach_character_candidate(
    db: AsyncSession,
    *,
    candidate: CharacterCandidate,
    character: Character,
) -> Character:
    updated = merge_profile_fields(character, {
        **_candidate_entity_payload(candidate),
        "first_chapter": min(int(candidate.chapter_number or 1), int(character.first_chapter or 1)),
        "last_seen_chapter": max(int(character.last_seen_chapter or character.first_chapter or 1), int(candidate.chapter_number or 1)),
    })
    for key, value in updated.items():
        setattr(character, key, value)
    candidate.matched_character_id = character.id
    candidate.status = CHARACTER_CANDIDATE_ACCEPTED
    if character.approval_state == CHARACTER_APPROVAL_PENDING_REVIEW or character.visibility_state != CHARACTER_VISIBILITY_VISIBLE:
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
        await db.execute(
            select(CharacterMention)
            .where(CharacterMention.book_id == character.book_id, CharacterMention.matched_character_id == character.id)
            .order_by(CharacterMention.chapter_number, CharacterMention.created_at)
        )
    ).scalars().all()
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
        confidence=max(0, min(100, int(round(float(metadata.get("canonical_confidence") or 0) * 100)))),
        reason_codes=["manual_demoted_for_review", *list(reason_codes or [])],
        evidence={
            "cluster_names": cluster_names,
            "cluster_size": max(1, int(metadata.get("cluster_size") or len(cluster_names) or 1)),
            "cluster_mention_count": max(
                0,
                int(metadata.get("cluster_mention_count") or character.mention_count or len(mention_rows)),
            ),
            "resolver_status": "manual_demoted_for_review",
            "resolver_reasons": ["manual_demoted_for_review", *[str(code).strip() for code in (reason_codes or []) if str(code).strip()]],
            "canonical_confidence": metadata.get("canonical_confidence"),
            "grounding_coverage": metadata.get("grounding_coverage"),
            "snippets": snippets,
            "repair_source": {
                "character_id": str(character.id),
                "mention_count": int(character.mention_count or 0),
                "first_chapter": int(character.first_chapter or 0),
                "last_seen_chapter": int(character.last_seen_chapter or 0) if character.last_seen_chapter else None,
                "review_note": clean_optional_text(review_note),
            },
        },
        source_batch_key=f"manual-demote:{character.book_id}:{character.id}",
    )
    await db.flush()
    return candidate


def _normalize_merge_score_value(value: float) -> int:
    return max(0, min(96, int(round(value * 100))))


def _cosine_similarity(left: Sequence[float] | None, right: Sequence[float] | None) -> float:
    if left is None or right is None:
        return 0.0
    if len(left) == 0 or len(right) == 0 or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) * float(value) for value in left))
    right_norm = math.sqrt(sum(float(value) * float(value) for value in right))
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _chapter_window_overlap(left: Character, right: Character) -> bool:
    left_first = int(left.first_chapter or 0)
    left_last = int(left.last_seen_chapter or left.first_chapter or 0)
    right_first = int(right.first_chapter or 0)
    right_last = int(right.last_seen_chapter or right.first_chapter or 0)
    return max(left_first, right_first) <= min(left_last, right_last)


async def _load_character_mention_evidence_map(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[uuid.UUID, dict[str, Any]]:
    rows = (
        await db.execute(
            select(CharacterMention).where(
                CharacterMention.book_id == book_id,
                CharacterMention.matched_character_id.is_not(None),
            )
        )
    ).scalars().all()
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]] = {}
    for row in rows:
        if row.matched_character_id is None:
            continue
        bucket = evidence_by_character_id.setdefault(
            row.matched_character_id,
            {"cluster_keys": set(), "chapter_numbers": set(), "snippets": [], "mention_count": 0},
        )
        if row.cluster_key:
            cast(set[str], bucket["cluster_keys"]).add(row.cluster_key)
        cast(set[int], bucket["chapter_numbers"]).add(int(row.chapter_number or 0))
        bucket["mention_count"] = int(bucket.get("mention_count") or 0) + int((row.evidence or {}).get("mention_count") or 1)
        snippet = clean_optional_text(row.mention_text)
        if snippet and snippet not in bucket["snippets"]:
            cast(list[str], bucket["snippets"]).append(snippet)
    return evidence_by_character_id


def score_duplicate_characters(
    left: Character,
    right: Character,
    *,
    left_evidence: dict[str, Any] | None = None,
    right_evidence: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if getattr(left, "is_manual", False) and getattr(right, "is_manual", False):
        return None
    left_name = normalize_character_name(left.name)
    right_name = normalize_character_name(right.name)
    if not left_name or not right_name:
        return None
    if has_conflicting_title_identity(left.name, right.name):
        return None

    left_aliases = [normalize_character_name(alias) for alias in (left.aliases or []) if normalize_character_name(alias)]
    right_aliases = [normalize_character_name(alias) for alias in (right.aliases or []) if normalize_character_name(alias)]

    reasons: list[str] = []
    shared_tokens: list[str] = []
    score = 0.0

    if left_name == right_name:
        reasons.append("Exact name match")
        score += 0.95
    if left_name in right_aliases or right_name in left_aliases:
        reasons.append("Primary name appears in alias list")
        score += 0.30

    shared_aliases = [alias for alias in left_aliases if alias in right_aliases]
    if shared_aliases:
        reasons.append("Shared aliases detected")
        score += min(0.22, len(shared_aliases) * 0.08)

    left_tokens = {token for token in left_name.split() if token}
    right_tokens = {token for token in right_name.split() if token}
    shared_tokens = sorted(token for token in left_tokens & right_tokens if len(token) > 3)
    if shared_tokens:
        reasons.append("Overlapping name tokens")
        score += min(0.16, len(shared_tokens) * 0.06)

    if int(left.first_chapter or 0) == int(right.first_chapter or -1) and int(left.first_chapter or 0) > 0:
        reasons.append("First seen in the same chapter")
        score += 0.06

    if name_similarity(left.name, right.name) >= 0.88:
        reasons.append("High name similarity")
        score += 0.10

    shared_cluster_keys = sorted(
        set(cast(set[str], (left_evidence or {}).get("cluster_keys") or set()))
        & set(cast(set[str], (right_evidence or {}).get("cluster_keys") or set()))
    )
    if shared_cluster_keys:
        reasons.append("Shared mention clusters")
        score += min(0.24, len(shared_cluster_keys) * 0.10)
        if bool(family_role_reference(left.name)[1]) ^ bool(family_role_reference(right.name)[1]):
            reasons.append("Role reference shares grounded cluster with canonical name")
            score += 0.12

    if _chapter_window_overlap(left, right):
        reasons.append("Overlapping chapter windows")
        score += 0.05

    left_chapters = set(cast(set[int], (left_evidence or {}).get("chapter_numbers") or set()))
    right_chapters = set(cast(set[int], (right_evidence or {}).get("chapter_numbers") or set()))
    shared_chapters = sorted(left_chapters & right_chapters)
    if shared_chapters:
        reasons.append("Shared grounded chapters")
        score += min(0.10, len(shared_chapters) * 0.02)

    embedding_similarity = _cosine_similarity(left.embedding, right.embedding)
    if embedding_similarity >= 0.92:
        reasons.append("High embedding similarity")
        score += 0.12
    elif embedding_similarity >= 0.84:
        reasons.append("Related embedding similarity")
        score += 0.06

    if score < 0.75:
        return None

    primary = left if int(left.mention_count or 0) >= int(right.mention_count or 0) else right
    secondary = right if primary.id == left.id else left
    return {
        "primary": primary,
        "secondary": secondary,
        "confidence": _normalize_merge_score_value(min(0.96, score)),
        "reasons": reasons,
        "shared_evidence": {
            "shared_aliases": shared_aliases[:6],
            "shared_tokens": shared_tokens[:6],
            "shared_cluster_keys": shared_cluster_keys[:6],
            "shared_chapters": shared_chapters[:8],
            "embedding_similarity": round(embedding_similarity, 4) if embedding_similarity > 0 else None,
            "first_chapter_pair": [int(left.first_chapter or 0), int(right.first_chapter or 0)],
            "manual_anchor_present": bool(getattr(left, "is_manual", False) or getattr(right, "is_manual", False)),
        },
    }


async def refresh_character_duplicate_suggestions(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    characters: Sequence[Character] | None = None,
) -> list[CharacterDuplicateSuggestion]:
    if characters is None:
        characters = (
            await db.execute(
                select(Character)
                .where(Character.book_id == book_id)
                .order_by(Character.first_chapter, Character.name)
            )
        ).scalars().all()
    characters = [
        character
        for character in characters
        if getattr(character, "merged_into_character_id", None) is None
        and character_governance(character)[0] != CHARACTER_VISIBILITY_NOISE
        and character_governance(character)[1] != CHARACTER_APPROVAL_REJECTED
    ]

    exact_groups: dict[str, list[Character]] = defaultdict(list)
    for character in characters:
        normalized = normalize_character_name(character.name)
        if normalized:
            exact_groups[normalized].append(character)

    merged_any = False
    for exact_matches in exact_groups.values():
        if len(exact_matches) < 2:
            continue
        ordered = sorted(
            exact_matches,
            key=lambda item: (int(item.mention_count or 0), -int(item.first_chapter or 0)),
            reverse=True,
        )
        primary = ordered[0]
        for secondary in ordered[1:]:
            if is_protected_character(secondary):
                continue
            if await has_blocking_identity_constraint(
                db,
                book_id=book_id,
                left_character_id=primary.id,
                right_character_id=secondary.id,
            ):
                continue
            await merge_characters(db, primary.id, secondary.id, book_id)
            merged_any = True

    if merged_any:
        characters = (
            await db.execute(
                select(Character)
                .where(Character.book_id == book_id)
                .order_by(Character.first_chapter, Character.name)
            )
        ).scalars().all()
        characters = [
            character
            for character in characters
            if getattr(character, "merged_into_character_id", None) is None
            and character_governance(character)[0] != CHARACTER_VISIBILITY_NOISE
            and character_governance(character)[1] != CHARACTER_APPROVAL_REJECTED
        ]
    assign_unique_active_normalized_names(characters)

    full_name_by_first: dict[str, list[Character]] = defaultdict(list)
    single_token_characters: list[Character] = []
    for character in characters:
        tokens = normalize_character_name(character.name).split()
        if len(tokens) == 1:
            single_token_characters.append(character)
        elif len(tokens) >= 2:
            full_name_by_first[tokens[0]].append(character)

    for alias_character in single_token_characters:
        token = first_name_token(alias_character.name)
        full_matches = full_name_by_first.get(token) or []
        if not full_matches or is_protected_character(alias_character):
            continue
        target = sorted(full_matches, key=lambda item: int(item.mention_count or 0), reverse=True)[0]
        if int(target.mention_count or 0) < int(alias_character.mention_count or 0):
            continue
        if await has_blocking_identity_constraint(
            db,
            book_id=book_id,
            left_character_id=alias_character.id,
            right_character_id=target.id,
        ):
            continue
        await add_character_alias(
            db,
            character=target,
            alias_text=alias_character.name,
            alias_kind="first_name",
            source="duplicate_refresh",
            confidence=0.9,
        )
        alias_character.merged_into_character_id = target.id
        alias_character.is_auto_suppressed = True
        alias_character.suppression_reason = "single_token_first_name_alias"
        set_character_review_state(
            alias_character,
            visibility_state=CHARACTER_VISIBILITY_NOISE,
            approval_state=CHARACTER_APPROVAL_REJECTED,
            approval_source=CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
            reason_codes=["single_token_first_name_alias"],
            action="character_auto_alias_suppressed",
            details={"target_character_id": str(target.id)},
        )
        mention_rows = (
            await db.execute(
                select(CharacterMention).where(
                    CharacterMention.book_id == book_id,
                    CharacterMention.matched_character_id == alias_character.id,
                )
            )
        ).scalars().all()
        for mention in mention_rows:
            mention.matched_character_id = target.id
        await suppress_candidate(
            db,
            book_id=book_id,
            character_id=alias_character.id,
            surface_text=alias_character.name,
            candidate_kind="alias",
            reason="single_token_first_name_alias",
            confidence=0.9,
        )

    characters = [
        character
        for character in characters
        if getattr(character, "merged_into_character_id", None) is None
        and character_governance(character)[0] != CHARACTER_VISIBILITY_NOISE
        and character_governance(character)[1] != CHARACTER_APPROVAL_REJECTED
    ]

    existing_suggestions = (
        await db.execute(
            select(CharacterDuplicateSuggestion).where(CharacterDuplicateSuggestion.book_id == book_id)
        )
    ).scalars().all()
    existing_by_pair = {
        (str(item.primary_character_id), str(item.secondary_character_id)): item
        for item in existing_suggestions
    }
    active_pairs: set[tuple[str, str]] = set()
    mention_evidence_by_character_id = await _load_character_mention_evidence_map(db, book_id=book_id)

    for index, left in enumerate(characters):
        for right in characters[index + 1:]:
            suggestion = score_duplicate_characters(
                left,
                right,
                left_evidence=mention_evidence_by_character_id.get(left.id),
                right_evidence=mention_evidence_by_character_id.get(right.id),
            )
            if suggestion is None:
                continue
            primary = cast(Character, suggestion["primary"])
            secondary = cast(Character, suggestion["secondary"])
            if await has_blocking_identity_constraint(
                db,
                book_id=book_id,
                left_character_id=primary.id,
                right_character_id=secondary.id,
            ):
                continue
            pair_key = (str(primary.id), str(secondary.id))
            active_pairs.add(pair_key)
            existing = existing_by_pair.get(pair_key)
            if existing is None:
                existing = CharacterDuplicateSuggestion(
                    book_id=book_id,
                    primary_character_id=primary.id,
                    secondary_character_id=secondary.id,
                )
                db.add(existing)
            if existing.status != CHARACTER_DUPLICATE_ACCEPTED:
                existing.status = CHARACTER_DUPLICATE_PENDING
            existing.confidence = int(suggestion["confidence"])
            existing.reasons = _clean_reason_codes(cast(Sequence[object], suggestion["reasons"]))
            existing.shared_evidence = dict(cast(dict[str, Any], suggestion["shared_evidence"]))

    for pair_key, existing in existing_by_pair.items():
        if pair_key in active_pairs or existing.status == CHARACTER_DUPLICATE_ACCEPTED:
            continue
        existing.status = CHARACTER_DUPLICATE_DISMISSED
        existing.auto_dismissed = True
        existing.dismissal_reason = existing.dismissal_reason or "duplicate_score_below_threshold"

    await db.flush()
    return (
        await db.execute(
            select(CharacterDuplicateSuggestion)
            .where(CharacterDuplicateSuggestion.book_id == book_id)
            .order_by(CharacterDuplicateSuggestion.confidence.desc(), CharacterDuplicateSuggestion.created_at)
        )
    ).scalars().all()


# ─── Name / similarity helpers ───────────────────────────────────────────────

_NAME_TITLES = {
    "mr", "mrs", "ms", "miss", "dr", "sir", "lady", "lord", "prof", "professor",
    "capt", "captain", "commander", "master", "mistress",
}
_TITLE_IDENTITY_GROUPS = {
    "mr": "male",
    "master": "male",
    "sir": "male",
    "mrs": "female",
    "ms": "female",
    "miss": "female",
    "mistress": "female",
}


def normalize_character_name(name: str | None) -> str:
    if not name:
        return ""
    tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name) if token.casefold() not in _NAME_TITLES]
    return " ".join(tokens).casefold().strip()


def _leading_title(name: str | None) -> str:
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name or "")]
    return tokens[0] if tokens and tokens[0] in _NAME_TITLES else ""


def partition_identity_key(name: str | None) -> str:
    normalized = normalize_character_name(name)
    if not normalized:
        return ""
    title = _leading_title(name)
    return f"{title}:{normalized}" if title else normalized


def has_conflicting_title_identity(name1: str | None, name2: str | None) -> bool:
    left_group = _TITLE_IDENTITY_GROUPS.get(_leading_title(name1))
    right_group = _TITLE_IDENTITY_GROUPS.get(_leading_title(name2))
    return bool(left_group and right_group and left_group != right_group)


def filter_character_identity_aliases(name: str | None, aliases: Sequence[object] | None) -> list[str]:
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


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current = [i]
        for j, char_right in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (char_left != char_right)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _sequence_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def name_similarity(name1: str | None, name2: str | None) -> float:
    left = normalize_character_name(name1)
    right = normalize_character_name(name2)
    if not left or not right:
        return 0.0
    if left == right:
        if has_conflicting_title_identity(name1, name2):
            return 0.35
        return 1.0

    jw = _sequence_ratio(left, right)
    token_sort = _sequence_ratio(" ".join(sorted(left.split())), " ".join(sorted(right.split())))
    token_set = _sequence_ratio(" ".join(sorted(set(left.split()))), " ".join(sorted(set(right.split()))))
    score = max(jw, token_sort, token_set)

    if has_conflicting_title_identity(name1, name2):
        score = min(score, 0.35)

    if has_shared_surname(name1, name2) and score >= 0.70:
        score = min(1.0, score + 0.15)

    left_tokens = left.split()
    right_tokens = right.split()
    if (
        len(left_tokens) <= 2
        and len(right_tokens) <= 2
        and _levenshtein_distance(left, right) <= 2
    ):
        score = max(score, 0.9)

    if (
        len(left_tokens) >= 2
        and len(right_tokens) >= 2
        and (left.startswith(right) or right.startswith(left))
    ):
        score = max(score, 0.88)

    return min(score, 1.0)


def description_similarity(desc1: str | None, desc2: str | None) -> float:
    left = " ".join((desc1 or "").split()).strip()
    right = " ".join((desc2 or "").split()).strip()
    if not left or not right:
        return 0.0
    if left.casefold() == right.casefold():
        return 1.0
    try:
        left_tokens = _similarity_tokens(left)
        right_tokens = _similarity_tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0

        doc_freq: dict[str, int] = {}
        for token in set(left_tokens) | set(right_tokens):
            doc_freq[token] = int(token in left_tokens) + int(token in right_tokens)

        def _vector(tokens: list[str]) -> dict[str, float]:
            counts = Counter(tokens)
            total = len(tokens)
            vector: dict[str, float] = {}
            for token, count in counts.items():
                idf = math.log((2 + 1) / (doc_freq[token] + 1)) + 1
                vector[token] = (count / total) * idf
            return vector

        left_vec = _vector(left_tokens)
        right_vec = _vector(right_tokens)
        return _cosine_from_vectors(left_vec, right_vec)
    except Exception:
        return 0.0


def _similarity_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9]+", text.casefold()) if len(token) > 2]


def _cosine_from_vectors(left_vec: dict[str, float], right_vec: dict[str, float]) -> float:
    shared = set(left_vec) & set(right_vec)
    if not shared:
        return 0.0
    dot = sum(left_vec[token] * right_vec[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left_vec.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vec.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def clean_markdown_asterisks(text: str) -> str:
    return text.replace("**", "").replace("*", "")


def apply_manual_character_description(character: Character, description: str | None) -> None:
    cleaned = clean_optional_text(description)
    trait_state = dict(character.trait_state or {})
    if cleaned:
        trait_state["manual_description"] = {"value": cleaned, "confidence": 1.0, "type": "abstract"}
    else:
        trait_state.pop("manual_description", None)
    character.trait_state = trait_state


GRAPH_VISIBILITY_OVERRIDE_KEY = "graph_visibility_override"
GRAPH_VISIBILITY_OVERRIDE_VALUES = {"include", "exclude"}


def graph_visibility_override_value(trait_state: dict[str, Any] | None) -> str | None:
    if not isinstance(trait_state, dict):
        return None
    raw = trait_state.get(GRAPH_VISIBILITY_OVERRIDE_KEY)
    if isinstance(raw, dict):
        value = clean_optional_text(raw.get("value"))
    else:
        value = clean_optional_text(raw)
    if not value:
        return None
    normalized = value.casefold()
    return normalized if normalized in GRAPH_VISIBILITY_OVERRIDE_VALUES else None


def get_graph_visibility_override(character: Character) -> str | None:
    trait_state = getattr(character, "trait_state", None)
    return graph_visibility_override_value(trait_state if isinstance(trait_state, dict) else None)


def apply_graph_visibility_override(character: Character, override: str | None) -> None:
    normalized = clean_optional_text(override)
    trait_state = dict(character.trait_state or {})
    if not normalized:
        trait_state.pop(GRAPH_VISIBILITY_OVERRIDE_KEY, None)
        character.trait_state = trait_state
        return
    normalized = normalized.casefold()
    if normalized not in GRAPH_VISIBILITY_OVERRIDE_VALUES:
        raise ValueError("Graph visibility override must be include or exclude")
    trait_state[GRAPH_VISIBILITY_OVERRIDE_KEY] = {
        "value": normalized,
        "confidence": 1.0,
        "type": "abstract",
    }
    character.trait_state = trait_state


def build_manual_character(
    *,
    book_id: uuid.UUID,
    name: str,
    first_chapter: int,
    aliases: list[str] | None = None,
    role: str | None = None,
    description: str | None = None,
    goal: str | None = None,
    lie_they_believe: str | None = None,
    backstory_wound: str | None = None,
    arc_type: str | None = None,
    arc_summary: str | None = None,
    personality_tags: list[str] | None = None,
    motivations: list[str] | None = None,
    fears: list[str] | None = None,
) -> Character:
    cleaned_name = clean_optional_text(name)
    if not cleaned_name:
        raise ValueError("Character name cannot be empty")

    normalized_name = normalize_character_name(cleaned_name)
    cleaned_aliases = [
        alias
        for alias in clean_string_list(aliases)
        if normalize_character_name(alias) != normalized_name
    ]
    chapter_number = max(1, first_chapter)

    character = Character(
        book_id=book_id,
        name=cleaned_name,
        aliases=cleaned_aliases,
        role=role,
        first_chapter=chapter_number,
        last_seen_chapter=chapter_number,
        mention_count=1,
        trait_state={"manual_entry": {"value": "manual", "confidence": 0.0, "type": "abstract"}},
        personality_tags=clean_string_list(personality_tags),
        motivations=clean_string_list(motivations),
        fears=clean_string_list(fears),
        goal=clean_optional_text(goal),
        lie_they_believe=clean_optional_text(lie_they_believe),
        backstory_wound=clean_optional_text(backstory_wound),
        arc_type=clean_optional_text(arc_type),
        arc_summary=clean_optional_text(arc_summary),
        is_manual=True,
        visibility_state=CHARACTER_VISIBILITY_VISIBLE,
        approval_state=CHARACTER_APPROVAL_PROTECTED,
        approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
        approval_reason_codes=["manual_character"],
        approval_updated_at=datetime.now(UTC),
    )
    apply_manual_character_description(character, description)
    return character


def _manual_character_description_value(trait_state: dict[str, Any] | None) -> str | None:
    if not isinstance(trait_state, dict):
        return None
    manual = trait_state.get("manual_description")
    if not isinstance(manual, dict):
        return None
    return clean_optional_text(manual.get("value"))


def _merge_character_descriptions(primary_description: str | None, secondary_description: str | None) -> str | None:
    primary_clean = clean_optional_text(primary_description)
    secondary_clean = clean_optional_text(secondary_description)
    if not primary_clean:
        return secondary_clean
    if not secondary_clean:
        return primary_clean

    primary_key = primary_clean.casefold()
    secondary_key = secondary_clean.casefold()
    if primary_key == secondary_key:
        return primary_clean
    if primary_key in secondary_key:
        return secondary_clean
    if secondary_key in primary_key:
        return primary_clean

    separator = "" if primary_clean.endswith((".", "!", "?", ";", ":")) else "."
    return f"{primary_clean}{separator} {secondary_clean}"


def _normalize_character_reference(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _character_reference_values(character: Character) -> set[str]:
    values = {_normalize_character_reference(character.id), _normalize_character_reference(character.name)}
    values.update(_normalize_character_reference(alias) for alias in (character.aliases or []))
    return {value for value in values if value}


def _replace_reference_list(values: list[object] | None, *, matches: set[str], replacement: str) -> list[str]:
    replaced: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        candidate = " ".join(str(item or "").split()).strip()
        if not candidate:
            continue
        next_value = replacement if _normalize_character_reference(candidate) in matches else candidate
        if next_value.lower() in seen:
            continue
        seen.add(next_value.lower())
        replaced.append(next_value)
    return replaced


def _expand_reference_list(values: list[object] | None, *, matches: set[str], replacements: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    normalized_replacements = [" ".join(item.split()).strip() for item in replacements if " ".join(item.split()).strip()]
    for item in values or []:
        candidate = " ".join(str(item or "").split()).strip()
        if not candidate:
            continue
        next_values = normalized_replacements if _normalize_character_reference(candidate) in matches else [candidate]
        for next_value in next_values:
            key = next_value.lower()
            if key in seen:
                continue
            seen.add(key)
            expanded.append(next_value)
    return expanded


def _find_name_occurrences(text: str, candidate: str) -> int:
    cleaned = " ".join(str(candidate or "").split()).strip()
    if not cleaned:
        return 0
    pattern = re.compile(rf"(?<![A-Za-z]){re.escape(cleaned)}(?![A-Za-z])")
    return len(pattern.findall(text or ""))


async def find_earliest_character_mention_chapter(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    name: str,
    aliases: list[str] | None = None,
    upto_chapter: int | None = None,
) -> int | None:
    candidates = merge_list_values([name], aliases)
    if not candidates:
        return None

    filters = [BookChunk.text.ilike(f"%{candidate}%") for candidate in candidates if candidate]
    if not filters:
        return None

    query = (
        select(Chapter.number, BookChunk.text)
        .join(BookChunk, BookChunk.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id, or_(*filters))
        .order_by(Chapter.number.asc(), BookChunk.chunk_index.asc())
    )
    if upto_chapter is not None:
        query = query.where(Chapter.number <= upto_chapter)

    rows = (await db.execute(query)).all()
    for chapter_number, text in rows:
        if any(_find_name_occurrences(text or "", candidate) > 0 for candidate in candidates):
            return int(chapter_number)
    return None


async def find_earliest_character_mention_chapters(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    candidates_by_key: Mapping[Hashable, Sequence[str]],
    upto_chapter: int | None = None,
) -> dict[Hashable, int]:
    normalized_candidates: dict[Hashable, list[str]] = {}
    filters: list[Any] = []

    for key, raw_candidates in candidates_by_key.items():
        candidates = merge_list_values([], list(raw_candidates))
        if not candidates:
            continue
        normalized_candidates[key] = candidates
        filters.extend(BookChunk.text.ilike(f"%{candidate}%") for candidate in candidates if candidate)

    if not normalized_candidates or not filters:
        return {}

    query = (
        select(Chapter.number, BookChunk.text)
        .join(BookChunk, BookChunk.chapter_id == Chapter.id)
        .where(Chapter.book_id == book_id, or_(*filters))
        .order_by(Chapter.number.asc(), BookChunk.chunk_index.asc())
    )
    if upto_chapter is not None:
        query = query.where(Chapter.number <= upto_chapter)

    rows = (await db.execute(query)).all()
    resolved: dict[Hashable, int] = {}
    unresolved = set(normalized_candidates)
    for chapter_number, text in rows:
        if not unresolved:
            break
        chapter_text = text or ""
        for key in list(unresolved):
            if any(_find_name_occurrences(chapter_text, candidate) > 0 for candidate in normalized_candidates[key]):
                resolved[key] = int(chapter_number)
                unresolved.remove(key)

    return resolved


async def backfill_character_first_chapters_for_chapter_text(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    chapter_text: str | None,
) -> bool:
    if not chapter_text or not chapter_text.strip():
        return False

    characters = (
        await db.execute(
            select(Character)
            .where(Character.book_id == book_id, Character.first_chapter > chapter_number)
            .order_by(Character.first_chapter.asc(), Character.name.asc())
        )
    ).scalars().all()

    changed = False
    for character in characters:
        candidates = merge_list_values([character.name], character.aliases or [])
        if not any(_find_name_occurrences(chapter_text, candidate) > 0 for candidate in candidates):
            continue

        earliest_chapter = await find_earliest_character_mention_chapter(
            db,
            book_id=book_id,
            name=character.name,
            aliases=character.aliases or [],
            upto_chapter=chapter_number,
        )
        resolved_first_chapter = earliest_chapter or chapter_number
        if resolved_first_chapter >= character.first_chapter:
            continue

        character.first_chapter = resolved_first_chapter
        if character.last_seen_chapter is None or character.last_seen_chapter < resolved_first_chapter:
            character.last_seen_chapter = resolved_first_chapter
        changed = True

    return changed


def _collect_partition_evidence(
    chapter_rows: list[tuple[int, str]],
    *,
    name: str,
    aliases: list[str],
) -> dict[str, Any]:
    candidates = merge_list_values([name], aliases)
    snippets: list[str] = []
    chapter_counts: dict[int, int] = {}
    mention_count = 0
    for chapter_number, text in chapter_rows:
        score = sum(_find_name_occurrences(text, candidate) for candidate in candidates)
        if score <= 0:
            continue
        mention_count += score
        chapter_counts[chapter_number] = chapter_counts.get(chapter_number, 0) + score
        if len(snippets) < 6:
            snippets.append(text[:2200])
    ordered_chapters = sorted(chapter_counts)
    return {
        "chapter_counts": chapter_counts,
        "snippets": snippets,
        "mention_count": mention_count,
        "first_chapter": ordered_chapters[0] if ordered_chapters else None,
        "last_seen_chapter": ordered_chapters[-1] if ordered_chapters else None,
    }


def _partition_matches_entity(name: str, aliases: list[str], entity: dict[str, Any]) -> bool:
    from app.engine.character.deduplicator import names_equivalent

    entity_name = str(entity.get("name") or "").strip()
    entity_aliases = [str(alias) for alias in (entity.get("aliases") or []) if str(alias).strip()]
    if not entity_name:
        return False
    if names_equivalent(name, aliases, entity_name, entity_aliases):
        return True
    partition_keys = {normalize_character_name(name), *(normalize_character_name(alias) for alias in aliases)}
    entity_keys = {normalize_character_name(entity_name), *(normalize_character_name(alias) for alias in entity_aliases)}
    partition_keys.discard("")
    entity_keys.discard("")
    return bool(partition_keys & entity_keys)


def _merge_partition_entities(name: str, aliases: list[str], entities: list[dict[str, Any]]) -> dict[str, Any]:
    merged_traits: dict[str, Any] = {}
    merged_growth_events: list[dict] = []
    merged_personality: list[str] = []
    merged_motivations: list[str] = []
    merged_fears: list[str] = []
    merged_aliases = merge_list_values([name], aliases)
    merged: dict[str, Any] = {
        "name": name,
        "aliases": aliases,
        "role": None,
        "goal": None,
        "lie_they_believe": None,
        "backstory_wound": None,
        "arc_type": None,
        "arc_summary": None,
        "archetype": None,
    }

    for entity in entities:
        merged_traits = merge_trait_states(merged_traits, entity.get("traits") if isinstance(entity.get("traits"), dict) else {})
        merged_aliases = merge_list_values(merged_aliases, entity.get("aliases") if isinstance(entity.get("aliases"), list) else [])
        merged_personality = merge_list_values(merged_personality, entity.get("personality_tags") if isinstance(entity.get("personality_tags"), list) else [])
        merged_motivations = merge_list_values(merged_motivations, entity.get("motivations") if isinstance(entity.get("motivations"), list) else [])
        merged_fears = merge_list_values(merged_fears, entity.get("fears") if isinstance(entity.get("fears"), list) else [])
        if not merged["role"]:
            merged["role"] = entity.get("role")
        merged["goal"] = choose_richer_text(merged["goal"], entity.get("goal"))
        merged["lie_they_believe"] = choose_richer_text(merged["lie_they_believe"], entity.get("lie_they_believe"))
        merged["backstory_wound"] = choose_richer_text(merged["backstory_wound"], entity.get("backstory_wound"))
        merged["arc_type"] = choose_richer_text(merged["arc_type"], entity.get("arc_type"))
        merged["arc_summary"] = choose_richer_text(merged["arc_summary"], entity.get("arc_summary"))
        merged["archetype"] = choose_richer_text(merged["archetype"], entity.get("archetype"))
        growth_event = entity.get("growth_event")
        merged_growth_events = merge_growth_events(merged_growth_events, [growth_event] if isinstance(growth_event, dict) else [])

    merged["traits"] = merged_traits
    merged["aliases"] = [alias for alias in merged_aliases if normalize_character_name(alias) != normalize_character_name(name)]
    merged["personality_tags"] = merged_personality
    merged["motivations"] = merged_motivations
    merged["fears"] = merged_fears
    merged["growth_events"] = merged_growth_events
    return merged


async def _build_partition_payload(
    *,
    source: Character,
    book_id: uuid.UUID,
    name: str,
    aliases: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    if evidence["snippets"]:
        try:
            extracted = await extract_characters_and_relationships("\n\n".join(evidence["snippets"])[:12000])
            entities = [
                entity
                for entity in extracted.get("characters", [])
                if isinstance(entity, dict) and _partition_matches_entity(name, aliases, entity)
            ]
        except Exception:
            entities = []

    merged_entity = _merge_partition_entities(name, aliases, entities)
    trait_state = merge_trait_states({}, merged_entity.get("traits") if isinstance(merged_entity.get("traits"), dict) else {})
    first_chapter = int(evidence.get("first_chapter") or source.first_chapter or 1)
    last_seen_chapter = int(
        evidence.get("last_seen_chapter")
        or source.last_seen_chapter
        or source.first_chapter
        or first_chapter
    )
    mention_count = max(1, int(evidence.get("mention_count") or 0))

    return {
        "book_id": book_id,
        "name": name,
        "aliases": merged_entity.get("aliases") or aliases,
        "role": merged_entity.get("role") or source.role,
        "first_chapter": first_chapter,
        "last_seen_chapter": last_seen_chapter,
        "mention_count": mention_count,
        "trait_state": trait_state,
        "hair": flat(trait_state, "hair"),
        "eyes": flat(trait_state, "eyes"),
        "build": flat(trait_state, "build"),
        "age_descriptor": flat(trait_state, "age"),
        "distinguishing": flat(trait_state, "distinguishing"),
        "personality_tags": merged_entity.get("personality_tags") or [],
        "goal": merged_entity.get("goal"),
        "motivations": merged_entity.get("motivations") or [],
        "fears": merged_entity.get("fears") or [],
        "lie_they_believe": merged_entity.get("lie_they_believe"),
        "backstory_wound": merged_entity.get("backstory_wound"),
        "arc_type": merged_entity.get("arc_type"),
        "arc_summary": merged_entity.get("arc_summary"),
        "archetype": merged_entity.get("archetype"),
        "growth_events": merged_entity.get("growth_events") or [],
    }


def _best_partition_for_chapter(
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
    chapter_number: int | None,
) -> Character | None:
    if chapter_number is None:
        return None
    scored = [
        (int((evidence_by_character_id.get(character.id) or {}).get("chapter_counts", {}).get(chapter_number, 0)), character)
        for character in partitions
    ]
    scored = [item for item in scored if item[0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def _best_partition_for_text(
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
    text: str | None,
) -> Character | None:
    scored = []
    for character in partitions:
        candidates = merge_list_values([character.name], character.aliases or [])
        score = sum(_find_name_occurrences(text or "", candidate) for candidate in candidates)
        if score > 0:
            scored.append((score, character))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None
        return scored[0][1]
    return None


async def _reassign_partition_references(
    db: AsyncSession,
    *,
    source: Character,
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
) -> None:
    primary_partition = max(
        partitions,
        key=lambda character: int((evidence_by_character_id.get(character.id) or {}).get("mention_count", 0)),
    )
    reference_values = _character_reference_values(source)

    state_rows = (await db.execute(select(CharacterState).where(CharacterState.character_id == source.id))).scalars().all()
    for state in state_rows:
        target = _best_partition_for_chapter(partitions, evidence_by_character_id, state.at_chapter) or primary_partition
        state.character_id = target.id

    relationships = (
        await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.book_id == source.book_id,
                or_(
                    CharacterRelationship.character_a_id == source.id,
                    CharacterRelationship.character_b_id == source.id,
                ),
            )
        )
    ).scalars().all()
    for relationship in relationships:
        target = _best_partition_for_chapter(partitions, evidence_by_character_id, relationship.from_chapter) or primary_partition
        if relationship.character_a_id == source.id:
            relationship.character_a_id = target.id
        if relationship.character_b_id == source.id:
            relationship.character_b_id = target.id
        if relationship.character_a_id == relationship.character_b_id:
            await db.delete(relationship)

    plot_threads = (await db.execute(select(PlotThread).where(PlotThread.book_id == source.book_id))).scalars().all()
    for thread in plot_threads:
        updated_ids = _expand_reference_list(
            thread.character_ids,
            matches=reference_values,
            replacements=[character.name for character in partitions],
        )
        if updated_ids:
            thread.character_ids = updated_ids

    wiki_entries = (await db.execute(select(WikiEntry).where(WikiEntry.book_id == source.book_id))).scalars().all()
    for entry in wiki_entries:
        updated_related = _expand_reference_list(
            entry.related_char_ids,
            matches=reference_values,
            replacements=[str(character.id) for character in partitions],
        )
        if updated_related:
            entry.related_char_ids = updated_related

    chapter_summaries = (
        await db.execute(
            select(ChapterSummary, Chapter.number)
            .join(ChapterSummary.chapter)
            .where(Chapter.book_id == source.book_id)
        )
    ).all()
    for summary, chapter_number in chapter_summaries:
        target = _best_partition_for_chapter(partitions, evidence_by_character_id, chapter_number) or primary_partition
        key_events = [dict(event) if isinstance(event, dict) else event for event in (summary.key_events or [])]
        key_events_changed = False
        for event in key_events:
            if not isinstance(event, dict):
                continue
            involved = _expand_reference_list(
                event.get("involved_characters"),
                matches=reference_values,
                replacements=[str(target.id)],
            )
            if involved != list(event.get("involved_characters") or []):
                event["involved_characters"] = involved
                key_events_changed = True
        if key_events_changed:
            summary.key_events = key_events

        char_changes = [dict(change) if isinstance(change, dict) else change for change in (summary.char_changes or [])]
        char_changes_changed = False
        for change in char_changes:
            if not isinstance(change, dict):
                continue
            candidate = " ".join(str(change.get("character") or "").split()).strip()
            if candidate and _normalize_character_reference(candidate) in reference_values:
                change["character"] = target.name
                char_changes_changed = True
        if char_changes_changed:
            summary.char_changes = char_changes

    quotes = (await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == source.book_id))).scalars().all()
    for quote in quotes:
        if _normalize_character_reference(quote.character_name) not in reference_values:
            continue
        target = _best_partition_for_text(partitions, evidence_by_character_id, quote.quote_text) or primary_partition
        quote.character_name = target.name


async def partition_character(
    db: AsyncSession,
    *,
    source: Character,
    partitions: list[dict[str, list[str] | str]],
) -> list[Character]:
    cleaned_partitions: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for partition in partitions:
        cleaned_name = clean_optional_text(partition.get("name"))
        if not cleaned_name:
            continue
        normalized_name = normalize_character_name(cleaned_name)
        identity_key = partition_identity_key(cleaned_name)
        if not identity_key or identity_key in seen_names:
            continue
        seen_names.add(identity_key)
        aliases = [
            alias
            for alias in clean_string_list(partition.get("aliases") if isinstance(partition.get("aliases"), list) else [])
            if normalize_character_name(alias) != normalized_name
        ]
        cleaned_partitions.append({"name": cleaned_name, "aliases": aliases})

    if len(cleaned_partitions) < 2:
        raise ValueError("At least two distinct partition targets are required")

    chapter_rows = (
        await db.execute(
            select(Chapter.number, BookChunk.text)
            .join(BookChunk, BookChunk.chapter_id == Chapter.id)
            .where(BookChunk.book_id == source.book_id)
            .order_by(Chapter.number.asc(), BookChunk.chunk_index.asc())
        )
    ).all()

    created_partitions: list[Character] = []
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]] = {}
    for partition in cleaned_partitions:
        evidence = _collect_partition_evidence(
            chapter_rows,
            name=str(partition["name"]),
            aliases=[str(alias) for alias in partition["aliases"]],
        )
        payload = await _build_partition_payload(
            source=source,
            book_id=source.book_id,
            name=str(partition["name"]),
            aliases=[str(alias) for alias in partition["aliases"]],
            evidence=evidence,
        )
        character = Character(**payload)
        db.add(character)
        await db.flush()
        update_character_classification(character)
        created_partitions.append(character)
        evidence_by_character_id[character.id] = evidence

    await _reassign_partition_references(
        db,
        source=source,
        partitions=created_partitions,
        evidence_by_character_id=evidence_by_character_id,
    )
    await _dedupe_relationships(db, source.book_id)
    await db.delete(source)
    await db.flush()
    return created_partitions


def _merge_voice_profiles(primary_profile: CharacterVoiceProfile | None, secondary_profile: CharacterVoiceProfile | None) -> None:
    if primary_profile is None or secondary_profile is None:
        return
    primary_profile.sample_dialogue_count = int(primary_profile.sample_dialogue_count or 0) + int(secondary_profile.sample_dialogue_count or 0)
    primary_profile.sample_word_count = int(primary_profile.sample_word_count or 0) + int(secondary_profile.sample_word_count or 0)
    for field_name in (
        "avg_sentence_length",
        "avg_word_length_x100",
        "contraction_rate_x1000",
        "question_rate_x1000",
        "exclamation_rate_x1000",
        "ellipsis_rate_x1000",
        "dash_rate_x1000",
        "uppercase_rate_x1000",
        "formality_score_x1000",
        "lexical_complexity_x1000",
        "emotional_intensity_x1000",
    ):
        if getattr(primary_profile, field_name) is None:
            setattr(primary_profile, field_name, getattr(secondary_profile, field_name))
    if not primary_profile.dominant_markers and secondary_profile.dominant_markers:
        primary_profile.dominant_markers = secondary_profile.dominant_markers
    if not primary_profile.signature_phrases and secondary_profile.signature_phrases:
        primary_profile.signature_phrases = secondary_profile.signature_phrases


async def _merge_character_references(
    db: AsyncSession,
    *,
    primary: Character,
    secondary: Character,
    book_id: uuid.UUID,
) -> None:
    reference_values = _character_reference_values(secondary)

    plot_threads = (
        await db.execute(select(PlotThread).where(PlotThread.book_id == book_id))
    ).scalars().all()
    for thread in plot_threads:
        updated_ids = _replace_reference_list(thread.character_ids, matches=reference_values, replacement=primary.name)
        if updated_ids:
            thread.character_ids = updated_ids

    wiki_entries = (
        await db.execute(select(WikiEntry).where(WikiEntry.book_id == book_id))
    ).scalars().all()
    for entry in wiki_entries:
        related = _replace_reference_list(entry.related_char_ids, matches=reference_values, replacement=str(primary.id))
        if related:
            entry.related_char_ids = related

    chapter_summaries = (
        await db.execute(
            select(ChapterSummary)
            .join(ChapterSummary.chapter)
            .where(ChapterSummary.chapter.has(book_id=book_id))
        )
    ).scalars().all()
    for summary in chapter_summaries:
        key_events = [dict(event) if isinstance(event, dict) else event for event in (summary.key_events or [])]
        changed = False
        for event in key_events:
            if not isinstance(event, dict):
                continue
            involved = _replace_reference_list(event.get("involved_characters"), matches=reference_values, replacement=str(primary.id))
            if involved != list(event.get("involved_characters") or []):
                event["involved_characters"] = involved
                changed = True
        if changed:
            summary.key_events = key_events

        char_changes = [dict(change) if isinstance(change, dict) else change for change in (summary.char_changes or [])]
        char_change_changed = False
        for change in char_changes:
            if not isinstance(change, dict):
                continue
            candidate = " ".join(str(change.get("character") or "").split()).strip()
            if candidate and _normalize_character_reference(candidate) in reference_values:
                change["character"] = primary.name
                char_change_changed = True
        if char_change_changed:
            summary.char_changes = char_changes

    quotes = (
        await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == book_id))
    ).scalars().all()
    for quote in quotes:
        if _normalize_character_reference(quote.character_name) in reference_values:
            quote.character_name = primary.name

    relationship_candidates = (
        await db.execute(
            select(CharacterRelationshipCandidate).where(
                CharacterRelationshipCandidate.book_id == book_id
            )
        )
    ).scalars().all()
    for candidate in relationship_candidates:
        changed = False
        if candidate.matched_character_a_id == secondary.id:
            candidate.matched_character_a_id = primary.id
            changed = True
        if candidate.matched_character_b_id == secondary.id:
            candidate.matched_character_b_id = primary.id
            changed = True
        if changed and candidate.status == CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
            candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_MERGED


async def merge_characters(
    db: AsyncSession,
    primary_id: uuid.UUID,
    secondary_id: uuid.UUID,
    book_id: uuid.UUID,
) -> Character:
    """Merge duplicate character records and preserve aliases / references."""
    characters = (
        await db.execute(
            select(Character)
            .options(selectinload(Character.voice_profile))
            .where(Character.id.in_([primary_id, secondary_id]))
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    characters_by_id = {character.id: character for character in characters}
    primary = characters_by_id.get(primary_id)
    secondary = characters_by_id.get(secondary_id)
    if not primary or not secondary:
        raise ValueError("Character not found")
    if primary.book_id != book_id or secondary.book_id != book_id:
        raise ValueError("Characters must belong to the same book")
    if primary.id == secondary.id:
        return primary
    primary_visibility, primary_approval, primary_source, primary_reason_codes = character_governance(primary)
    secondary_visibility, secondary_approval, secondary_source, secondary_reason_codes = character_governance(secondary)

    merged = merge_profile_fields(primary, secondary)
    merged_manual_description = _merge_character_descriptions(
        _manual_character_description_value(primary.trait_state),
        _manual_character_description_value(secondary.trait_state),
    )
    primary.aliases = merged["aliases"]
    primary.normalized_name = normalize_character_name(primary.name) or None
    primary.role = merged["role"]
    primary.first_chapter = merged["first_chapter"]
    primary.last_seen_chapter = merged["last_seen_chapter"]
    primary.mention_count = (primary.mention_count or 0) + (secondary.mention_count or 0)
    primary.trait_state = merged["trait_state"]
    if merged_manual_description:
        apply_manual_character_description(primary, merged_manual_description)
    primary.hair = merged["hair"]
    primary.eyes = merged["eyes"]
    primary.build = merged["build"]
    primary.age_descriptor = merged["age_descriptor"]
    primary.distinguishing = merged["distinguishing"]
    primary.personality_tags = merged["personality_tags"]
    primary.goal = merged["goal"]
    primary.motivations = merged["motivations"]
    primary.fears = merged["fears"]
    primary.lie_they_believe = merged["lie_they_believe"]
    primary.backstory_wound = merged["backstory_wound"]
    primary.arc_type = merged["arc_type"]
    primary.arc_summary = merged["arc_summary"]
    primary.archetype = merged["archetype"]
    primary.growth_events = merged["growth_events"]
    if primary.embedding is None and secondary.embedding is not None:
        primary.embedding = secondary.embedding
    if primary.voice_profile and secondary.voice_profile:
        _merge_voice_profiles(primary.voice_profile, secondary.voice_profile)
        # Detach the secondary profile and let delete-orphan remove it once.
        secondary.voice_profile = None
    elif primary.voice_profile is None and secondary.voice_profile is not None:
        moved_voice_profile = secondary.voice_profile
        secondary.voice_profile = None
        primary.voice_profile = moved_voice_profile
        moved_voice_profile.book_id = primary.book_id

    state_rows_result = await db.execute(select(CharacterState).where(CharacterState.character_id == secondary.id))
    state_rows = state_rows_result.scalars().all()
    for state in state_rows:
        existing_state = (
            await db.execute(
                select(CharacterState).where(
                    CharacterState.character_id == primary.id,
                    CharacterState.at_chapter == state.at_chapter,
                )
            )
        ).scalar()
        if existing_state:
            existing_state.trait_snapshot = state.trait_snapshot or existing_state.trait_snapshot
            if state.motivations_snapshot and not existing_state.motivations_snapshot:
                existing_state.motivations_snapshot = state.motivations_snapshot
            if state.fears_snapshot and not existing_state.fears_snapshot:
                existing_state.fears_snapshot = state.fears_snapshot
            if state.prompt_delta and not existing_state.prompt_delta:
                existing_state.prompt_delta = state.prompt_delta
            if state.arc_note and not existing_state.arc_note:
                existing_state.arc_note = state.arc_note
            if state.growth_event and not existing_state.growth_event:
                existing_state.growth_event = state.growth_event
            await db.delete(state)
        else:
            state.character_id = primary.id

    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            or_(
                CharacterRelationship.character_a_id == secondary.id,
                CharacterRelationship.character_b_id == secondary.id,
            ),
        )
    )
    rels = rels_result.scalars().all()
    for rel in rels:
        if rel.character_a_id == secondary.id:
            rel.character_a_id = primary.id
        if rel.character_b_id == secondary.id:
            rel.character_b_id = primary.id
        if rel.character_a_id == rel.character_b_id:
            await db.delete(rel)

    await _merge_character_references(db, primary=primary, secondary=secondary, book_id=book_id)
    mention_rows = (
        await db.execute(
            select(CharacterMention).where(
                CharacterMention.book_id == book_id,
                CharacterMention.matched_character_id == secondary.id,
            )
        )
    ).scalars().all()
    for mention in mention_rows:
        mention.matched_character_id = primary.id

    alias_rows = (
        await db.execute(
            select(CharacterAlias).where(
                CharacterAlias.book_id == book_id,
                CharacterAlias.character_id == secondary.id,
            )
        )
    ).scalars().all()
    existing_primary_aliases = {
        normalize_character_name(alias.alias_text)
        for alias in (
            await db.execute(
                select(CharacterAlias).where(
                    CharacterAlias.book_id == book_id,
                    CharacterAlias.character_id == primary.id,
                )
            )
        ).scalars().all()
    }
    for alias in alias_rows:
        if alias.normalized_alias in existing_primary_aliases:
            await db.delete(alias)
        else:
            alias.character_id = primary.id
            existing_primary_aliases.add(alias.normalized_alias)

    suppression_rows = (
        await db.execute(
            select(CharacterSuppression).where(
                CharacterSuppression.book_id == book_id,
                CharacterSuppression.character_id == secondary.id,
            )
        )
    ).scalars().all()
    for suppression in suppression_rows:
        suppression.character_id = primary.id

    constraint_rows = (
        await db.execute(
            select(CharacterIdentityConstraint).where(
                CharacterIdentityConstraint.book_id == book_id,
                or_(
                    CharacterIdentityConstraint.left_character_id == secondary.id,
                    CharacterIdentityConstraint.right_character_id == secondary.id,
                ),
            )
        )
    ).scalars().all()
    for constraint in constraint_rows:
        if constraint.left_character_id == secondary.id:
            constraint.left_character_id = primary.id
            constraint.left_text = primary.name
        if constraint.right_character_id == secondary.id:
            constraint.right_character_id = primary.id
            constraint.right_text = primary.name
        if constraint.left_character_id == constraint.right_character_id:
            await db.delete(constraint)

    suggestion_rows = (
        await db.execute(
            select(CharacterDuplicateSuggestion).where(
                CharacterDuplicateSuggestion.book_id == book_id,
                or_(
                    CharacterDuplicateSuggestion.primary_character_id == secondary.id,
                    CharacterDuplicateSuggestion.secondary_character_id == secondary.id,
                ),
            )
        )
    ).scalars().all()
    for suggestion in suggestion_rows:
        next_primary_id = primary.id if suggestion.primary_character_id == secondary.id else suggestion.primary_character_id
        next_secondary_id = primary.id if suggestion.secondary_character_id == secondary.id else suggestion.secondary_character_id
        if next_primary_id == next_secondary_id:
            suggestion.status = CHARACTER_DUPLICATE_ACCEPTED
            continue
        existing_conflict = (
            await db.execute(
                select(CharacterDuplicateSuggestion).where(
                    CharacterDuplicateSuggestion.book_id == book_id,
                    CharacterDuplicateSuggestion.id != suggestion.id,
                    CharacterDuplicateSuggestion.primary_character_id == next_primary_id,
                    CharacterDuplicateSuggestion.secondary_character_id == next_secondary_id,
                )
            )
        ).scalar_one_or_none()
        if existing_conflict is not None:
            await db.delete(suggestion)
            continue
        suggestion.primary_character_id = next_primary_id
        suggestion.secondary_character_id = next_secondary_id

    await _dedupe_relationships(db, book_id)
    if primary_approval == CHARACTER_APPROVAL_PROTECTED or secondary_approval == CHARACTER_APPROVAL_PROTECTED:
        merged_visibility = CHARACTER_VISIBILITY_VISIBLE
        merged_approval = CHARACTER_APPROVAL_PROTECTED
        merged_source = CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW
    elif primary_visibility == CHARACTER_VISIBILITY_VISIBLE or secondary_visibility == CHARACTER_VISIBILITY_VISIBLE:
        merged_visibility = CHARACTER_VISIBILITY_VISIBLE
        merged_approval = CHARACTER_APPROVAL_APPROVED
        merged_source = primary_source or secondary_source or CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW
    else:
        merged_visibility = CHARACTER_VISIBILITY_QUARANTINED
        merged_approval = CHARACTER_APPROVAL_PENDING_REVIEW
        merged_source = primary_source or secondary_source or CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW
    set_character_review_state(
        primary,
        visibility_state=merged_visibility,
        approval_state=merged_approval,
        approval_source=merged_source,
        reason_codes=[*primary_reason_codes, *secondary_reason_codes, "merged_character_record"],
        action="character_merged",
        details={"secondary_character_id": str(secondary.id)},
    )
    secondary.merged_into_character_id = primary.id
    secondary.normalized_name = None
    secondary.is_auto_suppressed = True
    secondary.suppression_reason = "merged_character_record"
    set_character_review_state(
        secondary,
        visibility_state=CHARACTER_VISIBILITY_NOISE,
        approval_state=CHARACTER_APPROVAL_REJECTED,
        approval_source=CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
        reason_codes=["merged_into_character", *secondary_reason_codes],
        action="character_soft_merged",
        details={"primary_character_id": str(primary.id)},
    )
    await record_identity_action(
        db,
        book_id=book_id,
        action_type="auto_merge",
        source_character_id=secondary.id,
        target_character_id=primary.id,
        surface_text=secondary.name,
        confidence=0.95,
        reason="merged_character_record",
        reversible=True,
        reversible_data={
            "secondary_name": secondary.name,
            "secondary_aliases": secondary.aliases or [],
            "secondary_visibility_state": secondary_visibility,
            "secondary_approval_state": secondary_approval,
        },
    )
    await db.flush()
    update_character_classification(primary)
    return primary


async def _dedupe_relationships(db: AsyncSession, book_id: uuid.UUID) -> None:
    await repair_relationship_timelines(db, book_id=book_id)


def _clean_tracker_text(value: object | None) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or None


def _event_chapter(event: dict[str, Any], fallback: int) -> int:
    raw = event.get("chapter_number") or event.get("chapter") or fallback
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return fallback


def _trait_value_for_history(raw: object) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("value")
        return _clean_tracker_text(value)
    return _clean_tracker_text(raw)


def _dominant_marker_lines(profile: CharacterVoiceProfile | None) -> list[str]:
    if profile is None:
        return []
    markers: list[str] = []
    for key, value in (profile.dominant_markers or {}).items():
        cleaned_key = _clean_tracker_text(key)
        cleaned_value = _clean_tracker_text(value)
        if cleaned_key and cleaned_value:
            markers.append(f"{cleaned_key.replace('_', ' ').title()}: {cleaned_value}")
        elif cleaned_key:
            markers.append(cleaned_key.replace("_", " ").title())
    for phrase in profile.signature_phrases or []:
        cleaned_phrase = _clean_tracker_text(phrase)
        if cleaned_phrase:
            markers.append(f'Signature phrase: "{cleaned_phrase}"')
    return dedupe_preserve_order(markers)


def _trait_label(trait_key: str) -> str:
    labels = {
        "hair": "Hair",
        "eyes": "Eyes",
        "build": "Build",
        "age": "Age",
        "face": "Face",
        "distinguishing": "Distinguishing details",
        "manual_description": "Description",
    }
    return labels.get(trait_key, trait_key.replace("_", " ").title())


def build_physical_description_history(states: list[CharacterState]) -> list[dict[str, Any]]:
    tracked_keys = ("hair", "eyes", "build", "age", "face", "distinguishing", "manual_description")
    history: list[dict[str, Any]] = []
    previous_values: dict[str, str] = {}
    for state in sorted(states, key=lambda row: row.at_chapter):
        snapshot = state.trait_snapshot or {}
        for trait_key in tracked_keys:
            current_value = _trait_value_for_history(snapshot.get(trait_key))
            if not current_value:
                continue
            if previous_values.get(trait_key, "").casefold() == current_value.casefold():
                continue
            history.append(
                {
                    "chapter_number": state.at_chapter,
                    "trait": trait_key,
                    "label": _trait_label(trait_key),
                    "value": current_value,
                    "previous_value": previous_values.get(trait_key),
                }
            )
            previous_values[trait_key] = current_value
    return history


def build_relationship_change_entries(
    character: Character,
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in sorted(relationships, key=lambda item: (item.from_chapter or 0, item.to_chapter or 10**6, str(item.id))):
        counterpart_id = rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        rows.append(
            {
                "counterpart_id": str(counterpart_id),
                "counterpart_name": counterpart_names.get(counterpart_id, "Unknown character"),
                "chapter_number": rel.from_chapter or character.first_chapter,
                "to_chapter": rel.to_chapter,
                "type": rel.rel_type or "connection",
                "sentiment": rel.sentiment,
                "description": _clean_tracker_text(rel.description),
            }
        )
    return rows


def build_character_contradictions(
    character: Character,
    states: list[CharacterState],
    physical_history: list[dict[str, Any]],
) -> list[str]:
    contradictions: list[str] = []
    for item in physical_history:
        previous_value = _clean_tracker_text(item.get("previous_value"))
        current_value = _clean_tracker_text(item.get("value"))
        label = _clean_tracker_text(item.get("label"))
        chapter_number = item.get("chapter_number")
        if previous_value and current_value and label:
            contradictions.append(
                f"{label} shifts from {previous_value} to {current_value} by chapter {chapter_number}."
            )

    previous_motivations: list[str] | None = None
    previous_fears: list[str] | None = None
    for state in sorted(states, key=lambda row: row.at_chapter):
        current_motivations = [item for item in (state.motivations_snapshot or []) if _clean_tracker_text(item)]
        current_fears = [item for item in (state.fears_snapshot or []) if _clean_tracker_text(item)]
        if previous_motivations and current_motivations and previous_motivations != current_motivations:
            contradictions.append(
                f"Motivation profile changes by chapter {state.at_chapter}: {', '.join(previous_motivations[:2])} -> {', '.join(current_motivations[:2])}."
            )
        if previous_fears and current_fears and previous_fears != current_fears:
            contradictions.append(
                f"Fear profile changes by chapter {state.at_chapter}: {', '.join(previous_fears[:2])} -> {', '.join(current_fears[:2])}."
            )
        if current_motivations:
            previous_motivations = current_motivations
        if current_fears:
            previous_fears = current_fears
    return dedupe_preserve_order(contradictions)[:10]


def build_character_arc_tracker(
    character: Character,
    *,
    states: list[CharacterState],
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
    voice_profile: CharacterVoiceProfile | None,
    total_chapters: int | None = None,
) -> dict[str, Any]:
    sorted_states = sorted(states, key=lambda row: row.at_chapter)
    raw_events = [event for event in (character.growth_events or []) if isinstance(event, dict)]
    raw_events.sort(key=lambda event: (_event_chapter(event, character.first_chapter), _clean_tracker_text(event.get("event_title") or event.get("event")) or ""))

    turning_points: list[dict[str, Any]] = []
    arc_timeline: list[str] = []
    for event in raw_events:
        chapter_number = _event_chapter(event, character.first_chapter)
        if chapter_number <= 0:
            continue
        title = _clean_tracker_text(event.get("event_title") or event.get("event")) or f"Shift in chapter {chapter_number}"
        description = _clean_tracker_text(event.get("description") or event.get("impact"))
        turning_points.append(
            {
                "chapter_number": chapter_number,
                "title": title,
                "description": description,
                "impact_score": event.get("impact_score") or event.get("importance"),
                "growth_direction": _clean_tracker_text(event.get("growth_direction") or event.get("tone")),
                "is_major": bool(event.get("is_major", False)),
            }
        )
        arc_timeline.append(
            f"Chapter {chapter_number}: {title}" + (f" - {description}" if description else "")
        )

    relationship_changes = build_relationship_change_entries(character, relationships, counterpart_names)
    physical_history = build_physical_description_history(sorted_states)
    contradictions = build_character_contradictions(character, sorted_states, physical_history)
    voice_markers = _dominant_marker_lines(voice_profile)

    diagnostics: list[str] = []
    last_change_chapter = max([character.first_chapter, *[item["chapter_number"] for item in turning_points]], default=character.first_chapter)
    last_seen = character.last_seen_chapter or character.first_chapter
    if last_seen - last_change_chapter >= 14:
        diagnostics.append("Character has not changed meaningfully in 14 chapters.")

    previous_motivations: list[str] | None = None
    for state in sorted_states:
        current_motivations = [item for item in (state.motivations_snapshot or []) if _clean_tracker_text(item)]
        if previous_motivations and current_motivations and previous_motivations != current_motivations:
            explained = any(abs(item["chapter_number"] - state.at_chapter) <= 1 for item in turning_points)
            if not explained:
                diagnostics.append("Motivation changed, but no scene explains why.")
                break
        if current_motivations:
            previous_motivations = current_motivations

    pair_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in relationship_changes:
        pair_history[item["counterpart_name"]].append(item)
    for counterpart_name, items in pair_history.items():
        ordered = sorted(items, key=lambda row: row["chapter_number"])
        for previous, current in zip(ordered, ordered[1:]):
            previous_negative = (previous.get("sentiment") or 0) <= -0.35 or str(previous.get("type") or "").lower() in {"enemy", "rival", "hostile"}
            current_positive = (current.get("sentiment") or 0) >= 0.35 or str(current.get("type") or "").lower() in {"ally", "friend", "romantic", "family", "mentor"}
            if previous_negative and current_positive and (current["chapter_number"] - previous["chapter_number"]) <= 2:
                diagnostics.append(
                    f"Relationship with {counterpart_name} shifts from hostile to trusting too abruptly."
                )
                break
        if diagnostics and diagnostics[-1].endswith("too abruptly."):
            break

    if total_chapters and character.last_seen_chapter and total_chapters - character.last_seen_chapter >= 25:
        diagnostics.append(f"Character is absent for {total_chapters - character.last_seen_chapter} chapters after the latest appearance.")

    latest_description = _clean_tracker_text(character.description if hasattr(character, "description") else None)
    return {
        "goal": _clean_tracker_text(getattr(character, "goal", None)) or (character.motivations or [None])[0],
        "motivation": (character.motivations or [None])[0],
        "motivations": character.motivations or [],
        "fear": (character.fears or [None])[0],
        "fears": character.fears or [],
        "lie_they_believe": _clean_tracker_text(getattr(character, "lie_they_believe", None)),
        "wound_backstory": _clean_tracker_text(getattr(character, "backstory_wound", None)),
        "arc_type": _clean_tracker_text(getattr(character, "arc_type", None) or character.archetype),
        "first_appearance": character.first_chapter,
        "major_turning_points": turning_points,
        "relationship_changes": relationship_changes,
        "contradictions": contradictions,
        "voice_markers": voice_markers,
        "physical_description_history": physical_history,
        "arc_timeline": arc_timeline,
        "diagnostics": dedupe_preserve_order(diagnostics),
        "latest_arc_note": _clean_tracker_text(sorted_states[-1].arc_note) if sorted_states else character.arc_summary,
        "summary": _clean_tracker_text(character.arc_summary) or latest_description,
    }


# ─── Character classification scoring ───────────────────────────────────────────

def compute_character_classification(char: Character) -> tuple[str, int, dict[str, int]]:
    """Compute character type and subtype scores for a character.

    Returns:
        (character_type, character_type_score, subtype_scores)
        character_type: "complex" | "normal" | "gag" | "meme"
        character_type_score: 0-10 score for main type
        subtype_scores: dict of subtype names to scores (only >= 3)
    """
    # Compute main type scores
    gag_score = gag_character_score(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        mention_count=char.mention_count or 0,
        role=char.role,
        growth_events=char.growth_events,
    )
    
    complex_score = complex_character_score(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        mention_count=char.mention_count or 0,
        role=char.role,
        growth_events=char.growth_events,
        motivations=char.motivations,
        fears=char.fears,
    )
    
    # Determine main type based on scores
    if gag_score >= 3:
        character_type = "gag" if gag_score > complex_score else "complex"
        character_type_score = max(gag_score, complex_score)
    elif complex_score >= 5:
        character_type = "complex"
        character_type_score = complex_score
    else:
        character_type = "normal"
        character_type_score = complex_score
    
    # Compute subtype scores
    subtype_scores = compute_all_subtype_scores(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        growth_events=char.growth_events,
    )
    
    return character_type, character_type_score, subtype_scores


def update_character_classification(char: Character) -> None:
    """Update character's classification fields with computed scores."""
    character_type, character_type_score, subtype_scores = compute_character_classification(char)
    char.character_type = character_type
    char.character_type_score = character_type_score
    char.subtype_scores = subtype_scores
