"""
Character utility helpers — shared across route modules.
Covers display filtering, status derivation, relationship summaries,
and text-sanitization helpers used on character data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.engine.character.entity_filters import (
    COMMON_NON_NAME_WORDS,
    entity_words,
)
from app.engine.character.profile_builder import (
    build_description,
)
from app.models.intelligence import (
    CharacterRelationship,
)
from app.utils.characters.constants import ROLE_ONLY_REFERENCE_WORDS
from app.utils.characters.governance import _clean_reason_code_values
from app.utils.characters.identity import normalize_character_name
from app.utils.characters.text import clean_optional_text, clean_string_list
from app.utils.relationship_utils import (
    normalize_relationship_labels,
    relationship_label_display,
)


def relationship_summary_for_character(
    rel: CharacterRelationship,
    name_a: str,
    name_b: str,
    perspective_name: str,
) -> str | None:
    counterpart = name_b if perspective_name == name_a else name_a
    shared_labels = normalize_relationship_labels(getattr(rel, "shared_labels", None))
    directional_labels = normalize_relationship_labels(
        getattr(rel, "character_a_to_b_labels", None)
        if perspective_name == name_a
        else getattr(rel, "character_b_to_a_labels", None)
    )
    labels = directional_labels + [
        label for label in shared_labels if label not in directional_labels
    ]
    if not labels:
        labels = [rel.rel_type or "connection"]
    label_text = ", ".join(relationship_label_display(label) for label in labels[:4])
    if getattr(rel, "from_chapter", None) and getattr(rel, "to_chapter", None):
        return f"{label_text.capitalize()} with {counterpart} through chapter {rel.to_chapter}."
    if getattr(rel, "from_chapter", None):
        return f"{label_text.capitalize()} with {counterpart} from chapter {rel.from_chapter}."
    return f"{label_text.capitalize()} with {counterpart}."


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
        segments.append(
            " ".join(_ensure_sentence(summary) for summary in relationship_preview if summary)
        )

    composed = " ".join(segment for segment in segments if segment).strip()
    return composed or None


# ─── Text-cleaning helpers ────────────────────────────────────────────────────


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
    entity_aliases = (
        clean_string_list(
            [str(alias) for alias in ((evidence or {}).get("entity") or {}).get("aliases") or []]
        )
        if isinstance((evidence or {}).get("entity"), Mapping)
        else []
    )
    merged_aliases = dedupe_preserve_order([*clean_aliases, *entity_aliases])
    words = entity_words(clean_name)
    single_token = len(words) == 1
    common_single_token = single_token and words[0].casefold() in COMMON_NON_NAME_WORDS
    role_only_single_token = single_token and words[0].casefold() in ROLE_ONLY_REFERENCE_WORDS
    evidence_map = dict(evidence or {})
    verifier = (
        evidence_map.get("verifier") if isinstance(evidence_map.get("verifier"), Mapping) else {}
    )
    local = (
        verifier.get("local")
        if isinstance(verifier, Mapping) and isinstance(verifier.get("local"), Mapping)
        else {}
    )
    final = (
        verifier.get("final")
        if isinstance(verifier, Mapping) and isinstance(verifier.get("final"), Mapping)
        else {}
    )
    cluster_names = clean_string_list(
        [str(item) for item in evidence_map.get("cluster_names") or []]
    )
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
    resolved_reason_codes = _clean_reason_code_values(
        reason_codes or evidence_map.get("resolver_reasons") or []
    )
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
    full_name_alias_support = int(
        any(len(entity_words(alias)) >= 2 for alias in [*merged_aliases, *cluster_names])
    )
    canonical_name = clean_optional_text(
        (
            (evidence_map.get("entity") or {})
            if isinstance(evidence_map.get("entity"), Mapping)
            else {}
        ).get("canonical_name")
    )
    full_name_link_support = int(
        bool(canonical_name and canonical_name.casefold() != clean_name.casefold())
    )
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
                strict_auto_eligible = final_band == "accept" and (
                    (len(chapter_numbers) >= 2 and person_ner_support >= 1)
                    or (
                        mention_count >= 2
                        and person_ner_support >= 1
                        and (
                            alias_link_support >= 1
                            or full_name_link_support >= 1
                            or dialogue_attribution_support >= 1
                        )
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
        "summary_reason_codes": dedupe_preserve_order(
            [*resolved_reason_codes, *strict_auto_reason_codes]
        ),
    }
