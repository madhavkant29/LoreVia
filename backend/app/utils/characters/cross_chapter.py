"""Combine independently verified exact-name mentions from other chapters."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.models.character import CharacterCandidate
from app.utils.characters.identity import normalize_character_name
from app.utils.characters.profile_evidence import PROFILE_LIST_FIELDS, PROFILE_SCALAR_FIELDS


def _verifier_part(evidence: Mapping[str, Any], part: str) -> dict[str, Any]:
    verifier = evidence.get("verifier")
    if not isinstance(verifier, Mapping):
        return {}
    value = verifier.get(part)
    return dict(value) if isinstance(value, Mapping) else {}


def _count(value: object) -> int:
    try:
        return max(0, int(value)) if not isinstance(value, bool) else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def _named_snippets(evidence: Mapping[str, Any], name: str) -> list[str]:
    values = evidence.get("snippets")
    if not isinstance(values, list):
        return []
    pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.I)
    return [value for value in values if isinstance(value, str) and pattern.search(value)]


def _cited_claim(value: object, *, chapter_number: int) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    quote = str(value.get("quote") or "").strip()
    start, end = value.get("start"), value.get("end")
    source_batch_key = str(value.get("source_batch_key") or "").strip()
    if (
        len(quote) < 8
        or not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or start < 0
        or end <= start
        or not source_batch_key
    ):
        return None
    return {**value, "chapter_number": chapter_number}


def _merge_cited_profile(
    entity: dict[str, Any],
    evidence: dict[str, Any],
    candidates: Sequence[CharacterCandidate],
) -> dict[str, Any]:
    """Copy only previously verified claims, preserving their chapter references."""
    updated = dict(entity)
    raw_claims = evidence.get("profile_claims")
    claims = dict(raw_claims) if isinstance(raw_claims, Mapping) else {}
    for candidate in sorted(candidates, key=lambda row: row.chapter_number, reverse=True):
        prior = candidate.evidence or {}
        prior_entity = prior.get("entity")
        prior_claims = prior.get("profile_claims")
        if not isinstance(prior_entity, Mapping) or not isinstance(prior_claims, Mapping):
            continue
        for field in PROFILE_SCALAR_FIELDS:
            value = prior_entity.get(field)
            citation = _cited_claim(
                prior_claims.get(field), chapter_number=candidate.chapter_number
            )
            if (
                not str(updated.get(field) or "").strip()
                and isinstance(value, str)
                and value.strip()
                and citation
            ):
                updated[field] = value
                claims[field] = citation
        for field in PROFILE_LIST_FIELDS:
            current_values = updated.get(field)
            values = (
                [value for value in current_values if isinstance(value, str)]
                if isinstance(current_values, list)
                else []
            )
            current_claims = claims.get(field)
            field_claims = dict(current_claims) if isinstance(current_claims, Mapping) else {}
            old_claims = prior_claims.get(field)
            if not isinstance(old_claims, Mapping):
                continue
            prior_values = prior_entity.get(field)
            for value in prior_values if isinstance(prior_values, list) else []:
                if not isinstance(value, str) or not value.strip():
                    continue
                citation = _cited_claim(
                    old_claims.get(value), chapter_number=candidate.chapter_number
                )
                if citation and value.casefold() not in {item.casefold() for item in values}:
                    values.append(value)
                    field_claims[value] = citation
            updated[field] = values
            if field_claims:
                claims[field] = field_claims
        current_traits = updated.get("traits")
        traits = dict(current_traits) if isinstance(current_traits, Mapping) else {}
        current_trait_claims = claims.get("traits")
        trait_claims = (
            dict(current_trait_claims) if isinstance(current_trait_claims, Mapping) else {}
        )
        old_traits = prior_entity.get("traits")
        old_claims = prior_claims.get("traits")
        if isinstance(old_traits, Mapping) and isinstance(old_claims, Mapping):
            for trait, value in old_traits.items():
                citation = _cited_claim(
                    old_claims.get(trait), chapter_number=candidate.chapter_number
                )
                if trait not in traits and isinstance(value, Mapping) and citation:
                    traits[trait] = dict(value)
                    trait_claims[trait] = citation
            updated["traits"] = traits
            if trait_claims:
                claims["traits"] = trait_claims
    evidence["profile_claims"] = claims
    return updated


def combine_exact_name_chapter_evidence(
    entity: dict[str, Any],
    *,
    chapter_number: int,
    prior_candidates: Sequence[CharacterCandidate],
) -> dict[str, Any]:
    """Add only source-verified, unambiguous evidence for the exact name."""
    current = entity.get("evidence")
    if (
        not isinstance(current, dict)
        or current.get("source_mention_count_verified") is not True
        or _count(current.get("mention_count")) < 1
    ):
        return entity
    if _verifier_part(current, "final").get("confidence_band") != "accept":
        return entity
    name = normalize_character_name(str(entity.get("name") or ""))
    if not name or current.get("ambiguous_full_name_fragment") or entity.get("anti_merge_names"):
        return entity
    if any(normalize_character_name(str(alias)) != name for alias in entity.get("aliases") or []):
        return entity

    by_chapter: dict[int, CharacterCandidate] = {}
    for candidate in prior_candidates:
        evidence = candidate.evidence if isinstance(candidate.evidence, dict) else {}
        if (
            candidate.status != "pending"
            or candidate.matched_character_id is not None
            or candidate.chapter_number == chapter_number
            or candidate.normalized_name != name
            or normalize_character_name(candidate.proposed_name) != name
            or any(
                normalize_character_name(str(alias)) != name for alias in candidate.aliases or []
            )
            or evidence.get("source_mention_count_verified") is not True
            or _count(evidence.get("mention_count")) < 1
            or evidence.get("profile_enrichment_status") == "unanchored_reference"
            or evidence.get("ambiguous_full_name_fragment")
            or evidence.get("anti_merge_names")
            or evidence.get("resolver_status") in {"ambiguous", "matched_needs_review"}
            or _verifier_part(evidence, "final").get("confidence_band") != "accept"
            or candidate.entity_type not in (None, "person", "alias_candidate")
            or candidate.rejection_reason
            or str(candidate.source_batch_key or "").startswith("manual-demote:")
            or any(
                str(reason).startswith("author_") or "conflict" in str(reason)
                for reason in candidate.reason_codes or []
            )
        ):
            continue
        old = by_chapter.get(candidate.chapter_number)
        if old is None or _count(evidence.get("mention_count")) > _count(
            (old.evidence or {}).get("mention_count")
        ):
            by_chapter[candidate.chapter_number] = candidate
    if not by_chapter:
        return entity

    combined = dict(current)
    local = _verifier_part(current, "local")
    snippets = _named_snippets(current, str(entity["name"]))
    for candidate in by_chapter.values():
        evidence = candidate.evidence or {}
        previous_local = _verifier_part(evidence, "local")
        for key in (
            "person_ner_mentions",
            "non_person_ner_mentions",
            "sentence_start_mentions",
            "mid_sentence_mentions",
            "person_context_mentions",
        ):
            local[key] = _count(local.get(key)) + _count(previous_local.get(key))
        for key in ("mention_count", "strong_mention_count"):
            combined[key] = _count(combined.get(key)) + _count(evidence.get(key))
        for key in (
            "has_dialogue_or_action",
            "has_attributed_speech",
            "has_direct_communication",
            "has_human_self_action",
            "has_physical_description",
        ):
            combined[key] = combined.get(key) is True or evidence.get(key) is True
        snippets.extend(_named_snippets(evidence, str(entity["name"])))
    combined["snippets"] = list(dict.fromkeys(snippets))[:8]
    combined["chapter_numbers"] = sorted([chapter_number, *by_chapter])
    combined["shared_chapters"] = combined["chapter_numbers"]
    combined["verifier"] = {**current["verifier"], "local": local}
    combined["cross_chapter_candidate_ids"] = [str(item.id) for item in by_chapter.values()]
    merged_entity = _merge_cited_profile(entity, combined, list(by_chapter.values()))
    return {**merged_entity, "evidence": combined}
