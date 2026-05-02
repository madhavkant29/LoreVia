"""
Screenplay parser for Fountain-like text and screenplay PDFs converted to text.
Supports scene headings, action, character cues, parentheticals, dialogue,
transitions, and shot lines.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from app.models.book import Dialogue, Scene

SCENE_HEADING_PREFIXES = (
    "INT",
    "EXT",
    "EST",
    "INT./EXT",
    "INT/EXT",
    "EXT./INT",
    "EXT/INT",
    "I/E",
)
SCENE_HEADING_REGEX = re.compile(
    r"^(?:[.!])?\s*(INT\.?/EXT\.?|EXT\.?/INT\.?|INT\.?|EXT\.?|EST\.?|I/E)\s*(.+)$",
    re.IGNORECASE,
)
CHARACTER_REGEX = re.compile(r"^(?:@)?([A-Z0-9][A-Z0-9 .'\-]+?)(?:\s*\(([^)]+)\))?$")
PARENTHETICAL_REGEX = re.compile(r"^\(([^)]+)\)$")
TRANSITION_REGEX = re.compile(r"^(?:>?\s*)?([A-Z][A-Z0-9 .'\-]+TO:)$")
COMMON_TIME_MARKERS = {
    "DAY",
    "NIGHT",
    "MORNING",
    "EVENING",
    "LATER",
    "CONTINUOUS",
    "SAME",
    "MOMENTS LATER",
    "SUNRISE",
    "SUNSET",
    "DAWN",
    "DUSK",
}
SHOT_PATTERNS = (
    "CLOSE ON",
    "CLOSEUP",
    "CLOSE UP",
    "CU",
    "ECU",
    "EXTREME CLOSEUP",
    "MEDIUM SHOT",
    "MS",
    "LONG SHOT",
    "LS",
    "WIDE SHOT",
    "WS",
    "ESTABLISHING",
    "POV",
    "POINT OF VIEW",
    "LOW ANGLE",
    "HIGH ANGLE",
    "PAN",
    "TILT",
    "DOLLY",
    "CRANE",
    "ZOOM",
)


class ScreenplayElement:
    def __init__(self, text: str, line_number: int):
        self.text = text.strip()
        self.line_number = line_number


class SceneHeading(ScreenplayElement):
    def __init__(
        self,
        text: str,
        line_number: int,
        interior: bool,
        exterior: bool,
        location: str,
        time_of_day: str | None,
        scene_number: str | None = None,
    ):
        super().__init__(text, line_number)
        self.interior = interior
        self.exterior = exterior
        self.location = location.strip()
        self.time_of_day = (time_of_day or "").strip() or None
        self.scene_number = scene_number.strip() if scene_number else None
        self.elements: list[ScreenplayElement] = []


class Action(ScreenplayElement):
    pass


class Character(ScreenplayElement):
    def __init__(self, text: str, line_number: int, name: str, extension: str | None = None):
        super().__init__(text, line_number)
        self.name = name.strip()
        self.extension = extension.strip() if extension else None


class DialogueElement(ScreenplayElement):
    pass


class Parenthetical(ScreenplayElement):
    def __init__(self, text: str, line_number: int, content: str):
        super().__init__(text, line_number)
        self.content = content.strip()


class Transition(ScreenplayElement):
    def __init__(self, text: str, line_number: int, content: str):
        super().__init__(text, line_number)
        self.content = content.strip()


class Shot(ScreenplayElement):
    def __init__(self, text: str, line_number: int, content: str | None = None):
        super().__init__(text, line_number)
        self.content = content.strip() if content else None


def _split_scene_remainder(remainder: str) -> tuple[str, str | None, str | None]:
    scene_number = None
    remainder = remainder.strip()
    numbered_match = re.search(r"\s+#\s*([^#\s]+)\s*#\s*$", remainder)
    if numbered_match:
        scene_number = numbered_match.group(1).strip()
        remainder = remainder[:numbered_match.start()].strip()

    for separator in (" - ", " – ", " — "):
        if separator in remainder:
            location, time_of_day = remainder.rsplit(separator, 1)
            return location.strip(), time_of_day.strip() or None, scene_number

    upper_remainder = remainder.upper()
    for marker in sorted(COMMON_TIME_MARKERS, key=len, reverse=True):
        if upper_remainder.endswith(f" {marker}"):
            location = remainder[: -len(marker)].strip(" -")
            return location.strip(), marker, scene_number
        if upper_remainder == marker:
            return "Unknown", marker, scene_number

    return remainder.strip(), None, scene_number


def parse_scene_heading(line: str, line_number: int) -> SceneHeading | None:
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith(".") and len(stripped) > 1:
        content = stripped[1:].strip()
        location, time_of_day, scene_number = _split_scene_remainder(content)
        return SceneHeading(stripped, line_number, False, False, location or content, time_of_day, scene_number)

    match = SCENE_HEADING_REGEX.match(stripped)
    if not match:
        return None
    prefix, remainder = match.groups()
    normalized_prefix = prefix.upper().replace(" ", "")
    location, time_of_day, scene_number = _split_scene_remainder(remainder)
    interior = normalized_prefix.startswith("INT") or normalized_prefix == "I/E"
    exterior = normalized_prefix.startswith("EXT") or normalized_prefix.startswith("EST") or normalized_prefix == "I/E"
    return SceneHeading(stripped, line_number, interior, exterior, location or "Unknown", time_of_day, scene_number)


def parse_parenthetical(line: str, line_number: int) -> Parenthetical | None:
    match = PARENTHETICAL_REGEX.match(line.strip())
    if not match:
        return None
    return Parenthetical(line, line_number, match.group(1))


def parse_transition(line: str, line_number: int) -> Transition | None:
    stripped = line.strip()
    if stripped.startswith(">") and len(stripped) > 1:
        return Transition(stripped, line_number, stripped[1:].strip())
    match = TRANSITION_REGEX.match(stripped)
    if not match:
        return None
    return Transition(stripped, line_number, match.group(1))


def parse_shot(line: str, line_number: int) -> Shot | None:
    stripped = line.strip()
    upper_line = stripped.upper()
    for pattern in SHOT_PATTERNS:
        if upper_line.startswith(pattern):
            return Shot(stripped, line_number, stripped)
    return None


def _looks_like_character_cue(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 42:
        return False
    letters = [ch for ch in stripped if ch.isalpha()]
    if not letters:
        return False
    if any(ch.islower() for ch in letters):
        return False
    if parse_scene_heading(stripped, 0) or parse_transition(stripped, 0) or parse_shot(stripped, 0):
        return False
    return True


def parse_character(line: str, line_number: int) -> Character | None:
    stripped = line.strip()
    if not _looks_like_character_cue(stripped):
        return None
    match = CHARACTER_REGEX.match(stripped)
    if not match:
        return None
    name, extension = match.groups()
    return Character(stripped, line_number, name, extension)


def _build_fallback_scene(first_line_number: int) -> SceneHeading:
    return SceneHeading("Scene 1", first_line_number, False, False, "Unknown", None)


def parse_screenplay(text: str) -> list[SceneHeading]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    scenes: list[SceneHeading] = []
    current_scene: SceneHeading | None = None
    scene_elements: list[ScreenplayElement] = []
    i = 0

    while i < len(lines):
        raw_line = lines[i].rstrip()
        stripped = raw_line.strip()
        line_number = i + 1

        if not stripped:
            i += 1
            continue

        scene_heading = parse_scene_heading(stripped, line_number)
        if scene_heading:
            if current_scene is not None:
                current_scene.elements = scene_elements.copy()
                scenes.append(current_scene)
            current_scene = scene_heading
            scene_elements = []
            i += 1
            continue

        if current_scene is None:
            current_scene = _build_fallback_scene(line_number)

        character = parse_character(stripped, line_number)
        if character:
            scene_elements.append(character)
            i += 1
            pending_parenthetical: Parenthetical | None = None
            while i < len(lines):
                dialogue_line = lines[i].rstrip()
                dialogue_stripped = dialogue_line.strip()
                dialogue_line_number = i + 1
                if not dialogue_stripped:
                    i += 1
                    break
                if parse_scene_heading(dialogue_stripped, dialogue_line_number) or parse_transition(dialogue_stripped, dialogue_line_number):
                    break
                next_character = parse_character(dialogue_stripped, dialogue_line_number)
                if next_character and pending_parenthetical is None:
                    break
                parenthetical = parse_parenthetical(dialogue_stripped, dialogue_line_number)
                if parenthetical:
                    pending_parenthetical = parenthetical
                    scene_elements.append(parenthetical)
                    i += 1
                    continue

                dialogue_buffer: list[str] = []
                while i < len(lines):
                    next_line = lines[i].rstrip()
                    next_stripped = next_line.strip()
                    next_line_number = i + 1
                    if not next_stripped:
                        i += 1
                        break
                    if parse_scene_heading(next_stripped, next_line_number) or parse_transition(next_stripped, next_line_number):
                        break
                    next_character = parse_character(next_stripped, next_line_number)
                    if next_character and dialogue_buffer:
                        break
                    if parse_parenthetical(next_stripped, next_line_number) and dialogue_buffer:
                        break
                    dialogue_buffer.append(next_stripped)
                    i += 1
                if dialogue_buffer:
                    scene_elements.append(DialogueElement("\n".join(dialogue_buffer), dialogue_line_number))
                    pending_parenthetical = None
                    continue
                break
            continue

        parenthetical = parse_parenthetical(stripped, line_number)
        if parenthetical:
            scene_elements.append(parenthetical)
            i += 1
            continue

        transition = parse_transition(stripped, line_number)
        if transition:
            scene_elements.append(transition)
            i += 1
            continue

        shot = parse_shot(stripped, line_number)
        if shot:
            scene_elements.append(shot)
            i += 1
            continue

        scene_elements.append(Action(stripped, line_number))
        i += 1

    if current_scene is not None:
        current_scene.elements = scene_elements
        scenes.append(current_scene)

    return scenes


def extract_dialogue_from_scene(scene: SceneHeading) -> list[dict[str, Any]]:
    dialogue_lines: list[dict[str, Any]] = []
    current_character: Character | None = None
    pending_parenthetical: Parenthetical | None = None
    line_number = 0

    for element in getattr(scene, "elements", []):
        if isinstance(element, Character):
            current_character = element
            pending_parenthetical = None
            continue
        if isinstance(element, Parenthetical):
            pending_parenthetical = element
            continue
        if isinstance(element, DialogueElement) and current_character is not None:
            dialogue_lines.append(
                {
                    "character_name": current_character.name,
                    "character_extension": current_character.extension,
                    "dialogue_text": element.text,
                    "parenthetical": pending_parenthetical.content if pending_parenthetical else None,
                    "line_number": line_number,
                }
            )
            line_number += 1
            pending_parenthetical = None

    return dialogue_lines


def create_scene_models(scenes: list[SceneHeading], book_id: uuid.UUID) -> list[Scene]:
    scene_models: list[Scene] = []

    for index, scene in enumerate(scenes, start=1):
        action_text = "\n".join(
            element.text for element in getattr(scene, "elements", []) if isinstance(element, Action) and element.text
        ).strip()
        dialogue = extract_dialogue_from_scene(scene)
        dialogue_word_count = sum(len(str(item.get("dialogue_text") or "").split()) for item in dialogue)
        scene_model = Scene(
            book_id=book_id,
            number=index,
            heading=scene.text or f"Scene {index}",
            location=scene.location,
            time_of_day=scene.time_of_day,
            interior=scene.interior,
            exterior=scene.exterior,
            scene_number=scene.scene_number,
            description=action_text or None,
            word_count=(len(action_text.split()) + dialogue_word_count) or None,
        )

        dialogue_models: list[Dialogue] = []
        for line in dialogue:
            dialogue_text = str(line.get("dialogue_text") or "").strip()
            if not dialogue_text:
                continue
            dialogue_models.append(
                Dialogue(
                    scene_id=scene_model.id,
                    character_name=str(line.get("character_name") or "Unknown").strip(),
                    character_extension=str(line.get("character_extension") or "").strip() or None,
                    dialogue_text=dialogue_text,
                    parenthetical=str(line.get("parenthetical") or "").strip() or None,
                    line_number=int(line.get("line_number") or 0),
                    word_count=len(dialogue_text.split()),
                )
            )

        scene_model.dialogue = dialogue_models
        scene_models.append(scene_model)

    return scene_models


def parse_fountain_screenplay(text: str) -> list[SceneHeading]:
    return parse_screenplay(text)


def analyze_screenplay_stats(scenes: list[SceneHeading]) -> dict[str, Any]:
    stats = {
        "total_scenes": len(scenes),
        "total_dialogue_lines": 0,
        "total_words": 0,
        "character_dialogue_counts": {},
        "scene_types": {"INT": 0, "EXT": 0, "OTHER": 0},
    }

    for scene in scenes:
        if scene.interior:
            stats["scene_types"]["INT"] += 1
        elif scene.exterior:
            stats["scene_types"]["EXT"] += 1
        else:
            stats["scene_types"]["OTHER"] += 1

        dialogue = extract_dialogue_from_scene(scene)
        stats["total_dialogue_lines"] += len(dialogue)
        for line in dialogue:
            name = str(line.get("character_name") or "Unknown")
            stats["character_dialogue_counts"][name] = stats["character_dialogue_counts"].get(name, 0) + 1
            stats["total_words"] += len(str(line.get("dialogue_text") or "").split())

        action_words = sum(
            len(element.text.split()) for element in getattr(scene, "elements", []) if isinstance(element, Action)
        )
        stats["total_words"] += action_words

    stats["estimated_pages"] = max(1, round(stats["total_words"] / 250)) if stats["total_words"] else 1
    return stats
