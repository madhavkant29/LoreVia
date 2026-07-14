from __future__ import annotations

import logging
import time
import uuid

from app.models.character import Character
from app.utils.characters.manual import find_earliest_character_mention_chapters
from app.utils.ingestion_utils import elapsed_ms

log = logging.getLogger("lorevia.extraction")


async def backfill_pending_first_chapter_mentions(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    pending_first_chapter_candidates: dict[uuid.UUID, list[str]],
    pending_first_chapter_updates: dict[uuid.UUID, Character],
) -> int:
    if not pending_first_chapter_candidates:
        return 0

    earliest_started = time.perf_counter()
    earliest_mentions = await find_earliest_character_mention_chapters(
        db,
        book_id=book_id,
        candidates_by_key=pending_first_chapter_candidates,
        upto_chapter=chapter_number,
    )
    for character_id, earliest_chapter in earliest_mentions.items():
        char = pending_first_chapter_updates.get(character_id)
        if char is None:
            continue
        if earliest_chapter < int(char.first_chapter or chapter_number):
            char.first_chapter = earliest_chapter
        current_last_seen = int(char.last_seen_chapter or char.first_chapter or earliest_chapter)
        char.last_seen_chapter = max(current_last_seen, char.first_chapter or earliest_chapter)

    log.info(
        "ingestion_timing stage=first_chapter_backfill book_id=%s chapter=%s elapsed_ms=%s characters=%s",
        book_id,
        chapter_number,
        elapsed_ms(earliest_started),
        len(pending_first_chapter_candidates),
    )
    return len(earliest_mentions)
