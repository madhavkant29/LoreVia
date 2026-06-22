"""Backfill source object sizes from configured local storage or R2.

Dry-run is the default. Use ``--apply`` only after explicitly configuring the
target database and storage environment for the intended VPS deployment.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.storage import get_object_size
from app.models.book import Book
from app.models.intelligence import WorldBuildingDocument


async def backfill(*, apply: bool, limit: int) -> dict[str, int]:
    checked = 0
    updated = 0
    missing = 0
    async with AsyncSessionLocal() as db:
        books = (
            (
                await db.execute(
                    select(Book)
                    .where(Book.source_size_bytes.is_(None))
                    .order_by(Book.created_at)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        remaining = max(limit - len(books), 0)
        documents = (
            (
                await db.execute(
                    select(WorldBuildingDocument)
                    .where(WorldBuildingDocument.source_size_bytes.is_(None))
                    .order_by(WorldBuildingDocument.created_at)
                    .limit(remaining)
                )
            )
            .scalars()
            .all()
        )
        for record in [*books, *documents]:
            checked += 1
            try:
                size = await asyncio.to_thread(get_object_size, record.s3_key)
            except (FileNotFoundError, KeyError):
                missing += 1
                continue
            if apply:
                record.source_size_bytes = size
                updated += 1
        if apply:
            await db.commit()
    return {"checked": checked, "updated": updated, "missing": missing}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()
    print(asyncio.run(backfill(apply=args.apply, limit=max(1, args.limit))))


if __name__ == "__main__":
    main()
