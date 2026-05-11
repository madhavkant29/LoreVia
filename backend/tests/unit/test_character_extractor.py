from app.engine.character.extractor import _allow_auto_augmentation, _apply_anti_merge_hints, _clean_character_entries


def test_clean_character_entries_strips_fragment_prefixes_and_keeps_supported_name():
    source_text = "Meeting Kunagisa in the hall, Aikawa Junya called to Kunagisa and Kunagisa frowned."
    characters = [
        {
            "name": "Meeting Kunagisa",
            "entity_type": "person",
            "is_character": True,
            "confidence": 0.92,
            "aliases": [],
            "traits": {"distinguishing": {"value": "sharp gaze", "confidence": 0.88, "type": "objective"}},
            "arc_summary": "sharp observer",
        }
    ]

    cleaned = _clean_character_entries(characters, ["Meeting Kunagisa"], source_text)

    assert len(cleaned) == 1
    assert cleaned[0]["name"] == "Kunagisa"


def test_clean_character_entries_rejects_locations_and_discourse_noise():
    source_text = "Feather Island was quiet. Well, Aikawa Junya kept walking toward the harbor."
    characters = [
        {
            "name": "Feather Island",
            "entity_type": "location",
            "is_character": False,
            "confidence": 0.98,
            "aliases": [],
        },
        {
            "name": "Well",
            "entity_type": "unknown",
            "is_character": True,
            "confidence": 0.81,
            "aliases": [],
        },
    ]

    cleaned = _clean_character_entries(characters, ["Feather Island", "Well"], source_text)

    assert cleaned == []


def test_clean_character_entries_drops_low_confidence_generic_summary():
    source_text = "Yeah, someone spoke once. Aikawa Junya glanced over."
    characters = [
        {
            "name": "Yeah",
            "entity_type": "unknown",
            "is_character": True,
            "confidence": 0.40,
            "aliases": [],
            "arc_summary": "mysterious figure",
        }
    ]

    cleaned = _clean_character_entries(characters, ["Yeah"], source_text)

    assert cleaned == []


def test_auto_augmentation_rejects_single_token_name():
    source_text = "Kunagisa spoke to Aikawa Junya. Kunagisa looked away."

    assert _allow_auto_augmentation(source_text, "Kunagisa") is False


def test_apply_anti_merge_hints_marks_same_sentence_characters_as_distinct():
    source_text = "Saitou Kengo and Saitou Masami entered the room together."
    characters = [
        {"name": "Saitou Kengo", "aliases": []},
        {"name": "Saitou Masami", "aliases": []},
    ]

    hinted = _apply_anti_merge_hints(source_text, characters)

    assert "Saitou Masami" in hinted[0]["anti_merge_names"]
    assert "Saitou Kengo" in hinted[1]["anti_merge_names"]


def test_clean_character_entries_keeps_titled_surname_only_names_distinct():
    source_text = "Mr. Samsa spoke first. Mrs. Samsa answered him from the doorway."
    characters = [
        {
            "name": "Mr. Samsa",
            "entity_type": "person",
            "is_character": True,
            "confidence": 0.91,
            "aliases": [],
            "traits": {},
            "arc_summary": "stern and worried",
        },
        {
            "name": "Mrs. Samsa",
            "entity_type": "person",
            "is_character": True,
            "confidence": 0.9,
            "aliases": [],
            "traits": {},
            "arc_summary": "protective and anxious",
        },
    ]

    cleaned = _clean_character_entries(characters, ["Mr. Samsa", "Mrs. Samsa"], source_text)

    assert [item["name"] for item in cleaned] == ["Mr. Samsa", "Mrs. Samsa"]
