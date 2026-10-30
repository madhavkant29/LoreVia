from copy import deepcopy

import pytest

from app.utils.voice_review_coverage import (
    aggregate_voice_review_coverage,
    complete_cached_voice_review,
    unattributed_quoted_ranges,
)


def _complete_cache_payload():
    per_character = [
        {
            "character_name": name,
            "total_characters": 20,
            "processed_ranges": [{"start": start, "end": end}],
            "unattributed_ranges": [],
            "compared_ranges": [{"start": start + 1, "end": end - 1}],
            "not_compared_ranges": [],
        }
        for name, start, end in (("Mara", 0, 10), ("Lio", 10, 20))
    ]
    coverage = aggregate_voice_review_coverage(
        [{"coverage": item} for item in per_character], total_characters=20
    )
    coverage["unattributed_quoted_ranges"] = []
    return {
        "review": {"status": "complete", "overall_verdict": "No supported change.", "issues": []},
        "voice_mode": "dialogue",
        "characters_reviewed": ["Mara", "Lio"],
        "coverage_by_character": per_character,
        "coverage": coverage,
    }


def test_complete_cached_voice_review_accepts_valid_complete_coverage():
    assert complete_cached_voice_review(
        _complete_cache_payload(),
        submitted_text="0123456789abcdefghij",
        character_names=["Mara", "Lio"],
        voice_mode="dialogue",
        baseline_by_name={"Mara": [], "Lio": []},
    )


def test_complete_cached_voice_review_rejects_scanned_text_without_any_voice_comparison():
    payload = _complete_cache_payload()
    for item in payload["coverage_by_character"]:
        item["compared_ranges"] = []
    payload["coverage"] = aggregate_voice_review_coverage(
        [{"coverage": item} for item in payload["coverage_by_character"]],
        total_characters=20,
    )

    assert not complete_cached_voice_review(
        payload,
        submitted_text="0123456789abcdefghij",
        character_names=["Mara", "Lio"],
        voice_mode="dialogue",
        baseline_by_name={"Mara": [], "Lio": []},
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda payload: payload["review"].update(status="partial_evidence"),
        lambda payload: payload["coverage"].update(unattributed_ranges=[{"start": 0, "end": 2}]),
        lambda payload: payload["coverage"].update(total_characters=True),
        lambda payload: payload["coverage"].update(
            unattributed_quoted_ranges=[{"start": 1, "end": 2}]
        ),
        lambda payload: payload["coverage_by_character"][1].update(
            processed_ranges=[{"start": 11, "end": 20}]
        ),
        lambda payload: payload["coverage_by_character"][0].update(
            compared_ranges=[{"start": 0, "end": 11}]
        ),
        lambda payload: payload.update(characters_reviewed=["Lio", "Mara"]),
        lambda payload: payload.update(voice_mode="first_person_narration"),
    ],
)
def test_complete_cached_voice_review_rejects_partial_stale_or_malformed_results(change):
    payload = deepcopy(_complete_cache_payload())
    change(payload)
    assert not complete_cached_voice_review(
        payload,
        submitted_text="0123456789abcdefghij",
        character_names=["Mara", "Lio"],
        voice_mode="dialogue",
        baseline_by_name={"Mara": [], "Lio": []},
    )


def test_complete_cached_voice_review_requires_current_exact_issue_evidence():
    payload = _complete_cache_payload()
    payload["review"]["issues"] = [
        {
            "character_name": "Mara",
            "classification": "possible",
            "severity": "moderate",
            "confidence": 0.8,
            "title": "Changed register",
            "description": "A different expression.",
            "submitted_excerpt": "234",
            "baseline_excerpt": "I will check the gate carefully.",
            "baseline_chapter_number": 1,
            "revision_direction": "Compare the intended register.",
            "intentionality_prompt": "Is the change deliberate?",
        }
    ]
    baseline = {"Mara": [{"chapter_number": 1, "excerpt": "I will check the gate carefully."}]}

    def accepted() -> bool:
        return complete_cached_voice_review(
            payload,
            submitted_text="0123456789abcdefghij",
            character_names=["Mara", "Lio"],
            voice_mode="dialogue",
            baseline_by_name=baseline,
        )

    assert accepted()
    payload["review"]["issues"][0]["baseline_excerpt"] = "An invented quotation."
    assert not accepted()
    payload["review"]["issues"][0]["baseline_excerpt"] = "I will check the gate carefully."
    payload["review"]["issues"][0]["submitted_excerpt"] = "Mara did not say this."
    assert not accepted()
    payload["review"]["issues"][0]["submitted_excerpt"] = "abc"
    assert not accepted()  # Present in the passage, but outside Mara's compared range.
    payload["review"]["issues"][0]["submitted_excerpt"] = "234"
    payload["review"]["issues"][0]["character_name"] = ["Mara"]
    assert not accepted()


def test_unattributed_quoted_ranges_finds_only_uncompared_speech_not_prose():
    passage = 'Mara said, "I will wait here." Lio said, “I will go now.”'
    first = passage.index("I will wait here.")
    second = passage.index("I will go now.")

    assert unattributed_quoted_ranges(
        passage,
        [
            {"start": 0, "end": first},
            {"start": first + len("I will wait here."), "end": len(passage)},
        ],
    ) == [{"start": second, "end": second + len("I will go now.")}]


def test_unattributed_quoted_ranges_reports_only_missing_quote_tail():
    passage = "He said, 'Stay until morning.'"
    start = passage.index("Stay until morning.")

    assert unattributed_quoted_ranges(
        passage, [{"start": start + len("Stay "), "end": len(passage)}]
    ) == [{"start": start + len("Stay "), "end": start + len("Stay until morning.")}]
    assert unattributed_quoted_ranges(passage, []) == []


def test_aggregate_voice_review_coverage_combines_disjoint_character_sections():
    reviewed = [
        {"coverage": {"processed_ranges": [{"start": 0, "end": 40}], "total_characters": 100}},
        {"coverage": {"processed_ranges": [{"start": 60, "end": 100}], "total_characters": 100}},
    ]

    assert aggregate_voice_review_coverage(reviewed, total_characters=100) == {
        "processed_ranges": [{"start": 0, "end": 40}, {"start": 60, "end": 100}],
        "unattributed_ranges": [{"start": 40, "end": 60}],
        "total_characters": 100,
    }


def test_aggregate_voice_review_coverage_merges_overlaps_without_double_counting():
    reviewed = [
        {"coverage": {"processed_ranges": [{"start": 0, "end": 60}], "total_characters": 100}},
        {"coverage": {"processed_ranges": [{"start": 40, "end": 100}], "total_characters": 100}},
    ]

    assert aggregate_voice_review_coverage(reviewed, total_characters=100) == {
        "processed_ranges": [{"start": 0, "end": 100}],
        "unattributed_ranges": [],
        "total_characters": 100,
    }


def test_aggregate_voice_review_coverage_separates_scanned_sections_from_compared_voice():
    reviewed = [
        {
            "coverage": {
                "processed_ranges": [{"start": 0, "end": 60}],
                "compared_ranges": [{"start": 20, "end": 30}],
                "total_characters": 100,
            }
        },
        {
            "coverage": {
                "processed_ranges": [{"start": 50, "end": 100}],
                "compared_ranges": [{"start": 70, "end": 90}],
                "total_characters": 100,
            }
        },
    ]

    assert aggregate_voice_review_coverage(reviewed, total_characters=100) == {
        "processed_ranges": [{"start": 0, "end": 100}],
        "unattributed_ranges": [],
        "compared_ranges": [{"start": 20, "end": 30}, {"start": 70, "end": 90}],
        "not_compared_ranges": [
            {"start": 0, "end": 20},
            {"start": 30, "end": 70},
            {"start": 90, "end": 100},
        ],
        "total_characters": 100,
    }


def test_aggregate_voice_review_coverage_reports_unreviewed_passage_without_baseline():
    assert aggregate_voice_review_coverage([], total_characters=42) == {
        "processed_ranges": [],
        "unattributed_ranges": [{"start": 0, "end": 42}],
        "total_characters": 42,
    }
    assert aggregate_voice_review_coverage([], total_characters=0) == {
        "processed_ranges": [],
        "unattributed_ranges": [],
        "total_characters": 0,
    }


@pytest.mark.parametrize(
    "coverage",
    [
        {"processed_ranges": [{"start": -1, "end": 2}], "total_characters": 10},
        {"processed_ranges": [{"start": 4, "end": 4}], "total_characters": 10},
        {"processed_ranges": [{"start": 2, "end": 11}], "total_characters": 10},
        {"processed_ranges": [{"start": True, "end": 2}], "total_characters": 10},
        {"processed_ranges": [], "total_characters": 9},
        {"processed_ranges": "all", "total_characters": 10},
        {
            "processed_ranges": [],
            "compared_ranges": [{"start": 2, "end": 11}],
            "total_characters": 10,
        },
    ],
)
def test_aggregate_voice_review_coverage_rejects_invalid_character_ranges(coverage):
    with pytest.raises(ValueError, match="invalid_voice_character_coverage"):
        aggregate_voice_review_coverage([{"coverage": coverage}], total_characters=10)
