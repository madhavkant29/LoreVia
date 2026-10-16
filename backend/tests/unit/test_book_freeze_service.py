"""Regression tests for administrative freezing of stale manuscript jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.operations import (
    BookProcessingRun,
    ManuscriptImportJob,
    TaskDispatchOutbox,
    TaskExecution,
)
from app.models.user import AdminAuditEvent, User
from app.services.book_freeze_service import (
    ACTION_FREEZE,
    FROZEN_USER_MESSAGE,
    book_is_frozen,
    freeze_book_processing,
    is_book_frozen,
    unfreeze_book_processing,
)
from app.services.pipeline_state_service import book_processing_has_blocking_failure
from app.services.processing_allowance_service import ensure_project_writable
from app.services.processing_pause_service import write_book_terminal_processing_state
from app.utils.books.writer_workspace import normalize_writer_workspace


async def _create_user(db: AsyncSession, *, tier: str = "author") -> User:
    user = User(
        email=f"freeze-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"freeze{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier=tier,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_processing_book(db: AsyncSession, *, user: User) -> Book:
    book = Book(
        user_id=user.id,
        title="Stuck Import",
        format="txt",
        work_type="novel",
        s3_key=f"books/{user.id}/{uuid.uuid4()}/manuscript.txt",
        status="processing",
        mode="author",
        total_chapters=3,
        total_tokens=1200,
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "queued",
                "chapters_completed": 0,
                "chapters_total": 3,
                "started_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        },
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Chapter 1",
        s3_key=f"chapters/{book.id}/1.txt",
        word_count=1100,
        processed=True,
    )
    db.add(chapter)
    await db.flush()
    return book


async def _create_non_terminal_rows(db: AsyncSession, *, user: User, book: Book) -> dict:
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind="initial_upload",
        status="running",
        chapters_total=3,
    )
    db.add(run)
    await db.flush()
    execution = TaskExecution(
        identity_key=f"freeze-exec-{uuid.uuid4().hex}",
        task_name="extraction_tasks.process_chapter",
        feature="processing",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        status="queued",
        arguments_json={"book_id": str(book.id)},
    )
    db.add(execution)
    await db.flush()
    outbox = TaskDispatchOutbox(
        execution_id=execution.id,
        task_name="extraction_tasks.process_chapter",
        queue="extraction",
        payload_json={"book_id": str(book.id)},
        status="pending",
    )
    db.add(outbox)
    paused_execution = TaskExecution(
        identity_key=f"freeze-paused-{uuid.uuid4().hex}",
        task_name="analysis_tasks.analyse_chapter",
        feature="analysis",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        status="paused",
        arguments_json={"book_id": str(book.id)},
    )
    db.add(paused_execution)
    import_job = ManuscriptImportJob(
        user_id=user.id,
        book_id=book.id,
        status="queued",
        request_json={},
        source_files_json=[],
        progress_total=1,
    )
    db.add(import_job)
    await db.flush()
    return {
        "run": run,
        "execution": execution,
        "paused_execution": paused_execution,
        "outbox": outbox,
        "import_job": import_job,
    }


@pytest.mark.asyncio
async def test_freeze_marks_book_and_dismisses_all_non_terminal_work(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_processing_book(db, user=user)
    rows = await _create_non_terminal_rows(db, user=user, book=book)
    await db.commit()

    result = await freeze_book_processing(db, book_id=book.id)
    await db.refresh(book)

    assert result["status"] == "frozen"
    assert book.status == "failed"
    processing = book.writer_workspace["processing"]
    assert processing["frozen"] is True
    assert processing["retry_actions"] == []
    assert processing["last_error"] == FROZEN_USER_MESSAGE
    assert is_book_frozen(book) is True
    assert await book_is_frozen(db, book.id) is True

    await db.refresh(rows["execution"])
    await db.refresh(rows["paused_execution"])
    await db.refresh(rows["outbox"])
    await db.refresh(rows["run"])
    await db.refresh(rows["import_job"])
    assert rows["execution"].status == "dismissed"
    assert rows["execution"].error_category == "administrative_freeze"
    assert rows["paused_execution"].status == "dismissed"
    assert rows["outbox"].status == "cancelled"
    assert rows["run"].status == "failed_terminal"
    assert rows["import_job"].status == "cancelled"
    assert rows["import_job"].cancel_requested is True

    # Content is preserved.
    preserved = (
        (await db.execute(select(Chapter).where(Chapter.book_id == book.id))).scalars().all()
    )
    assert len(preserved) == 1
    assert preserved[0].word_count == 1100

    audit = (
        (
            await db.execute(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.target_book_id == book.id,
                    AdminAuditEvent.action_type == ACTION_FREEZE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) == 1
    assert audit[0].metadata_json["dismissed_executions"] == 2


@pytest.mark.asyncio
async def test_freeze_is_idempotent_and_audits_once(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_processing_book(db, user=user)
    await db.commit()

    first = await freeze_book_processing(db, book_id=book.id)
    second = await freeze_book_processing(db, book_id=book.id)

    assert first["status"] == "frozen"
    assert second["status"] == "already_frozen"
    audit_count = len(
        (await db.execute(select(AdminAuditEvent).where(AdminAuditEvent.target_book_id == book.id)))
        .scalars()
        .all()
    )
    assert audit_count == 1


@pytest.mark.asyncio
async def test_freeze_skips_ready_and_editor_projects(db: AsyncSession):
    user = await _create_user(db)
    ready_book = await _create_processing_book(db, user=user)
    ready_book.status = "ready"
    editor_book = await _create_processing_book(db, user=user)
    editor_book.is_editor_project = True
    await db.commit()

    ready_result = await freeze_book_processing(db, book_id=ready_book.id)
    editor_result = await freeze_book_processing(db, book_id=editor_book.id)

    assert ready_result["status"] == "skipped"
    assert editor_result["status"] == "skipped"
    await db.refresh(ready_book)
    assert is_book_frozen(ready_book) is False


@pytest.mark.asyncio
async def test_unfreeze_clears_flag_without_starting_work(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_processing_book(db, user=user)
    await db.commit()

    await freeze_book_processing(db, book_id=book.id)
    result = await unfreeze_book_processing(db, book_id=book.id)
    await db.refresh(book)

    assert result["status"] == "unfrozen"
    assert is_book_frozen(book) is False
    processing = book.writer_workspace["processing"]
    assert processing["status"] == "failed"
    assert processing.get("retry_actions")
    pending = (
        (
            await db.execute(
                select(TaskExecution).where(
                    TaskExecution.book_id == book.id,
                    TaskExecution.status.in_(("pending_dispatch", "queued", "running")),
                )
            )
        )
        .scalars()
        .all()
    )
    assert pending == []


@pytest.mark.asyncio
async def test_retry_and_reprocess_guards_reject_frozen_books(db: AsyncSession):
    from app.services.pipeline_state_service import retry_book_processing

    user = await _create_user(db)
    book = await _create_processing_book(db, user=user)
    await db.commit()
    await freeze_book_processing(db, book_id=book.id)
    await db.refresh(book)

    with pytest.raises(HTTPException) as retry_exc:
        await retry_book_processing(db, book)
    assert retry_exc.value.status_code == 409
    assert "interrupted" in str(retry_exc.value.detail).lower()

    with pytest.raises(HTTPException) as writable_exc:
        await ensure_project_writable(db, book)
    assert writable_exc.value.status_code == 409


@pytest.mark.asyncio
async def test_terminal_state_updates_cannot_overwrite_freeze(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_processing_book(db, user=user)
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind="initial_upload",
        status="running",
    )
    db.add(run)
    await db.flush()
    await db.commit()

    await freeze_book_processing(db, book_id=book.id)
    await db.refresh(book)
    await db.refresh(run)

    await write_book_terminal_processing_state(
        db,
        run,
        error="missing_chapter_payload:book:1",
    )
    await db.commit()
    await db.refresh(book)

    processing = book.writer_workspace["processing"]
    assert processing["frozen"] is True
    assert processing["retry_actions"] == []
    assert processing["last_error"] == FROZEN_USER_MESSAGE


def test_processing_payload_reports_frozen_state_without_retry():
    from types import SimpleNamespace

    from app.utils.books.writer_workspace import build_book_processing_payload

    book = SimpleNamespace(
        writer_workspace={
            "processing": {
                "status": "failed",
                "stage": "failed",
                "frozen": True,
                "freeze_reason": "interrupted_legacy_import",
                "freeze_message": FROZEN_USER_MESSAGE,
                "frozen_at": datetime.now(UTC).isoformat(),
                "retry_actions": [],
                "last_error": FROZEN_USER_MESSAGE,
            }
        }
    )
    payload = build_book_processing_payload(book)
    assert payload is not None
    assert payload["stage"] == "frozen"
    assert payload["retry_available"] is False
    assert payload["frozen"] is True
    assert payload["freeze_message"] == FROZEN_USER_MESSAGE


def test_workspace_normalization_preserves_freeze_and_fingerprint():
    workspace = normalize_writer_workspace(
        {
            "source_fingerprint": "abc123",
            "processing": {
                "status": "failed",
                "stage": "failed",
                "frozen": True,
                "freeze_reason": "interrupted_legacy_import",
                "freeze_message": FROZEN_USER_MESSAGE,
                "frozen_at": datetime.now(UTC).isoformat(),
            },
        }
    )
    assert workspace["source_fingerprint"] == "abc123"
    assert workspace["processing"]["frozen"] is True


def test_blocking_failure_predicate_detects_failed_pipeline():
    from types import SimpleNamespace

    book = SimpleNamespace(
        writer_workspace={
            "processing": {
                "status": "failed",
                "stage": "failed",
                "retry_actions": [],
                "pipeline": {"analysis": {"status": "failed", "failed_chapters": [1]}},
            }
        }
    )
    assert book_processing_has_blocking_failure(book) is True


@pytest.mark.asyncio
async def test_repair_sweeps_skip_frozen_books(db: AsyncSession):
    from app.services.pipeline_state_service import (
        repair_stale_completed_processing_state,
        requeue_stalled_book_processing_if_needed,
    )

    user = await _create_user(db)
    book = await _create_processing_book(db, user=user)
    await db.commit()
    await freeze_book_processing(db, book_id=book.id)
    await db.refresh(book)

    # Both sweeps filter on Book.status == "processing"; a frozen book is
    # "failed", so neither can requeue or promote it.
    assert await requeue_stalled_book_processing_if_needed(db, book=book) is False
    assert await repair_stale_completed_processing_state(db, book) is False
    await db.refresh(book)
    assert is_book_frozen(book) is True
    assert book.status == "failed"
