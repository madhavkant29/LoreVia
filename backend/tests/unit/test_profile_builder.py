from app.engine.character.profile_builder import build_description, merge_trait_states


def test_subjective_trait_capped():
    traits = {"face": {"value": "plain", "confidence": 0.8, "type": "subjective"}}
    result = merge_trait_states({}, traits)
    assert result["face"]["confidence"] <= 0.50


def test_merge_boosts_matching_traits():
    existing = {"hair": {"value": "black", "confidence": 0.6, "type": "objective"}}
    new = {"hair": {"value": "black", "confidence": 0.65, "type": "objective"}}
    result = merge_trait_states(existing, new)
    assert result["hair"]["confidence"] > 0.6


def test_merge_replaces_on_higher_confidence():
    existing = {"hair": {"value": "brown", "confidence": 0.4, "type": "objective"}}
    new = {"hair": {"value": "black", "confidence": 0.9, "type": "objective"}}
    result = merge_trait_states(existing, new)
    assert result["hair"]["value"] == "black"


def test_build_description_uses_archetype_when_sparse():
    desc = build_description({}, "japanese high school boy")
    assert "japanese" in desc.lower() or "school" in desc.lower()


def test_build_description_uses_traits():
    trait_state = {
        "hair": {"value": "black", "confidence": 0.9, "type": "objective"},
        "eyes": {"value": "tired", "confidence": 0.8, "type": "objective"},
    }
    desc = build_description(trait_state, None)
    assert "black" in desc
    assert "tired" in desc
