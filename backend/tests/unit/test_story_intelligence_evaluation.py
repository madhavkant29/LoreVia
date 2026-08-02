from pathlib import Path

from app.evaluation.story_intelligence import (
    evaluate_predictions,
    evaluate_rollout_gates,
    load_evaluation_cases,
)

CORPUS = Path(__file__).parents[2] / "evals" / "story_intelligence" / "v1" / "cases.json"


def test_versioned_evaluation_corpus_has_required_genre_coverage():
    cases = load_evaluation_cases(CORPUS)

    assert len(cases) == 25
    assert {case["genre"] for case in cases} == {
        "fantasy",
        "romance",
        "mystery",
        "science_fiction",
        "contemporary",
    }


def test_evaluation_metrics_report_per_version_cost_latency_and_citations():
    cases = [
        {
            "id": "case-1",
            "labels": {
                "characters": [{"canonical_name": "Ilya"}],
                "identity_links": {"Ilya": "Ilya"},
                "findings": [{"key": "eyes"}],
            },
        }
    ]
    predictions = [
        {
            "case_id": "case-1",
            "extractor_version": "v2",
            "latency_ms": 250,
            "cost_usd": 0.04,
            "word_count": 100_000,
            "characters": [{"canonical_name": "Ilya", "is_major": True}],
            "identity_links": {"Ilya": "Ilya"},
            "findings": [
                {
                    "key": "eyes",
                    "confidence": 0.95,
                    "evidence": [
                        {"excerpt": "Her eyes were blue."},
                        {"excerpt": "Her eyes were green."},
                    ],
                }
            ],
        }
    ]

    metrics = evaluate_predictions(cases, predictions)

    assert metrics["character_precision"] == 1.0
    assert metrics["identity_merge_accuracy"] == 1.0
    assert metrics["continuity_recall"] == 1.0
    assert metrics["citation_coverage"] == 1.0
    assert metrics["major_character_precision"] == 1.0
    assert metrics["high_confidence_continuity_precision"] == 1.0
    assert metrics["by_extractor_version"]["v2"] == {
        "case_count": 1,
        "average_latency_ms": 250.0,
        "total_cost_usd": 0.04,
        "average_cost_usd": 0.04,
        "word_count": 100_000,
        "latency_ms_per_100k_words": 250.0,
        "cost_usd_per_100k_words": 0.04,
    }


def test_rollout_gates_report_quality_and_production_feedback_separately():
    gates = evaluate_rollout_gates(
        {
            "major_character_precision": 0.99,
            "major_character_recall": 0.96,
            "character_precision": 0.96,
            "character_recall": 0.92,
            "identity_merge_precision": 0.995,
            "high_confidence_continuity_precision": 0.91,
            "citation_coverage": 1.0,
        },
        production_dismissal_rate=0.1,
    )

    assert gates["all_evaluated_gates_passed"] is True
    assert gates["all_gates_evaluated"] is True
    assert gates["rollout_ready"] is True
    assert gates["gates"]["identity_merge_precision"]["status"] == "passed"


def test_rollout_is_not_ready_when_production_feedback_is_missing():
    gates = evaluate_rollout_gates(
        {
            "major_character_precision": 0.99,
            "major_character_recall": 0.96,
            "character_precision": 0.96,
            "character_recall": 0.92,
            "identity_merge_precision": 0.995,
            "high_confidence_continuity_precision": 0.91,
            "citation_coverage": 1.0,
        }
    )

    assert gates["all_evaluated_gates_passed"] is True
    assert gates["all_gates_evaluated"] is False
    assert gates["rollout_ready"] is False


def test_merge_precision_excludes_trivial_self_identity_links():
    cases = [
        {
            "id": "case-1",
            "labels": {
                "characters": [{"canonical_name": "Alexandra Moreno"}],
                "identity_links": {
                    "Alexandra Moreno": "Alexandra Moreno",
                    "Lex": "Alexandra Moreno",
                },
                "findings": [],
            },
        }
    ]
    predictions = [
        {
            "case_id": "case-1",
            "characters": [{"canonical_name": "Alexandra Moreno"}],
            "identity_links": {
                "Alexandra Moreno": "Alexandra Moreno",
                "Lex": "Alexandra Martin",
            },
            "findings": [],
        }
    ]

    metrics = evaluate_predictions(cases, predictions)

    assert metrics["identity_merge_precision"] == 0.0
    assert metrics["identity_merge_recall"] == 0.0


def test_duplicate_prediction_keys_cannot_push_citation_coverage_above_one():
    cases = [
        {
            "id": "case-1",
            "labels": {
                "characters": [],
                "identity_links": {},
                "findings": [{"key": "eyes"}],
            },
        }
    ]
    cited_finding = {
        "key": "eyes",
        "confidence": 0.95,
        "evidence": [{"excerpt": "Blue."}, {"excerpt": "Green."}],
    }
    predictions = [
        {
            "case_id": "case-1",
            "characters": [],
            "identity_links": {},
            "findings": [cited_finding, cited_finding],
        }
    ]

    assert evaluate_predictions(cases, predictions)["citation_coverage"] == 1.0
