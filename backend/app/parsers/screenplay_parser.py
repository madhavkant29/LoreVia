"""
Screenplay parser for Fountain format and standard screenplay formats.
Supports scene headings, action lines, character names, dialogue, parentheticals,
transitions, and shots.
"""
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.models.book import Scene, Dialogue


# Scene heading patterns
SCENE_HEADING_PREFIXES = [
    "INT", "EXT", "EST", "INT./EXT", "INT/EXT", "I/E", "INT./", "EXT./"
]

SCENE_HEADING_REGEX = re.compile(
    r"^(?:(?:\.|!)?)(?:(" + "|".join(SCENE_HEADING_PREFIXES) + r")\.)\s*(.+?)\s*-\s*(.+?)(?:\s*#\s*([^#\s]+)\s*#)?\s*$",
    re.IGNORECASE
)

# Character name pattern (all uppercase, at least one letter)
CHARACTER_REGEX = re.compile(r"^([A-Z][A-Z0-9\s]*[A-Z])(?:\s*\(([^)]+)\))?$")

# Parenthetical pattern
PARENTHETICAL_REGEX = re.compile(r"^\(([^)]+)\)$")

# Transition pattern (ends with TO:)
TRANSITION_REGEX = re.compile(r"^(.+?)\s*TO:\s*$", re.IGNORECASE)

# Shot pattern (camera angles)
SHOT_PATTERNS = [
    "CLOSE ON", "CLOSEUP", "CLOSE UP", "CU", "ECU", "EXTREME CLOSEUP",
    "MEDIUM SHOT", "MS", "MEDIUM", "LONG SHOT", "LS", "WIDE SHOT", "WS",
    "ESTABLISHING", "POV", "POINT OF VIEW", "OVERHEAD SHOT", "BIRD'S EYE VIEW",
    "LOW ANGLE", "HIGH ANGLE", "DUTCH ANGLE", "CANTED ANGLE",
    "PAN", "TILT", "DOLLY", "CRANE", "STEDDICAM", "HANDHELD", "ZOOM"
]


class ScreenplayElement:
    """Base class for screenplay elements."""
    def __init__(self, text: str, line_number: int):
        self.text = text.strip()
        self.line_number = line_number


class SceneHeading(ScreenplayElement):
    """Scene heading element (INT./EXT. LOCATION - TIME)."""
    def __init__(self, text: str, line_number: int, interior: bool, exterior: bool, 
                 location: str, time_of_day: str, scene_number: Optional[str] = None):
        super().__init__(text, line_number)
        self.interior = interior
        self.exterior = exterior
        self.location = location.strip()
        self.time_of_day = time_of_day.strip()
        self.scene_number = scene_number.strip() if scene_number else None


class Action(ScreenplayElement):
    """Action/description element."""
    pass


class Character(ScreenplayElement):
    """Character name element."""
    def __init__(self, text: str, line_number: int, name: str, extension: Optional[str] = None):
        super().__init__(text, line_number)
        self.name = name.strip()
        self.extension = extension.strip() if extension else None


class Dialogue(ScreenplayElement):
    """Dialogue element."""
    pass


class Parenthetical(ScreenplayElement):
    """Parenthetical element."""
    pass


class Transition(ScreenplayElement):
    """Transition element."""
    pass


class Shot(ScreenplayElement):
    """Shot element."""
    pass


def parse_scene_heading(line: str, line_number: int) -> Optional[SceneHeading]:
    """Parse a scene heading line."""
    # Standard format: INT. LOCATION - DAY
    match = SCENE_HEADING_REGEX.match(line.strip())
    if match:
        prefix, location, time_of_day, scene_num = match.groups()
        interior = prefix.upper().startswith("INT")
        exterior = prefix.upper().startswith("EXT") or prefix.upper() in ["EST", "I/E"]
        return SceneHeading(
            line, line_number, interior, exterior, 
            location, time_of_day, scene_num
        )
    
    # Forced scene heading with period
    if line.startswith('.') and len(line) > 1:
        content = line[1:].strip()
        return SceneHeading(
            line, line_number, False, True, content, "UNKNOWN"
        )
    
    return None


def parse_character(line: str, line_number: int) -> Optional[Character]:
    """Parse a character name line."""
    # Forced character with @ symbol
    if line.startswith('@') and len(line) > 1:
        name = line[1:].strip()
        return Character(line, line_number, name)
    
    # Standard uppercase character
    match = CHARACTER_REGEX.match(line.strip())
    if match:
        name, extension = match.groups()
        return Character(line, line_number, name, extension)
    
    return None


def parse_parenthetical(line: str, line_number: int) -> Optional[Parenthetical]:
    """Parse a parenthetical line."""
    match = PARENTHETICAL_REGEX.match(line.strip())
    if match:
        content = match.group(1)
        return Parenthetical(line, line_number, content)
    return None


def parse_transition(line: str, line_number: int) -> Optional[Transition]:
    """Parse a transition line."""
    # Forced transition with > symbol
    if line.startswith('>') and len(line) > 1:
        content = line[1:].strip()
        return Transition(line, line_number, content)
    
    # Standard transition ending in TO:
    match = TRANSITION_REGEX.match(line.strip())
    if match:
        content = match.group(1)
        return Transition(line, line_number, content)
    
    return None


def parse_shot(line: str, line_number: int) -> Optional[Shot]:
    """Parse a shot/camera angle line."""
    upper_line = line.strip().upper()
    for pattern in SHOT_PATTERNS:
        if upper_line.startswith(pattern):
            return Shot(line, line_number)
    return None


def parse_screenplay(text: str) -> List[SceneHeading]:
    """
    Parse screenplay text and return a list of scenes with their elements.
    
    Args:
        text: Raw screenplay text
        
    Returns:
        List of parsed scenes
    """
    lines = text.split('\n')
    scenes: List[SceneHeading] = []
    current_scene: Optional[SceneHeading] = None
    scene_elements: List[Any] = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        line_number = i + 1
        
        if not line:
            i += 1
            continue
        
        # Check for scene heading
        scene_heading = parse_scene_heading(line, line_number)
        if scene_heading:
            # Save previous scene if exists
            if current_scene:
                current_scene.elements = scene_elements.copy()
                scenes.append(current_scene)
            
            current_scene = scene_heading
            scene_elements = []
            i += 1
            continue
        
        # Check for character
        character = parse_character(line, line_number)
        if character and current_scene:
            scene_elements.append(character)
            i += 1
            continue
        
        # Check for parenthetical
        parenthetical = parse_parenthetical(line, line_number)
        if parenthetical and current_scene:
            scene_elements.append(parenthetical)
            i += 1
            continue
        
        # Check for transition
        transition = parse_transition(line, line_number)
        if transition and current_scene:
            scene_elements.append(transition)
            i += 1
            continue
        
        # Check for shot
        shot = parse_shot(line, line_number)
        if shot and current_scene:
            scene_elements.append(shot)
            i += 1
            continue
        
        # Default to action
        if current_scene:
            action = Action(line, line_number)
            scene_elements.append(action)
        
        i += 1
    
    # Add last scene
    if current_scene:
        current_scene.elements = scene_elements
        scenes.append(current_scene)
    
    return scenes


def extract_dialogue_from_scene(scene: SceneHeading) -> List[Dict[str, Any]]:
    """Extract dialogue lines from a scene's elements."""
    dialogue_lines = []
    current_character = None
    line_number = 0
    
    for element in getattr(scene, 'elements', []):
        if isinstance(element, Character):
            current_character = element
            line_number = 0
        elif isinstance(element, Dialogue) and current_character:
            dialogue_lines.append({
                'character_name': current_character.name,
                'character_extension': current_character.extension,
                'dialogue_text': element.text,
                'line_number': line_number
            })
            line_number += 1
        elif isinstance(element, Parenthetical) and dialogue_lines:
            # Add parenthetical to last dialogue line
            dialogue_lines[-1]['parenthetical'] = element.text
    
    return dialogue_lines


def create_scene_models(scenes: List[SceneHeading], book_id: uuid.UUID) -> List[Scene]:
    """Convert parsed scenes to database models."""
    scene_models = []
    
    for i, scene in enumerate(scenes, 1):
        dialogue = extract_dialogue_from_scene(scene)
        
        # Calculate word count
        action_text = ' '.join([
            elem.text for elem in getattr(scene, 'elements', [])
            if isinstance(elem, Action)
        ])
        word_count = len(action_text.split())
        
        scene_model = Scene(
            book_id=book_id,
            number=i,
            heading=scene.text,
            location=scene.location,
            time_of_day=scene.time_of_day,
            interior=scene.interior,
            exterior=scene.exterior,
            scene_number=scene.scene_number,
            description=action_text or None,
            word_count=word_count
        )
        
        # Add dialogue models
        dialogue_models = []
        for j, line in enumerate(dialogue):
            dialogue_word_count = len(line['dialogue_text'].split())
            dialogue_model = Dialogue(
                scene_id=scene_model.id,  # Will be set after commit
                character_name=line['character_name'],
                character_extension=line.get('character_extension'),
                dialogue_text=line['dialogue_text'],
                parenthetical=line.get('parenthetical'),
                line_number=line['line_number'],
                word_count=dialogue_word_count
            )
            dialogue_models.append(dialogue_model)
        
        scene_model.dialogue = dialogue_models
        scene_models.append(scene_model)
    
    return scene_models


def parse_fountain_screenplay(text: str) -> List[SceneHeading]:
    """
    Parse Fountain format screenplay text.
    Fountain is a plain text screenplay format that looks like a screenplay.
    """
    # For now, use the standard parser - Fountain is designed to look like
    # standard screenplay format, so our parser should handle most cases
    return parse_screenplay(text)


def analyze_screenplay_stats(scenes: List[SceneHeading]) -> Dict[str, Any]:
    """Analyze screenplay statistics."""
    stats = {
        'total_scenes': len(scenes),
        'total_dialogue_lines': 0,
        'total_words': 0,
        'character_dialogue_counts': {},
        'scene_types': {'INT': 0, 'EXT': 0, 'OTHER': 0}
    }
    
    for scene in scenes:
        # Scene type
        if scene.interior:
            stats['scene_types']['INT'] += 1
        elif scene.exterior:
            stats['scene_types']['EXT'] += 1
        else:
            stats['scene_types']['OTHER'] += 1
        
        # Dialogue analysis
        dialogue = extract_dialogue_from_scene(scene)
        stats['total_dialogue_lines'] += len(dialogue)
        
        for line in dialogue:
            char_name = line['character_name']
            if char_name not in stats['character_dialogue_counts']:
                stats['character_dialogue_counts'][char_name] = 0
            stats['character_dialogue_counts'][char_name] += 1
        
        # Word count
        action_text = ' '.join([
            elem.text for elem in getattr(scene, 'elements', [])
            if isinstance(elem, Action)
        ])
        stats['total_words'] += len(action_text.split())
    
    # Estimate pages (1 page ≈ 1 minute)
    stats['estimated_pages'] = max(1, round(stats['total_words'] / 250))
    
    return stats
