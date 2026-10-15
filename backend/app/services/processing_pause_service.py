from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.operations import BookProcessingRun, TaskExecution
from app.services.book_freeze_service import is_book_frozen


def parse_processing_blocker(error_detail: str | None) -> dict[str, Any]:
    if not error_detail:
        return {}
    try:
        parsed = json.loads(error_detail)
    except (TypeError, ValueError):
        return {"detail": error_detail}
    return parsed if isinstance(parsed, dict) else {"detail": error_detail}


def parse_processing_resume_at(value: object | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


async def write_book_pause_state(
    db: AsyncSession,
    run: BookProcessingRun,
    *,
    blocker: dict[str, Any] | None,
) -> None:
    book = await db.get(Book, run.book_id, with_for_update=True)
    if book is None:
        return
    if is_book_frozen(book):
        # Frozen books are administratively paused; no sweep or late task may
        # overwrite their state or make a retry look available.
        return
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = dict(
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    if blocker is None:
        processing.update(
            {
                "status": "processing",
                "stage": "queued",
                "pause_reason": None,
                "auto_resume": False,
                "resume_available": False,
                "resume_blockers": [],
                "next_resume_at": None,
                "retry_actions": [],
                "last_error": None,
            }
        )
    else:
        auto_resume = bool(blocker.get("auto_resume")) or run.pause_reason == "llm_capacity"
        stage = "budget_limited" if blocker.get("kind") == "llm_budget" else "usage_limited"
        processing.update(
            {
                "status": "paused",
                "stage": stage,
                "processing_run_id": str(run.id),
                "pause_reason": run.pause_reason,
                "auto_resume": auto_resume,
                "resume_available": not auto_resume,
                "resume_blockers": [blocker],
                "next_resume_at": blocker.get("next_resume_at"),
                "retry_actions": [] if auto_resume else ["continue_processing"],
                "last_error": blocker.get("detail"),
            }
        )
    workspace["processing"] = processing
    book.writer_workspace = workspace
    book.status = "processing"


async def write_book_terminal_processing_state(
    db: AsyncSession,
    run: BookProcessingRun,
    *,
    error: str,
    rebuild_run_id: str | None = None,
) -> None:
    book = await db.get(Book, run.book_id, with_for_update=True)
    if book is None:
        return
    if is_book_frozen(book):
        # Keep the administrative freeze authoritative over late task failures.
        return
    from app.utils.processing_error_utils import friendly_processing_error

    user_visible_error = friendly_processing_error(error)
    effective_rebuild_run_id = rebuild_run_id or run.rebuild_run_id
    if effective_rebuild_run_id:
        from app.services.editor_project_service import fail_rebuild_if_active

        if await fail_rebuild_if_active(
            db,
            book,
            expected_rebuild_run_id=effective_rebuild_run_id,
            error=user_visible_error,
        ):
            return
        return
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = dict(
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    processing.update(
        {
            "status": "failed",
            "stage": "failed",
            "pause_reason": None,
            "auto_resume": False,
            "resume_available": False,
            "resume_blockers": [],
            "next_resume_at": None,
            "retry_actions": ["retry_extraction"],
            "last_error": user_visible_error,
        }
    )
    workspace["processing"] = processing
    book.writer_workspace = workspace
    book.status = "failed"


async def processing_rebuild_is_current(
    db: AsyncSession,
    execution: TaskExecution,
) -> bool:
    if not execution.rebuild_run_id:
        return True
    if execution.book_id is None:
        return False
    book = await db.get(Book, execution.book_id)
    if book is None:
        return False
    workspace = book.writer_workspace if isinstance(book.writer_workspace, dict) else {}
    processing = workspace.get("processing")
    if not isinstance(processing, dict):
        return False
    return processing.get("rebuild_run_id") == execution.rebuild_run_id


async def release_execution_processing_reservation(
    db: AsyncSession,
    execution: TaskExecution,
) -> None:
    reservation_id = (execution.arguments_json or {}).get("processing_reservation_id")
    if not reservation_id:
        return
    from app.services.processing_allowance_service import release_processing_reservation

    await release_processing_reservation(db, uuid.UUID(str(reservation_id)))


async def settle_terminal_processing_failure(
    db: AsyncSession,
    execution: TaskExecution,
    *,
    error: str,
    completed_at: datetime,
) -> BookProcessingRun | None:
    await release_execution_processing_reservation(db, execution)
    run = (
        await db.get(BookProcessingRun, execution.processing_run_id, with_for_update=True)
        if execution.processing_run_id
        else None
    )
    if run is None:
        return None
    run.status = "failed_terminal"
    run.completed_at = completed_at
    # Terminal failures must be visible to the author for every run kind, not
    # only rebuilds. Otherwise the book stays "processing" forever and the
    # retry endpoint refuses to act because no retryable state was recorded.
    await write_book_terminal_processing_state(
        db,
        run,
        error=error,
        rebuild_run_id=execution.rebuild_run_id,
    )
    return run
