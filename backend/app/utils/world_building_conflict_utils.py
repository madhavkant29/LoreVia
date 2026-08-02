from __future__ import annotations

import re
from collections import defaultdict

from app.engine.character.deduplicator import names_equivalent
from app.engine.world.extractor import extract_claims_from_text
from app.utils.characters.identity import normalize_character_name
from app.utils.characters.similarity import name_similarity

WORLD_KEEPABLE_TYPES = {
    "character",
    "concept",
    "country",
    "creature",
    "culture",
    "currency",
    "era",
    "event",
    "language",
    "law",
    "magic_system",
    "object",
    "organization",
    "place",
    "politics",
    "power_limit",
    "race",
    "region",
    "religion",
    "technology",
    "travel_rule",
}

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "of",
    "to",
    "in",
    "for",
    "with",
    "on",
    "at",
    "from",
    "by",
    "is",
    "are",
    "was",
    "were",
}
CLIMATE_BUCKETS = {
    "cold": {"cold", "frozen", "snow", "snowbound", "icy", "ice", "winter"},
    "hot": {"desert", "arid", "drought", "sun-scorched", "burning", "heat"},
    "wet": {"rain", "storm", "flooded", "marsh", "mist", "wet"},
}


def _world_names_equivalent(left: str | None, right: str | None) -> bool:
    left_normalized = _normalize_world_name(left)
    right_normalized = _normalize_world_name(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    if names_equivalent(left, [], right, []):
        return True
    return name_similarity(left, right) >= 0.9


def _normalize_world_name(name: str | None) -> str:
    normalized = normalize_character_name(name)
    if normalized:
        return normalized
    return " ".join(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", name or "")).strip().lower()


def _world_text_mentions_name(world_text: str, name: str) -> bool:
    normalized_name = _normalize_world_name(name)
    if not normalized_name:
        return False
    if normalized_name in world_text:
        return True
    world_tokens = set(re.findall(r"[a-z0-9']+", world_text))
    name_tokens = [token for token in normalized_name.split() if token]
    return bool(name_tokens) and set(name_tokens).issubset(world_tokens)


def _should_surface_world_item(world_item: dict) -> bool:
    element_type = str(world_item.get("element_type") or "")
    confidence = float(world_item.get("confidence") or 0.0)
    usage_count = int(world_item.get("usage_count") or 0)
    if element_type not in WORLD_KEEPABLE_TYPES:
        return False
    if confidence < 0.5 and usage_count < 2:
        return False
    return True


def _should_surface_story_item(story_item: dict) -> bool:
    element_type = str(story_item.get("element_type") or "")
    usage_count = int(story_item.get("usage_count") or 0)
    chapter_count = int(
        story_item.get("chapter_count") or len(story_item.get("chapter_numbers") or [])
    )
    presence_score = float(story_item.get("presence_score") or 0.0)
    confidence = float(story_item.get("confidence") or 0.0)
    if element_type not in WORLD_KEEPABLE_TYPES:
        return False
    if presence_score >= 0.62:
        return True
    if usage_count >= 3 and chapter_count >= 2 and confidence >= 0.58:
        return True
    return False


def _is_underintegrated_story_match(story_item: dict) -> bool:
    presence_score = float(story_item.get("presence_score") or 0.0)
    usage_count = int(story_item.get("usage_count") or 0)
    chapter_count = int(
        story_item.get("chapter_count") or len(story_item.get("chapter_numbers") or [])
    )
    return presence_score < 0.58 or usage_count <= 1 or chapter_count <= 1


def _detect_internal_candidate_conflicts(records: list[dict], *, source_kind: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        normalized_name = _normalize_world_name(
            str(record.get("canonical_name") or record.get("name") or "")
        )
        if not normalized_name:
            continue
        grouped[normalized_name].append(record)

    items: list[dict] = []
    for candidates in grouped.values():
        if len(candidates) < 2:
            continue
        ordered = sorted(
            candidates,
            key=lambda item: (
                int(item.get("chapter_number") or 0),
                str(item.get("world_document_title") or ""),
                str(item.get("description") or ""),
            ),
        )
        conflict_detail: dict | None = None
        for index, left_item in enumerate(ordered):
            for right_item in ordered[index + 1 :]:
                if _same_source_reference(left_item, right_item, source_kind=source_kind):
                    continue
                conflict_detail = _build_internal_conflict_detail(
                    left_item, right_item, source_kind=source_kind
                )
                if conflict_detail is not None:
                    break
            if conflict_detail is not None:
                break
        if conflict_detail is not None:
            items.append(conflict_detail)
    return items


def _same_source_reference(left_item: dict, right_item: dict, *, source_kind: str) -> bool:
    if source_kind == "story":
        return int(left_item.get("chapter_number") or 0) == int(
            right_item.get("chapter_number") or 0
        )
    return str(left_item.get("world_document_id") or "") == str(
        right_item.get("world_document_id") or ""
    )


def _build_internal_conflict_detail(
    left_item: dict, right_item: dict, *, source_kind: str
) -> dict | None:
    name = str(
        left_item.get("canonical_name") or left_item.get("name") or right_item.get("name") or ""
    ).strip()
    left_claims = _claims_by_attribute(left_item.get("claims") or [])
    right_claims = _claims_by_attribute(right_item.get("claims") or [])
    for attribute, attribute_left_claims in left_claims.items():
        attribute_right_claims = right_claims.get(attribute) or []
        for left_claim in attribute_left_claims:
            for right_claim in attribute_right_claims:
                if _claims_contradict(left_claim, right_claim):
                    detail = _build_conflict_detail(
                        name,
                        left_item,
                        right_item,
                        left_claim,
                        right_claim,
                        source_kind=source_kind,
                    )
                    detail["id"] = f"story_conflicts-{_normalize_world_name(name)}-{source_kind}"
                    return detail
    if not _descriptions_conflict(
        str(left_item.get("description") or ""), str(right_item.get("description") or "")
    ):
        return None
    left_label = _source_label(left_item, source_kind=source_kind)
    right_label = _source_label(right_item, source_kind=source_kind)
    return {
        "id": f"story_conflicts-{_normalize_world_name(name)}-{source_kind}",
        "category": "story_conflicts",
        "severity": "critical",
        "title": f"{name} conflicts across the {'manuscript' if source_kind == 'story' else 'world notes'}",
        "description": f"{name} is described differently in {left_label} and {right_label}.",
        "suggested_fix": f"Choose the canonical version of {name} and revise the conflicting {'chapter' if source_kind == 'story' else 'worldbuilding note'} so both references align.",
        "world_evidence": _best_evidence_text(left_item),
        "story_evidence": _best_evidence_text(right_item),
        "world_document_id": str(left_item.get("world_document_id") or "") or None,
        "world_document_title": str(left_item.get("world_document_title") or "") or None,
        "story_chapter_number": int(right_item.get("chapter_number") or 0) or None,
        "story_chapter_title": str(right_item.get("chapter_title") or "") or None,
        "character_name": None,
        "priority": 10,
        "entity_type": str(left_item.get("element_type") or right_item.get("element_type") or ""),
        "canonical_name": name,
        "confidence": max(
            float(left_item.get("confidence") or 0.0), float(right_item.get("confidence") or 0.0)
        ),
        "provenance": {
            "world": list(left_item.get("provenance") or [])[:2],
            "story": list(right_item.get("provenance") or [])[:2],
        },
    }


def _build_cross_source_conflict_detail(world_item: dict, story_item: dict) -> dict | None:
    world_claims = _claims_by_attribute(world_item.get("claims") or [])
    story_claims = _claims_by_attribute(story_item.get("claims") or [])
    if world_claims and story_claims:
        for attribute, left_claims in world_claims.items():
            right_claims = story_claims.get(attribute) or []
            if not right_claims:
                continue
            for left_claim in left_claims:
                for right_claim in right_claims:
                    if _claims_contradict(left_claim, right_claim):
                        return _build_conflict_detail(
                            str(world_item.get("name") or ""),
                            world_item,
                            story_item,
                            left_claim,
                            right_claim,
                            source_kind="cross_source",
                        )
        return None

    if not _descriptions_conflict(
        str(world_item.get("description") or ""), str(story_item.get("description") or "")
    ):
        return None
    return {
        "title": f"{world_item['name']} conflicts with the story manuscript",
        "description": "The story manuscript describes this lore differently from the world-building corpus.",
        "suggested_fix": f"Choose the canonical version of {world_item['name']} and update either the world document or the relevant story chapter to match it.",
        "world_evidence": _best_evidence_text(world_item),
        "story_evidence": _best_evidence_text(story_item),
    }


def _build_conflict_detail(
    name: str,
    left_item: dict,
    right_item: dict,
    left_claim: dict,
    right_claim: dict,
    *,
    source_kind: str,
) -> dict:
    left_label = _source_label(left_item, source_kind=source_kind)
    right_label = _source_label(right_item, source_kind=source_kind)
    subject = _conflict_subject(
        name, str(left_item.get("element_type") or right_item.get("element_type") or "")
    )
    description = (
        f"{subject} is described as {_claim_phrase(left_claim)} in {left_label}, "
        f"but {_claim_phrase(right_claim)} in {right_label}. No explanation found in the extracted canon."
    )
    return {
        "title": f"{name} conflicts with the {'story manuscript' if source_kind == 'cross_source' else ('manuscript itself' if source_kind == 'story' else 'world notes')}",
        "description": description,
        "suggested_fix": f"Choose whether {left_label} or {right_label} is canonical for {name}, then update the conflicting reference and add an explicit explanation if the change is intentional.",
        "world_evidence": _best_evidence_text(left_item),
        "story_evidence": _best_evidence_text(right_item),
        "world_document_id": str(left_item.get("world_document_id") or "") or None,
        "world_document_title": str(left_item.get("world_document_title") or "") or None,
        "story_chapter_number": int(right_item.get("chapter_number") or 0) or None,
        "story_chapter_title": str(right_item.get("chapter_title") or "") or None,
        "character_name": None,
        "priority": 10,
        "entity_type": str(left_item.get("element_type") or right_item.get("element_type") or ""),
        "canonical_name": name,
        "confidence": max(
            float(left_item.get("confidence") or 0.0), float(right_item.get("confidence") or 0.0)
        ),
        "provenance": {
            "world": list(left_item.get("provenance") or [])[:2],
            "story": list(right_item.get("provenance") or [])[:2],
        },
    }


def _conflict_subject(name: str, element_type: str) -> str:
    if name == "Magic System":
        return "Magic"
    if name == "Political System":
        return "Politics"
    if name == "Travel Constraints":
        return "Travel"
    if name == "Power Limits":
        return "Power use"
    return name


def _source_label(item: dict, *, source_kind: str) -> str:
    if source_kind == "story":
        chapter_number = int(item.get("chapter_number") or 0)
        return f"Chapter {chapter_number}" if chapter_number else "the manuscript"
    if source_kind == "world":
        title = str(item.get("world_document_title") or "").strip()
        return title or "the world corpus"
    if str(item.get("world_document_title") or "").strip():
        return str(item.get("world_document_title")).strip()
    chapter_number = int(item.get("chapter_number") or 0)
    return f"Chapter {chapter_number}" if chapter_number else "the story manuscript"


def _best_evidence_text(item: dict) -> str | None:
    excerpt = str(item.get("source_excerpt") or "").strip()
    if excerpt:
        return excerpt
    provenance = list(item.get("provenance") or [])
    for entry in provenance:
        excerpt = " ".join(str((entry or {}).get("excerpt") or "").split()).strip()
        if excerpt:
            return excerpt
    return " ".join(str(item.get("description") or "").split()).strip() or None


def _claim_phrase(claim: dict) -> str:
    attribute = str(claim.get("attribute") or "").strip().lower()
    value = " ".join(str(claim.get("value") or "").split()).strip()
    negated = bool(claim.get("negated"))
    if attribute == "requirement":
        return f"{'works without' if negated else 'requires'} {value}"
    if attribute == "cost":
        return f"{'happens without' if negated else 'costs'} {value}"
    if attribute == "relative_position":
        return f"is {value}"
    if attribute == "governance":
        return f"is ruled by {value}"
    if attribute == "travel_time":
        return f"takes {value}"
    if attribute == "power_limit":
        return f"{'is not limited by' if negated else 'can only'} {value}"
    if attribute == "currency":
        return f"uses {value}"
    if attribute == "legality":
        return f"{value} is {'legal' if not negated else 'illegal'}"
    if attribute == "location":
        return f"{'is not in' if negated else 'is in'} {value}"
    if attribute == "climate":
        return f"{'is not' if negated else 'is'} {value}"
    if attribute == "descriptor":
        return f"{'is not a' if negated else 'is a'} {value}"
    if attribute == "occupation":
        return f"{'is not a' if negated else 'is a'} {value}"
    return f"{'is not' if negated else 'is'} {value}"


def _claims_by_attribute(claims: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for claim in claims:
        attribute = " ".join(str(claim.get("attribute") or "").split()).strip().lower()
        value = " ".join(str(claim.get("value") or "").split()).strip()
        if not attribute or not value:
            continue
        grouped[attribute].append(
            {
                "attribute": attribute,
                "value": value,
                "confidence": float(claim.get("confidence") or 0.0),
                "negated": bool(claim.get("negated")),
                "cue": " ".join(str(claim.get("cue") or "").split()).strip() or None,
            }
        )
    return grouped


def _claims_contradict(left_claim: dict, right_claim: dict) -> bool:
    attribute = str(left_claim.get("attribute") or "")
    left_value = _normalize_text(str(left_claim.get("value") or ""))
    right_value = _normalize_text(str(right_claim.get("value") or ""))
    left_negated = bool(left_claim.get("negated"))
    right_negated = bool(right_claim.get("negated"))
    if not left_value or not right_value:
        return False
    if left_value == right_value:
        return left_negated != right_negated

    left_numbers = {token for token in left_value.split() if token.isdigit()}
    right_numbers = {token for token in right_value.split() if token.isdigit()}
    if (
        left_numbers
        and right_numbers
        and left_numbers != right_numbers
        and left_negated == right_negated
    ):
        return True

    if attribute == "relative_position":
        left_anchor = left_value.split(" of ", 1)[1] if " of " in left_value else left_value
        right_anchor = right_value.split(" of ", 1)[1] if " of " in right_value else right_value
        if (
            left_anchor == right_anchor
            and left_value != right_value
            and left_negated == right_negated
        ):
            return True

    if attribute == "travel_time" and left_value != right_value and left_negated == right_negated:
        return True

    if (
        attribute in {"requirement", "cost", "power_limit", "governance", "currency", "legality"}
        and left_value != right_value
        and left_negated == right_negated
    ):
        return True

    if attribute == "climate":
        left_bucket = _climate_bucket(left_value)
        right_bucket = _climate_bucket(right_value)
        if left_bucket and right_bucket:
            if left_bucket == right_bucket:
                return left_negated != right_negated
            if left_negated == right_negated:
                return True
            return False

    left_tokens = {token for token in left_value.split() if token not in STOPWORDS}
    right_tokens = {token for token in right_value.split() if token not in STOPWORDS}
    overlap = left_tokens & right_tokens
    if left_negated != right_negated and overlap:
        return True
    if overlap:
        if left_tokens <= right_tokens or right_tokens <= left_tokens:
            return False
        return False

    if left_negated != right_negated:
        return False
    return True


def _extract_claims_from_description(text: str) -> list[dict]:
    return extract_claims_from_text("", text, "concept")


def _descriptions_conflict(left: str, right: str) -> bool:
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right or normalized_left == normalized_right:
        return False

    left_numbers = {token for token in normalized_left.split() if token.isdigit()}
    right_numbers = {token for token in normalized_right.split() if token.isdigit()}
    if left_numbers and right_numbers and left_numbers != right_numbers:
        return True

    left_bucket = _climate_bucket(normalized_left)
    right_bucket = _climate_bucket(normalized_right)
    if left_bucket and right_bucket and left_bucket != right_bucket:
        return True

    left_claims = _claims_by_attribute(_extract_claims_from_description(normalized_left))
    right_claims = _claims_by_attribute(_extract_claims_from_description(normalized_right))
    shared_attributes = set(left_claims) & set(right_claims)
    for attribute in shared_attributes:
        for left_claim in left_claims[attribute]:
            for right_claim in right_claims[attribute]:
                if _claims_contradict(left_claim, right_claim):
                    return True

    return False


def _climate_bucket(text: str) -> str | None:
    tokens = set(text.split())
    for name, words in CLIMATE_BUCKETS.items():
        if tokens & words:
            return name
    return None


def _normalize_text(value: str) -> str:
    return " ".join((value or "").replace("\n", " ").replace("\r", " ").split()).strip().lower()
