import json
import uuid

import pytest

from app.models.character import Character
from app.utils.characters.narrator_profile_review import (
    accept_narrator_profile_proposal,
    dedupe_narrator_profile_proposals,
    narrator_profile_proposals,
)


def test_narrator_profile_proposals_keep_only_passage_quoted_claims():
    passage = 'I wanted to leave. Lina said, "I feared the river." I stayed.'
    response = json.dumps(
        {
            "profile": {
                "motivations": ["leave", "hide"],
                "fears": ["the river"],
                "claim_evidence": {
                    "motivations": {
                        "leave": "I wanted to leave.",
                        "hide": "I wanted to hide.",
                    },
                    "fears": {"the river": "I feared the river."},
                },
            }
        }
    )

    proposals = narrator_profile_proposals(
        response,
        character_name="Arun Vale",
        chapter_number=2,
        window_start=100,
        source_passage=passage,
    )

    assert [(row["field"], row["value"]) for row in proposals] == [("motivations", "leave")]
    assert proposals[0]["source_start"] == 100
    assert proposals[0]["source_end"] == 118


def test_narrator_profile_proposals_reject_malformed_output():
    assert (
        narrator_profile_proposals(
            "not json",
            character_name="Arun Vale",
            chapter_number=1,
            window_start=0,
            source_passage="I waited.",
        )
        == []
    )


def test_dedupe_narrator_profile_proposals_preserves_first_quote():
    rows = [
        {"field": "motivations", "value": "Go home", "quote": "I went home."},
        {"field": "motivations", "value": "go home", "quote": "I left."},
        {"field": "fears", "value": "rain", "quote": "I feared rain."},
    ]
    assert dedupe_narrator_profile_proposals(rows, limit=2) == [rows[0], rows[2]]


def test_accept_narrator_profile_proposal_keeps_quote_and_marks_reviewed():
    generation = uuid.uuid4()
    character = Character(
        name="Arun Vale",
        book_id=uuid.uuid4(),
        generation_id=generation,
        first_chapter=1,
        trait_state={},
        motivations=[],
        analysis_metadata={
            "narrator_profile_review": {
                "generation_id": str(generation),
                "author_confirmed_identity": True,
                "proposals": [
                    {
                        "field": "motivations",
                        "value": "return home",
                        "quote": "I wanted to return home.",
                        "chapter_number": 1,
                        "source_start": 40,
                        "source_end": 64,
                    }
                ],
            }
        },
    )

    accept_narrator_profile_proposal(character, 0)

    assert character.motivations == ["return home"]
    assert character.analysis_metadata["profile_claims"][0]["quote"] == ("I wanted to return home.")
    assert (
        character.analysis_metadata["narrator_profile_review"]["proposals"][0]["status"]
        == "accepted"
    )
    with pytest.raises(ValueError, match="already_reviewed"):
        accept_narrator_profile_proposal(character, 0)


def test_accept_narrator_profile_proposal_rejects_stale_identity_and_conflicting_goal():
    generation = uuid.uuid4()
    proposal = {
        "field": "goal",
        "value": "return home",
        "quote": "I wanted to return home.",
        "chapter_number": 1,
        "source_start": 40,
        "source_end": 64,
    }
    character = Character(
        name="Arun Vale",
        book_id=uuid.uuid4(),
        generation_id=generation,
        first_chapter=1,
        goal="save the gate",
        analysis_metadata={
            "narrator_profile_review": {
                "generation_id": str(generation),
                "author_confirmed_identity": True,
                "proposals": [proposal],
            }
        },
    )
    with pytest.raises(ValueError, match="conflicts"):
        accept_narrator_profile_proposal(character, 0)
    assert character.goal == "save the gate"
    character.generation_id = uuid.uuid4()
    with pytest.raises(ValueError, match="unavailable"):
        accept_narrator_profile_proposal(character, 0)
