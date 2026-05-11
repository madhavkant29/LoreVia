import uuid

from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import CharacterRelationship
from app.utils.character_utils import build_character_arc_tracker


def test_build_character_arc_tracker_surfaces_timeline_and_diagnostics():
    character_id = uuid.uuid4()
    counterpart_id = uuid.uuid4()
    character = Character(
        id=character_id,
        book_id=uuid.uuid4(),
        name="Mira",
        first_chapter=1,
        last_seen_chapter=24,
        goal="Keep the caravan alive.",
        motivations=["Protect the caravan"],
        fears=["Failing her people"],
        lie_they_believe="Leadership always costs love.",
        backstory_wound="She watched a former captain die after trusting the council.",
        arc_type="positive change",
        arc_summary="Mira resists command until crisis forces her to lead.",
        growth_events=[
            {"chapter_number": 1, "event_title": "Refuses leadership"},
            {"chapter_number": 8, "event_title": "Takes responsibility for the caravan"},
            {"chapter_number": 24, "event_title": "Accepts command"},
        ],
        trait_state={},
    )
    states = [
        CharacterState(
            character_id=character_id,
            at_chapter=1,
            trait_snapshot={"build": {"value": "slight", "confidence": 0.9}},
            motivations_snapshot=["Stay unnoticed"],
            fears_snapshot=["Failing her people"],
            arc_note="Still hiding from duty.",
        ),
        CharacterState(
            character_id=character_id,
            at_chapter=16,
            trait_snapshot={"build": {"value": "battle-worn", "confidence": 0.9}},
            motivations_snapshot=["Protect the caravan"],
            fears_snapshot=["Failing her people"],
            arc_note="Starts stepping into responsibility.",
        ),
    ]
    relationships = [
        CharacterRelationship(
            book_id=character.book_id,
            character_a_id=character_id,
            character_b_id=counterpart_id,
            rel_type="enemy",
            sentiment=-0.7,
            description="Mira distrusts Joren.",
            from_chapter=4,
        ),
        CharacterRelationship(
            book_id=character.book_id,
            character_a_id=character_id,
            character_b_id=counterpart_id,
            rel_type="ally",
            sentiment=0.8,
            description="Mira trusts Joren with the caravan.",
            from_chapter=5,
        ),
    ]
    voice_profile = CharacterVoiceProfile(
        book_id=character.book_id,
        character_id=character_id,
        dominant_markers={"tone": "guarded", "question_rate": "high"},
        signature_phrases=["Keep moving."],
    )

    tracker = build_character_arc_tracker(
        character,
        states=states,
        relationships=relationships,
        counterpart_names={counterpart_id: "Joren"},
        voice_profile=voice_profile,
        total_chapters=24,
    )

    assert tracker["goal"] == "Keep the caravan alive."
    assert tracker["arc_timeline"][0] == "Chapter 1: Refuses leadership"
    assert any("Motivation changed, but no scene explains why." == item for item in tracker["diagnostics"])
    assert any("Relationship with Joren shifts from hostile to trusting too abruptly." == item for item in tracker["diagnostics"])
    assert any(item["label"] == "Build" for item in tracker["physical_description_history"])
    assert any("Signature phrase" in item for item in tracker["voice_markers"])
