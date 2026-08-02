"""Safely report or repair processing books whose chapters are complete.

Dry run:
    python fix_book_status.py --book-id <uuid>

Apply:
    python fix_book_status.py --book-id <uuid> --apply --confirm APPLY_BOOK_STATUS_FIX
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.book import Book, Chapter
from app.utils.notification_utils import collect_book_ready_stats

CONFIRM_TOKEN = "APPLY_BOOK_STATUS_FIX"


@dataclass(frozen=True)
class BookStatusRepairCandidate:
    book_id: uuid.UUID
    title: str
    current_status: str
    processed_chapters: int
    total_chapters: int
    analyzed_chapters: int
    analysis_complete: bool
    recommended_status: str


async def _candidate_for_book(db, book: Book) -> BookStatusRepairCandidate:
    total_chapters = int(
        (
            await db.execute(
                select(func.count()).select_from(Chapter).where(Chapter.book_id == book.id)
            )
        ).scalar_one()
    )
    processed_chapters = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Chapter)
                .where(Chapter.book_id == book.id, Chapter.processed.is_(True))
            )
        ).scalar_one()
    )
    stats = await collect_book_ready_stats(db, book)
    ready = total_chapters > 0 and processed_chapters >= total_chapters and stats.analysis_complete
    return BookStatusRepairCandidate(
        book_id=book.id,
        title=book.title,
        current_status=book.status,
        processed_chapters=processed_chapters,
        total_chapters=total_chapters,
        analyzed_chapters=stats.analyzed_chapter_count,
        analysis_complete=stats.analysis_complete,
        recommended_status="ready" if ready else book.status,
    )


async def build_status_repair_report(
    *,
    book_id: uuid.UUID | None,
    limit: int,
) -> list[BookStatusRepairCandidate]:
    async with AsyncSessionLocal() as db:
        if book_id is not None:
            book = await db.get(Book, book_id)
            books = [book] if book is not None else []
        else:
            books = (
                (
                    await db.execute(
                        select(Book)
                        .where(Book.status == "processing")
                        .order_by(Book.created_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [await _candidate_for_book(db, book) for book in books]


async def apply_status_repair(candidates: list[BookStatusRepairCandidate]) -> int:
    async with AsyncSessionLocal() as db:
        changed = 0
        for candidate in candidates:
            if candidate.recommended_status != "ready":
                continue
            book = await db.get(Book, candidate.book_id, with_for_update=True)
            if book is None or book.status != candidate.current_status:
                continue
            book.status = "ready"
            changed += 1
        await db.commit()
        return changed


def _print_report(candidates: list[BookStatusRepairCandidate], *, apply: bool) -> None:
    print(f"Mode: {'apply' if apply else 'dry-run'}")
    print(f"Candidates: {len(candidates)}")
    for candidate in candidates:
        action = (
            f"{candidate.current_status} -> {candidate.recommended_status}"
            if candidate.current_status != candidate.recommended_status
            else "no change"
        )
        print(f"- {candidate.title} ({candidate.book_id})")
        print(f"  status: {candidate.current_status}")
        print(f"  chapters: {candidate.processed_chapters}/{candidate.total_chapters} processed")
        print(
            f"  analysis: {candidate.analyzed_chapters}/{candidate.total_chapters} "
            f"complete={candidate.analysis_complete}"
        )
        print(f"  recommendation: {action}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", type=uuid.UUID, default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    candidates = await build_status_repair_report(book_id=args.book_id, limit=max(1, args.limit))
    _print_report(candidates, apply=args.apply)

    if not args.apply:
        return 0
    if args.confirm != CONFIRM_TOKEN:
        print(f"Refusing to write without --confirm {CONFIRM_TOKEN}")
        return 2
    changed = await apply_status_repair(candidates)
    print(f"Updated books: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
