import pytest

from app.engine.character.adjudicator import (
    ADJUDICATION_MERGED_ALIAS,
    ADJUDICATION_OBJECT,
    ADJUDICATION_PLACE,
    ADJUDICATION_PROMOTED_CHARACTER,
    ADJUDICATION_QUARANTINED,
    ADJUDICATION_REJECTED,
    ADJUDICATION_TITLE_OR_ROLE,
    ENTITY_ALIAS_CANDIDATE,
    ENTITY_JUNK,
    ENTITY_OBJECT,
    ENTITY_PERSON,
    ENTITY_PLACE,
    ENTITY_TITLE_OR_ROLE,
    adjudicate_character_candidate,
)
from app.services.character_identity.normalization import display_name_form, normalized_comparison_name


def test_normalization_preserves_display_and_expands_honorifics_for_comparison():
    assert display_name_form("  Dr.  Kemp... ") == "Dr. Kemp"
    assert normalized_comparison_name("Dr. Kemp") == "doctor kemp"
    assert normalized_comparison_name("Mr Marvel") == "mister marvel"
    assert normalized_comparison_name("Prof. Cavor") == "professor cavor"


@pytest.mark.parametrize("name", ["T", "B"])
def test_one_letter_fragments_are_rejected(name):
    adjudication = adjudicate_character_candidate(name, evidence={"mention_count": 3})

    assert adjudication.entity_type == ENTITY_JUNK
    assert adjudication.adjudication_status == ADJUDICATION_REJECTED
    assert "one_letter_fragment" in adjudication.reason_codes


@pytest.mark.parametrize(
    "name",
    ["Port Stowe", "Bloomsbury Square", "Bedford Street", "Covent Garden Market"],
)
def test_place_candidates_are_classified_without_promotion(name):
    adjudication = adjudicate_character_candidate(
        name,
        evidence={
            "mention_count": 2,
            "snippets": [f"They arrived at {name} before dusk."],
        },
    )

    assert adjudication.entity_type == ENTITY_PLACE
    assert adjudication.adjudication_status == ADJUDICATION_PLACE
    assert adjudication.rejection_reason == "likely_place"


@pytest.mark.parametrize("name", ["Doctor Kemp", "Thomas Marvel", "Teddy Henfrey"])
def test_person_candidates_promote_with_strong_human_evidence(name):
    adjudication = adjudicate_character_candidate(
        name,
        confidence=0.8,
        evidence={
            "mention_count": 4,
            "chapter_numbers": [1, 2],
            "has_dialogue_or_action": True,
            "has_physical_description": True,
            "snippets": [
                f"{name} said he would return before nightfall.",
                f"{name} walked to the door with his coat in his hands.",
            ],
        },
    )

    assert adjudication.entity_type in {ENTITY_PERSON, ENTITY_ALIAS_CANDIDATE}
    assert adjudication.adjudication_status == ADJUDICATION_PROMOTED_CHARACTER
    assert adjudication.character_score >= 60


def test_honorific_alias_forms_share_comparison_name():
    assert normalized_comparison_name("Dr. Kemp") == normalized_comparison_name("Doctor Kemp")
    assert normalized_comparison_name("Kemp") == "kemp"

    adjudication = adjudicate_character_candidate(
        "Dr. Kemp",
        aliases=["Doctor Kemp", "Kemp"],
        matched_character_id="character-1",
        evidence={
            "mention_count": 3,
            "has_dialogue_or_action": True,
            "snippets": ["Dr. Kemp said he knew the answer."],
        },
    )

    assert adjudication.adjudication_status == ADJUDICATION_MERGED_ALIAS


def test_verifier_local_windows_contribute_to_person_evidence():
    adjudication = adjudicate_character_candidate(
        "Eleanor Vane",
        evidence={
            "mention_count": 2,
            "verifier": {
                "local": {
                    "mention_count": 2,
                    "person_context_mentions": 1,
                    "person_ner_mentions": 1,
                    "subject_action_mentions": 1,
                    "windows": [
                        {
                            "text": "Eleanor Vane turned and answered him quietly.",
                            "has_person_context": True,
                            "ner_label": "PERSON",
                        }
                    ],
                },
                "final": {"is_person_like": True},
            },
        },
    )

    assert adjudication.entity_type == ENTITY_PERSON
    assert adjudication.adjudication_status == ADJUDICATION_PROMOTED_CHARACTER
    assert "person_ner_window" in adjudication.reason_codes


def test_repeated_full_name_with_human_evidence_promotes_at_boundary():
    adjudication = adjudicate_character_candidate(
        "Anna Sergeyevna",
        confidence=0.94,
        evidence={
            "mention_count": 2,
            "has_dialogue_or_action": True,
            "has_physical_description": True,
            "appears_multiple_times": True,
        },
    )

    assert adjudication.adjudication_status == ADJUDICATION_PROMOTED_CHARACTER
    assert adjudication.character_score >= 60
    assert "full_name_human_evidence" in adjudication.reason_codes


def test_reverse_dialogue_attribution_supports_real_character_promotion():
    adjudication = adjudicate_character_candidate(
        "Thomas Marvel",
        evidence={
            "mention_count": 2,
            "chapter_numbers": [1, 2],
            "snippets": [
                '"I will not go," said Thomas Marvel. He trembled beside the road.',
                '"Wait," replied Thomas Marvel, and he turned back.',
            ],
        },
    )

    assert adjudication.adjudication_status == ADJUDICATION_PROMOTED_CHARACTER
    assert "dialogue_attribution" in adjudication.reason_codes


@pytest.mark.parametrize("name", ["the villagers", "the guards", "the servants"])
def test_group_descriptors_do_not_promote_as_characters(name):
    adjudication = adjudicate_character_candidate(
        name,
        evidence={
            "mention_count": 3,
            "chapter_numbers": [1, 2],
            "snippets": [
                f'"Stop there," said {name}. They gathered at the gate.',
                f'{name} shouted that they would not leave.',
            ],
        },
    )

    assert adjudication.entity_type == ENTITY_TITLE_OR_ROLE
    assert adjudication.adjudication_status == ADJUDICATION_TITLE_OR_ROLE
    assert "candidate_kind_group_descriptor" in adjudication.reason_codes


@pytest.mark.parametrize("name", ["the police", "the crew", "the army"])
def test_collective_group_words_do_not_promote_as_characters(name):
    adjudication = adjudicate_character_candidate(
        name,
        evidence={
            "mention_count": 4,
            "chapter_numbers": [1, 2],
            "snippets": [f'"Go back," said {name}. They blocked the street.'],
        },
    )

    assert adjudication.entity_type == ENTITY_TITLE_OR_ROLE
    assert adjudication.adjudication_status == ADJUDICATION_TITLE_OR_ROLE


@pytest.mark.parametrize("name", ["the room", "the door", "the ship"])
def test_object_or_place_kind_is_suppressed_without_human_evidence(name):
    adjudication = adjudicate_character_candidate(
        name,
        evidence={
            "mention_count": 3,
            "chapter_numbers": [1, 2],
            "snippets": [f"They waited in {name} until dawn."],
        },
    )

    assert adjudication.entity_type == ENTITY_OBJECT
    assert adjudication.adjudication_status == ADJUDICATION_OBJECT
    assert "candidate_kind_object_or_place" in adjudication.reason_codes


@pytest.mark.parametrize("name", ["the stranger", "Invisible Man"])
def test_ambiguous_aliases_quarantine_with_human_context(name):
    adjudication = adjudicate_character_candidate(
        name,
        evidence={
            "mention_count": 1,
            "has_dialogue_or_action": True,
            "snippets": [f"{name} said he could not be seen."],
        },
    )

    assert adjudication.adjudication_status == ADJUDICATION_QUARANTINED
    assert adjudication.character_score >= 15
