"""
Backfill character classification scores for existing characters.

This script recomputes character_type, character_type_score, and subtype_scores
for all existing characters in the database using the new scoring system.

Run with: python scripts/backfill_character_classification.py
"""
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        "-c",
        """
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_engine
from app.models.character import Character
from app.utils.character_utils import update_character_classification

async def backfill():
    async with AsyncSession(async_engine) as db:
        result = await db.execute(select(Character))
        characters = result.scalars().all()
        print(f"Found {len(characters)} characters to backfill...")
        updated_count = 0
        for char in characters:
            try:
                update_character_classification(char)
                updated_count += 1
                if updated_count % 100 == 0:
                    print(f"Processed {updated_count}/{len(characters)} characters...")
            except Exception as e:
                print(f"Error processing character {char.name}: {e}")
                continue
        await db.commit()
        print(f"Successfully backfilled {updated_count} characters.")

asyncio.run(backfill())
"""
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
