from copy import deepcopy
from pathlib import Path

from app.evaluation.story_intelligence import (
    evaluate_predictions,
    evaluate_rollout_gates,
    load_evaluation_cases,
)
from app.utils.characters.text import extraction_source_coverage, split_text_for_token_budget

CORPUS = Path(__file__).parents[2] / "evals" / "story_intelligence" / "v1" / "cases.json"


def test_versioned_evaluation_corpus_has_required_genre_coverage():
    cases = load_evaluation_cases(CORPUS)

    assert len(cases) >= 28
    assert {case["genre"] for case in cases} == {
        "fantasy",
        "romance",
        "mystery",
        "science_fiction",
        "contemporary",
    }

    ids = {case["id"] for case in cases}
    assert {
        "contemporary_first_person_shared_surname_and_discourse_prefix",
        "mystery_two_independent_source_conflicts",
        "science_fiction_intentional_register_shift",
        "science_fiction_long_form_narrator_shared_surname_and_two_conflicts",
    } <= ids
    long_cases = [case for case in cases if len(case["text"]) > 4_000]
    assert len(long_cases) >= 2
    long_science_fiction = next(
        case
        for case in long_cases
        if case["id"] == "science_fiction_long_form_narrator_shared_surname_and_two_conflicts"
    )
    labels = long_science_fiction["labels"]
    assert labels["identity_links"]["I"] == "Leena Voss"
    assert labels["identity_links"]["Magistrate Sol"] != labels["identity_links"]["Sister Sol"]
    assert labels["identity_links"]["the mechanic"] == "the mechanic"
    assert len(labels["findings"]) == 2
    assert any(state["intentional"] is True for state in labels["state_transitions"])


def test_evaluation_metrics_report_per_version_cost_latency_and_citations():
    cases = [
        {
            "id": "case-1",
            "text": "Her eyes were blue. Her eyes were green.",
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
            "characters": [
                {
                    "canonical_name": "Ilya",
                    "is_major": True,
                    "analysis_metadata": {
                        "profile_claims": [
                            {
                                "field": "trait:eyes",
                                "value": "blue",
                                "quote": "Her eyes were blue.",
                            }
                        ]
                    },
                }
            ],
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

    assert metrics["prediction_coverage"] == 1.0
    assert metrics["missing_prediction_ids"] == []
    assert metrics["character_precision"] == 1.0
    assert metrics["identity_merge_accuracy"] == 1.0
    assert metrics["continuity_recall"] == 1.0
    assert metrics["citation_coverage"] == 1.0
    assert metrics["profile_claim_source_coverage"] == 1.0
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
            "prediction_coverage": 1.0,
            "major_character_precision": 0.99,
            "major_character_recall": 0.96,
            "character_precision": 0.96,
            "character_recall": 0.92,
            "identity_merge_precision": 0.995,
            "relationship_precision": 0.95,
            "relationship_recall": 0.85,
            "relationship_citation_coverage": 1.0,
            "extraction_source_coverage": 1.0,
            "high_confidence_continuity_precision": 0.91,
            "high_confidence_continuity_recall": 0.85,
            "citation_coverage": 1.0,
            "profile_claim_source_coverage": 1.0,
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
            "prediction_coverage": 1.0,
            "major_character_precision": 0.99,
            "major_character_recall": 0.96,
            "character_precision": 0.96,
            "character_recall": 0.92,
            "identity_merge_precision": 0.995,
            "relationship_precision": 0.95,
            "relationship_recall": 0.85,
            "relationship_citation_coverage": 1.0,
            "extraction_source_coverage": 1.0,
            "high_confidence_continuity_precision": 0.91,
            "high_confidence_continuity_recall": 0.85,
            "citation_coverage": 1.0,
            "profile_claim_source_coverage": 1.0,
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


def test_relationship_and_source_coverage_metrics_verify_full_prediction_evidence():
    source = "Mara crossed the bridge. Ivo followed Mara to the gate."
    passages = split_text_for_token_budget(source, max_tokens=20, count_tokens=len)
    assert len(passages) > 1
    coverage = extraction_source_coverage(
        [source], [[passage] for passage in passages], max_tokens=20, count_tokens=len
    )
    coverage["batch_outcomes"] = [
        {"batch_index": index, "status": "succeeded"} for index in range(1, len(passages) + 1)
    ]
    cases = [
        {
            "id": "bridge",
            "text": source,
            "labels": {
                "characters": [],
                "identity_links": {},
                "relationships": [{"a": "Mara", "b": "Ivo", "type": "allies", "from": 2, "to": 4}],
                "findings": [],
            },
        }
    ]
    prediction = {
        "case_id": "bridge",
        "relationships": [
            {
                "character_a": "Mara",
                "character_b": "Ivo",
                "rel_type": "allies",
                "from_chapter": 2,
                "to_chapter": 4,
                "label_evidence": {"quote": "Ivo followed Mara to the gate."},
            }
        ],
        "source_coverage": coverage,
    }
    metrics = evaluate_predictions(cases, [prediction])
    assert metrics["relationship_precision"] == 1.0
    assert metrics["relationship_recall"] == 1.0
    assert metrics["relationship_citation_coverage"] == 1.0
    assert metrics["extraction_source_coverage"] == 1.0

    wrong_endpoint = deepcopy(prediction)
    wrong_endpoint["relationships"][0]["character_b"] = "Nora"
    assert evaluate_predictions(cases, [wrong_endpoint])["relationship_precision"] == 0.0

    invented_quote = deepcopy(prediction)
    invented_quote["relationships"][0]["label_evidence"]["quote"] = "Mara trusted Ivo."
    assert evaluate_predictions(cases, [invented_quote])["relationship_citation_coverage"] == 0.0
    assert (
        evaluate_rollout_gates(
            evaluate_predictions(cases, [invented_quote]), production_dismissal_rate=0.1
        )["gates"]["relationship_citation_coverage"]["status"]
        == "failed"
    )

    missing_tail = deepcopy(prediction)
    missing_tail["source_coverage"]["ranges"][-1]["end"] -= 1
    assert evaluate_predictions(cases, [missing_tail])["extraction_source_coverage"] == 0.0

    changed_hash = deepcopy(prediction)
    changed_hash["source_coverage"]["chunks"][0]["sha256"] = "0" * 64
    assert evaluate_predictions(cases, [changed_hash])["extraction_source_coverage"] == 0.0

    malformed_ranges = deepcopy(prediction)
    malformed_ranges["source_coverage"]["ranges"] = [None]
    assert evaluate_predictions(cases, [malformed_ranges])["extraction_source_coverage"] == 0.0

    failed_batch = deepcopy(prediction)
    failed_batch["source_coverage"]["batch_outcomes"][0]["status"] = "failed"
    assert evaluate_predictions(cases, [failed_batch])["extraction_source_coverage"] == 0.0

    missing_batch = deepcopy(prediction)
    missing_batch["source_coverage"]["batch_outcomes"].pop()
    assert evaluate_predictions(cases, [missing_batch])["extraction_source_coverage"] == 0.0

    duplicated_batch = deepcopy(prediction)
    duplicated_batch["source_coverage"]["batch_outcomes"].append(
        deepcopy(duplicated_batch["source_coverage"]["batch_outcomes"][0])
    )
    assert evaluate_predictions(cases, [duplicated_batch])["extraction_source_coverage"] == 0.0


def test_duplicate_prediction_keys_cannot_push_citation_coverage_above_one():
    cases = [
        {
            "id": "case-1",
            "text": "Blue. Green.",
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


def test_duplicate_finding_with_one_fabricated_citation_fails_source_coverage():
    cases = [
        {
            "id": "case-1",
            "text": "Blue. Green.",
            "labels": {"characters": [], "identity_links": {}, "findings": [{"key": "eyes"}]},
        }
    ]
    predictions = [
        {
            "case_id": "case-1",
            "characters": [],
            "identity_links": {},
            "findings": [
                {
                    "key": "eyes",
                    "evidence": [{"excerpt": "Blue."}, {"excerpt": "Green."}],
                },
                {
                    "key": "eyes",
                    "evidence": [{"excerpt": "Blue."}, {"excerpt": "Purple."}],
                },
            ],
        }
    ]

    assert evaluate_predictions(cases, predictions)["citation_coverage"] == 0.0


def test_fabricated_citations_and_unsourced_profile_claims_fail_quality_metrics():
    cases = [
        {
            "id": "case-1",
            "text": "Mara said the silver gate was closed. Later it opened.",
            "labels": {
                "characters": [{"canonical_name": "Mara"}],
                "identity_links": {},
                "findings": [{"key": "gate", "confidence": 0.9}],
            },
        }
    ]
    predictions = [
        {
            "case_id": "case-1",
            "characters": [
                {
                    "canonical_name": "Mara",
                    "analysis_metadata": {
                        "profile_claims": [
                            {"field": "goal", "value": "open the gate", "quote": "Mara opened it."}
                        ]
                    },
                }
            ],
            "findings": [
                {
                    "key": "gate",
                    "confidence": 0.9,
                    "evidence": [
                        {"excerpt": "the silver gate was closed"},
                        {"excerpt": "Mara opened it."},
                    ],
                }
            ],
        }
    ]

    metrics = evaluate_predictions(cases, predictions)
    assert metrics["citation_coverage"] == 0.0
    assert metrics["profile_claim_source_coverage"] == 0.0
    gates = evaluate_rollout_gates(metrics, production_dismissal_rate=0.1)
    assert gates["rollout_ready"] is False
    assert gates["gates"]["citation_coverage"]["status"] == "failed"


def test_rollout_does_not_pass_when_no_profile_claims_were_measured():
    gates = evaluate_rollout_gates(
        {
            "prediction_coverage": 1.0,
            "major_character_precision": 1.0,
            "major_character_recall": 1.0,
            "character_precision": 1.0,
            "character_recall": 1.0,
            "identity_merge_precision": 1.0,
            "high_confidence_continuity_precision": 1.0,
            "high_confidence_continuity_recall": 1.0,
            "citation_coverage": 1.0,
            "profile_claim_source_coverage": None,
        },
        production_dismissal_rate=0.1,
    )

    assert gates["rollout_ready"] is False
    assert gates["gates"]["profile_claim_source_coverage"]["status"] == "not_evaluated"


def test_missing_predictions_block_rollout_even_when_available_scores_are_high():
    cases = [
        {"id": "present", "text": "Mara waited.", "labels": {"characters": [], "findings": []}},
        {"id": "missing", "text": "Ivo waited.", "labels": {"characters": [], "findings": []}},
    ]
    metrics = evaluate_predictions(cases, [{"case_id": "present"}])

    assert metrics["prediction_coverage"] == 0.5
    assert metrics["missing_prediction_ids"] == ["missing"]
    gates = evaluate_rollout_gates(metrics, production_dismissal_rate=0.1)
    assert gates["rollout_ready"] is False
    assert gates["gates"]["prediction_coverage"]["status"] == "failed"


def test_duplicate_or_unknown_prediction_ids_are_rejected():
    cases = [{"id": "known", "labels": {"characters": [], "findings": []}}]

    for predictions in (
        [{"case_id": "known"}, {"case_id": "known"}],
        [{"case_id": "unexpected"}],
        [{"case_id": ""}],
    ):
        try:
            evaluate_predictions(cases, predictions)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid prediction IDs must not be scored")
