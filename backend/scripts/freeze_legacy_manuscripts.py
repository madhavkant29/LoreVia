"""One-time global freeze of legacy incomplete manuscript processing.

Freezes every book that was created before a fixed, persisted cutoff and is
still incomplete (pending, processing, failed, or error). Nothing is deleted,
resumed, retried, re-analyzed, or re-uploaded. New manuscripts created after
the cutoff are never touched by this script.

Dry-run is the default. Nothing is modified unless ``--execute`` and
``--confirm YES_I_UNDERSTAND`` are both provided.

Recommended procedure (see DEPLOY_AND_FREEZE.md):
    python scripts/freeze_legacy_manuscripts.py                # dry run, review output
    python scripts/freeze_legacy_manuscripts.py --execute --confirm YES_I_UNDERSTAND

Optional deploy-time cutoff recording (writes only the persisted marker, never
touches a book), if you want the cutoff to equal the deployment moment exactly:
    python scripts/freeze_legacy_manuscripts.py --record-cutoff --execute --confirm YES_I_UNDERSTAND

Release a single project later (targeted only; never a global unfreeze):
    python scripts/freeze_legacy_manuscripts.py --unfreeze --book-id <uuid> --execute --confirm YES_I_UNDERSTAND
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

from sqlalchemy import func, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import AsyncSessionLocal
from app.models.book import Book, Chapter
from app.models.operations import TaskExecution
from app.models.user import User
from app.services.book_freeze_service import (
    FREEZABLE_BOOK_STATUSES,
    NON_TERMINAL_EXECUTION_STATUSES,
    freeze_book_processing,
    is_book_frozen,
    load_persisted_freeze_cutoff,
    parse_freeze_cutoff,
    record_freeze_cutoff,
    unfreeze_book_processing,
)
from app.utils.ingestion_utils import get_processing_started_at

CONFIRMATION_PHRASE = "YES_I_UNDERSTAND"
CUTOFF_FORMAT_HELP = "ISO-8601 timestamp, e.g. 2026-10-15T00:00:00Z"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-time global freeze of legacy incomplete manuscript processing "
            "(dry-run by default)."
        ),
    )
    parser.add_argument(
        "--cutoff",
        help=(
            "Fixed legacy cutoff. Books created before it may be frozen; books "
            f"created after it never are. {CUTOFF_FORMAT_HELP}. Defaults to the "
            "persisted cutoff, or to the current time on first execution."
        ),
    )
    parser.add_argument(
        "--book-id",
        action="append",
        default=[],
        help="Repeatable. Restrict the operation to these book UUIDs.",
    )
    parser.add_argument(
        "--record-cutoff",
        action="store_true",
        help="Only persist the cutoff marker (write-once); never touches a book.",
    )
    parser.add_argument(
        "--unfreeze",
        action="store_true",
        help="Release frozen books. Requires --book-id; there is no global unfreeze.",
    )
    parser.add_argument("--execute", action="store_true", help="Apply changes.")
    parser.add_argument("--confirm", help=f"Required with --execute: {CONFIRMATION_PHRASE}")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    return parser.parse_args(argv)


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "(none)"
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _target_book_ids(args: argparse.Namespace) -> list[uuid.UUID]:
    try:
        return [uuid.UUID(value) for value in args.book_id]
    except ValueError as exc:
        raise SystemExit(f"Invalid --book-id value: {exc}") from exc


async def _resolve_cutoff(
    db, args: argparse.Namespace
) -> tuple[datetime, datetime | None, str]:
    """Return (effective cutoff, persisted cutoff, source).

    A fixed cutoff is required: an explicitly provided value may never disagree
    with an already persisted one.
    """
    persisted = await load_persisted_freeze_cutoff(db)
    explicit = parse_freeze_cutoff(args.cutoff) if args.cutoff else None
    if args.cutoff and explicit is None:
        raise SystemExit(f"Invalid --cutoff value: {args.cutoff!r}. {CUTOFF_FORMAT_HELP}")
    if persisted is not None and explicit is not None and persisted != explicit:
        raise SystemExit(
            "Refusing to run: --cutoff disagrees with the persisted legacy cutoff "
            f"({persisted.isoformat()}). Re-run without --cutoff or use the persisted value."
        )
    if persisted is not None:
        return persisted, persisted, "persisted"
    if explicit is not None:
        return explicit, None, "explicit"
    return datetime.now(UTC), None, "now"


async def _load_legacy_candidates(
    db, cutoff: datetime, target_ids: list[uuid.UUID]
) -> list[Book]:
    if target_ids:
        # Explicit targets are always loaded so the output can explain why a
        # book was skipped (after cutoff, ready, already frozen) instead of
        # silently disappearing from the report.
        statement = (
            select(Book)
            .where(Book.hidden_at.is_(None), Book.id.in_(target_ids))
            .order_by(Book.created_at.asc())
        )
    else:
        statement = (
            select(Book)
            .where(
                Book.hidden_at.is_(None),
                Book.status.in_(FREEZABLE_BOOK_STATUSES),
                Book.created_at < cutoff,
            )
            .order_by(Book.created_at.asc())
        )
    return list((await db.execute(statement)).scalars().all())


def _latest_processing_activity(book: Book) -> datetime | None:
    """Newest recorded processing timestamp from the book workspace."""
    candidates = [get_processing_started_at(book)]
    workspace = book.writer_workspace if isinstance(book.writer_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace, dict) else {}
    if isinstance(processing, dict):
        candidates.append(parse_freeze_cutoff(processing.get("updated_at")))
    return max((value for value in candidates if value is not None), default=None)


async def _describe_book(db, book: Book, cutoff: datetime) -> dict[str, Any]:
    user = await db.get(User, book.user_id)
    execution_rows = (
        (
            await db.execute(
                select(TaskExecution.status, func.count())
                .where(TaskExecution.book_id == book.id)
                .group_by(TaskExecution.status)
            )
        )
        .all()
    )
    execution_counts = {str(status): int(count) for status, count in execution_rows}
    non_terminal = sum(
        execution_counts.get(status, 0) for status in NON_TERMINAL_EXECUTION_STATUSES
    )
    in_flight = int(
        await db.scalar(
            select(func.count())
            .select_from(TaskExecution)
            .where(
                TaskExecution.book_id == book.id,
                TaskExecution.status == "running",
                TaskExecution.locked_until.is_not(None),
                TaskExecution.locked_until > datetime.now(UTC),
            )
        )
        or 0
    )
    total_words = int(
        await db.scalar(
            select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                Chapter.book_id == book.id
            )
        )
        or 0
    )
    created_at = book.created_at if book.created_at.tzinfo else book.created_at.replace(tzinfo=UTC)
    processing = (
        book.writer_workspace.get("processing")
        if isinstance(book.writer_workspace, dict)
        else None
    )
    latest_activity = _latest_processing_activity(book)
    return {
        "book_id": str(book.id),
        "user_email": mask_email(user.email if user else None),
        "status": book.status,
        "stage": processing.get("stage") if isinstance(processing, dict) else None,
        "created_at": created_at.isoformat(),
        "age_days": round((datetime.now(UTC) - created_at).total_seconds() / 86400, 1),
        "before_cutoff": created_at < cutoff,
        "processing_after_cutoff": latest_activity is not None and latest_activity >= cutoff,
        "chapters_total": int(book.total_chapters or 0),
        "total_words": total_words,
        "frozen": is_book_frozen(book),
        "non_terminal_executions": non_terminal,
        "in_flight_executions": in_flight,
        "execution_counts": execution_counts,
    }


def _print_results(summary: dict[str, Any]) -> None:
    print(
        f"mode={summary['mode']} action={summary['action']} cutoff={summary['cutoff']} "
        f"cutoff_source={summary['cutoff_source']} candidates={summary['candidates']} "
        f"changed={summary['changed']} skipped={summary['skipped']}"
    )
    if summary["cutoff_will_be_persisted"]:
        print("First execution will persist this cutoff so later runs can never freeze newer books.")
    if summary["in_flight_total"]:
        print(
            f"WARNING: {summary['in_flight_total']} execution(s) are currently running. "
            "They will be dismissed and stop before their next provider call; an LLM "
            "request already in flight may still complete once."
        )
    for item in summary["results"]:
        print(
            "  - book={book_id} user={user_email} status={status} stage={stage} "
            "created={created_at} age_days={age_days} words={total_words} "
            "execs={non_terminal_executions} in_flight={in_flight_executions} "
            "frozen={frozen} action={action}".format(**item)
        )
    if not summary["applied"]:
        print(
            "\nDry run only. Re-run with --execute --confirm "
            f"{CONFIRMATION_PHRASE} to apply."
        )


async def run(args: argparse.Namespace) -> int:
    apply_changes = bool(args.execute)
    if apply_changes and args.confirm != CONFIRMATION_PHRASE:
        print(
            f"Refusing to modify records without --confirm {CONFIRMATION_PHRASE}.",
            file=sys.stderr,
        )
        return 2
    if args.unfreeze and not args.book_id:
        print("Refusing to unfreeze: --book-id is required (no global unfreeze).", file=sys.stderr)
        return 2
    if args.record_cutoff and not apply_changes:
        print("--record-cutoff requires --execute --confirm (it is a write).", file=sys.stderr)
        return 2

    target_ids = _target_book_ids(args)
    results: list[dict[str, Any]] = []
    changed = 0
    skipped = 0
    in_flight_total = 0

    async with AsyncSessionLocal() as db:
        cutoff, persisted, source = await _resolve_cutoff(db, args)
        action = "unfreeze" if args.unfreeze else ("record_cutoff" if args.record_cutoff else "freeze")
        cutoff_will_be_persisted = persisted is None and action == "freeze"

        if args.record_cutoff:
            recorded = False
            if apply_changes:
                recorded = await record_freeze_cutoff(db, cutoff=cutoff)
            summary = {
                "mode": "execute" if apply_changes else "dry_run",
                "action": "record_cutoff",
                "applied": apply_changes,
                "cutoff": cutoff.astimezone(UTC).isoformat(),
                "cutoff_source": source,
                "cutoff_will_be_persisted": persisted is None,
                "cutoff_recorded": recorded,
                "candidates": 0,
                "changed": 0,
                "skipped": 0,
                "in_flight_total": 0,
                "results": [],
            }
            print(json.dumps(summary, indent=2) if args.json else "", end="")
            if not args.json:
                if persisted is not None:
                    print(f"Cutoff already persisted: {persisted.isoformat()} (no change).")
                elif apply_changes:
                    print(f"Cutoff persisted: {cutoff.astimezone(UTC).isoformat()}")
                else:
                    print(f"Would persist cutoff: {cutoff.astimezone(UTC).isoformat()}")
            return 0

        if apply_changes and persisted is None and action == "freeze":
            if await record_freeze_cutoff(db, cutoff=cutoff):
                cutoff_will_be_persisted = False

        if args.unfreeze:
            books: list[Book] = []
            for book_id in target_ids:
                book = await db.get(Book, book_id)
                if book is not None:
                    books.append(book)
        else:
            books = await _load_legacy_candidates(db, cutoff, target_ids)

        for book in books:
            description = await _describe_book(db, book, cutoff)
            in_flight_total += description["in_flight_executions"]
            if args.unfreeze:
                if not description["frozen"]:
                    description["action"] = "skipped_not_frozen"
                    skipped += 1
                    results.append(description)
                    continue
                description["action"] = "unfreeze"
                if apply_changes:
                    outcome = await unfreeze_book_processing(
                        db, book_id=book.id, actor_user_id=None, reason="operator_release"
                    )
                    description["outcome"] = outcome.get("status")
                    changed += 1
                results.append(description)
                continue

            if description["frozen"]:
                description["action"] = "already_frozen"
                skipped += 1
                results.append(description)
                continue
            if description["status"] == "ready":
                description["action"] = "skipped_ready"
                skipped += 1
                results.append(description)
                continue
            if not description["before_cutoff"]:
                description["action"] = "skipped_after_cutoff"
                skipped += 1
                results.append(description)
                continue
            if description["processing_after_cutoff"]:
                # The workspace shows processing activity newer than the cutoff.
                # Never freeze a book that may be legitimately running under
                # the new deployment; investigate it manually instead.
                description["action"] = "skipped_processing_after_cutoff"
                skipped += 1
                results.append(description)
                continue
            description["action"] = "freeze"
            if apply_changes:
                outcome = await freeze_book_processing(
                    db,
                    book_id=book.id,
                    actor_user_id=None,
                    reason="one_time_legacy_cutover",
                    include_editor_projects=True,
                )
                description["outcome"] = outcome.get("status")
                changed += 1
            results.append(description)

    summary = {
        "mode": "execute" if apply_changes else "dry_run",
        "action": action,
        "applied": apply_changes,
        "cutoff": cutoff.astimezone(UTC).isoformat(),
        "cutoff_source": source,
        "cutoff_will_be_persisted": cutoff_will_be_persisted,
        "candidates": len(results),
        "changed": changed,
        "skipped": skipped,
        "in_flight_total": in_flight_total,
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        _print_results(summary)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
