from __future__ import annotations

from app.engine.character.deduplicator import names_equivalent
from app.engine.world.extractor import infer_element_type
from app.utils.characters.similarity import name_similarity
from app.utils.world_building_conflict_utils import (
    _normalize_world_name,
    _world_names_equivalent,
)

WORLD_HIGH_SIGNAL_TYPES = {
    "character",
    "country",
    "currency",
    "law",
    "magic_system",
    "object",
    "organization",
    "place",
    "politics",
    "power_limit",
    "race",
    "region",
    "travel_rule",
}


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = " ".join((value or "").split()).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _candidate_priority_score(candidate: dict) -> float:
    description = str(candidate.get("description") or "").strip()
    confidence = float(candidate.get("confidence") or 0.0)
    usage_count = int(candidate.get("usage_count") or 0)
    return confidence + min(0.25, usage_count * 0.05) + min(0.2, len(description) / 500.0)


def _normalize_candidate_record(candidate: dict) -> dict:
    canonical_name = " ".join(
        str(candidate.get("canonical_name") or candidate.get("name") or "").split()
    ).strip()
    name = " ".join(str(candidate.get("name") or canonical_name).split()).strip()
    element_type = (
        " ".join(
            str(
                candidate.get("element_type")
                or infer_element_type(name, str(candidate.get("description") or ""))
            ).split()
        )
        .strip()
        .lower()
        or "concept"
    )
    aliases = _dedupe_strings([name, *[str(alias) for alias in (candidate.get("aliases") or [])]])
    description = " ".join(str(candidate.get("description") or "").split()).strip() or None
    chapter_number = candidate.get("chapter_number")
    provenance = (
        candidate.get("provenance") if isinstance(candidate.get("provenance"), dict) else {}
    )
    claims = [claim for claim in (candidate.get("claims") or []) if isinstance(claim, dict)]
    confidence = max(0.05, min(0.99, float(candidate.get("confidence") or 0.35)))
    return {
        "name": canonical_name or name,
        "canonical_name": canonical_name or name,
        "aliases": aliases,
        "element_type": element_type,
        "description": description,
        "usage_count": int(candidate.get("usage_count") or 1),
        "chapter_number": chapter_number,
        "chapter_numbers": [chapter_number] if chapter_number else [],
        "confidence": confidence,
        "claims": claims,
        "provenance": [provenance] if provenance else [],
        "narrative_modes": [str(provenance.get("narrative_mode") or "")] if provenance else [],
        "source_excerpt": str(provenance.get("excerpt") or description or "").strip() or None,
        "character_id": candidate.get("character_id"),
        "author_override": bool(candidate.get("author_override")),
        "summary_mentions": int(candidate.get("summary_mentions") or 0),
        "presence_score": float(candidate.get("presence_score") or 0.0),
    }


def _apply_character_and_override_resolution(
    candidates: list[dict],
    *,
    character_registry: list[dict],
    override_lookup: dict[str, dict],
) -> list[dict]:
    resolved: list[dict] = []
    for candidate in candidates:
        normalized = _normalize_candidate_record(candidate)
        raw_name = normalized["name"]
        override = _resolve_override(raw_name, normalized["aliases"], override_lookup)
        match = _resolve_character_match(raw_name, normalized["aliases"], character_registry)
        if override is not None:
            normalized["canonical_name"] = override["canonical_name"]
            normalized["name"] = override["canonical_name"]
            normalized["aliases"] = _dedupe_strings(
                [
                    *normalized["aliases"],
                    override["canonical_name"],
                    *(override.get("aliases") or []),
                ]
            )
            if override.get("entity_type"):
                normalized["element_type"] = str(override["entity_type"]).strip().lower()
            normalized["author_override"] = True
            normalized["confidence"] = max(float(normalized.get("confidence") or 0.0), 0.96)
        elif match is not None:
            normalized["canonical_name"] = match["canonical_name"]
            normalized["name"] = match["canonical_name"]
            normalized["aliases"] = _dedupe_strings(
                [*normalized["aliases"], match["canonical_name"], *(match.get("aliases") or [])]
            )
            normalized["element_type"] = "character"
            normalized["character_id"] = match["character_id"]
            normalized["confidence"] = max(float(normalized.get("confidence") or 0.0), 0.9)
        resolved.append(normalized)
    return _merge_canonical_candidates(resolved)


def _resolve_override(
    name: str, aliases: list[str], override_lookup: dict[str, dict]
) -> dict | None:
    keys = {_normalize_world_name(name), *(_normalize_world_name(alias) for alias in aliases)}
    keys.discard("")
    for key in keys:
        if key in override_lookup:
            return override_lookup[key]
    for override in override_lookup.values():
        if _world_names_equivalent(name, override.get("canonical_name")):
            return override
    return None


def _resolve_character_match(
    name: str, aliases: list[str], character_registry: list[dict]
) -> dict | None:
    best_match: dict | None = None
    best_score = 0.0
    for character in character_registry:
        canonical_name = str(character.get("canonical_name") or "").strip()
        character_aliases = [
            str(alias) for alias in (character.get("aliases") or []) if str(alias).strip()
        ]
        if not canonical_name:
            continue
        if not names_equivalent(name, aliases, canonical_name, character_aliases):
            continue
        candidate_names = [canonical_name, *character_aliases]
        score = max(
            max(
                (name_similarity(name, candidate_name) for candidate_name in candidate_names),
                default=0.0,
            ),
            max(
                (
                    name_similarity(alias, candidate_name)
                    for alias in aliases
                    for candidate_name in candidate_names
                ),
                default=0.0,
            ),
        )
        if score >= best_score:
            best_score = score
            best_match = character
    return best_match if best_score >= 0.74 else None


def _merge_canonical_candidates(candidates: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for candidate in candidates:
        key = _normalize_world_name(candidate.get("canonical_name") or candidate.get("name") or "")
        if not key:
            continue
        current = merged.get(key)
        if current is None:
            merged[key] = dict(candidate)
            continue
        current["usage_count"] = int(current.get("usage_count") or 0) + int(
            candidate.get("usage_count") or 0
        )
        current["aliases"] = _dedupe_strings(
            [*(current.get("aliases") or []), *(candidate.get("aliases") or [])]
        )
        current["chapter_numbers"] = sorted(
            {*current.get("chapter_numbers", []), *candidate.get("chapter_numbers", [])}
        )
        current["summary_mentions"] = int(current.get("summary_mentions") or 0) + int(
            candidate.get("summary_mentions") or 0
        )
        current["provenance"] = [*current.get("provenance", []), *candidate.get("provenance", [])][
            :8
        ]
        current["narrative_modes"] = _dedupe_strings(
            [*current.get("narrative_modes", []), *candidate.get("narrative_modes", [])]
        )
        current["claims"] = _merge_claims(
            current.get("claims") or [], candidate.get("claims") or []
        )
        current["confidence"] = max(
            float(current.get("confidence") or 0.0), float(candidate.get("confidence") or 0.0)
        )
        current["author_override"] = bool(current.get("author_override")) or bool(
            candidate.get("author_override")
        )
        current["character_id"] = current.get("character_id") or candidate.get("character_id")
        if _candidate_priority_score(candidate) > _candidate_priority_score(current):
            current["description"] = candidate.get("description")
            current["source_excerpt"] = candidate.get("source_excerpt")
            current["element_type"] = candidate.get("element_type") or current.get("element_type")
        elif not current.get("description") and candidate.get("description"):
            current["description"] = candidate.get("description")
            current["source_excerpt"] = candidate.get("source_excerpt")
        current["presence_score"] = max(
            float(current.get("presence_score") or 0.0),
            float(candidate.get("presence_score") or 0.0),
        )

    normalized_items = list(merged.values())
    for item in normalized_items:
        item["presence_score"] = _presence_score(item)
    return sorted(
        normalized_items,
        key=lambda item: (
            -float(item.get("confidence") or 0.0),
            -int(item.get("usage_count") or 0),
            str(item.get("name") or ""),
        ),
    )


def _merge_claims(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], dict] = {}
    for claim in [*existing, *incoming]:
        attribute = " ".join(str(claim.get("attribute") or "").split()).strip().lower()
        value = " ".join(str(claim.get("value") or "").split()).strip().lower()
        if not attribute or not value:
            continue
        key = (attribute, value)
        current = by_key.get(key)
        if current is None or float(claim.get("confidence") or 0.0) > float(
            current.get("confidence") or 0.0
        ):
            by_key[key] = dict(claim)
    return list(by_key.values())


def _presence_score(candidate: dict) -> float:
    usage_count = int(candidate.get("usage_count") or 0)
    chapter_count = len(candidate.get("chapter_numbers") or [])
    summary_mentions = int(candidate.get("summary_mentions") or 0)
    narrative_modes = {mode for mode in (candidate.get("narrative_modes") or []) if mode}
    confidence = float(candidate.get("confidence") or 0.0)
    score = (
        0.15
        + min(0.25, usage_count * 0.06)
        + min(0.25, chapter_count * 0.12)
        + min(0.15, summary_mentions * 0.07)
    )
    score += min(0.15, confidence * 0.15)
    if narrative_modes and narrative_modes == {"dialogue"}:
        score -= 0.12
    if candidate.get("character_id"):
        score += 0.08
    if str(candidate.get("element_type") or "") in WORLD_HIGH_SIGNAL_TYPES:
        score += 0.05
    return max(0.0, min(0.99, round(score, 3)))
