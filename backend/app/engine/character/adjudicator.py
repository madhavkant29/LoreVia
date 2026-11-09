from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.engine.character.entity_filters import character_visibility_score, entity_words
from app.services.character_identity.classification import CandidateKind, classify_candidate_kind
from app.services.character_identity.normalization import (
    display_name_form,
    normalized_comparison_name,
)

ADJUDICATION_CANDIDATE = "candidate"
ADJUDICATION_PROMOTED_CHARACTER = "promoted_character"
ADJUDICATION_QUARANTINED = "quarantined"
ADJUDICATION_REJECTED = "rejected"
ADJUDICATION_MERGED_ALIAS = "merged_alias"
ADJUDICATION_PLACE = "place"
ADJUDICATION_ORGANIZATION = "organization"
ADJUDICATION_OBJECT = "object"
ADJUDICATION_TITLE_OR_ROLE = "title_or_role"
ADJUDICATION_UNKNOWN = "unknown"

ENTITY_PERSON = "person"
ENTITY_PLACE = "place"
ENTITY_ORGANIZATION = "organization"
ENTITY_OBJECT = "object"
ENTITY_TITLE_OR_ROLE = "title_or_role"
ENTITY_ALIAS_CANDIDATE = "alias_candidate"
ENTITY_JUNK = "junk"
ENTITY_UNKNOWN = "unknown"

DIALOGUE_VERBS = {
    "said",
    "asked",
    "replied",
    "cried",
    "whispered",
    "shouted",
    "answered",
    "muttered",
    "called",
    "told",
}
HUMAN_PRONOUNS = {"he", "she", "they", "him", "her", "his", "hers", "their", "theirs"}
LOCATION_PREPOSITIONS = {
    "in",
    "at",
    "from",
    "near",
    "towards",
    "toward",
    "inside",
    "outside",
    "through",
}
HUMAN_ACTION_VERBS = {
    "walked",
    "looked",
    "turned",
    "spoke",
    "ran",
    "came",
    "went",
    "stood",
    "sat",
    "laughed",
    "smiled",
    "frowned",
    "thought",
    "felt",
    "knew",
    "wanted",
    "held",
    "took",
    "gave",
}
TRAIT_WORDS = {
    "old",
    "young",
    "tall",
    "short",
    "thin",
    "stout",
    "hair",
    "eyes",
    "face",
    "voice",
    "beard",
    "scar",
    "hands",
}
RELATIONSHIP_WORDS = {
    "father",
    "mother",
    "brother",
    "sister",
    "friend",
    "wife",
    "husband",
    "son",
    "daughter",
    "uncle",
    "aunt",
}
PLACE_TERMS = {
    "street",
    "square",
    "market",
    "road",
    "lane",
    "avenue",
    "station",
    "port",
    "garden",
    "bridge",
    "hill",
    "hall",
    "house",
    "inn",
    "village",
    "town",
    "city",
    "county",
    "river",
    "forest",
    "castle",
    "kingdom",
    "empire",
    "school",
    "church",
    "hospital",
}
ORGANIZATION_TERMS = {
    "company",
    "council",
    "committee",
    "department",
    "guild",
    "office",
    "society",
    "university",
}
OBJECT_TERMS = {
    "book",
    "boat",
    "carriage",
    "cart",
    "letter",
    "door",
    "window",
    "table",
    "chair",
    "bed",
    "box",
    "coat",
    "hat",
    "room",
    "ship",
    "train",
    "vessel",
    "wagon",
}
TITLE_ROLE_TERMS = {
    "doctor",
    "professor",
    "captain",
    "inspector",
    "officer",
    "maid",
    "servant",
    "stranger",
    "mariner",
    "man",
    "woman",
    "boy",
    "girl",
}


@dataclass(frozen=True)
class CandidateAdjudication:
    raw_name: str
    display_name: str
    normalized_name: str
    entity_type: str
    adjudication_status: str
    character_score: int
    confidence: float
    reason_codes: tuple[str, ...]
    rejection_reason: str | None
    evidence_windows: tuple[dict[str, Any], ...]


def adjudicate_character_candidate(
    name: str | None,
    *,
    aliases: Sequence[object] | None = None,
    confidence: object | None = None,
    evidence: Mapping[str, Any] | None = None,
    reason_codes: Sequence[object] | None = None,
    matched_character_id: object | None = None,
) -> CandidateAdjudication:
    raw_name = str(name or "")
    display_name = display_name_form(raw_name)
    normalized_name = normalized_comparison_name(display_name)
    evidence_map = dict(evidence or {})
    evidence_windows = collect_candidate_evidence_windows(display_name, evidence_map)
    entity_type, type_reasons = classify_entity_type(display_name, evidence_map)
    score, score_reasons = score_character_likeness(
        display_name,
        aliases=aliases,
        evidence=evidence_map,
        evidence_windows=evidence_windows,
        entity_type=entity_type,
    )
    status, status_reason = adjudication_status_for_score(
        score,
        entity_type=entity_type,
        matched_character_id=matched_character_id,
    )
    rejection_reason = (
        status_reason
        if status
        in {
            ADJUDICATION_REJECTED,
            ADJUDICATION_PLACE,
            ADJUDICATION_ORGANIZATION,
            ADJUDICATION_OBJECT,
            ADJUDICATION_TITLE_OR_ROLE,
        }
        else None
    )
    return CandidateAdjudication(
        raw_name=raw_name,
        display_name=display_name,
        normalized_name=normalized_name,
        entity_type=entity_type,
        adjudication_status=status,
        character_score=score,
        confidence=_coerce_confidence(confidence),
        reason_codes=tuple(
            _dedupe([*(reason_codes or []), *type_reasons, *score_reasons, status_reason])
        ),
        rejection_reason=rejection_reason,
        evidence_windows=tuple(evidence_windows),
    )


def classify_entity_type(
    name: str | None, evidence: Mapping[str, Any] | None = None
) -> tuple[str, list[str]]:
    display_name = display_name_form(name)
    words = [word.casefold() for word in entity_words(display_name)]
    reasons: list[str] = []
    if not display_name or not words:
        return ENTITY_JUNK, ["junk_shape"]
    if len(words) == 1 and len(words[0]) == 1:
        return ENTITY_JUNK, ["one_letter_fragment"]
    if _mostly_punctuation_or_numbers(display_name):
        return ENTITY_JUNK, ["punctuation_or_number_noise"]

    kind = classify_candidate_kind(display_name)
    if kind in {CandidateKind.FRAGMENT, CandidateKind.PRONOUN}:
        return ENTITY_JUNK, [f"candidate_kind_{kind.value}"]
    if kind == CandidateKind.GROUP_DESCRIPTOR:
        return ENTITY_TITLE_OR_ROLE, [f"candidate_kind_{kind.value}"]
    if kind in {
        CandidateKind.ROLE_DESCRIPTOR,
        CandidateKind.TITLE_NAME,
        CandidateKind.KINSHIP_DESCRIPTOR,
    }:
        reasons.append(f"candidate_kind_{kind.value}")
        if _has_human_evidence(evidence or {}):
            return ENTITY_ALIAS_CANDIDATE, reasons
        return ENTITY_TITLE_OR_ROLE, reasons
    if kind == CandidateKind.OBJECT_OR_PLACE:
        reasons.append("candidate_kind_object_or_place")
        if not _has_human_evidence(evidence or {}):
            return ENTITY_OBJECT, reasons

    if any(term in words for term in ORGANIZATION_TERMS):
        return ENTITY_ORGANIZATION, ["organization_term"]
    if any(term in words for term in PLACE_TERMS):
        if _has_human_evidence(evidence or {}):
            return ENTITY_ALIAS_CANDIDATE, ["place_shape_with_human_evidence"]
        return ENTITY_PLACE, ["place_term"]
    if any(term in words for term in OBJECT_TERMS):
        return ENTITY_OBJECT, ["object_term"]
    if len(words) >= 2 and words[-1] in {"man", "woman", "boy", "girl", "stranger"}:
        return ENTITY_ALIAS_CANDIDATE, ["generic_title_alias_candidate"]
    if words[0] in {"the", "a", "an"} and len(words) >= 2:
        noun = words[-1]
        if noun in TITLE_ROLE_TERMS:
            return ENTITY_ALIAS_CANDIDATE, ["article_title_alias_candidate"]
        return ENTITY_UNKNOWN, ["article_phrase"]
    if len(words) == 1:
        return ENTITY_ALIAS_CANDIDATE, ["single_token_alias_candidate"]
    return ENTITY_PERSON, reasons or ["person_name_shape"]


def collect_candidate_evidence_windows(
    name: str | None, evidence: Mapping[str, Any]
) -> list[dict[str, Any]]:
    display_name = display_name_form(name)
    windows: list[dict[str, Any]] = []
    for raw_windows in _candidate_window_sources(evidence):
        for raw in raw_windows:
            if not isinstance(raw, Mapping):
                continue
            text = _compact_text(raw.get("window") or raw.get("text") or raw.get("snippet") or "")
            if not text:
                continue
            windows.append(_window_features(display_name, text, raw))
            if len(windows) >= 8:
                return windows

    for key in ("snippets", "mention_texts", "passages", "local_passages"):
        raw_value = evidence.get(key)
        values = (
            raw_value
            if isinstance(raw_value, list)
            else [raw_value]
            if isinstance(raw_value, str)
            else []
        )
        for value in values:
            text = _compact_text(value)
            if not text:
                continue
            windows.append(_window_features(display_name, text, {}))
            if len(windows) >= 8:
                return windows

    for key in ("mention_text", "local_passage"):
        text = _compact_text(evidence.get(key))
        if text:
            windows.append(_window_features(display_name, text, {}))
    return windows[:8]


def score_character_likeness(
    name: str | None,
    *,
    aliases: Sequence[object] | None = None,
    evidence: Mapping[str, Any],
    evidence_windows: Sequence[Mapping[str, Any]],
    entity_type: str,
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    verifier_local = _verifier_local_evidence(evidence)
    mention_count = _int_value(
        evidence.get("mention_count")
        or evidence.get("cluster_mention_count")
        or verifier_local.get("mention_count")
    )
    chapter_numbers = evidence.get("chapter_numbers")
    chapter_count = (
        len(
            {
                int(chapter)
                for chapter in chapter_numbers
                if isinstance(chapter, int) or str(chapter).isdigit()
            }
        )
        if isinstance(chapter_numbers, list)
        else 0
    )

    if any(window.get("dialogue_attribution") for window in evidence_windows) or evidence.get(
        "dialogue_support"
    ):
        score += 25
        reasons.append("dialogue_attribution")
    if any(window.get("subject_action") for window in evidence_windows) or evidence.get(
        "has_dialogue_or_action"
    ):
        score += 20
        reasons.append("human_action")
    if any(window.get("human_pronouns") for window in evidence_windows):
        score += 15
        reasons.append("nearby_human_pronouns")
    if any(window.get("person_ner") for window in evidence_windows):
        score += 15
        reasons.append("person_ner_window")
    if any(window.get("trait_words") for window in evidence_windows) or evidence.get(
        "has_physical_description"
    ):
        score += 15
        reasons.append("trait_evidence")
    if chapter_count >= 2 or evidence.get("appears_multiple_times") or mention_count >= 2:
        score += 10
        reasons.append("multiple_mentions")
    if any(window.get("relationship_words") for window in evidence_windows):
        score += 10
        reasons.append("relationship_evidence")

    visibility = character_visibility_score(name, aliases=[str(alias) for alias in aliases or []])
    if visibility >= 2:
        score += 10
        reasons.append("visibility_score_person_like")

    words = [word.casefold() for word in entity_words(name)]
    if (
        entity_type == ENTITY_PERSON
        and len(words) >= 2
        and mention_count >= 2
        and _has_human_evidence(evidence)
    ):
        score += 5
        reasons.append("full_name_human_evidence")
    if (
        entity_type == ENTITY_PERSON
        and mention_count >= 2
        and _has_named_profile_claim_evidence(name, aliases, evidence)
    ):
        score += 15
        reasons.append("cited_profile_person_evidence")
    if entity_type == ENTITY_JUNK:
        score -= 40
        reasons.append("junk_shape")
    if entity_type == ENTITY_PLACE and not _has_human_evidence(evidence):
        score -= 30
        reasons.append("place_without_human_evidence")
    if any(
        window.get("location_preposition") for window in evidence_windows
    ) and not _has_human_evidence(evidence):
        score -= 25
        reasons.append("location_preposition_context")
    if mention_count <= 1 and not _has_human_evidence(evidence):
        score -= 20
        reasons.append("single_mention_low_evidence")
    if entity_type == ENTITY_ALIAS_CANDIDATE and mention_count <= 1:
        score -= 15
        reasons.append("single_mention_alias_needs_review")
    if evidence.get("front_matter_only") or evidence.get("heading_only"):
        score -= 20
        reasons.append("heading_or_front_matter_only")
    if words and words[0] == "the" and len(words) <= 3:
        score -= 15
        reasons.append("article_phrase_without_proper_name")

    return max(-100, min(100, score)), reasons


def _has_named_profile_claim_evidence(
    name: str | None, aliases: Sequence[object] | None, evidence: Mapping[str, Any]
) -> bool:
    """Count a verified, named source quote as positive character evidence."""
    claims = evidence.get("profile_claims")
    if not isinstance(claims, Mapping):
        return False
    names = [str(value).strip() for value in [name, *(aliases or [])] if str(value).strip()]
    if not names:
        return False

    def cited_quotes(value: object) -> Iterator[str]:
        if not isinstance(value, Mapping):
            return
        if "quote" in value:
            if (
                isinstance(value.get("start"), int)
                and isinstance(value.get("end"), int)
                and value.get("source_batch_key")
            ):
                yield str(value.get("quote") or "")
            return
        for nested in value.values():
            yield from cited_quotes(nested)

    return any(
        len(quote.split()) >= 5
        and any(
            re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", quote, re.IGNORECASE)
            for candidate in names
        )
        for quote in cited_quotes(claims)
    )


def adjudication_status_for_score(
    score: int,
    *,
    entity_type: str,
    matched_character_id: object | None = None,
) -> tuple[str, str]:
    if (
        matched_character_id is not None
        and entity_type in {ENTITY_PERSON, ENTITY_ALIAS_CANDIDATE}
        and score >= 35
    ):
        return ADJUDICATION_MERGED_ALIAS, "matched_existing_character"
    if entity_type == ENTITY_JUNK:
        return ADJUDICATION_REJECTED, "junk_fragment"
    if entity_type == ENTITY_PLACE and score < 60:
        return ADJUDICATION_PLACE, "likely_place"
    if entity_type == ENTITY_ORGANIZATION and score < 60:
        return ADJUDICATION_ORGANIZATION, "likely_organization"
    if entity_type == ENTITY_OBJECT and score < 60:
        return ADJUDICATION_OBJECT, "likely_object"
    if entity_type == ENTITY_TITLE_OR_ROLE and score < 60:
        return ADJUDICATION_TITLE_OR_ROLE, "title_or_role_without_person_evidence"
    if entity_type == ENTITY_ALIAS_CANDIDATE and matched_character_id is None and score < 70:
        return ADJUDICATION_QUARANTINED, "alias_candidate_needs_review"
    if score >= 60:
        return ADJUDICATION_PROMOTED_CHARACTER, "score_promote"
    if score >= 15:
        return ADJUDICATION_QUARANTINED, "score_quarantine"
    return ADJUDICATION_REJECTED, "score_reject"


def _window_features(name: str, text: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    lowered = text.casefold()
    name_pattern = re.escape(name.casefold()) if name else ""
    dialogue_attribution = (
        bool(raw.get("dialogue_attribution"))
        or bool(
            name_pattern
            and re.search(
                rf"\b{name_pattern}\b[^.!?]{{0,40}}\b({'|'.join(DIALOGUE_VERBS)})\b", lowered
            )
        )
        or bool(
            name_pattern
            and re.search(
                rf"\b({'|'.join(DIALOGUE_VERBS)})\b[^.!?]{{0,40}}\b{name_pattern}\b", lowered
            )
        )
    )
    subject_action = bool(raw.get("subject_action") or raw.get("has_person_context")) or bool(
        name_pattern
        and re.search(rf"\b{name_pattern}\b\s+(?:{'|'.join(HUMAN_ACTION_VERBS)})\b", lowered)
    )
    tokens = set(re.findall(r"[a-z][a-z'-]*", lowered))
    return {
        "text": text[:700],
        "dialogue_attribution": dialogue_attribution,
        "subject_action": subject_action,
        "person_ner": str(raw.get("ner_label") or "").strip().upper() == "PERSON",
        "human_pronouns": sorted(tokens & HUMAN_PRONOUNS),
        "location_preposition": bool(tokens & LOCATION_PREPOSITIONS),
        "trait_words": sorted(tokens & TRAIT_WORDS),
        "relationship_words": sorted(tokens & RELATIONSHIP_WORDS),
    }


def _has_human_evidence(evidence: Mapping[str, Any]) -> bool:
    verifier_local = _verifier_local_evidence(evidence)
    verifier_final = _verifier_final_evidence(evidence)
    return bool(
        evidence.get("has_dialogue_or_action")
        or evidence.get("has_physical_description")
        or verifier_final.get("is_person_like")
        or _int_value(verifier_local.get("subject_action_mentions")) >= 1
        or _int_value(verifier_local.get("person_context_mentions")) >= 1
        or _int_value(verifier_local.get("person_ner_mentions")) >= 1
        or _int_value(evidence.get("strong_mention_count")) >= 1
        or _int_value(evidence.get("dialogue_support")) >= 1
        or _int_value(evidence.get("person_context_mentions")) >= 1
        or _int_value(evidence.get("person_ner_mentions")) >= 1
    )


def _candidate_window_sources(evidence: Mapping[str, Any]) -> list[list[object]]:
    sources: list[list[object]] = []
    for key in ("mention_windows", "windows", "evidence_windows"):
        raw_windows = evidence.get(key)
        if isinstance(raw_windows, list):
            sources.append(raw_windows)
    verifier_local = _verifier_local_evidence(evidence)
    local_windows = verifier_local.get("windows")
    if isinstance(local_windows, list):
        sources.append(local_windows)
    return sources


def _verifier_local_evidence(evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    verifier = evidence.get("verifier")
    if not isinstance(verifier, Mapping):
        return {}
    local = verifier.get("local")
    return local if isinstance(local, Mapping) else {}


def _verifier_final_evidence(evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    verifier = evidence.get("verifier")
    if not isinstance(verifier, Mapping):
        return {}
    final = verifier.get("final")
    return final if isinstance(final, Mapping) else {}


def _mostly_punctuation_or_numbers(value: str) -> bool:
    compact = re.sub(r"\s+", "", value)
    if not compact:
        return True
    non_letters = sum(1 for char in compact if not char.isalpha())
    return non_letters / max(1, len(compact)) >= 0.65


def _compact_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _coerce_confidence(value: object | None) -> float:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric if numeric <= 1 else numeric / 100))


def _int_value(value: object | None) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dedupe(values: Sequence[object]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        item = str(value or "").strip()
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned
