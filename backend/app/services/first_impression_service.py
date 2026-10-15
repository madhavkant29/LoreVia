"""Automatic supportive first-read orchestration for newly analyzed manuscripts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.user import User
from app.schemas.advisor import BetaReaderAnalysisRequest, FirstImpressionOut
from app.services.advisor_jobs_service import (
    ADVISOR_SCOPE_FIRST_IMPRESSION,
    create_advisor_job,
    get_advisor_job,
    mark_advisor_job_failed,
)
from app.services.beta_reader_analysis_service import (
    list_beta_reader_reports,
    prepare_beta_reader_run,
)
from app.utils.billing_utils import require_author_access
from app.utils.books import writer_workspace
from app.utils.first_impression_utils import normalize_first_impression_state
from app.utils.logging.errors import public_error_message
from app.utils.task_queue_errors import TASK_ENQUEUE_ERRORS


def first_impression_request() -> BetaReaderAnalysisRequest:
    return BetaReaderAnalysisRequest(scope="full_book", checks=["reader_feedback"])


def _now_text() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_owner_author_access(book: Book, user: User) -> None:
    if book.user_id != user.id:
        raise HTTPException(403, "Only the manuscript owner can use the first read.")
    require_author_access(user)
    if book.mode != "author":
        raise HTTPException(400, "The supportive first read is available for Author manuscripts.")
    work_type = str(getattr(book, "work_type", "novel") or "novel").strip().lower()
    if work_type not in {"novel", "screenplay"}:
        raise HTTPException(
            400,
            "The supportive first read is available for novels and screenplays.",
        )


def _ensure_eligible(book: Book, user: User) -> None:
    _ensure_owner_author_access(book, user)
    if book.status != "ready" or int(book.total_chapters or 0) <= 0:
        raise HTTPException(409, "The manuscript must finish analysis before its first read.")


async def queue_first_impression(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    allow_retry: bool = False,
    strict: bool = False,
) -> FirstImpressionOut | None:
    """Queue the one-time first read, returning quietly for ineligible automatic calls."""

    await db.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"first_impression:{book_id}")))
    )
    book = (
        await db.execute(select(Book).where(Book.id == book_id).with_for_update())
    ).scalar_one_or_none()
    user = await db.get(User, user_id)
    if book is None or user is None:
        if strict:
            raise HTTPException(404, "Manuscript not found.")
        return None
    try:
        _ensure_eligible(book, user)
    except HTTPException:
        if strict:
            raise
        # Not an error path: release the advisory/row locks without rolling
        # back. A rollback would expire every ORM object already loaded in the
        # caller's session, and the caller's next synchronous attribute access
        # would then raise MissingGreenlet in async workers.
        await db.commit()
        return None

    workspace = writer_workspace.normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    state = normalize_first_impression_state(workspace.get("first_impression"))
    if state["status"] in {"queued", "running", "complete"}:
        if allow_retry and strict:
            raise HTTPException(409, "The first read is not in a retryable state.")
        await db.commit()
        await db.refresh(book)
        return await get_first_impression_status(db, book=book, user=user)
    if state["status"] == "failed" and not allow_retry:
        await db.commit()
        await db.refresh(book)
        return await get_first_impression_status(db, book=book, user=user)
    if allow_retry and state["status"] != "failed":
        if strict:
            raise HTTPException(409, "The first read is not in a retryable state.")
        # Release locks with a commit so the caller's session state stays valid.
        await db.commit()
        return None

    body = first_impression_request()
    prepared = await prepare_beta_reader_run(db, book=book, collaborator=None, body=body)
    if not prepared["chapters"]:
        if strict:
            raise HTTPException(409, "No analyzed manuscript chapters are available yet.")
        # Release locks with a commit so the caller's session state stays valid.
        await db.commit()
        return None

    now_text = _now_text()
    if prepared["cached"] is not None:
        report = prepared["cached"]
        state.update(
            {
                "status": "complete",
                "job_id": None,
                "report_id": report["report_id"],
                "request_hash": prepared["request_hash"],
                "source_fingerprint": prepared["source_fingerprint"],
                "started_at": state.get("started_at") or now_text,
                "completed_at": now_text,
                "error_code": None,
            }
        )
        workspace["first_impression"] = state
        book.writer_workspace = workspace
        await db.commit()
        return FirstImpressionOut(status="complete", report=report)

    job = await create_advisor_job(
        db,
        scope=ADVISOR_SCOPE_FIRST_IMPRESSION,
        user_id=user.id,
        book_id=book.id,
        commit=False,
    )
    state.update(
        {
            "status": "queued",
            "job_id": str(job.id),
            "report_id": None,
            "request_hash": prepared["request_hash"],
            "source_fingerprint": prepared["source_fingerprint"],
            "started_at": now_text,
            "completed_at": None,
            "error_code": None,
        }
    )
    workspace["first_impression"] = state
    book.writer_workspace = workspace
    await db.commit()

    try:
        from app.workers.tasks.intelligence_tasks import generate_beta_reader_report_task

        generate_beta_reader_report_task.apply_async(
            task_id=str(job.id),
            kwargs={
                "job_id": str(job.id),
                "book_id": str(book.id),
                "user_id": str(user.id),
                "request_payload": body.model_dump(mode="json"),
            },
        )
    except TASK_ENQUEUE_ERRORS:
        await mark_advisor_job_failed(
            db,
            job_id=job.id,
            error_code="first_impression_enqueue_failed",
            error_detail=public_error_message(500),
        )
        await mark_first_impression_failed(
            db,
            book_id=book.id,
            job_id=job.id,
            error_code="first_impression_enqueue_failed",
        )
        if strict:
            raise HTTPException(503, public_error_message(503))
        return FirstImpressionOut(
            status="failed",
            task_id=str(job.id),
            error="first_impression_enqueue_failed",
            can_retry=True,
        )

    return FirstImpressionOut(status="queued", task_id=str(job.id))


async def get_first_impression_status(
    db: AsyncSession,
    *,
    book: Book,
    user: User,
) -> FirstImpressionOut:
    _ensure_owner_author_access(book, user)
    state = normalize_first_impression_state(
        (book.writer_workspace or {}).get("first_impression")
        if isinstance(book.writer_workspace, dict)
        else None
    )
    report = None
    if state["report_id"]:
        reports = await list_beta_reader_reports(db, book=book)
        report = next(
            (item for item in reports if item["report_id"] == state["report_id"]),
            None,
        )
    job = None
    if state["job_id"]:
        try:
            job = await get_advisor_job(db, job_id=uuid.UUID(state["job_id"]))
        except ValueError:
            job = None

    status = state["status"]
    progress = None
    error = state["error_code"]
    if job is not None and job.scope == ADVISOR_SCOPE_FIRST_IMPRESSION:
        status = job.status
        if job.status == "running" and isinstance(job.result_json, dict):
            progress = job.result_json.get("progress")
        elif job.status == "complete" and report is None:
            report = job.result_json
        elif job.status == "failed":
            error = job.error_detail or job.error_code
    elif status in {"queued", "running"}:
        status = "failed"
        error = "first_impression_job_unavailable"

    return FirstImpressionOut(
        status=status,
        task_id=state["job_id"],
        progress=progress,
        report=report,
        error=error if status == "failed" else None,
        can_retry=status == "failed",
    )


async def mark_first_impression_running(
    db: AsyncSession, *, book_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    await _update_first_impression_state(
        db, book_id=book_id, job_id=job_id, updates={"status": "running", "error_code": None}
    )


async def mark_first_impression_complete(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    report: dict[str, Any],
) -> None:
    await _update_first_impression_state(
        db,
        book_id=book_id,
        job_id=job_id,
        updates={
            "status": "complete",
            "report_id": report.get("report_id"),
            "request_hash": report.get("request_hash"),
            "source_fingerprint": report.get("source_fingerprint"),
            "completed_at": _now_text(),
            "error_code": None,
        },
    )


async def mark_first_impression_failed(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    error_code: str,
) -> None:
    await _update_first_impression_state(
        db,
        book_id=book_id,
        job_id=job_id,
        updates={
            "status": "failed",
            "completed_at": _now_text(),
            "error_code": error_code,
        },
    )


async def _update_first_impression_state(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    updates: dict[str, Any],
) -> None:
    book = (
        await db.execute(select(Book).where(Book.id == book_id).with_for_update())
    ).scalar_one_or_none()
    if book is None:
        return
    workspace = writer_workspace.normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    state = normalize_first_impression_state(workspace.get("first_impression"))
    if state.get("job_id") != str(job_id):
        # Stale update for a replaced job; release the lock without expiring
        # the caller's loaded ORM state.
        await db.commit()
        return
    state.update(updates)
    workspace["first_impression"] = state
    book.writer_workspace = workspace
    await db.commit()
