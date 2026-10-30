"""Shared direct-speaker evidence for persisted and scoped voice metrics."""

import uuid

from app.utils.voice_profile_samples import explicit_dialogue_by_character


def test_explicit_dialogue_ignores_nearby_names_and_contextual_pronouns():
    cast = [
        {"id": uuid.uuid4(), "name": "Mara", "aliases": []},
        {"id": uuid.uuid4(), "name": "Lina", "aliases": []},
    ]
    passage = (
        'Mara watched the door. "The gate is open," Lina said. '
        'Mara closed the window. She said, "Stay here."'
    )

    assert explicit_dialogue_by_character(passage, cast, chapter_number=2) == {
        "Lina": ["The gate is open,"]
    }


def test_explicit_dialogue_credits_verified_first_person_speaker_without_claiming_other_speech():
    cast = [{"name": "Mara Vale", "aliases": []}, {"name": "Lina", "aliases": []}]
    passage = 'I am Mara Vale. I said, "Keep the lamps low." Lina replied, "I will check the gate."'

    assert explicit_dialogue_by_character(passage, cast) == {
        "Mara Vale": ["Keep the lamps low."],
        "Lina": ["I will check the gate."],
    }


def test_explicit_dialogue_does_not_guess_narrator_when_two_people_self_identify():
    cast = [{"name": "Mara Vale", "aliases": []}, {"name": "Lina Moss", "aliases": []}]
    passage = (
        'I am Mara Vale. I said, "Keep the lamps low." I am Lina Moss. I said, "Open the gate."'
    )

    assert explicit_dialogue_by_character(passage, cast) == {}


def test_shared_surname_is_not_promoted_to_either_character_alias():
    cast = [
        {"name": "Madame Arlen", "aliases": ["Arlen"]},
        {"name": "Monsieur Arlen", "aliases": ["Arlen"]},
    ]
    passage = 'Arlen said, "Wait." Madame Arlen replied, "Please stay."'

    assert explicit_dialogue_by_character(passage, cast) == {"Madame Arlen": ["Please stay."]}


def test_postposed_full_name_does_not_credit_shorter_distinct_character():
    cast = [
        {"name": "Alice", "aliases": []},
        {"name": "Alice Smith", "aliases": []},
    ]
    passage = (
        '"Wait here," said Alice Smith. '
        '"I will return," Alice said. '
        '"Please listen," said Alice softly. '
        'Said Alice Smith, "Do not move."'
    )

    assert explicit_dialogue_by_character(passage, cast) == {
        "Alice": ["I will return,", "Please listen,"],
        "Alice Smith": ["Wait here,", "Do not move."],
    }


def test_long_quote_is_counted_once_without_overlapping_words():
    cast = [{"name": "Mara", "aliases": []}]
    speech = " ".join(f"word{index}" for index in range(180))

    assert explicit_dialogue_by_character(f'Mara said, "{speech}"', cast) == {"Mara": [speech]}


def test_late_speech_after_character_4000_is_kept_in_voice_profile_evidence():
    cast = [{"name": "Mara", "aliases": []}]
    passage = "The road remained quiet. " * 180 + 'Mara said, "I shall return before dawn."'
    assert passage.index("Mara said") > 4_000

    assert explicit_dialogue_by_character(passage, cast, chapter_number=9) == {
        "Mara": ["I shall return before dawn."]
    }


def test_empty_or_unattributed_passage_has_no_character_voice_evidence():
    cast = [{"name": "Mara", "aliases": []}]

    assert explicit_dialogue_by_character("", cast) == {}
    assert explicit_dialogue_by_character('Mara watched. "Wait here."', cast) == {}
    assert explicit_dialogue_by_character('Mara said, "Wait here."', []) == {}
