"""Administrative freeze for stale manuscript-processing jobs.

A frozen book:
- stops every pending, queued, running, or paused book task (dismissed at the
  database level, so repair sweeps and worker restarts cannot reactivate them),
- refuses new imports, retries, and reprocessing,
- cannot generate further provider calls because workers check the freeze state
  before each costly operation,
- keeps every stored manuscript file, chapter, and completed analysis result.

The freeze flag lives inside ``writer_workspace.processing`` because that JSON
round-trips through the existing normalizers without a database migration.

Freezing is deliberately separate from ordinary processing failure: it records
an operator actor, a reason code, and user-facing copy, and it never schedules
work. This module does not delete user content.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.operations import (
    BookProcessingRun,
    ManuscriptImportJob,
    TaskDispatchOutbox,
    TaskExecution,
)
from app.models.user import AdminAuditEvent

log = logging.getLogger("lorevia.freeze")

FREEZE_KIND = "administrative_freeze"
FREEZE_REASON_LEGACY_IMPORT = "interrupted_legacy_import"
FROZEN_USER_MESSAGE = (
    "Import interrupted - please upload again. "
    "Your project and files have been preserved."
)
LEGACY_INCOMPLETE_MESSAGE = (
    "This project predates the current release and its interrupted import is "
    "awaiting review, so new processing cannot start. Upload the manuscript "
    "again as a new project."
)
ACTION_FREEZE = "book_processing_frozen"
ACTION_UNFREEZE = "book_processing_unfrozen"
ACTION_CUTOFF_RECORDED = "legacy_freeze_cutoff_recorded"

NON_TERMINAL_EXECUTION_STATUSES = ("pending_dispatch", "queued", "running", "paused")
NON_TERMINAL_RUN_STATUSES = ("queued", "running", "paused")
ACTIVE_IMPORT_JOB_STATUSES = ("queued", "running", "cancel_requested")
CANCELLABLE_OUTBOX_STATUSES = ("pending", "publishing", "publish_failed")

FREEZABLE_BOOK_STATUSES = ("pending", "processing", "failed", "error")


def book_freeze_state(book: Book) -> dict[str, Any] | None:
    """Return the freeze record stored on a book, if the book is frozen."""
    workspace = getattr(book, "writer_workspace", None)
    workspace = workspace if isinstance(workspace, dict) else {}
    processing = workspace.get("processing")
    if not isinstance(processing, dict):
        return None
    if processing.get("frozen") is True:
        return processing
    freeze = processing.get("freeze")
    if isinstance(freeze, dict) and freeze.get("frozen") is True:
        return freeze
    return None


def is_book_frozen(book: Book) -> bool:
    """Pure check against an already-loaded book row."""
    return book_freeze_state(book) is not None


async def book_is_frozen(db: AsyncSession, book_id: uuid.UUID) -> bool:
    """Authoritative freeze check that re-reads the stored workspace."""
    workspace = await db.scalar(
        select(Book.writer_workspace).where(Book.id == book_id)
    )
    if not isinstance(workspace, dict):
        return False
    processing = workspace.get("processing")
    if not isinstance(processing, dict):
        return False
    if processing.get("frozen") is True:
        return True
    freeze = processing.get("freeze")
    return isinstance(freeze, dict) and freeze.get("frozen") is True


def frozen_conflict_message() -> str:
    return FROZEN_USER_MESSAGE


def parse_freeze_cutoff(value: object | None) -> datetime | None:
    """Parse an ISO-8601 cutoff value into an aware UTC datetime."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


async def load_persisted_freeze_cutoff(db: AsyncSession) -> datetime | None:
    """Read the one-time legacy-freeze cutoff marker, if it was recorded."""
    raw = await db.scalar(
        select(AdminAuditEvent.metadata_json["cutoff"].astext)
        .where(AdminAuditEvent.action_type == ACTION_CUTOFF_RECORDED)
        .order_by(AdminAuditEvent.created_at.desc())
        .limit(1)
    )
    return parse_freeze_cutoff(raw)


async def record_freeze_cutoff(
    db: AsyncSession,
    *,
    cutoff: datetime,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> bool:
    """Persist the legacy-freeze cutoff exactly once.

    Write-once is enforced here (not by a unique constraint) because the marker
    lives in the existing audit table without a migration. Returns True when
    this call recorded the cutoff.
    """
    existing = await load_persisted_freeze_cutoff(db)
    if existing is not None:
        return False
    db.add(
        AdminAuditEvent(
            actor_user_id=actor_user_id,
            action_type=ACTION_CUTOFF_RECORDED,
            reason="one_time_legacy_cutover",
            result="recorded",
            request_id=request_id,
            metadata_json={"cutoff": cutoff.astimezone(UTC).isoformat()},
        )
    )
    await db.commit()
    log.warning("legacy_freeze_cutoff_recorded cutoff=%s", cutoff.astimezone(UTC).isoformat())
    return True


def _aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def book_created_before_cutoff(book: Book, cutoff: datetime | None) -> bool:
    created_at = _aware_datetime(getattr(book, "created_at", None))
    if created_at is None or cutoff is None:
        return False
    return created_at < cutoff


def book_is_legacy_incomplete(book: Book, cutoff: datetime | None) -> bool:
    """True when a book predates the release cutoff and is not complete.

    These books are intended for the one-time freeze. Until the operator runs
    it, the deployment transition gate holds their queued work so no provider
    calls are made and no new work can be started against them.
    """
    if cutoff is None:
        return False
    if not book_created_before_cutoff(book, cutoff):
        return False
    return str(getattr(book, "status", "") or "") != "ready"


async def ensure_legacy_processing_allowed(db: AsyncSession, book: Book) -> None:
    """Reject new processing for pre-cutoff incomplete books (transition gate)."""
    from fastapi import HTTPException

    cutoff = await load_persisted_freeze_cutoff(db)
    if book_is_legacy_incomplete(book, cutoff) and not is_book_frozen(book):
        raise HTTPException(409, LEGACY_INCOMPLETE_MESSAGE)


def _freeze_workspace_state(
    workspace: dict[str, Any] | None,
    *,
    actor_user_id: uuid.UUID | None,
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    payload = dict(workspace) if isinstance(workspace, dict) else {}
    processing = (
        dict(payload.get("processing")) if isinstance(payload.get("processing"), dict) else {}
    )
    now_iso = now.isoformat()
    processing.update(
        {
            "status": "failed",
            "stage": "failed",
            "frozen": True,
            "freeze_kind": FREEZE_KIND,
            "freeze_reason": reason,
            "freeze_message": FROZEN_USER_MESSAGE,
            "frozen_at": now_iso,
            "updated_at": now_iso,
            "pause_reason": None,
            "auto_resume": False,
            "resume_available": False,
            "resume_blockers": [],
            "next_resume_at": None,
            "retry_actions": [],
            "last_error": FROZEN_USER_MESSAGE,
        }
    )
    if actor_user_id is not None:
        processing["freeze_actor_user_id"] = str(actor_user_id)
    payload["processing"] = processing
    return payload


def _unfreeze_workspace_state(workspace: dict[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    payload = dict(workspace) if isinstance(workspace, dict) else {}
    processing = (
        dict(payload.get("processing")) if isinstance(payload.get("processing"), dict) else {}
    )
    for key in (
        "frozen",
        "freeze_kind",
        "freeze_reason",
        "freeze_message",
        "frozen_at",
        "freeze_actor_user_id",
    ):
        processing.pop(key, None)
    processing.update(
        {
            "status": "failed",
            "stage": "failed",
            "updated_at": now.isoformat(),
            "retry_actions": ["retry_extraction"],
            "last_error": None,
        }
    )
    payload["processing"] = processing
    return payload


async def _record_audit_event(
    db: AsyncSession,
    *,
    action_type: str,
    book: Book,
    actor_user_id: uuid.UUID | None,
    reason: str,
    result: str,
    request_id: str | None,
    metadata: dict[str, Any],
) -> None:
    db.add(
        AdminAuditEvent(
            actor_user_id=actor_user_id,
            target_user_id=book.user_id,
            target_book_id=book.id,
            action_type=action_type,
            reason=reason,
            result=result,
            request_id=request_id,
            metadata_json=metadata,
        )
    )


async def freeze_book_processing(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
    reason: str = FREEZE_REASON_LEGACY_IMPORT,
    request_id: str | None = None,
    include_editor_projects: bool = False,
) -> dict[str, Any]:
    """Freeze one book's processing without touching stored content.

    Idempotent: freezing an already-frozen book changes nothing and returns
    ``status="already_frozen"``. Ready books are never frozen because their
    analysis is complete and they cannot consume further ingestion tokens.
    Editor projects are only frozen when the caller opts in (the one-time
    legacy freeze does; interactive flows do not).
    """
    await db.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"admin_freeze:{book_id}")))
    )
    book = await db.get(Book, book_id, with_for_update=True)
    if book is None:
        return {"status": "missing", "book_id": str(book_id)}

    if is_book_frozen(book):
        await db.commit()
        return {"status": "already_frozen", "book_id": str(book_id)}

    if book.status == "ready" or (
        getattr(book, "is_editor_project", False) and not include_editor_projects
    ):
        await db.commit()
        return {"status": "skipped", "reason": "ready_or_editor_project", "book_id": str(book_id)}

    if book.status not in FREEZABLE_BOOK_STATUSES:
        await db.commit()
        return {"status": "skipped", "reason": f"unfreezable_status:{book.status}", "book_id": str(book_id)}

    now = datetime.now(UTC)

    dismissed_executions = (
        (
            await db.execute(
                select(TaskExecution.id).where(
                    TaskExecution.book_id == book.id,
                    TaskExecution.status.in_(NON_TERMINAL_EXECUTION_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    execution_ids = list(dismissed_executions)
    if execution_ids:
        await db.execute(
            update(TaskExecution)
            .where(TaskExecution.id.in_(execution_ids))
            .values(
                status="dismissed",
                error_category="administrative_freeze",
                error_detail="Administratively frozen after an interrupted import.",
                completed_at=now,
                locked_until=None,
            )
        )
        await db.execute(
            update(TaskDispatchOutbox)
            .where(
                TaskDispatchOutbox.execution_id.in_(execution_ids),
                TaskDispatchOutbox.status.in_(CANCELLABLE_OUTBOX_STATUSES),
            )
            .values(status="cancelled", lease_until=None, last_error="administrative_freeze")
        )
        from app.services.processing_pause_service import release_execution_processing_reservation

        for execution_id in execution_ids:
            execution = await db.get(TaskExecution, execution_id)
            if execution is None:
                continue
            await release_execution_processing_reservation(db, execution)

    runs_frozen = (
        await db.execute(
            update(BookProcessingRun)
            .where(
                BookProcessingRun.book_id == book.id,
                BookProcessingRun.status.in_(NON_TERMINAL_RUN_STATUSES),
            )
            .values(
                status="failed_terminal",
                completed_at=now,
                pause_reason=None,
                resume_blockers=[],
                paused_at=None,
            )
        )
    ).rowcount or 0

    import_jobs_frozen = (
        await db.execute(
            update(ManuscriptImportJob)
            .where(
                ManuscriptImportJob.book_id == book.id,
                ManuscriptImportJob.status.in_(ACTIVE_IMPORT_JOB_STATUSES),
            )
            .values(
                status="cancelled",
                cancel_requested=True,
                completed_at=now,
                error_detail=FROZEN_USER_MESSAGE,
            )
        )
    ).rowcount or 0

    book.writer_workspace = _freeze_workspace_state(
        book.writer_workspace,
        actor_user_id=actor_user_id,
        reason=reason,
        now=now,
    )
    book.status = "failed"

    preserved_chapters = int(
        await db.scalar(
            select(func.count()).select_from(Chapter).where(Chapter.book_id == book.id)
        )
        or 0
    )
    metadata = {
        "dismissed_executions": len(execution_ids),
        "runs_frozen": runs_frozen,
        "import_jobs_frozen": import_jobs_frozen,
        "preserved_chapters": preserved_chapters,
        "chapters_total": int(book.total_chapters or 0),
        "total_tokens": int(book.total_tokens or 0),
    }
    await _record_audit_event(
        db,
        action_type=ACTION_FREEZE,
        book=book,
        actor_user_id=actor_user_id,
        reason=reason,
        result="frozen",
        request_id=request_id,
        metadata=metadata,
    )
    await db.commit()
    log.warning(
        "book_processing_frozen book_id=%s user_id=%s executions=%s runs=%s import_jobs=%s",
        book.id,
        book.user_id,
        len(execution_ids),
        runs_frozen,
        import_jobs_frozen,
    )
    return {
        "status": "frozen",
        "book_id": str(book.id),
        "user_id": str(book.user_id),
        **metadata,
    }


async def unfreeze_book_processing(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
    reason: str = "operator_rollback",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Clear a freeze flag without resuming any paid processing.

    The book is left in a normal, user-visible failed state with a retry
    action; an operator must still trigger any restart explicitly.
    """
    await db.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"admin_freeze:{book_id}")))
    )
    book = await db.get(Book, book_id, with_for_update=True)
    if book is None:
        return {"status": "missing", "book_id": str(book_id)}
    if not is_book_frozen(book):
        await db.commit()
        return {"status": "not_frozen", "book_id": str(book_id)}

    book.writer_workspace = _unfreeze_workspace_state(book.writer_workspace, now=datetime.now(UTC))
    await _record_audit_event(
        db,
        action_type=ACTION_UNFREEZE,
        book=book,
        actor_user_id=actor_user_id,
        reason=reason,
        result="unfrozen",
        request_id=request_id,
        metadata={"resumed_processing": False},
    )
    await db.commit()
    log.warning("book_processing_unfrozen book_id=%s user_id=%s", book.id, book.user_id)
    return {"status": "unfrozen", "book_id": str(book.id)}
