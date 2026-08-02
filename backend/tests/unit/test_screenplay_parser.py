"""Unit tests for screenplay parsing primitives."""

from app.parsers.screenplay_parser import (
    Character,
    DialogueElement,
    extract_dialogue_from_scene,
    parse_screenplay,
)


def test_parse_screenplay_emits_dialogue_blocks_with_parentheticals_and_extensions():
    screenplay = """INT. HALLWAY - NIGHT

MAYA (O.S.)
(urgent)
Open the door.
Right now.

JON
I'm trying.
"""

    scenes = parse_screenplay(screenplay)

    assert len(scenes) == 1
    scene = scenes[0]
    assert scene.text == "INT. HALLWAY - NIGHT"
    assert any(
        isinstance(element, Character) and element.name == "MAYA" and element.extension == "O.S."
        for element in scene.elements
    )
    assert any(
        isinstance(element, DialogueElement) and "Open the door." in element.text
        for element in scene.elements
    )

    dialogue = extract_dialogue_from_scene(scene)

    assert len(dialogue) == 2
    assert dialogue[0]["character_name"] == "MAYA"
    assert dialogue[0]["character_extension"] == "O.S."
    assert dialogue[0]["parenthetical"] == "urgent"
    assert dialogue[0]["dialogue_text"] == "Open the door.\nRight now."
    assert dialogue[1]["character_name"] == "JON"
    assert dialogue[1]["dialogue_text"] == "I'm trying."


def test_parse_screenplay_splits_multiple_scenes_and_preserves_action():
    screenplay = """INT. APARTMENT - DAY

Dust hangs in the sunlight.

EXT. FIRE ESCAPE - CONTINUOUS

MAYA
Move.
"""

    scenes = parse_screenplay(screenplay)

    assert len(scenes) == 2
    assert scenes[0].location == "APARTMENT"
    assert scenes[0].time_of_day == "DAY"
    assert scenes[1].location == "FIRE ESCAPE"
    assert scenes[1].time_of_day == "CONTINUOUS"
    assert any(element.text == "Dust hangs in the sunlight." for element in scenes[0].elements)
