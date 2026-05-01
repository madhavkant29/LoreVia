"""
Backfill character classification scores for existing characters.

This script recomputes character_type, character_type_score, and subtype_scores
for all existing characters in the database using the new scoring system.

Run with: python scripts/backfill_character_classification.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.character import Character
from app.utils.character_utils import update_character_classification
from app.utils.logging import get_logger

log = get_logger("lorevia.backfill.character_classification")


async def backfill() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Character))
        characters = result.scalars().all()
        log.info("backfill_started", extra={"character_count": len(characters)})

        updated_count = 0
        for character in characters:
            try:
                update_character_classification(character)
                updated_count += 1
                if updated_count % 100 == 0:
                    log.info(
                        "backfill_progress",
                        extra={"processed": updated_count, "total": len(characters)},
                    )
            except Exception:
                log.exception(
                    "backfill_character_failed",
                    extra={"character_id": str(character.id), "character_name": character.name},
                )
                continue

        await db.commit()
        log.info("backfill_completed", extra={"updated_count": updated_count})


if __name__ == "__main__":
    asyncio.run(backfill())
