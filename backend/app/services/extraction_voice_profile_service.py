from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from app.core.storage import download_book
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterVoiceProfile
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.intelligence_utils import (
    compute_voice_metrics,
    merge_voice_profile_metrics,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS
from app.utils.voice_profile_samples import explicit_dialogue_by_character

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

log = logging.getLogger("lorevia.extraction")


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
    chapter_number: int | None = None,
    new_character_ids: set[Any] | None = None,
) -> int:
    cast = [
        {"id": str(char.id), "name": char.name, "aliases": char.aliases or []}
        for char in existing_characters
        if char.name
    ]
    dialogue_samples = explicit_dialogue_by_character(
        chapter_text,
        cast,
        chapter_number=chapter_number or 0,
    )
    late_characters = [
        char
        for char in existing_characters
        if new_character_ids
        and char.id in new_character_ids
        and chapter_number is not None
        and char.first_chapter < chapter_number
    ]
    if late_characters:
        earlier_samples: dict[str, list[str]] = {}
        earlier_chapters = (
            await db.execute(
                select(Chapter.number, Chapter.s3_key)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.number >= min(char.first_chapter for char in late_characters),
                    Chapter.number < chapter_number,
                )
                .order_by(Chapter.number)
            )
        ).all()
        for earlier_number, storage_key in earlier_chapters:
            try:
                raw = await asyncio.to_thread(download_book, storage_key)
                source = str(deserialize_manuscript_content(raw).get("text") or "")
            except STORAGE_IO_EXCEPTIONS:
                log.warning(
                    "voice_profile_earlier_chapter_unavailable book_id=%s chapter=%s",
                    book.id,
                    earlier_number,
                    exc_info=True,
                )
                continue
            earlier_dialogue = explicit_dialogue_by_character(
                source, cast, chapter_number=earlier_number
            )
            for char in late_characters:
                if char.first_chapter <= earlier_number:
                    earlier_samples.setdefault(char.name, []).extend(
                        earlier_dialogue.get(char.name, [])
                    )
        for name, samples in earlier_samples.items():
            dialogue_samples[name] = [*samples, *dialogue_samples.get(name, [])]
    if not dialogue_samples:
        return 0

    existing_voice_profiles = (
        (
            await db.execute(
                select(CharacterVoiceProfile)
                .where(
                    CharacterVoiceProfile.book_id == book.id,
                    CharacterVoiceProfile.character_id.in_(
                        [char.id for char in existing_characters]
                    ),
                )
                .execution_options(include_all_generations=True)
            )
        )
        .scalars()
        .all()
    )
    profiles_by_identity = {
        (profile.character_id, profile.generation_id): profile
        for profile in existing_voice_profiles
    }
    legacy_profiles_by_character_id: dict[Any, list[CharacterVoiceProfile]] = {}
    for profile in existing_voice_profiles:
        if profile.generation_id is not None:
            legacy_profiles_by_character_id.setdefault(profile.character_id, []).append(profile)

    refreshed = 0
    for char in existing_characters:
        samples = dialogue_samples.get(char.name)
        if not samples:
            continue
        metrics = compute_voice_metrics(samples)
        if int(metrics.get("sample_dialogue_count") or 0) <= 0:
            continue

        current_profile = profiles_by_identity.get((char.id, char.generation_id))
        if current_profile is None and char.generation_id is None:
            # A curated/legacy character can retain a profile adopted into an
            # older generation. Keep that single profile rather than creating
            # two visible one-to-one rows during a rebuild.
            legacy_profiles = legacy_profiles_by_character_id.get(char.id, [])
            if len(legacy_profiles) == 1:
                current_profile = legacy_profiles[0]
            elif legacy_profiles:
                log.warning(
                    "character_voice_profile_ambiguous_generation character_id=%s profiles=%s",
                    char.id,
                    len(legacy_profiles),
                )
                continue
        # A newly promoted character's samples include all earlier chapters;
        # replace any partial profile instead of counting the same speech twice.
        merged_metrics = (
            metrics
            if new_character_ids and char.id in new_character_ids
            else merge_voice_profile_metrics(
                _voice_profile_metrics_snapshot(current_profile), metrics
            )
        )
        if current_profile is None:
            db.add(
                CharacterVoiceProfile(
                    book_id=book.id,
                    character_id=char.id,
                    generation_id=char.generation_id,
                    **merged_metrics,
                )
            )
        else:
            current_profile.generation_id = char.generation_id
            for key, value in merged_metrics.items():
                setattr(current_profile, key, value)
        refreshed += 1

    return refreshed
