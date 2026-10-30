from app.utils.characters.narrator import (
    contextual_first_person_narrators,
    detect_explicit_first_person_narrator,
    explicit_first_person_narrators,
    first_person_addressed_name,
    first_person_self_identification,
)


def test_first_person_self_identification_finds_explicit_named_narrator():
    text = (
        "I arrived at the clinic before sunrise. The receptionist asked for my name; "
        "I told her I was Arun Vale. She wrote it in the visitor book."
    )

    assert first_person_self_identification(text, "Arun Vale") == "I told her I was Arun Vale"
    assert first_person_self_identification(text, "Madame Vale") is None


def test_first_person_self_identification_accepts_narrators_identified_by_their_pass():
    text = "My pass identified me as Leena Voss. I showed it to the mechanic."

    assert first_person_self_identification(text, "Leena Voss") == (
        "My pass identified me as Leena Voss"
    )
    assert first_person_self_identification(text, "the mechanic") is None
    assert (
        first_person_self_identification(
            'The visitor said, "My pass identified me as Leena Voss." I listened.',
            "Leena Voss",
        )
        is None
    )


def test_first_person_self_identification_does_not_use_quoted_dialogue():
    for text in (
        'The stranger said, "I was Arun Vale." The narrator watched him.',
        "The stranger said, ‘I was Arun Vale.’ The narrator watched him.",
        "The stranger said, 'I was Arun Vale.' The narrator watched him.",
    ):
        assert first_person_self_identification(text, "Arun Vale") is None


def test_first_person_self_identification_accepts_narrator_attributed_dialogue():
    assert (
        first_person_self_identification(
            'I told the registrar, "My name is Arun Vale."', "Arun Vale"
        )
        == "My name is Arun Vale"
    )
    assert (
        first_person_self_identification("“I am Arun Vale,” I replied.", "Arun Vale")
        == "I am Arun Vale"
    )
    assert (
        first_person_self_identification('I said, "He claimed I was Arun Vale."', "Arun Vale")
        is None
    )
    assert first_person_self_identification('I said, "I was not Arun Vale."', "Arun Vale") is None
    assert (
        first_person_self_identification('She said, "I am Arun Vale." I listened.', "Arun Vale")
        is None
    )
    assert (
        first_person_self_identification(
            'The stranger said, "I am Arun Vale." I replied that I doubted him.', "Arun Vale"
        )
        is None
    )


def test_first_person_self_identification_rejects_ambiguous_or_negated_references():
    assert first_person_self_identification("I was not Arun Vale.", "Arun Vale") is None
    assert first_person_self_identification("I knew Arun Vale well.", "Arun Vale") is None
    assert first_person_self_identification("I was Arun Vale's brother.", "Arun Vale") is None
    assert first_person_self_identification("I was Vale.", "Vale") is None
    assert first_person_self_identification("", "Arun Vale") is None


def test_known_single_name_can_self_identify_outside_dialogue_without_prefix_merges():
    assert first_person_self_identification("I am Mara.", "Mara") is None
    assert (
        first_person_self_identification("I am Mara.", "Mara", allow_single_name=True)
        == "I am Mara"
    )
    assert (
        first_person_self_identification(
            "I am Mara Vale, not her sister.", "Mara", allow_single_name=True
        )
        is None
    )
    assert (
        first_person_self_identification('She said, "I am Lina."', "Lina", allow_single_name=True)
        is None
    )


def test_addressed_name_is_a_tentative_narrator_clue_not_self_identification():
    text = (
        'The registrar said, "I will leave you here, Monsieur Vale." '
        "I thanked her and walked into the hall."
    )

    assert first_person_addressed_name(text, "Monsieur Vale") == "you here, Monsieur Vale"
    assert first_person_self_identification(text, "Monsieur Vale") is None
    assert first_person_addressed_name(text, "Madame Vale") is None


def test_addressed_name_requires_narrator_response_and_complete_name():
    assert (
        first_person_addressed_name(
            'He told the guard, "I will leave you, Arun Vale."', "Arun Vale"
        )
        is None
    )
    assert (
        first_person_addressed_name('"I will leave you, Arun Vale." I thanked him.', "Arun") is None
    )
    assert first_person_addressed_name("", "Arun Vale") is None
    assert (
        first_person_addressed_name('"I know you know Arun Vale." I nodded.', "Arun Vale") is None
    )
    assert first_person_addressed_name('"You, Mara." I nodded.', "Mara") is None
    assert (
        first_person_addressed_name('"You, Mara." I nodded.', "Mara", allow_single_name=True)
        == "You, Mara"
    )


def test_auto_detect_narrator_accepts_explicit_alias_without_merging_shared_surnames():
    characters = [
        {"name": "Madame Arlen", "aliases": ["Mrs. Arlen"]},
        {"name": "Monsieur Arlen", "aliases": ["Mr. Arlen"]},
    ]

    detected = detect_explicit_first_person_narrator(
        'I told the clerk, "My name is Mrs. Arlen." Mr. Arlen waited outside.', characters
    )

    assert detected is characters[0]


def test_auto_detect_narrator_refuses_quoted_other_speaker_or_multiple_self_names():
    characters = [{"name": "Mara", "aliases": []}, {"name": "Lina", "aliases": []}]

    assert (
        detect_explicit_first_person_narrator(
            'Lina said, "I am Lina." I watched her leave.', characters
        )
        is None
    )
    assert detect_explicit_first_person_narrator("I am Mara. Later I am Lina.", characters) is None
    assert detect_explicit_first_person_narrator("I crossed the square.", characters) is None


def test_explicit_narrators_report_mixed_viewpoints_without_other_speaker_false_positives():
    characters = [{"name": "Mara", "aliases": []}, {"name": "Lina", "aliases": []}]

    assert (
        explicit_first_person_narrators(
            "I am Mara. Later I am Lina. I crossed the square.", characters
        )
        == characters
    )
    assert (
        explicit_first_person_narrators(
            'I am Mara. Lina said, "I am Lina." I listened.', characters
        )
        == characters[:1]
    )


def test_contextual_narrators_keep_direct_address_separate_from_explicit_identity():
    characters = [
        {"name": "Madame Vale", "aliases": []},
        {"name": "Monsieur Vale", "aliases": ["Mr. Vale"]},
    ]
    text = 'The warden said, "I leave you here, Monsieur Vale." I thanked him.'

    assert contextual_first_person_narrators(text, characters) == characters[1:]
    assert explicit_first_person_narrators(text, characters) == []
    assert (
        contextual_first_person_narrators('"You, Mr. Vale." I nodded.', characters)
        == characters[1:]
    )
    assert contextual_first_person_narrators('"You, Vale." I nodded.', characters) == []
    assert (
        contextual_first_person_narrators(
            '"You, Madame Vale." I nodded. "You, Monsieur Vale." I replied.', characters
        )
        == characters
    )
