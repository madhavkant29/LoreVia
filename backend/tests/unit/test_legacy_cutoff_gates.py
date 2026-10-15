"""Deployment transition gate: pre-cutoff work must never start provider calls.

These tests exercise every choke point that holds legacy (pre-cutoff) work
between the deployment and the one-time global freeze. Fresh (post-cutoff)
work must be unaffected.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.models.book import Book, Chapter
from app.models.operations import ManuscriptImportJob, TaskDispatchOutbox, TaskExecution
from app.models.user import AdminAuditEvent, ProcessingUsageEvent, User
from app.services import task_execution_service
from app.services.book_freeze_service import (
    ACTION_CUTOFF_RECORDED,
    LEGACY_INCOMPLETE_MESSAGE,
    book_created_before_cutoff,
    book_is_legacy_incomplete,
    record_freeze_cutoff,
)


@pytest.fixture(autouse=True)
async def _clear_cutoff_marker(db):
    """The legacy cutoff marker is global; keep tests independent."""
    await db.execute(
        delete(AdminAuditEvent).where(AdminAuditEvent.action_type == ACTION_CUTOFF_RECORDED)
    )
    await db.commit()
    yield
    await db.execute(
        delete(AdminAuditEvent).where(AdminAuditEvent.action_type == ACTION_CUTOFF_RECORDED)
    )
    await db.commit()


async def _create_user(db) -> User:
    user = User(
        email=f"gate-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"gate{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    return user


async def _create_book(
    db,
    *,
    user: User,
    status: str = "processing",
    age_days: float = 10,
    chapter_count: int = 0,
    editor_project: bool = False,
) -> Book:
    created_at = datetime.now(UTC) - timedelta(days=age_days)
    book = Book(
        user_id=user.id,
        title=f"Gate {status}",
        format="txt",
        work_type="novel",
        s3_key=f"books/{user.id}/{uuid.uuid4()}/manuscript.txt",
        status=status,
        mode="author",
        language="en",
        source_kind="single_upload",
        total_chapters=chapter_count,
        is_editor_project=editor_project,
        created_at=created_at,
        writer_workspace={
            "processing": {
                "status": "processing" if status == "processing" else "failed",
                "stage": "queued",
                "started_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
            }
        },
    )
    db.add(book)
    await db.flush()
    for number in range(1, chapter_count + 1):
        db.add(
            Chapter(
                book_id=book.id,
                number=number,
                title=f"Chapter {number}",
                s3_key=f"books/{user.id}/{uuid.uuid4()}/chapter-{number}.txt",
                word_count=5,
                processed=False,
                analysis_state={"status": "queued"},
            )
        )
    await db.flush()
    return book


def _execution(book: Book | None, *, task_name: str, status: str, created_at: datetime) -> TaskExecution:
    return TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name=task_name,
        user_id=book.user_id if book is not None else None,
        book_id=book.id if book is not None else None,
        status=status,
        created_at=created_at,
    )


def test_legacy_incomplete_helpers() -> None:
    cutoff = datetime(2026, 10, 1, tzinfo=UTC)
    legacy = SimpleNamespace(created_at=datetime(2026, 9, 1, tzinfo=UTC), status="failed")
    fresh = SimpleNamespace(created_at=datetime(2026, 10, 2, tzinfo=UTC), status="failed")
    complete = SimpleNamespace(created_at=datetime(2026, 9, 1, tzinfo=UTC), status="ready")

    assert book_created_before_cutoff(legacy, cutoff) is True
    assert book_created_before_cutoff(fresh, cutoff) is False
    assert book_created_before_cutoff(legacy, None) is False
    assert book_is_legacy_incomplete(legacy, cutoff) is True
    assert book_is_legacy_incomplete(fresh, cutoff) is False
    assert book_is_legacy_incomplete(complete, cutoff) is False
    assert book_is_legacy_incomplete(legacy, None) is False


@pytest.mark.asyncio
async def test_ensure_project_writable_blocks_legacy_incomplete_books(db) -> None:
    from app.services.processing_allowance_service import ensure_project_writable

    user = await _create_user(db)
    legacy = await _create_book(db, user=user, status="failed")
    fresh = await _create_book(db, user=user, status="failed", age_days=0)
    legacy_ready = await _create_book(db, user=user, status="ready")
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))

    with pytest.raises(HTTPException) as exc:
        await ensure_project_writable(db, legacy)
    assert exc.value.status_code == 409
    assert exc.value.detail == LEGACY_INCOMPLETE_MESSAGE

    await ensure_project_writable(db, fresh)
    await ensure_project_writable(db, legacy_ready)


@pytest.mark.asyncio
async def test_retry_and_continue_reject_legacy_incomplete_books(db) -> None:
    from app.services.pipeline_state_service import (
        continue_book_processing,
        retry_book_processing,
    )

    user = await _create_user(db)
    legacy = await _create_book(db, user=user, status="failed")
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))

    with pytest.raises(HTTPException) as retry_exc:
        await retry_book_processing(db, legacy)
    assert retry_exc.value.status_code == 409
    assert retry_exc.value.detail == LEGACY_INCOMPLETE_MESSAGE

    with pytest.raises(HTTPException) as continue_exc:
        await continue_book_processing(db, legacy)
    assert continue_exc.value.status_code == 409
    assert continue_exc.value.detail == LEGACY_INCOMPLETE_MESSAGE


@pytest.mark.asyncio
async def test_requeue_gate_skips_pre_cutoff_books(monkeypatch, db) -> None:
    from app.services import pipeline_state_service

    dispatched: list[uuid.UUID] = []

    async def record_dispatch(db_session, book, *, run_kind, identity_suffix=None):
        dispatched.append(book.id)
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(
        pipeline_state_service, "_dispatch_durable_book_processing", record_dispatch
    )

    user = await _create_user(db)
    legacy = await _create_book(db, user=user, status="processing", chapter_count=1)
    fresh = await _create_book(db, user=user, status="processing", age_days=0, chapter_count=1)
    for book in (legacy, fresh):
        workspace = dict(book.writer_workspace)
        processing = dict(workspace["processing"])
        processing["started_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        workspace["processing"] = processing
        book.writer_workspace = workspace
    await db.commit()
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))

    assert await pipeline_state_service.requeue_stalled_book_processing_if_needed(
        db, book=legacy
    ) is False
    assert dispatched == []

    assert await pipeline_state_service.requeue_stalled_book_processing_if_needed(
        db, book=fresh
    ) is True
    assert dispatched == [fresh.id]


@pytest.mark.asyncio
async def test_claim_dismisses_pre_cutoff_executions(db) -> None:
    user = await _create_user(db)
    book = await _create_book(db, user=user, status="processing")
    execution = _execution(
        book,
        task_name="extraction_tasks.process_book",
        status="queued",
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    db.add(execution)
    await db.flush()
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))

    claimed = await task_execution_service.claim_task_execution(
        db, str(execution.id), str(uuid.uuid4())
    )

    assert claimed is False
    await db.refresh(execution)
    assert execution.status == "dismissed"
    assert execution.error_category == "legacy_cutoff"


@pytest.mark.asyncio
async def test_dispatchers_ignore_pre_cutoff_executions(db) -> None:
    user = await _create_user(db)
    book = await _create_book(db, user=user, status="processing")
    legacy_at = datetime.now(UTC) - timedelta(days=5)
    extraction = _execution(
        book, task_name="extraction_tasks.process_book", status="pending_dispatch", created_at=legacy_at
    )
    analysis = _execution(
        book, task_name="analysis_tasks.analyse_chapter", status="pending_dispatch", created_at=legacy_at
    )
    embedding = _execution(
        book,
        task_name="embedding_tasks.update_character_embedding",
        status="pending_dispatch",
        created_at=legacy_at,
    )
    db.add_all([extraction, analysis, embedding])
    await db.flush()
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))

    await task_execution_service.dispatch_pending_extraction_tasks(db)
    await task_execution_service.dispatch_pending_analysis_tasks(db)
    await task_execution_service.dispatch_pending_embedding_tasks(db)

    for row in (extraction, analysis, embedding):
        await db.refresh(row)
        assert row.status == "pending_dispatch"


@pytest.mark.asyncio
async def test_publish_cancels_pre_cutoff_outbox_rows(monkeypatch, db) -> None:
    user = await _create_user(db)
    book = await _create_book(db, user=user, status="processing")
    execution = _execution(
        book,
        task_name="extraction_tasks.process_book",
        status="queued",
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    db.add(execution)
    await db.flush()
    row = TaskDispatchOutbox(
        execution_id=execution.id,
        task_name=execution.task_name,
        queue="legacy-gate-test",
        payload_json={"execution_id": str(execution.id)},
        status="pending",
        available_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db.add(row)
    await db.flush()
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))

    def _unexpected_publish(_row):  # pragma: no cover - failure path
        raise AssertionError("pre-cutoff outbox rows must never be published")

    monkeypatch.setattr(task_execution_service, "_publish_outbox_task", _unexpected_publish)

    await task_execution_service.publish_task_dispatch_outbox(
        db, queues=("legacy-gate-test",), limit=10
    )

    await db.refresh(row)
    assert row.status == "cancelled"
    assert row.last_error == "legacy_cutoff"


@pytest.mark.asyncio
async def test_import_job_dispatcher_and_task_hold_pre_cutoff_jobs(db) -> None:
    from app.services.manuscript_import_job_service import (
        dispatch_pending_manuscript_import_jobs,
        process_manuscript_import_job,
    )

    user = await _create_user(db)
    book = await _create_book(db, user=user, status="pending")
    created_at = datetime.now(UTC) - timedelta(days=5)
    job = ManuscriptImportJob(
        user_id=user.id,
        book_id=book.id,
        status="queued",
        request_json={"replace_existing": False},
        created_at=created_at,
        updated_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db.add(job)
    await db.flush()
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))

    await dispatch_pending_manuscript_import_jobs(db)
    await db.refresh(job)
    assert job.status == "queued"
    assert job.celery_task_id is None

    result = await process_manuscript_import_job(db, job.id)
    assert result["status"] == "held_legacy_cutoff"
    await db.refresh(job)
    assert job.status == "queued"


@pytest.mark.asyncio
async def test_editor_retry_reserves_processed_words(monkeypatch, db) -> None:
    from app.services.editor_project_service import (
        dispatch_manual_rebuild_with_reservations,
    )

    published: list[object] = []
    monkeypatch.setattr(
        task_execution_service, "_publish_outbox_task", lambda row: published.append(row)
    )

    user = await _create_user(db)
    book = await _create_book(
        db, user=user, status="failed", chapter_count=2, editor_project=True
    )
    await db.commit()

    chapters_queued, total_words = await dispatch_manual_rebuild_with_reservations(db, book)

    assert chapters_queued == 2
    assert total_words == 10
    reservations = (
        (
            await db.execute(
                select(ProcessingUsageEvent).where(
                    ProcessingUsageEvent.book_id == book.id,
                    ProcessingUsageEvent.usage_kind == "manual_reprocess",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(reservations) == 2
    assert all(event.status == "reserved" for event in reservations)
    executions = (
        (
            await db.execute(select(TaskExecution).where(TaskExecution.book_id == book.id))
        )
        .scalars()
        .all()
    )
    execution_arguments = {
        (row.arguments_json or {}).get("processing_reservation_id") for row in executions
    }
    assert execution_arguments == {str(event.id) for event in reservations}
