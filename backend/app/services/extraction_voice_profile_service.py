from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.character import Character, CharacterVoiceProfile
from app.models.book import Book
from app.utils.intelligence_utils import (
    compute_voice_metrics,
    extract_dialogue_samples_by_character,
    merge_voice_profile_metrics,
)

VOICE_PROFILE_METRIC_FIELDS = (
    "sample_dialogue_count",
    "sample_word_count",
    "avg_sentence_length",
    "avg_word_length_x100",
    "contraction_rate_x1000",
    "question_rate_x1000",
    "exclamation_rate_x1000",
    "ellipsis_rate_x1000",
    "dash_rate_x1000",
    "uppercase_rate_x1000",
    "formality_score_x1000",
    "lexical_complexity_x1000",
    "emotional_intensity_x1000",
)


def _voice_profile_metrics_snapshot(profile: CharacterVoiceProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        **{field: getattr(profile, field, 0) or 0 for field in VOICE_PROFILE_METRIC_FIELDS},
        "dominant_markers": profile.dominant_markers or {},
        "signature_phrases": profile.signature_phrases or [],
    }


async def refresh_chapter_voice_profiles(
    db,
    *,
    book: Book,
    chapter_text: str,
    existing_characters: list[Character],
) -> int:
    dialogue_samples = extract_dialogue_samples_by_character(
        chapter_text,
        [
            {"id": str(char.id), "name": char.name, "aliases": char.aliases or []}
            for char in existing_characters
            if char.name
        ],
    )
    if not dialogue_samples:
        return 0

    existing_voice_profiles = (
        (
            await db.execute(
                select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    profiles_by_character_id = {
        profile.character_id: profile for profile in existing_voice_profiles
    }

    refreshed = 0
    for char in existing_characters:
        samples = dialogue_samples.get(char.name)
        if not samples:
            continue
        metrics = compute_voice_metrics(samples)
        if int(metrics.get("sample_dialogue_count") or 0) <= 0:
            continue

        current_profile = profiles_by_character_id.get(char.id)
        merged_metrics = merge_voice_profile_metrics(
            _voice_profile_metrics_snapshot(current_profile),
            metrics,
        )
        if current_profile is None:
            db.add(
                CharacterVoiceProfile(
                    book_id=book.id,
                    character_id=char.id,
                    **merged_metrics,
                )
            )
        else:
            for key, value in merged_metrics.items():
                setattr(current_profile, key, value)
        refreshed += 1

    return refreshed
