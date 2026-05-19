import pytest

from app.engine.character.entity_filters import character_persistence_decision


@pytest.mark.parametrize("name", ["Well", "Back", "Would", "Come", "Mother"])
def test_character_persistence_gate_rejects_noise_names(name: str):
    decision = character_persistence_decision(
        name,
        entity_type="person",
        evidence={
            "mention_count": 1,
            "strong_mention_count": 0,
            "has_dialogue_or_action": False,
            "has_physical_description": False,
            "appears_multiple_times": False,
        },
        arc_summary="is a character",
    )

    assert decision.allowed is False


@pytest.mark.parametrize("name", ["Grete", "Ling", "Yuki"])
def test_character_persistence_gate_allows_legitimate_short_names(name: str):
    decision = character_persistence_decision(
        name,
        entity_type="person",
        evidence={
            "mention_count": 2,
            "strong_mention_count": 1,
            "has_dialogue_or_action": True,
            "has_physical_description": True,
            "appears_multiple_times": True,
        },
        arc_summary="A grounded supporting character.",
    )

    assert decision.allowed is True


def test_character_persistence_gate_ignores_placeholder_summaries_for_noise_names():
    decision = character_persistence_decision(
        "Well",
        entity_type="person",
        evidence={
            "mention_count": 1,
            "strong_mention_count": 0,
            "has_dialogue_or_action": False,
            "has_physical_description": False,
            "appears_multiple_times": False,
        },
        arc_summary="mysterious figure",
    )

    assert decision.allowed is False
    assert "generic_profile_summary" in decision.reasons or "visibility_score_below_threshold" in decision.reasons
