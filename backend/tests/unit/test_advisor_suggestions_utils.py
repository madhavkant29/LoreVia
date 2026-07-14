from types import SimpleNamespace
import uuid

from app.utils.advisor_suggestions_utils import (
    build_relationship_drift_suggestions,
    build_world_drift_suggestions,
)


def test_build_relationship_drift_suggestions_flags_type_changes():
    character_a_id = uuid.uuid4()
    character_b_id = uuid.uuid4()

    suggestions = build_relationship_drift_suggestions(
        [
            SimpleNamespace(
                character_a_id=character_a_id,
                character_b_id=character_b_id,
                rel_type="allies",
                sentiment=0.5,
                from_chapter=2,
                description="They work together.",
            ),
            SimpleNamespace(
                character_a_id=character_a_id,
                character_b_id=character_b_id,
                rel_type="enemies",
                sentiment=-0.9,
                from_chapter=8,
                description="They betray each other.",
            ),
        ],
        {character_a_id: "Mara", character_b_id: "Ilan"},
    )

    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "relationship_flip"
    assert suggestions[0]["severity"] == "warning"
    assert suggestions[0]["title"] == "Relationship drift: Mara / Ilan"
    assert suggestions[0]["chapter_ref"] == 8


def test_build_relationship_drift_suggestions_flags_sentiment_swings():
    character_a_id = uuid.uuid4()
    character_b_id = uuid.uuid4()

    suggestions = build_relationship_drift_suggestions(
        [
            SimpleNamespace(
                character_a_id=character_a_id,
                character_b_id=character_b_id,
                rel_type="siblings",
                sentiment=0.8,
                from_chapter=1,
                description=None,
            ),
            SimpleNamespace(
                character_a_id=character_a_id,
                character_b_id=character_b_id,
                rel_type="siblings",
                sentiment=-0.5,
                from_chapter=4,
                description=None,
            ),
        ],
        {character_a_id: "Mara", character_b_id: "Ilan"},
    )

    assert len(suggestions) == 1
    assert suggestions[0]["severity"] == "info"
    assert "emotional tone" in suggestions[0]["description"]


def test_build_world_drift_suggestions_flags_conflicting_canon():
    suggestions = build_world_drift_suggestions(
        [
            SimpleNamespace(
                element_type="location",
                name="Glass Harbor",
                description="Glass Harbor is north of the capital.",
            ),
            SimpleNamespace(
                element_type="location",
                name="Glass Harbor",
                description="Glass Harbor sits south of the capital beyond the marsh.",
            ),
        ]
    )

    assert len(suggestions) == 1
    assert suggestions[0]["type"] == "location_conflict"
    assert suggestions[0]["title"] == "Location details drift: Glass Harbor"
    assert suggestions[0]["ask_prompt"].startswith("Check the canon for Glass Harbor")
