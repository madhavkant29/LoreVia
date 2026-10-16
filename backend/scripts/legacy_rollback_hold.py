"""Fail-closed hold for legacy processing before a code rollback.

A code rollback can restore a revision that predates the deployment transition
gate. Without this hold, held pre-cutoff work (pending executions, cancelled
outbox rows, frozen projects) could be picked up again by the older code and
spend provider tokens, or be restarted by user retry actions in the older UI.

This script makes the legacy state fail-closed at the data level so ANY older
revision respects it:

  - pre-cutoff incomplete or frozen books are hidden from owned-book lookups
    (older retry/continue endpoints resolve books through those filters),
  - every non-terminal execution and its dispatch outbox rows for those books
    are cancelled,
  - the original hidden state is remembered so ``--release`` can restore it
    exactly after the rollback is resolved.

Dry-run is the default. Nothing is modified unless ``--execute`` and
``--confirm YES_I_UNDERSTAND`` are both provided.

Recommended rollback procedure (see DEPLOY_AND_FREEZE.md section 8):
    python scripts/legacy_rollback_hold.py                       # dry run
    python scripts/legacy_rollback_hold.py --execute --confirm YES_I_UNDERSTAND
    # ... roll back the code while the application stack is stopped ...
    # after the rollback is resolved and the gated revision is deployed again:
    python scripts/legacy_rollback_hold.py --release --execute --confirm YES_I_UNDERSTAND
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import AsyncSessionLocal
from app.models.book import Book
from app.models.operations import TaskDispatchOutbox, TaskExecution
from app.models.user import User
from app.services.book_freeze_service import (
    is_book_frozen,
    load_persisted_freeze_cutoff,
)

CONFIRMATION_PHRASE = "YES_I_UNDERSTAND"
HOLD_MARKER_KEY = "rollback_hold"
NON_TERMINAL_STATUSES = ("pending_dispatch", "queued", "running", "paused")
OUTBOX_HOLD_STATUSES = ("pending", "publishing", "publish_failed")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed data hold for legacy processing before a code rollback "
            "(dry-run by default)."
        ),
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Release a previous hold: restore hidden state and remove the marker.",
    )
    parser.add_argument("--execute", action="store_true", help="Apply changes.")
    parser.add_argument("--confirm", help=f"Required with --execute: {CONFIRMATION_PHRASE}")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    parser.add_argument(
        "--book-id",
        action="append",
        default=[],
        help="Repeatable. Restrict the operation to these book UUIDs.",
    )
    return parser.parse_args(argv)


def _target_book_ids(args: argparse.Namespace) -> list[uuid.UUID]:
    try:
        return [uuid.UUID(value) for value in args.book_id]
    except ValueError as exc:
        raise SystemExit(f"Invalid --book-id value: {exc}") from exc


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "(none)"
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


async def _load_legacy_books(
    db, cutoff: datetime | None, target_ids: list[uuid.UUID]
) -> list[Book]:
    statement = select(Book).order_by(Book.created_at.asc())
    if target_ids:
        statement = statement.where(Book.id.in_(target_ids))
    books = list((await db.execute(statement)).scalars().all())
    selected: list[Book] = []
    for book in books:
        if is_book_frozen(book):
            selected.append(book)
            continue
        if cutoff is None or book.created_at is None:
            continue
        created_at = (
            book.created_at if book.created_at.tzinfo else book.created_at.replace(tzinfo=UTC)
        )
        if created_at < cutoff and str(book.status or "") != "ready":
            selected.append(book)
    return selected


def _hold_marker(book: Book) -> dict[str, Any] | None:
    workspace = book.writer_workspace if isinstance(book.writer_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace, dict) else {}
    marker = processing.get(HOLD_MARKER_KEY) if isinstance(processing, dict) else None
    return marker if isinstance(marker, dict) else None


async def _hold_book(db, book: Book, now: datetime) -> dict[str, Any]:
    """Cancel held work, hide the book, and record the original hidden state."""
    previous_hidden_at = getattr(book, "hidden_at", None)
    executions = (
        (
            await db.execute(
                select(TaskExecution).where(
                    TaskExecution.book_id == book.id,
                    TaskExecution.status.in_(NON_TERMINAL_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    execution_ids = [execution.id for execution in executions]
    for execution in executions:
        execution.status = "dismissed"
        execution.error_category = "rollback_hold"
        execution.error_detail = "Held before a code rollback; no provider calls are allowed."
        execution.completed_at = now
        execution.locked_until = None

    outbox_cancelled = 0
    if execution_ids:
        result = await db.execute(
            update(TaskDispatchOutbox)
            .where(
                TaskDispatchOutbox.execution_id.in_(execution_ids),
                TaskDispatchOutbox.status.in_(OUTBOX_HOLD_STATUSES),
            )
            .values(status="cancelled", lease_until=None, last_error="rollback_hold")
        )
        outbox_cancelled = int(result.rowcount or 0)

    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = (
        dict(workspace.get("processing")) if isinstance(workspace.get("processing"), dict) else {}
    )
    processing[HOLD_MARKER_KEY] = {
        "held_at": now.isoformat(),
        "reason": "code_rollback_fail_closed",
        "previous_hidden_at": (
            previous_hidden_at.astimezone(UTC).isoformat()
            if isinstance(previous_hidden_at, datetime) and previous_hidden_at.tzinfo
            else (
                previous_hidden_at.isoformat() if isinstance(previous_hidden_at, datetime) else None
            )
        ),
    }
    workspace["processing"] = processing
    book.writer_workspace = workspace
    book.hidden_at = now
    return {
        "executions_held": len(executions),
        "outbox_cancelled": outbox_cancelled,
    }


async def _release_book(db, book: Book, now: datetime) -> dict[str, Any]:
    marker = _hold_marker(book)
    if marker is None:
        return {"released": False}
    previous_hidden_raw = marker.get("previous_hidden_at")
    previous_hidden_at: datetime | None = None
    if isinstance(previous_hidden_raw, str) and previous_hidden_raw.strip():
        try:
            parsed = datetime.fromisoformat(previous_hidden_raw)
            previous_hidden_at = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            previous_hidden_at = None
    book.hidden_at = previous_hidden_at
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = (
        dict(workspace.get("processing")) if isinstance(workspace.get("processing"), dict) else {}
    )
    processing.pop(HOLD_MARKER_KEY, None)
    workspace["processing"] = processing
    book.writer_workspace = workspace
    return {"released": True}


async def run(args: argparse.Namespace) -> int:
    apply_changes = bool(args.execute)
    if apply_changes and args.confirm != CONFIRMATION_PHRASE:
        print(
            f"Refusing to modify records without --confirm {CONFIRMATION_PHRASE}.",
            file=sys.stderr,
        )
        return 2
    target_ids = _target_book_ids(args)
    action = "release" if args.release else "hold"
    results: list[dict[str, Any]] = []
    changed = 0
    skipped = 0

    async with AsyncSessionLocal() as db:
        cutoff = await load_persisted_freeze_cutoff(db)
        if action == "hold" and cutoff is None:
            print(
                "WARNING: no persisted legacy cutoff found; only frozen-marked books will be held.",
                file=sys.stderr,
            )
        books = (
            await _load_and_filter_release_books(db, target_ids)
            if action == "release"
            else await _load_legacy_books(db, cutoff, target_ids)
        )

        now = datetime.now(UTC)
        for book in books:
            user = await db.get(User, book.user_id)
            description: dict[str, Any] = {
                "book_id": str(book.id),
                "user_email": mask_email(user.email if user else None),
                "status": book.status,
                "frozen": is_book_frozen(book),
                "already_held": _hold_marker(book) is not None,
            }
            if action == "release":
                if description["already_held"]:
                    description["action"] = "release"
                    if apply_changes:
                        outcome = await _release_book(db, book, now)
                        description.update(outcome)
                        changed += 1
                else:
                    description["action"] = "skipped_not_held"
                    skipped += 1
                results.append(description)
                continue

            if description["already_held"]:
                description["action"] = "already_held"
                skipped += 1
                results.append(description)
                continue
            description["action"] = "hold"
            if apply_changes:
                outcome = await _hold_book(db, book, now)
                description.update(outcome)
                changed += 1
            results.append(description)
        if apply_changes:
            await db.commit()

    summary = {
        "mode": "execute" if apply_changes else "dry_run",
        "action": action,
        "applied": apply_changes,
        "cutoff": cutoff.astimezone(UTC).isoformat() if cutoff else None,
        "candidates": len(results),
        "changed": changed,
        "skipped": skipped,
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(
            f"mode={summary['mode']} action={summary['action']} "
            f"candidates={summary['candidates']} changed={summary['changed']} "
            f"skipped={summary['skipped']}"
        )
        for item in results:
            print(f"  - {json.dumps(item, default=str)}")
        if not apply_changes:
            print(
                f"\nDry run only. Re-run with --execute --confirm {CONFIRMATION_PHRASE} to apply."
            )
    return 0


async def _load_and_filter_release_books(db, target_ids: list[uuid.UUID]) -> list[Book]:
    statement = select(Book).order_by(Book.created_at.asc())
    if target_ids:
        statement = statement.where(Book.id.in_(target_ids))
    books = list((await db.execute(statement)).scalars().all())
    return [book for book in books if _hold_marker(book) is not None]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
