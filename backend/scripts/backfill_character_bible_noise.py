"""Run one-time character-bible noise cleanup across books.

Dry-run by default:
    python scripts/backfill_character_bible_noise.py

Apply after explicit confirmation:
    python scripts/backfill_character_bible_noise.py --apply --confirm-apply REPAIR_CHARACTER_BIBLE_BACKFILL
"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import exists, select

from app.core.database import AsyncSessionLocal
from app.models.book import Book
from app.models.character import Character
from app.utils.logging import get_logger
from scripts.repair_character_bible_book import apply_repair_plan, build_repair_plan

log = get_logger("lorevia.repair.character_bible.backfill")
CONFIRM_TOKEN = "REPAIR_CHARACTER_BIBLE_BACKFILL"
BACKFILL_VERSION = 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill noisy character-bible records across books.")
    parser.add_argument("--apply", action="store_true", help="Apply the repair backfill instead of printing a dry run.")
    parser.add_argument("--confirm-apply", type=str, default="", help=f"Required confirmation token for apply mode: {CONFIRM_TOKEN}")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of books to inspect.")
    parser.add_argument("--book-id", type=uuid.UUID, default=None, help="Optional single book override.")
    parser.add_argument("--force", action="store_true", help="Re-run books already marked as backfilled.")
    parser.add_argument("--output-json", type=str, default=None, help="Optional path to write the report JSON.")
    return parser.parse_args()


def _write_output_json(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _backfill_state(book: Book) -> dict[str, Any]:
    workspace = dict(book.writer_workspace or {})
    state = workspace.get("character_noise_backfill")
    return dict(state) if isinstance(state, dict) else {}


def _mark_backfill_state(book: Book, *, status: str, payload: dict[str, Any]) -> None:
    workspace = dict(book.writer_workspace or {})
    workspace["character_noise_backfill"] = {
        "version": BACKFILL_VERSION,
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
        "summary": payload,
    }
    book.writer_workspace = workspace


async def _iter_target_books(*, book_id: uuid.UUID | None, limit: int, force: bool) -> list[Book]:
    async with AsyncSessionLocal() as session:
        stmt = select(Book).where(
            exists(select(Character.id).where(Character.book_id == Book.id))
        ).order_by(Book.created_at.asc())
        if book_id is not None:
            stmt = stmt.where(Book.id == book_id)
        rows = list((await session.execute(stmt)).scalars().all())
        if not force:
            rows = [
                row for row in rows
                if int(_backfill_state(row).get("version") or 0) < BACKFILL_VERSION
            ]
        if limit > 0:
            rows = rows[:limit]
        return rows


async def _run_backfill(*, apply: bool, book_id: uuid.UUID | None, limit: int, force: bool) -> dict[str, Any]:
    books = await _iter_target_books(book_id=book_id, limit=limit, force=force)
    report: dict[str, Any] = {
        "apply": apply,
        "version": BACKFILL_VERSION,
        "books_considered": len(books),
        "books": [],
    }

    for book in books:
        if apply:
            async with AsyncSessionLocal() as session:
                db_book = await session.get(Book, book.id)
                if db_book is None:
                    continue
                result = await apply_repair_plan(
                    db_book.id,
                    allow_merge_safe_pairs=True,
                    allow_demote_obvious_noise=True,
                    db=session,
                )
                _mark_backfill_state(
                    db_book,
                    status="applied",
                    payload={
                        "demoted_character_ids": result.get("demoted_character_ids", []),
                        "merged_pairs": result.get("merged_pairs", []),
                    },
                )
                await session.commit()
                report["books"].append({"book_id": str(db_book.id), "result": result})
        else:
            async with AsyncSessionLocal() as session:
                db_book = await session.get(Book, book.id)
                if db_book is None:
                    continue
                plan = await build_repair_plan(
                    db_book.id,
                    allow_merge_safe_pairs=True,
                    allow_demote_obvious_noise=True,
                    db=session,
                )
                report["books"].append({"book_id": str(db_book.id), "plan": plan.__dict__})
    return report


async def _main() -> None:
    args = _parse_args()
    if args.apply and args.confirm_apply != CONFIRM_TOKEN:
        raise SystemExit(f"Apply mode requires --confirm-apply {CONFIRM_TOKEN}")
    result = await _run_backfill(
        apply=bool(args.apply),
        book_id=args.book_id,
        limit=max(0, int(args.limit or 0)),
        force=bool(args.force),
    )
    _write_output_json(args.output_json, result)
    log.info("character_bible_noise_backfill %s", json.dumps(result, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
