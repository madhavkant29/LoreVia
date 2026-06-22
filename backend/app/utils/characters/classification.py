"""Focused character classification workflows."""

from __future__ import annotations

from app.engine.character.entity_filters import (
    complex_character_score,
    compute_all_subtype_scores,
    gag_character_score,
)
from app.models.character import (
    Character,
)


def compute_character_classification(char: Character) -> tuple[str, int, dict[str, int]]:
    """Compute character type and subtype scores for a character.

    Returns:
        (character_type, character_type_score, subtype_scores)
        character_type: "complex" | "normal" | "gag" | "meme"
        character_type_score: 0-10 score for main type
        subtype_scores: dict of subtype names to scores (only >= 3)
    """
    # Compute main type scores
    gag_score = gag_character_score(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        mention_count=char.mention_count or 0,
        role=char.role,
        growth_events=char.growth_events,
    )

    complex_score = complex_character_score(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        mention_count=char.mention_count or 0,
        role=char.role,
        growth_events=char.growth_events,
        motivations=char.motivations,
        fears=char.fears,
    )

    # Determine main type based on scores
    if gag_score >= 3:
        character_type = "gag" if gag_score > complex_score else "complex"
        character_type_score = max(gag_score, complex_score)
    elif complex_score >= 5:
        character_type = "complex"
        character_type_score = complex_score
    else:
        character_type = "normal"
        character_type_score = complex_score

    # Compute subtype scores
    subtype_scores = compute_all_subtype_scores(
        personality_tags=char.personality_tags,
        archetype=char.archetype,
        arc_summary=char.arc_summary,
        growth_events=char.growth_events,
    )

    return character_type, character_type_score, subtype_scores


def update_character_classification(char: Character) -> None:
    """Update character's classification fields with computed scores."""
    character_type, character_type_score, subtype_scores = compute_character_classification(char)
    char.character_type = character_type
    char.character_type_score = character_type_score
    char.subtype_scores = subtype_scores
