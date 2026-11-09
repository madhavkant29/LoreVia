"""Offline evaluation of source-backed Voice Review predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.utils.characters.narrator import detect_explicit_first_person_narrator
from app.utils.voice_review_utils import (
    _voice_excerpt_evidence_matches,
    attributed_voice_samples,
    first_person_narration_samples,
    voice_ranges_cover_text,
)

REQUIRED_SCENARIOS = {
    "formal_to_slang",
    "fear_or_anger",
    "earned_growth",
    "first_person_narrator",
    "unattributed_dialogue",
    "shared_surnames_aliases",
    "similar_voices",
    "insufficient_evidence",
    "code_switching",
    "long_passage",
    "fabricated_citation",
    "pronoun_attribution",
    "ambiguous_pronoun",
}
REVIEW_STATUSES = {"complete", "partial_evidence", "insufficient_evidence", "error"}


def load_voice_evaluation_cases(path: Path) -> list[dict[str, Any]]:
    """Load original synthetic cases and expand bounded long-passage fixtures."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("voice_corpus_invalid_shape")
    cases = payload.get("cases")
    library = payload.get("baseline_library")
    if not isinstance(cases, list) or not isinstance(library, dict):
        raise ValueError("voice_corpus_invalid_shape")
    seen_ids: set[str] = set()
    scenarios: set[str] = set()
    expanded: list[dict[str, Any]] = []
    for raw in cases:
        if not isinstance(raw, dict):
            raise ValueError("voice_corpus_invalid_case")
        case_id = str(raw.get("id") or "").strip()
        scenario = str(raw.get("scenario") or "").strip()
        if not case_id or case_id in seen_ids or not scenario:
            raise ValueError("voice_corpus_duplicate_or_missing_id")
        seen_ids.add(case_id)
        scenarios.add(scenario)
        baseline_key = raw.get("baseline_key")
        if not isinstance(baseline_key, str) or not baseline_key:
            raise ValueError(f"voice_corpus_missing_baseline:{case_id}")
        baseline = library.get(baseline_key)
        if not isinstance(baseline, list) or not baseline:
            raise ValueError(f"voice_corpus_missing_baseline:{case_id}")
        limit = raw.get("baseline_limit")
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
                raise ValueError(f"voice_corpus_invalid_baseline_limit:{case_id}")
            baseline = baseline[:limit]
        for sample in baseline:
            if (
                not isinstance(sample, dict)
                or not isinstance(sample.get("chapter_number"), int)
                or sample["chapter_number"] < 1
                or not str(sample.get("excerpt") or "").strip()
            ):
                raise ValueError(f"voice_corpus_invalid_baseline:{case_id}")
        submitted_chapter = raw.get("submitted_chapter")
        if (
            isinstance(submitted_chapter, bool)
            or not isinstance(submitted_chapter, int)
            or submitted_chapter < 1
            or any(sample["chapter_number"] >= submitted_chapter for sample in baseline)
        ):
            raise ValueError(f"voice_corpus_invalid_chapter_order:{case_id}")
        other_keys = raw.get("other_baseline_keys", [])
        if not isinstance(other_keys, list) or any(
            not isinstance(key, str) or not isinstance(library.get(key), list) for key in other_keys
        ):
            raise ValueError(f"voice_corpus_invalid_other_baselines:{case_id}")
        repeat = raw.get("repeat")
        repeat_text = ""
        if repeat is not None:
            if (
                not isinstance(repeat, dict)
                or not isinstance(repeat.get("text"), str)
                or not repeat["text"]
                or isinstance(repeat.get("count"), bool)
                or not isinstance(repeat.get("count"), int)
                or not 1 <= repeat["count"] <= 200
            ):
                raise ValueError(f"voice_corpus_invalid_repeat:{case_id}")
            repeat_text = repeat["text"] * repeat["count"]
        submitted_text = (
            str(raw.get("submitted_text") or "")
            + repeat_text
            + str(raw.get("submitted_tail") or "")
        )
        if not submitted_text.strip() or len(submitted_text) > 12_000:
            raise ValueError(f"voice_corpus_invalid_submitted_text:{case_id}")
        if raw.get("voice_mode") not in {"dialogue", "first_person_narration"}:
            raise ValueError(f"voice_corpus_invalid_voice_mode:{case_id}")
        other_character_names = raw.get("other_character_names", [])
        if not isinstance(other_character_names, list) or any(
            not isinstance(name, str) or not name.strip() for name in other_character_names
        ):
            raise ValueError(f"voice_corpus_invalid_other_characters:{case_id}")
        if raw.get("expected_status") not in REVIEW_STATUSES:
            raise ValueError(f"voice_corpus_invalid_expected_status:{case_id}")
        expected_issues = raw.get("expected_issues")
        allowed_variations = raw.get("allowed_variations", [])
        if not isinstance(expected_issues, list) or not isinstance(allowed_variations, list):
            raise ValueError(f"voice_corpus_invalid_expected_issues:{case_id}")
        for issue in [*expected_issues, *allowed_variations]:
            if (
                not isinstance(issue, dict)
                or issue.get("classification")
                not in {"confirmed", "possible", "justified_variation"}
                or not isinstance(issue.get("submitted_excerpt"), str)
                or issue["submitted_excerpt"] not in submitted_text
            ):
                raise ValueError(f"voice_corpus_invalid_expected_evidence:{case_id}")
        if any(item["classification"] != "justified_variation" for item in allowed_variations):
            raise ValueError(f"voice_corpus_invalid_allowed_variation:{case_id}")
        if scenario == "long_passage" and (
            len(submitted_text) <= 4_000
            or any(
                submitted_text.index(item["submitted_excerpt"]) <= 4_000 for item in expected_issues
            )
        ):
            raise ValueError("voice_corpus_missing_late_issue")
        probe = raw.get("invalid_evidence_probe")
        if scenario == "fabricated_citation" and not isinstance(probe, dict):
            raise ValueError(f"voice_corpus_missing_probe:{case_id}")
        if probe is not None and (
            not isinstance(probe, dict)
            or not isinstance(probe.get("submitted_excerpt"), str)
            or not isinstance(probe.get("baseline_excerpt"), str)
            or not isinstance(probe.get("baseline_chapter_number"), int)
        ):
            raise ValueError(f"voice_corpus_invalid_probe:{case_id}")
        if probe and (
            probe.get("submitted_excerpt") in submitted_text
            or any(
                probe.get("baseline_excerpt") in sample["excerpt"]
                and probe.get("baseline_chapter_number") == sample["chapter_number"]
                for sample in baseline
            )
        ):
            raise ValueError(f"voice_corpus_invalid_probe:{case_id}")
        expanded.append({**raw, "submitted_text": submitted_text, "baseline_samples": baseline})
    if not REQUIRED_SCENARIOS.issubset(scenarios):
        raise ValueError(f"voice_corpus_scenarios_missing:{sorted(REQUIRED_SCENARIOS - scenarios)}")
    return expanded


def evaluate_voice_predictions(
    cases: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Score outcomes, exact issue labels, citation support, and source coverage."""
    prediction_by_id: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        if not isinstance(prediction, dict):
            raise ValueError("voice_predictions_invalid_shape")
        case_id = str(prediction.get("case_id") or "")
        if not case_id or case_id in prediction_by_id:
            raise ValueError("voice_predictions_duplicate_or_missing_id")
        prediction_by_id[case_id] = prediction
    case_ids = {case["id"] for case in cases}
    if set(prediction_by_id) - case_ids:
        raise ValueError("voice_predictions_unknown_case")

    correct_statuses = 0
    expected_issue_keys: set[tuple[str, str]] = set()
    predicted_issue_keys: set[tuple[str, str]] = set()
    correctly_classified_keys: set[tuple[str, str]] = set()
    supported_citations = 0
    attributed_citations = 0
    predicted_issue_count = 0
    complete_coverage = 0
    coverage_eligible = 0
    justified_variations = 0
    unsafe_variation_claims = 0
    for case in cases:
        prediction = prediction_by_id.get(case["id"], {})
        submitted_text = case["submitted_text"]
        cast = [
            {"name": case["character_name"], "aliases": case.get("aliases") or []},
            *[{"name": name, "aliases": []} for name in case.get("other_character_names", [])],
        ]
        narrator = detect_explicit_first_person_narrator(submitted_text, cast)
        submitted_samples = (
            first_person_narration_samples(
                submitted_text,
                chapter_number=case["submitted_chapter"],
                include_offsets=True,
            )
            if case["voice_mode"] == "first_person_narration"
            else attributed_voice_samples(
                submitted_text,
                character_name=case["character_name"],
                aliases=case.get("aliases") or (),
                chapter_number=case["submitted_chapter"],
                include_offsets=True,
                first_person_speaker=(narrator is cast[0]),
            )
        )
        review = prediction.get("review") or {}
        if not isinstance(review, dict):
            raise ValueError("voice_predictions_invalid_review")
        status = review.get("status") or prediction.get("status")
        correct_statuses += int(status == case["expected_status"])
        coverage = prediction.get("coverage") or {}
        if case["expected_status"] == "complete":
            coverage_eligible += 1
            if isinstance(coverage, dict):
                ranges = coverage.get("processed_ranges") or []
                if isinstance(ranges, list):
                    try:
                        complete_coverage += int(
                            voice_ranges_cover_text(ranges, len(case["submitted_text"]))
                        )
                    except (KeyError, TypeError, ValueError):
                        pass
        expected_by_excerpt = {
            item["submitted_excerpt"]: item["classification"] for item in case["expected_issues"]
        }
        allowed_variations = {
            item["submitted_excerpt"] for item in case.get("allowed_variations", [])
        }
        expected_issue_keys.update((case["id"], excerpt) for excerpt in expected_by_excerpt)
        for issue in review.get("issues") or []:
            if not isinstance(issue, dict):
                raise ValueError("voice_predictions_invalid_issue")
            excerpt = str(issue.get("submitted_excerpt") or "")
            key = (case["id"], excerpt)
            if (
                excerpt in allowed_variations
                and issue.get("classification") == "justified_variation"
            ):
                justified_variations += 1
            else:
                predicted_issue_keys.add(key)
                unsafe_variation_claims += int(excerpt in allowed_variations)
            predicted_issue_count += 1
            if (
                excerpt in expected_by_excerpt
                and issue.get("classification") == expected_by_excerpt[excerpt]
            ):
                correctly_classified_keys.add(key)
            baseline_excerpt = str(issue.get("baseline_excerpt") or "")
            source_supported = (
                bool(excerpt)
                and excerpt in submitted_text
                and bool(baseline_excerpt)
                and any(
                    sample["chapter_number"] == issue.get("baseline_chapter_number")
                    and baseline_excerpt in sample["excerpt"]
                    for sample in case["baseline_samples"]
                )
            )
            supported_citations += int(source_supported)
            if source_supported:
                positions: list[int] = []
                cursor = 0
                while (position := submitted_text.find(excerpt, cursor)) >= 0:
                    positions.append(position)
                    cursor = position + 1
                attributed_citations += int(
                    bool(positions)
                    and all(
                        _voice_excerpt_evidence_matches(
                            submitted_samples,
                            excerpt,
                            source_start=position,
                            require_offsets=True,
                        )
                        for position in positions
                    )
                )
    true_positives = len(expected_issue_keys & predicted_issue_keys)
    return {
        "case_count": len(cases),
        "prediction_count": len(prediction_by_id),
        "missing_prediction_ids": sorted(case_ids - set(prediction_by_id)),
        "status_accuracy": round(correct_statuses / len(cases), 4) if cases else 0.0,
        "issue_precision": (
            round(true_positives / len(predicted_issue_keys), 4) if predicted_issue_keys else 0.0
        ),
        "issue_recall": (
            round(true_positives / len(expected_issue_keys), 4) if expected_issue_keys else 0.0
        ),
        "classification_accuracy": (
            round(
                len(correctly_classified_keys & predicted_issue_keys) / true_positives,
                4,
            )
            if true_positives
            else 0.0
        ),
        "citation_coverage": (
            round(supported_citations / predicted_issue_count, 4) if predicted_issue_count else 0.0
        ),
        "attributed_citation_coverage": (
            round(attributed_citations / predicted_issue_count, 4) if predicted_issue_count else 0.0
        ),
        "complete_source_coverage": (
            round(complete_coverage / coverage_eligible, 4) if coverage_eligible else 0.0
        ),
        "justified_variation_count": justified_variations,
        "unsafe_variation_claim_count": unsafe_variation_claims,
    }
