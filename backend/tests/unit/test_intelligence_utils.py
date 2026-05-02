"""Unit tests for voice fingerprint utility helpers."""

from app.utils.intelligence_utils import (
    compute_voice_metrics,
    extract_dialogue_samples_by_character,
    score_voice_match,
)


def test_extract_dialogue_samples_by_character_matches_nearby_names():
    text = 'Kael muttered, "Keep moving." Elder Mira replied, "We proceed with care."'

    samples = extract_dialogue_samples_by_character(
        text,
        [
            {"name": "Kael", "aliases": []},
            {"name": "Elder Mira", "aliases": ["Mira"]},
        ],
    )

    assert samples["Kael"] == ["Keep moving."]
    assert samples["Elder Mira"] == ["We proceed with care."]


def test_compute_voice_metrics_tracks_formality_and_punctuation():
    metrics = compute_voice_metrics(
        [
            "We shall proceed with caution, therefore remain alert.",
            "Do you understand? Excellent!",
        ]
    )

    assert metrics["sample_dialogue_count"] == 2
    assert metrics["sample_word_count"] > 5
    assert metrics["formality_score_x1000"] > 0
    assert metrics["question_rate_x1000"] > 0
    assert metrics["exclamation_rate_x1000"] > 0


def test_score_voice_match_penalizes_drift_and_explains_signals():
    profile = compute_voice_metrics(
        [
            "No. Move.",
            "Keep low. Stay sharp.",
        ]
    )
    sample = compute_voice_metrics(
        [
            "We should, perhaps, proceed with greater delicacy and caution.",
            "Do you agree with this approach?",
        ]
    )

    score, signals = score_voice_match(profile, sample)

    assert score < 70
    assert signals
