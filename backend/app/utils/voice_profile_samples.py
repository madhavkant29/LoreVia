"""Source-attributed, non-overlapping dialogue for character voice metrics."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.utils.characters.narrator import detect_explicit_first_person_narrator
from app.utils.voice_review_utils import (
    attributed_voice_samples,
    disambiguate_voice_aliases,
    voice_independent_source_texts,
)


def explicit_dialogue_by_character(
    text: str,
    characters: Sequence[dict[str, Any]],
    *,
    chapter_number: int = 0,
) -> dict[str, list[str]]:
    """Measure only directly tagged speech; uncertain pronouns cannot establish a baseline."""
    cast = disambiguate_voice_aliases(
        [character for character in characters if str(character.get("name") or "").strip()]
    )
    narrator = detect_explicit_first_person_narrator(text, cast)
    dialogue: dict[str, list[str]] = {}
    for character in cast:
        name = str(character["name"])
        samples = attributed_voice_samples(
            text,
            character_name=name,
            aliases=character["aliases"],
            chapter_number=chapter_number,
            include_offsets=True,
            first_person_speaker=(narrator is character),
        )
        explicit = [
            sample
            for sample in samples
            if sample.get("attribution_confidence", "explicit") == "explicit"
        ]
        if explicit:
            dialogue[name] = voice_independent_source_texts(explicit)
    return dialogue
