"""Reconcile displayed character mention counts after chapter replacement."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character, CharacterMention
from app.utils.characters.text import unique_source_mention_spans


def count_character_mention_evidence(
    rows: list[tuple[uuid.UUID, int, dict[str, Any] | None]],
) -> dict[uuid.UUID, int]:
    """Count physical source spans once, with one row per legacy mention as fallback."""
    spans_by_character: dict[tuple[uuid.UUID, int], list[dict[str, int]]] = defaultdict(list)
    legacy_counts: dict[uuid.UUID, int] = defaultdict(int)
    for character_id, chapter_number, evidence in rows:
        source_mentions = evidence.get("source_mentions") if isinstance(evidence, dict) else None
        if not isinstance(source_mentions, list):
            legacy_counts[character_id] += 1
            continue
        for span in source_mentions:
            if (
                isinstance(span, dict)
                and all(
                    isinstance(span.get(key), int) and not isinstance(span[key], bool)
                    for key in ("chunk_index", "start", "end")
                )
                and span["chunk_index"] >= 0
                and span["start"] >= 0
                and span["end"] > span["start"]
            ):
                spans_by_character[(character_id, chapter_number)].append(span)
    counts = dict(legacy_counts)
    for (character_id, _chapter_number), spans in spans_by_character.items():
        counts[character_id] = counts.get(character_id, 0) + len(unique_source_mention_spans(spans))
    return counts


async def reconcile_character_mention_counts(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    previous_character_ids: set[uuid.UUID],
    characters: list[Character],
) -> None:
    """Replace retry-inflated counters with the surviving mention audit trail."""
    current_ids = set(
        (
            await db.scalars(
                select(CharacterMention.matched_character_id).where(
                    CharacterMention.book_id == book_id,
                    CharacterMention.chapter_number == chapter_number,
                    CharacterMention.matched_character_id.is_not(None),
                )
            )
        ).all()
    )
    affected_ids = previous_character_ids | current_ids
    if not affected_ids:
        return
    rows = (
        await db.execute(
            select(
                CharacterMention.matched_character_id,
                CharacterMention.chapter_number,
                CharacterMention.evidence,
            ).where(
                CharacterMention.book_id == book_id,
                CharacterMention.matched_character_id.in_(affected_ids),
            )
        )
    ).all()
    counts = count_character_mention_evidence(list(rows))
    legacy_character_ids = {
        character_id
        for character_id, _source_chapter, evidence in rows
        if not isinstance(evidence, dict) or not isinstance(evidence.get("source_mentions"), list)
    }
    for character in characters:
        if character.id in affected_ids:
            character.mention_count = counts.get(character.id, 0)
            character.analysis_metadata = {
                **(character.analysis_metadata or {}),
                "mention_count_basis": (
                    "mixed_legacy_records"
                    if character.id in legacy_character_ids
                    else "source_positions"
                ),
            }
