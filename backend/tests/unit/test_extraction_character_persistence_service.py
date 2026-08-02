from app.services.extraction_character_persistence_service import (
    _build_observed_state_snapshot,
    _changed,
    _diff,
    _observed_trait_keys,
)


def test_observed_state_snapshot_preserves_conflicting_incoming_value():
    merged = {"eyes": {"value": "blue", "confidence": 0.9, "type": "objective"}}
    observed = {"eyes": {"value": "green", "confidence": 0.8, "type": "objective"}}

    snapshot = _build_observed_state_snapshot(merged, observed)

    assert snapshot["eyes"]["value"] == "green"
    assert merged["eyes"]["value"] == "blue"


def test_state_change_detects_equal_confidence_value_contradiction():
    old = {"eyes": {"value": "blue", "confidence": 0.8}}
    new = {"eyes": {"value": "green", "confidence": 0.8}}

    assert _changed(old, new) is True
    assert _diff(old, new) == "eyes: blue->green"


def test_state_change_ignores_case_and_whitespace_only_difference():
    old = {"hair": {"value": "Dark Brown", "confidence": 0.8}}
    new = {"hair": {"value": "  dark   brown ", "confidence": 0.8}}

    assert _changed(old, new) is False
    assert _diff(old, new) == "minor update"


def test_observed_trait_keys_exclude_carried_profile_traits():
    assert _observed_trait_keys(
        {
            "eyes": {"value": "green", "confidence": 0.8},
            "hair": {"confidence": 0.9},
        }
    ) == ["eyes"]
