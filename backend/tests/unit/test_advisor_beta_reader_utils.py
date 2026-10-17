import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.advisor import BetaReaderAnalysisRequest
from app.utils.advisor_beta_reader_analysis_utils import (
    MAX_BETA_READER_BATCH_CHARS,
    analyze_character_voice_distinctness,
    analyze_overused_language,
    build_beta_reader_request_hash,
    build_chapter_source_fingerprint,
    build_passage_source_fingerprint,
    build_scoped_voice_profiles,
    normalize_beta_reader_synthesis,
    split_beta_reader_batches,
    stable_beta_reader_id,
)
from app.utils.advisor_beta_reader_report_utils import (
    bound_beta_reader_report,
    build_beta_reader_revision_candidates,
    find_cached_beta_reader_report,
    merge_beta_reader_report,
    normalize_ai_beta_reader_state,
)


def test_beta_reader_request_validates_each_scope_and_unique_checks():
    assert (
        BetaReaderAnalysisRequest(scope="passage", text="  A useful passage.  ").text
        == "A useful passage."
    )
    assert BetaReaderAnalysisRequest(scope="chapter", chapter_number=3).chapter_number == 3
    assert (
        BetaReaderAnalysisRequest(scope="chapter_range", chapter_start=2, chapter_end=4).chapter_end
        == 4
    )
    assert BetaReaderAnalysisRequest(scope="full_book").checks == [
        "repetition",
        "voice",
        "reader_feedback",
    ]

    invalid_payloads = [
        {"scope": "passage", "text": ""},
        {"scope": "chapter"},
        {"scope": "chapter", "chapter_number": 1, "text": "not allowed"},
        {"scope": "chapter_range", "chapter_start": 5, "chapter_end": 2},
        {"scope": "full_book", "chapter_number": 1},
        {"scope": "full_book", "checks": []},
        {"scope": "full_book", "checks": ["voice", "voice"]},
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            BetaReaderAnalysisRequest.model_validate(payload)


def test_repetition_analysis_normalizes_terms_splits_dialogue_and_bounds_evidence():
    text = (
        "“Quietly, quietly, quietly,” Mara said. "
        "Quietly the silver moon rose. Silver moon rose. Silver moon rose. Quietly."
    )
    results = analyze_overused_language({1: text}, excluded_names=["Mara"])
    quiet = next(item for item in results if item["term"] == "quietly")
    phrase = next(item for item in results if item["term"] == "silver moon")

    assert quiet["count"] == 5
    assert quiet["dialogue_count"] == 3
    assert quiet["narration_count"] == 2
    assert quiet["burst_detected"] is True
    assert len(quiet["evidence"]) == 3
    assert all(len(item["excerpt"]) <= 240 for item in quiet["evidence"])
    assert phrase["count"] == 3
    assert not any(item["term"] == "mara" for item in results)
    assert not any(item["kind"] == "word" and len(item["term"]) < 4 for item in results)


def test_repetition_analysis_does_not_cross_sentence_boundaries_or_rank_all_stopwords():
    results = analyze_overused_language(
        {1: "Amber falls. River amber falls. River amber falls. River amber falls."}
    )
    assert not any(item["term"] == "falls river" for item in results)
    stopword_results = analyze_overused_language({1: "this that this that this that."})
    assert stopword_results == []


def _voice_profile(character_id: uuid.UUID, *, samples: int, words: int, offset: int = 0):
    return SimpleNamespace(
        character_id=character_id,
        sample_dialogue_count=samples,
        sample_word_count=words,
        avg_sentence_length=12 + offset,
        formality_score_x1000=500 + offset,
        contraction_rate_x1000=300 + offset,
        question_rate_x1000=100 + offset,
        exclamation_rate_x1000=50 + offset,
        ellipsis_rate_x1000=30 + offset,
        dash_rate_x1000=20 + offset,
        lexical_complexity_x1000=550 + offset,
        emotional_intensity_x1000=450 + offset,
        signature_phrases=["you know", "all right"],
    )


def test_voice_distinctness_uses_pairwise_similarity_confidence_and_data_gaps():
    left_id, right_id, sparse_id, missing_id = [uuid.uuid4() for _ in range(4)]
    characters = [
        SimpleNamespace(id=left_id, name="Mara"),
        SimpleNamespace(id=right_id, name="Ivo"),
        SimpleNamespace(id=sparse_id, name="Nell"),
        SimpleNamespace(id=missing_id, name="Orin"),
    ]
    rows, warnings = analyze_character_voice_distinctness(
        characters,
        [
            _voice_profile(left_id, samples=15, words=300),
            _voice_profile(right_id, samples=18, words=350),
            _voice_profile(sparse_id, samples=2, words=49, offset=50),
        ],
    )

    mara = next(item for item in rows if item["character_name"] == "Mara")
    nell = next(item for item in rows if item["character_name"] == "Nell")
    orin = next(item for item in rows if item["character_name"] == "Orin")
    assert mara["confidence"] == "high"
    assert mara["closest_character_name"] == "Ivo"
    assert mara["distinctness_score"] == 0
    assert mara["shared_phrases"] == ["all right", "you know"]
    assert "avg_sentence_length" in mara["signals"]
    assert nell["confidence"] == "insufficient" and nell["distinctness_score"] is None
    assert orin["sample_word_count"] == 0
    assert any("at least 3" in warning for warning in warnings)
    assert any("does not have" in warning for warning in warnings)


def test_voice_profiles_use_only_dialogue_from_the_requested_scope():
    mara_id, ivo_id = uuid.uuid4(), uuid.uuid4()
    characters = [
        SimpleNamespace(id=mara_id, name="Mara", aliases=["Captain Mara"]),
        SimpleNamespace(id=ivo_id, name="Ivo", aliases=[]),
    ]
    long_mara_line = " ".join(["quietly"] * 18)
    long_ivo_line = " ".join(["certainly"] * 18)
    chapter_text = " ".join(
        [f'Mara said, "{long_mara_line}."' for _ in range(3)]
        + [f'Ivo said, "{long_ivo_line}!"' for _ in range(3)]
    )
    stored_profiles = [
        SimpleNamespace(
            character_id=mara_id,
            sample_dialogue_count=99,
            sample_word_count=999,
            signature_phrases=["stored phrase"],
        ),
        SimpleNamespace(
            character_id=ivo_id,
            sample_dialogue_count=99,
            sample_word_count=999,
            signature_phrases=["other phrase"],
        ),
    ]

    scoped = build_scoped_voice_profiles(
        {4: chapter_text}, characters, stored_profiles, include_stored_signatures=False
    )
    assert [row["sample_dialogue_count"] for row in scoped] == [3, 3]
    assert [row["sample_word_count"] for row in scoped] == [54, 54]
    assert "stored phrase" not in scoped[0]["signature_phrases"]
    rows, _ = analyze_character_voice_distinctness(characters, scoped)
    assert {row["confidence"] for row in rows} == {"low"}

    scoped_with_signatures = build_scoped_voice_profiles(
        {4: chapter_text}, characters, stored_profiles, include_stored_signatures=True
    )
    assert "stored phrase" in scoped_with_signatures[0]["signature_phrases"]
    assert scoped_with_signatures[0]["sample_dialogue_count"] == 3


def test_fingerprints_hashes_and_stable_ids_are_deterministic():
    chapter_id = uuid.uuid4()
    chapters = [SimpleNamespace(id=chapter_id, number=1, content_version=2)]
    changed = [SimpleNamespace(id=chapter_id, number=1, content_version=3)]
    assert build_chapter_source_fingerprint(chapters) != build_chapter_source_fingerprint(changed)
    assert build_passage_source_fingerprint("  It’s here  ") == build_passage_source_fingerprint(
        "it's HERE"
    )
    assert build_beta_reader_request_hash({"b": 2, "a": 1}) == build_beta_reader_request_hash(
        {"a": 1, "b": 2}
    )
    assert stable_beta_reader_id("finding", "Voice", 2, "Same title") == stable_beta_reader_id(
        "finding", "voice", 2, "same title"
    )


def test_batch_splitting_caps_characters_and_chapter_count():
    chapter_texts = {number: f"Chapter {number} text" for number in range(1, 6)}
    batches = split_beta_reader_batches(chapter_texts)
    assert [len({chapter for chapter, _ in batch}) for batch in batches] == [4, 1]

    large = "paragraph words\n\n" * 2_000
    large_batches = split_beta_reader_batches({1: large})
    assert len(large_batches) > 1
    assert all(
        sum(len(text) for _, text in batch) <= MAX_BETA_READER_BATCH_CHARS
        for batch in large_batches
    )


def test_synthesis_normalization_rejects_malformed_findings_and_bounds_values():
    normalized = normalize_beta_reader_synthesis(
        '{"overall_impression":"Engaging", "strengths":["Clear stakes"], '
        '"findings":[{"category":"pacing", "severity":"urgent", "title":"Slow turn", '
        '"description":"The scene stalls.", "chapter_number":2, "evidence":"A long pause", '
        '"recommendation":"Compress the exchange."}, {"title":"Incomplete"}]}'
    )
    assert normalized["overall_impression"] == "Engaging"
    assert normalized["findings"][0]["severity"] == "medium"
    assert normalized["findings"][0]["chapter_number"] == 2
    assert len(normalized["findings"]) == 1


def _report(index: int) -> dict:
    return {
        "report_id": f"report-{index}",
        "scope": "chapter",
        "request_hash": "request",
        "source_fingerprint": "source",
        "created_at": f"2026-08-{index + 1:02d}T00:00:00Z",
        "is_stale": False,
        "checks": ["repetition"],
        "coverage": {
            "requested_chapters": [1],
            "analyzed_chapters": [1],
            "missing_chapters": [],
            "word_count": 100,
            "character_count": 0,
        },
        "overall_impression": "Deterministic pass complete.",
        "strengths": [],
        "reader_questions": [],
        "prioritized_revisions": [],
        "overused_terms": [],
        "character_voices": [],
        "findings": [],
        "revision_candidates": [],
        "warnings": [],
    }


def test_report_state_is_bounded_cached_and_does_not_mutate_input():
    report = _report(0)
    report["reader_vibe"] = "v" * 2_000
    report["story_understanding"] = "s" * 2_000
    report["strengths"] = ["x" * 800 for _ in range(10)]
    report["warnings"] = ["w" * 700 for _ in range(35)]
    report["overused_terms"] = [
        {
            "id": "term-1",
            "term": "echo",
            "kind": "word",
            "count": 6,
            "rate_per_1000": 6,
            "narration_count": 6,
            "dialogue_count": 0,
            "burst_detected": False,
            "chapter_counts": {str(index): 1 for index in range(600)},
            "evidence": [],
        }
    ]
    report["findings"] = [
        {
            "id": f"finding-{index}",
            "category": "clarity",
            "severity": "low",
            "title": "A finding",
            "description": "Description",
            "chapter_number": 1,
            "evidence": [{"chapter_number": 1, "excerpt": "x" * 400}],
            "recommendation": "Revise it.",
            "reader_question": None,
        }
        for index in range(25)
    ]
    bounded = bound_beta_reader_report(report)
    assert bounded is not None and len(bounded["findings"]) == 20
    assert len(bounded["findings"][0]["evidence"][0]["excerpt"]) == 240
    assert len(bounded["reader_vibe"]) == 1200
    assert len(bounded["strengths"]) == 8
    assert len(bounded["strengths"][0]) == 600
    assert len(bounded["warnings"]) == 30
    assert len(bounded["overused_terms"][0]["chapter_counts"]) == 500
    assert len(report["findings"][0]["evidence"][0]["excerpt"]) == 400
    assert len(report["reader_vibe"]) == 2_000

    state = normalize_ai_beta_reader_state({"reports": [_report(index) for index in range(6)]})
    assert len(state["reports"]) == 5
    merged = merge_beta_reader_report(state, _report(7))
    assert merged["reports"][0]["report_id"] == "report-7"
    assert (
        find_cached_beta_reader_report(merged, request_hash="request", source_fingerprint="source")
        is not None
    )


def test_revision_candidate_generation_is_stable_and_prioritized():
    finding = {
        "id": "finding-1",
        "category": "clarity",
        "severity": "high",
        "title": "Clarify the turn",
        "description": "The motivation is unclear.",
        "recommendation": "Add the missing reaction.",
        "chapter_number": 2,
        "evidence": [],
    }
    first = build_beta_reader_revision_candidates(
        overused_terms=[], character_voices=[], findings=[finding]
    )
    second = build_beta_reader_revision_candidates(
        overused_terms=[], character_voices=[], findings=[finding]
    )
    assert first == second
    assert first[0]["severity"] == "high"
