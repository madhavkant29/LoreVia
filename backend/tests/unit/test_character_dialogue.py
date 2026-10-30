"""Distinguish explicit character speech from nearby physical actions."""

import pytest

from app.utils.characters.dialogue import (
    has_direct_communication_attribution,
    has_explicit_speech_attribution,
    has_named_human_self_action,
)


@pytest.mark.parametrize(
    ("source", "name"),
    [
        ('Mira said, "The river is rising."', "Mira"),
        ('"The river is rising," said Mira.', "Mira"),
        ("“The river is rising,” whispered Mira.", "Mira"),
        ('"Did you see the river?" asked Rowan.', "Rowan"),
    ],
)
def test_explicit_speech_attribution_accepts_named_speakers(source: str, name: str) -> None:
    assert has_explicit_speech_attribution(source, name)


@pytest.mark.parametrize(
    ("source", "name"),
    [
        ("Mira crossed the river. Mira waved at the boat.", "Mira"),
        ('I said Mira was late. "Wait for her," I added.', "Mira"),
        ("Door opened. The Door closed again.", "Door"),
        ("Mira said the river was high.", "Rowan"),
        ("Mira said nothing and closed the door.", "Mira"),
        ("Mira said the river was high.", "Mira"),
        ("The memo read, \"Mira said, 'Wait.'\" Mira opened the door.", "Mira"),
        ("", "Mira"),
        ("Mira spoke.", ""),
    ],
)
def test_explicit_speech_attribution_rejects_actions_objects_and_missing_names(
    source: str, name: str
) -> None:
    assert not has_explicit_speech_attribution(source, name)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Paz warned Sera that the gate was sealed.", True),
        ("Paz texted Sera before dawn.", True),
        ("Paz opened the gate before dawn.", False),
        ("Paz said nothing before dawn.", False),
        ('The report said, "Paz warned Sera." Paz opened the gate.', False),
    ],
)
def test_direct_communication_requires_named_action_outside_quotes(
    source: str, expected: bool
) -> None:
    assert has_direct_communication_attribution(source, "Paz") is expected


@pytest.mark.parametrize(
    ("source", "name", "expected"),
    [
        ("Mara raised her hand.", "Mara", True),
        ("Mara wiped their face.", "Mara", True),
        ("Paris opened its museum.", "Paris", False),
        ("Mara opened the gate.", "Mara", False),
        ('The sign read "Mara raised her hand."', "Mara", False),
        ("Mara raised her hand.", "Rowan", False),
    ],
)
def test_named_human_self_action_requires_unquoted_matching_name(
    source: str, name: str, expected: bool
) -> None:
    assert has_named_human_self_action(source, name) is expected
