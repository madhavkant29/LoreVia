import uuid

from app.engine.character.profile_builder import build_character_profile


def test_profile_builder_handles_sparse_data():
    extracted = {
        "name": "John",
        "aliases": [],
        "traits": {},
        "personality_tags": [],
        "archetype": "young adult male protagonist",
    }
    profile = build_character_profile(extracted, uuid.uuid4(), first_chapter=1)
    assert profile["name"] == "John"
    assert profile["archetype"] == "young adult male protagonist"
    assert profile["trait_state"] == {}


def test_profile_builder_extracts_flat_columns():
    extracted = {
        "name": "Aria",
        "aliases": ["Lady Aria"],
        "traits": {
            "hair": {"value": "silver", "confidence": 0.9, "type": "objective"},
            "eyes": {"value": "violet", "confidence": 0.85, "type": "objective"},
        },
        "personality_tags": ["cold", "strategic"],
    }
    profile = build_character_profile(extracted, uuid.uuid4(), first_chapter=3)
    assert profile["hair"] == "silver"
    assert profile["eyes"] == "violet"
    assert "cold" in profile["personality_tags"]
