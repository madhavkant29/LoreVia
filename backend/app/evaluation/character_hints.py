"""Offline diagnostics for deterministic character discovery and cleaning."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.engine.character.extractor import (
    _clean_character_entries,
    _local_mention_verifier,
    _normalize_name,
    collect_character_discovery_hints,
)
from app.services.extraction_character_decision_service import (
    _can_auto_save_character,
    _entity_dossier_summary,
)

NON_NAME_REFERENCES = {
    "i",
    "me",
    "my",
    "mine",
    "he",
    "him",
    "his",
    "she",
    "her",
    "hers",
    "they",
    "them",
    "their",
    "theirs",
    "we",
    "us",
    "our",
    "you",
    "your",
}


def evaluate_unlabeled_hint_auto_promotion(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Estimate false-save risk if a model proposes an unlabeled name hint.

    Corpus character labels are assumed complete. This is a conditional local
    gate check, not a measurement of the model's actual false positives.
    """
    scored = 0
    locally_accepted = 0
    auto_eligible: list[dict[str, str]] = []
    for case in cases:
        source = str(case.get("text") or "")
        strict_hints, review_hints = collect_character_discovery_hints(source)
        labeled_mentions = {
            _normalize_name(mention)
            for character in (case.get("labels") or {}).get("characters") or []
            for mention in [
                character.get("canonical_name") or character.get("name"),
                *(character.get("mentions") or []),
            ]
            if isinstance(mention, str) and mention.strip()
        }
        for hint in dict.fromkeys([*strict_hints, *review_hints]):
            if _normalize_name(hint) in labeled_mentions:
                continue
            scored += 1
            cleaned = _clean_character_entries(
                [{"name": hint, "entity_type": "person", "is_character": True, "confidence": 0.9}],
                strict_hints,
                source,
            )
            if not cleaned:
                continue
            entity = cleaned[0]
            local = _local_mention_verifier(source, str(entity["name"]))
            if local.get("confidence_band") != "accept":
                continue
            locally_accepted += 1
            evidence = dict(entity.get("evidence") or {})
            evidence["verifier"] = {
                "local": local,
                "llm": {"used": False},
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": list(local.get("reasons") or []),
                },
            }
            entity["evidence"] = evidence
            if _can_auto_save_character(entity):
                auto_eligible.append({"case_id": str(case.get("id")), "hint": hint})
    return {
        "scope": "unlabeled_hint_local_verifier_and_save_gate_no_ai",
        "case_count": len(cases),
        "unlabeled_hint_count": scored,
        "local_accept_count": locally_accepted,
        "auto_save_eligible_count": len(auto_eligible),
        "auto_save_eligible_hints": auto_eligible,
    }


def _source_exact_gold_name(character: dict[str, Any], source: str) -> str | None:
    canonical = character.get("canonical_name") or character.get("name")
    for mention in [canonical, *(character.get("mentions") or [])]:
        if (
            isinstance(mention, str)
            and len(mention.strip()) >= 3
            and mention.strip().casefold() not in NON_NAME_REFERENCES
            and mention.strip() in source
        ):
            return mention.strip()
    return None


def evaluate_gold_candidate_auto_promotion(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure the local-verifier and save-policy ceiling with correct model names.

    This does not call a provider or measure model recall. A local ``review``
    verdict is counted separately because production requests another model
    decision before persisting such candidates. Optional local NER can affect
    the result; the production image does not install that model by default.
    """
    scored = 0
    unscored = 0
    cleaner_survived = 0
    local_accepted = 0
    auto_eligible = 0
    local_review = 0
    local_rejected = 0
    hold_reasons: Counter[str] = Counter()
    for case in cases:
        source = str(case.get("text") or "")
        strict_hints, _review_hints = collect_character_discovery_hints(source)
        for character in (case.get("labels") or {}).get("characters") or []:
            name = _source_exact_gold_name(character, source)
            if name is None:
                unscored += 1
                continue
            scored += 1
            cleaned = _clean_character_entries(
                [{"name": name, "entity_type": "person", "is_character": True, "confidence": 0.9}],
                strict_hints,
                source,
            )
            if not cleaned:
                hold_reasons["cleaner_rejected"] += 1
                continue
            cleaner_survived += 1
            entity = cleaned[0]
            local = _local_mention_verifier(source, str(entity["name"]))
            band = str(local.get("confidence_band") or "")
            if band == "review":
                local_review += 1
                continue
            if band == "reject":
                local_rejected += 1
                continue
            local_accepted += 1
            evidence = dict(entity.get("evidence") or {})
            evidence["verifier"] = {
                "local": local,
                "llm": {"used": False},
                "final": {
                    "confidence_band": "accept",
                    "is_person_like": True,
                    "reasons": list(local.get("reasons") or []),
                },
            }
            entity["evidence"] = evidence
            if _can_auto_save_character(entity):
                auto_eligible += 1
            else:
                reasons = _entity_dossier_summary(entity)["strict_auto_reason_codes"]
                for reason in reasons or ["persistence_gate"]:
                    hold_reasons[str(reason)] += 1
    return {
        "scope": "gold_candidate_local_verifier_and_save_gate_no_ai",
        "case_count": len(cases),
        "scored_character_count": scored,
        "unscored_character_count": unscored,
        "cleaner_survived_count": cleaner_survived,
        "local_accept_count": local_accepted,
        "local_review_count": local_review,
        "local_reject_count": local_rejected,
        "auto_save_eligible_count": auto_eligible,
        "auto_save_eligibility_rate": round(auto_eligible / scored, 4) if scored else None,
        "hold_reasons": dict(sorted(hold_reasons.items())),
    }


def evaluate_gold_character_candidate_survival(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure whether the deterministic cleaner retains a correct model-supplied person.

    This is a conditional recall ceiling, not a live model or final-cast score.
    The model is simulated by supplying one source-exact gold name per identity.
    """
    misses: list[dict[str, Any]] = []
    scored = 0
    survived = 0
    unscored = 0
    joint_cases_scored = 0
    joint_cases_preserved = 0
    joint_identity_risks: list[dict[str, Any]] = []
    for case in cases:
        source = str(case.get("text") or "")
        strict_hints, _review_hints = collect_character_discovery_hints(source)
        joint_inputs: list[dict[str, Any]] = []
        joint_expected: dict[str, str] = {}
        for character in (case.get("labels") or {}).get("characters") or []:
            canonical = character.get("canonical_name") or character.get("name")
            name = _source_exact_gold_name(character, source)
            if name is None:
                unscored += 1
                continue
            scored += 1
            rejected: list[dict[str, Any]] = []
            cleaned = _clean_character_entries(
                [{"name": name, "entity_type": "person", "is_character": True, "confidence": 0.9}],
                strict_hints,
                source,
                rejected_characters=rejected,
            )
            if cleaned:
                survived += 1
                joint_inputs.append(
                    {"name": name, "entity_type": "person", "is_character": True, "confidence": 0.9}
                )
                joint_expected[str(canonical)] = _normalize_name(str(cleaned[0]["name"]))
            else:
                misses.append(
                    {
                        "case_id": case.get("id"),
                        "character": canonical,
                        "source_name": name,
                        "rejection_reasons": [item.get("reason") for item in rejected],
                    }
                )
        if len(joint_expected) >= 2:
            joint_cases_scored += 1
            jointly_cleaned = _clean_character_entries(joint_inputs, strict_hints, source)
            joint_names = {_normalize_name(str(item["name"])) for item in jointly_cleaned}
            missing_identities = [
                canonical
                for canonical, expected_name in joint_expected.items()
                if expected_name not in joint_names
                or list(joint_expected.values()).count(expected_name) > 1
            ]
            if missing_identities:
                joint_identity_risks.append(
                    {"case_id": case.get("id"), "missing_or_collapsed": missing_identities}
                )
            else:
                joint_cases_preserved += 1
    return {
        "scope": "gold_candidate_deterministic_cleaner_only",
        "case_count": len(cases),
        "scored_character_count": scored,
        "survived_character_count": survived,
        "unscored_character_count": unscored,
        "conditional_survival_rate": round(survived / scored, 4) if scored else None,
        "misses": misses,
        "joint_identity_cases_scored": joint_cases_scored,
        "joint_identity_cases_preserved": joint_cases_preserved,
        "joint_identity_preservation_rate": (
            round(joint_cases_preserved / joint_cases_scored, 4) if joint_cases_scored else None
        ),
        "joint_identity_risks": joint_identity_risks,
    }


def evaluate_character_name_hints(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure recall of source-named people in regex hints, not final cast quality.

    Unnamed people and references without a source-supported capitalized name are
    reported as unscored because the hint stage is not expected to identify them.
    """
    misses: list[dict[str, Any]] = []
    scored = 0
    hinted = 0
    unscored = 0
    strict_hint_count = 0
    labeled_strict_hint_count = 0
    unlabeled_strict_hints: list[dict[str, Any]] = []
    for case in cases:
        source = str(case.get("text") or "")
        strict_hints, review_hints = collect_character_discovery_hints(source)
        hints = {_normalize_name(name) for name in strict_hints + review_hints}
        labeled_mentions: set[str] = set()
        for character in (case.get("labels") or {}).get("characters") or []:
            mentions = character.get("mentions") or []
            named_mentions = [
                mention
                for mention in mentions
                if isinstance(mention, str)
                and len(mention.strip()) >= 3
                and mention.strip()[0].isupper()
                and mention in source
            ]
            if not named_mentions:
                unscored += 1
                continue
            labeled_mentions.update(_normalize_name(mention) for mention in named_mentions)
            scored += 1
            if any(_normalize_name(mention) in hints for mention in named_mentions):
                hinted += 1
            else:
                misses.append(
                    {
                        "case_id": case.get("id"),
                        "character": character.get("canonical_name") or character.get("name"),
                        "source_mentions": named_mentions,
                    }
                )
        for name in strict_hints:
            strict_hint_count += 1
            if _normalize_name(name) in labeled_mentions:
                labeled_strict_hint_count += 1
            else:
                unlabeled_strict_hints.append({"case_id": case.get("id"), "hint": name})
    return {
        "scope": "deterministic_name_hints_only",
        "case_count": len(cases),
        "scored_character_count": scored,
        "hinted_character_count": hinted,
        "unscored_character_count": unscored,
        "named_hint_coverage": round(hinted / scored, 4) if scored else None,
        "strict_hint_count": strict_hint_count,
        "labeled_strict_hint_count": labeled_strict_hint_count,
        "strict_hint_label_match_rate": (
            round(labeled_strict_hint_count / strict_hint_count, 4) if strict_hint_count else None
        ),
        "unlabeled_strict_hints": unlabeled_strict_hints,
        "misses": misses,
    }
