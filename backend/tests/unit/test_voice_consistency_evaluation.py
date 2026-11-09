import json
from pathlib import Path

import pytest

from app.evaluation.voice_consistency import (
    REQUIRED_SCENARIOS,
    evaluate_voice_predictions,
    load_voice_evaluation_cases,
)
from app.utils.voice_review_utils import (
    VoiceReviewFormatError,
    validate_voice_section_result,
)

CORPUS = Path(__file__).resolve().parents[2] / "evals/voice_consistency/v1/cases.json"


def test_voice_corpus_covers_all_original_synthetic_scenarios_and_late_issue():
    cases = load_voice_evaluation_cases(CORPUS)

    assert len(cases) == 19
    assert len(REQUIRED_SCENARIOS) == 13
    assert REQUIRED_SCENARIOS.issubset({case["scenario"] for case in cases})
    assert {"multi_speaker_chapter", "long_narrator_chapter"}.issubset(
        {case["scenario"] for case in cases}
    )
    long_case = next(case for case in cases if case["scenario"] == "long_passage")
    assert 4_000 < len(long_case["submitted_text"]) <= 12_000
    assert (
        long_case["submitted_text"].index(long_case["expected_issues"][0]["submitted_excerpt"])
        > 4_000
    )
    assert all(case["baseline_samples"] for case in cases)


def test_voice_corpus_includes_late_finding_near_full_accepted_passage_length():
    cases = load_voice_evaluation_cases(CORPUS)
    near_limit = next(case for case in cases if case["id"] == "late_dialogue_near_character_12000")
    submitted = near_limit["submitted_text"]

    assert 11_900 <= len(submitted) <= 12_000
    assert submitted.index(near_limit["expected_issues"][0]["submitted_excerpt"]) > 11_900


def test_voice_corpus_rejects_duplicate_ids_and_unsupported_expected_quote(tmp_path):
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    payload["cases"][1]["id"] = payload["cases"][0]["id"]
    bad_path = tmp_path / "duplicate.json"
    bad_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate_or_missing_id"):
        load_voice_evaluation_cases(bad_path)

    payload["cases"][1]["id"] = "different_id"
    payload["cases"][0]["expected_issues"][0]["submitted_excerpt"] = "not in source"
    bad_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_expected_evidence"):
        load_voice_evaluation_cases(bad_path)


def test_voice_corpus_rejects_future_baselines_and_missing_fabricated_probe(tmp_path):
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    payload["cases"][0]["submitted_chapter"] = 1
    bad_path = tmp_path / "bad-voice.json"
    bad_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_chapter_order"):
        load_voice_evaluation_cases(bad_path)

    payload["cases"][0]["submitted_chapter"] = 5
    next(case for case in payload["cases"] if case["scenario"] == "fabricated_citation").pop(
        "invalid_evidence_probe"
    )
    bad_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="missing_probe"):
        load_voice_evaluation_cases(bad_path)


def test_voice_evaluation_scores_exact_status_issue_citation_and_coverage():
    cases = load_voice_evaluation_cases(CORPUS)
    formal = next(case for case in cases if case["scenario"] == "formal_to_slang")
    insufficient = next(case for case in cases if case["scenario"] == "insufficient_evidence")
    excerpt = formal["expected_issues"][0]["submitted_excerpt"]
    baseline = formal["baseline_samples"][0]
    predictions = [
        {
            "case_id": formal["id"],
            "review": {
                "status": "complete",
                "issues": [
                    {
                        "classification": "possible",
                        "submitted_excerpt": excerpt,
                        "baseline_excerpt": baseline["excerpt"],
                        "baseline_chapter_number": baseline["chapter_number"],
                    }
                ],
            },
            "coverage": {
                "processed_ranges": [{"start": 0, "end": len(formal["submitted_text"])}],
                "total_characters": len(formal["submitted_text"]),
            },
        },
        {
            "case_id": insufficient["id"],
            "review": {"status": "insufficient_evidence", "issues": []},
        },
    ]

    metrics = evaluate_voice_predictions([formal, insufficient], predictions)

    assert metrics["status_accuracy"] == 1.0
    assert metrics["issue_precision"] == 1.0
    assert metrics["issue_recall"] == 1.0
    assert metrics["classification_accuracy"] == 1.0
    assert metrics["citation_coverage"] == 1.0
    assert metrics["attributed_citation_coverage"] == 1.0
    assert metrics["complete_source_coverage"] == 1.0
    assert metrics["missing_prediction_ids"] == []


def test_voice_evaluation_exposes_missing_prediction_and_fabricated_citation():
    cases = load_voice_evaluation_cases(CORPUS)
    formal = next(case for case in cases if case["scenario"] == "formal_to_slang")
    insufficient = next(case for case in cases if case["scenario"] == "insufficient_evidence")
    prediction = {
        "case_id": formal["id"],
        "review": {
            "status": "complete",
            "issues": [
                {
                    "classification": "possible",
                    "submitted_excerpt": formal["expected_issues"][0]["submitted_excerpt"],
                    "baseline_excerpt": "Invented baseline quote.",
                    "baseline_chapter_number": 1,
                }
            ],
        },
        "coverage": {"processed_ranges": [{"start": 0, "end": 10}]},
    }

    metrics = evaluate_voice_predictions([formal, insufficient], [prediction])

    assert metrics["missing_prediction_ids"] == [insufficient["id"]]
    assert metrics["status_accuracy"] == 0.5
    assert metrics["citation_coverage"] == 0.0
    assert metrics["attributed_citation_coverage"] == 0.0
    assert metrics["complete_source_coverage"] == 0.0


def test_voice_evaluation_does_not_credit_unattributed_dialogue_as_character_evidence():
    case = next(
        item
        for item in load_voice_evaluation_cases(CORPUS)
        if item["scenario"] == "unattributed_dialogue"
    )
    baseline = case["baseline_samples"][0]
    metrics = evaluate_voice_predictions(
        [case],
        [
            {
                "case_id": case["id"],
                "review": {
                    "status": "complete",
                    "issues": [
                        {
                            "classification": "possible",
                            "submitted_excerpt": "Dude, that plan is totally busted.",
                            "baseline_excerpt": baseline["excerpt"],
                            "baseline_chapter_number": baseline["chapter_number"],
                        }
                    ],
                },
            }
        ],
    )

    assert metrics["citation_coverage"] == 1.0
    assert metrics["attributed_citation_coverage"] == 0.0


def test_voice_evaluation_credits_only_unambiguous_first_person_dialogue():
    cases = load_voice_evaluation_cases(CORPUS)
    explicit = next(
        case for case in cases if case["id"] == "explicit_narrator_dialogue_is_attributed"
    )
    conflicting = next(
        case
        for case in cases
        if case["id"] == "conflicting_narrator_identities_do_not_attribute_i_dialogue"
    )
    predictions = []
    for case, excerpt in (
        (explicit, explicit["expected_issues"][0]["submitted_excerpt"]),
        (conflicting, "Keep the gate closed."),
    ):
        baseline = case["baseline_samples"][0]
        predictions.append(
            {
                "case_id": case["id"],
                "review": {
                    "status": case["expected_status"],
                    "issues": [
                        {
                            "classification": "possible",
                            "submitted_excerpt": excerpt,
                            "baseline_excerpt": baseline["excerpt"],
                            "baseline_chapter_number": baseline["chapter_number"],
                        }
                    ],
                },
            }
        )

    metrics = evaluate_voice_predictions([explicit, conflicting], predictions)

    assert metrics["citation_coverage"] == 1.0
    assert metrics["attributed_citation_coverage"] == 0.5


def test_voice_evaluation_requires_every_repeated_excerpt_to_be_attributed():
    original = next(
        item
        for item in load_voice_evaluation_cases(CORPUS)
        if item["scenario"] == "formal_to_slang"
    )
    excerpt = original["expected_issues"][0]["submitted_excerpt"]
    case = {
        **original,
        "submitted_text": original["submitted_text"] + f'\n\n"{excerpt}"',
    }
    baseline = case["baseline_samples"][0]
    metrics = evaluate_voice_predictions(
        [case],
        [
            {
                "case_id": case["id"],
                "review": {
                    "status": "complete",
                    "issues": [
                        {
                            "classification": "possible",
                            "submitted_excerpt": excerpt,
                            "baseline_excerpt": baseline["excerpt"],
                            "baseline_chapter_number": baseline["chapter_number"],
                        }
                    ],
                },
            }
        ],
    )

    assert metrics["citation_coverage"] == 1.0
    assert metrics["attributed_citation_coverage"] == 0.0


def test_intentional_variation_can_be_omitted_or_labeled_justified_without_false_positive():
    case = next(
        item for item in load_voice_evaluation_cases(CORPUS) if item["scenario"] == "fear_or_anger"
    )
    excerpt = case["allowed_variations"][0]["submitted_excerpt"]
    baseline = case["baseline_samples"][0]

    no_issue = evaluate_voice_predictions(
        [case],
        [{"case_id": case["id"], "review": {"status": "complete", "issues": []}}],
    )
    justified_issue = {
        "classification": "justified_variation",
        "submitted_excerpt": excerpt,
        "baseline_excerpt": baseline["excerpt"],
        "baseline_chapter_number": baseline["chapter_number"],
    }
    justified = evaluate_voice_predictions(
        [case],
        [
            {
                "case_id": case["id"],
                "review": {"status": "complete", "issues": [justified_issue]},
            }
        ],
    )
    unsafe = evaluate_voice_predictions(
        [case],
        [
            {
                "case_id": case["id"],
                "review": {
                    "status": "complete",
                    "issues": [{**justified_issue, "classification": "confirmed"}],
                },
            }
        ],
    )

    assert no_issue["status_accuracy"] == 1.0
    assert no_issue["unsafe_variation_claim_count"] == 0
    assert justified["justified_variation_count"] == 1
    assert justified["unsafe_variation_claim_count"] == 0
    assert unsafe["unsafe_variation_claim_count"] == 1
    assert unsafe["issue_precision"] == 0.0


def test_fabricated_citation_probe_is_rejected_by_runtime_evidence_validator():
    case = next(
        item
        for item in load_voice_evaluation_cases(CORPUS)
        if item["scenario"] == "fabricated_citation"
    )
    issue = {
        "character_name": case["character_name"],
        "classification": "possible",
        "severity": "moderate",
        "title": "Invented shift",
        "description": "This claim cites material that is not present.",
        **case["invalid_evidence_probe"],
        "confidence": 0.7,
        "revision_direction": "Keep the established register.",
        "intentionality_prompt": "Was this intentional?",
    }
    raw = json.dumps({"issues": [issue], "overall_verdict": "Possible shift."})

    with pytest.raises(VoiceReviewFormatError, match="unsupported_evidence"):
        validate_voice_section_result(
            raw,
            section_text=case["submitted_text"],
            baseline_samples=case["baseline_samples"],
            submitted_samples=[{"excerpt": "Please check the figures before we decide."}],
            character_name=case["character_name"],
        )


def test_voice_evaluation_rejects_duplicate_and_unknown_prediction_ids():
    formal = next(
        case
        for case in load_voice_evaluation_cases(CORPUS)
        if case["scenario"] == "formal_to_slang"
    )
    with pytest.raises(ValueError, match="duplicate_or_missing_id"):
        evaluate_voice_predictions([formal], [{"case_id": formal["id"]}, {"case_id": formal["id"]}])
    with pytest.raises(ValueError, match="unknown_case"):
        evaluate_voice_predictions([formal], [{"case_id": "unknown"}])


def test_voice_evaluation_treats_malformed_ranges_as_incomplete_not_a_crash():
    formal = next(
        case
        for case in load_voice_evaluation_cases(CORPUS)
        if case["scenario"] == "formal_to_slang"
    )
    metrics = evaluate_voice_predictions(
        [formal],
        [
            {
                "case_id": formal["id"],
                "review": {"status": "complete", "issues": []},
                "coverage": {"processed_ranges": [{"start": "bad"}]},
            }
        ],
    )
    assert metrics["complete_source_coverage"] == 0.0
