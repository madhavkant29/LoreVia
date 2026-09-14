"""
Character utility helpers — shared across route modules.
Covers display filtering, status derivation, relationship summaries,
and text-sanitization helpers used on character data.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from app.engine.character.entity_filters import (
    COMMON_NON_NAME_WORDS,
    VISIBILITY_THRESHOLD,
    character_visibility_score,
    entity_words,
)
from app.models.character import (
    Character,
)
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_PROTECTED,
    CHARACTER_APPROVAL_REJECTED,
    CHARACTER_APPROVAL_SOURCE_LEGACY_IMPORT,
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
    CHARACTER_TRUST_TIER_REPAIRED_NOISE,
    CHARACTER_TRUST_TIER_REVIEW_ONLY,
    CHARACTER_TRUST_TIER_VISIBLE,
    CHARACTER_VISIBILITY_NOISE,
    CHARACTER_VISIBILITY_QUARANTINED,
    CHARACTER_VISIBILITY_VISIBLE,
    ROLE_ONLY_REFERENCE_WORDS,
    VALID_CHARACTER_APPROVAL_SOURCES,
    VALID_CHARACTER_APPROVAL_STATES,
    VALID_CHARACTER_TRUST_TIERS,
    VALID_CHARACTER_VISIBILITY_STATES,
)
from app.utils.characters.text import clean_optional_text, clean_string_list


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
    if (
        getattr(char, "is_manual", False)
        or metadata.get("user_curated")
        or metadata.get("protected_from_repair")
    ):
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
    grounding_passage_count = int(
        metadata.get("grounding_passage_count")
        or metadata.get("evidence_count")
        or mention_count
        or 0
    )
    quality_flags = {
        str(flag).strip() for flag in (metadata.get("quality_flags") or []) if str(flag).strip()
    }
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
    if any(
        getattr(char, field, None)
        for field in ("personality_tags", "motivations", "fears", "growth_events")
    ):
        return True
    arc_summary = clean_optional_text(getattr(char, "arc_summary", None))
    return bool(
        arc_summary
        and arc_summary.casefold()
        not in {
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
        }
    )


def infer_character_trust_tier(char: Character) -> tuple[str, list[str]]:
    visibility_state, approval_state, _approval_source, approval_reason_codes = (
        character_governance(char)
    )
    if visibility_state == CHARACTER_VISIBILITY_VISIBLE and approval_state in {
        CHARACTER_APPROVAL_APPROVED,
        CHARACTER_APPROVAL_PROTECTED,
    }:
        return CHARACTER_TRUST_TIER_VISIBLE, approval_reason_codes or ["approval_visible"]
    if (
        visibility_state == CHARACTER_VISIBILITY_NOISE
        or approval_state == CHARACTER_APPROVAL_REJECTED
    ):
        return CHARACTER_TRUST_TIER_REPAIRED_NOISE, approval_reason_codes or ["approval_rejected"]
    if (
        visibility_state == CHARACTER_VISIBILITY_QUARANTINED
        or approval_state == CHARACTER_APPROVAL_PENDING_REVIEW
    ):
        return CHARACTER_TRUST_TIER_REVIEW_ONLY, approval_reason_codes or [
            "approval_pending_review"
        ]

    metadata = dict(getattr(char, "analysis_metadata", None) or {})
    explicit_tier = normalize_character_trust_tier(metadata.get("trust_tier"))
    explicit_reasons = clean_string_list(cast(list[str] | None, metadata.get("trust_reasons")))
    if (
        getattr(char, "is_manual", False)
        or metadata.get("user_curated")
        or metadata.get("protected_from_repair")
    ):
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
    grounding_passage_count = int(
        metadata.get("grounding_passage_count")
        or metadata.get("evidence_count")
        or mention_count
        or 0
    )
    quality_flags = {
        str(flag).strip() for flag in (metadata.get("quality_flags") or []) if str(flag).strip()
    }
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

    if reasons and (
        common_single_token
        or role_only_single_token
        or score < VISIBILITY_THRESHOLD
        or "thin_single_token_grounding" in reasons
    ):
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
            " ".join(
                event.get("event", "")
                for event in (char.growth_events or [])
                if isinstance(event, dict)
            ),
        ]
        if part
    ).lower()
    deceased_markers = (
        "deceased",
        "dead",
        "dies",
        "died",
        "killed",
        "murdered",
        "executed",
        "buried",
    )
    return "deceased" if any(marker in text for marker in deceased_markers) else "alive"


# ─── Relationship summary helpers ─────────────────────────────────────────────
