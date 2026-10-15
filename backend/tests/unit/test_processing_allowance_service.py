import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.models.book import Book
from app.models.operations import BookProcessingRun, TaskExecution
from app.models.user import ProcessingUsageEvent, User
from app.services.processing_allowance_service import (
    CONSUMED_STATUS,
    RELEASED_STATUS,
    ProcessingReservationRequest,
    ensure_project_writable,
    release_stale_processing_reservations,
    reserve_processing_word_batch,
    reserve_processing_words,
    summarize_processing_allowances,
)


async def test_archived_projects_are_read_only(db) -> None:
    await ensure_project_writable(
        db,
        SimpleNamespace(archived_at=None, status="ready", writer_workspace={}),
    )
    with pytest.raises(HTTPException) as exc:
        await ensure_project_writable(
            db,
            SimpleNamespace(
                archived_at=datetime.now(UTC),
                status="ready",
                writer_workspace={},
            ),
        )
    assert exc.value.status_code == 409


async def _user(db) -> User:
    user = User(
        email=f"allowance-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"allowance{uuid.uuid4().hex[:8]}",
        password_hash="fake",
    )
    db.add(user)
    await db.flush()
    return user


async def test_summarize_processing_allowances_uses_one_statement(monkeypatch) -> None:
    class _Result:
        def one(self):
            return SimpleNamespace(
                active_manuscript_words=100,
                active_world_words=25,
                book_storage=2048,
                world_storage=512,
                monthly_processed_words=75,
            )

    class _DB:
        def __init__(self):
            self.execute_count = 0
            self.statements = []

        async def execute(self, statement):
            self.execute_count += 1
            self.statements.append(statement)
            return _Result()

    db = _DB()
    user = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(
        "app.services.processing_allowance_service._tier_limits",
        lambda _user: (1000, 2000, 3000),
    )

    summary = await summarize_processing_allowances(db, user)

    assert db.execute_count == 1
    assert summary.active_analyzed_words == 125
    assert summary.monthly_processed_words == 75
    assert summary.source_storage_bytes == 2560
    assert summary.active_word_limit == 1000


async def test_processing_reservation_is_idempotent_and_counted(db) -> None:
    user = await _user(db)
    event, first_summary = await reserve_processing_words(
        db,
        user,
        book_id=None,
        usage_kind="test",
        source_id="same-source",
        word_count=750,
    )
    duplicate, second_summary = await reserve_processing_words(
        db,
        user,
        book_id=None,
        usage_kind="test",
        source_id="same-source",
        word_count=750,
    )
    assert duplicate.id == event.id
    assert first_summary.monthly_processed_words == 750
    assert second_summary.monthly_processed_words == 750


async def test_processing_reservation_batch_is_atomic_and_idempotent(db, monkeypatch) -> None:
    user = await _user(db)
    monkeypatch.setattr(settings, "PROCESSING_ALLOWANCES_MODE", "enforce")
    monkeypatch.setattr(settings, "AUTHOR_MONTHLY_PROCESSED_WORD_LIMIT", 100)
    requests = [
        ProcessingReservationRequest(source_id="batch:1", word_count=40),
        ProcessingReservationRequest(source_id="batch:2", word_count=60),
    ]

    events, summary = await reserve_processing_word_batch(
        db,
        user,
        book_id=None,
        usage_kind="manual_reprocess",
        requests=requests,
    )
    duplicates, duplicate_summary = await reserve_processing_word_batch(
        db,
        user,
        book_id=None,
        usage_kind="manual_reprocess",
        requests=requests,
    )

    assert [event.id for event in duplicates] == [event.id for event in events]
    assert summary.monthly_processed_words == 100
    assert duplicate_summary.monthly_processed_words == 100

    with pytest.raises(HTTPException):
        await reserve_processing_word_batch(
            db,
            user,
            book_id=None,
            usage_kind="manual_reprocess",
            requests=[
                ProcessingReservationRequest(source_id="blocked:1", word_count=1),
                ProcessingReservationRequest(source_id="blocked:2", word_count=1),
            ],
        )
    blocked_count = await db.scalar(
        select(func.count(ProcessingUsageEvent.id)).where(
            ProcessingUsageEvent.source_id.startswith("blocked:")
        )
    )
    assert int(blocked_count or 0) == 0


async def test_stale_reservations_are_released(db) -> None:
    user = await _user(db)
    event = ProcessingUsageEvent(
        user_id=user.id,
        usage_kind="test",
        source_id="stale-source",
        word_count=500,
        status="reserved",
        reserved_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db.add(event)
    await db.flush()
    released = await release_stale_processing_reservations(db, older_than=timedelta(hours=1))
    await db.flush()
    assert released == 1
    assert event.status == RELEASED_STATUS
    assert (await summarize_processing_allowances(db, user)).monthly_processed_words == 0


async def test_stale_reservations_follow_durable_task_outcomes(db) -> None:
    user = await _user(db)
    book = Book(
        user_id=user.id,
        title="Reservation reconciliation",
        format="manual",
        s3_key="reservation-reconciliation.txt",
        status="processing",
    )
    db.add(book)
    await db.flush()
    run = BookProcessingRun(user_id=user.id, book_id=book.id, chapters_total=3)
    db.add(run)
    await db.flush()
    succeeded = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="extraction_tasks.process_chapter",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        chapter_number=1,
        status="succeeded",
    )
    paused = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="extraction_tasks.process_chapter",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        chapter_number=2,
        status="paused",
    )
    succeeded_analysis = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="analysis_tasks.analyse_chapter",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        chapter_number=3,
        status="succeeded",
    )
    db.add_all([succeeded, paused, succeeded_analysis])
    await db.flush()
    stale_at = datetime.now(UTC) - timedelta(hours=2)
    succeeded_event = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id="reconcile:succeeded",
        word_count=100,
        task_id=str(succeeded.id),
        status="reserved",
        reserved_at=stale_at,
    )
    paused_event = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id="reconcile:paused",
        word_count=100,
        task_id=str(paused.id),
        status="reserved",
        reserved_at=stale_at,
    )
    orphaned_event = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id="reconcile:orphaned",
        word_count=100,
        status="reserved",
        reserved_at=stale_at,
    )
    non_extraction_event = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id="reconcile:non-extraction",
        word_count=100,
        task_id=str(succeeded_analysis.id),
        status="reserved",
        reserved_at=stale_at,
    )
    db.add_all([succeeded_event, paused_event, orphaned_event, non_extraction_event])
    await db.flush()

    released = await release_stale_processing_reservations(db, older_than=timedelta(hours=1))
    await db.flush()

    assert released == 2
    assert succeeded_event.status == CONSUMED_STATUS
    assert paused_event.status == "reserved"
    assert orphaned_event.status == RELEASED_STATUS
    assert non_extraction_event.status == RELEASED_STATUS


@pytest.mark.parametrize(
    ("usage_kind", "source_prefix", "run_kind"),
    (
        ("manual_reprocess", "manual", "manual_reprocess"),
        ("auto_first_reprocess", "auto-first", "auto_first_reprocess"),
    ),
)
async def test_stale_unlinked_reprocess_reservation_fails_partial_dispatch_run(
    db,
    usage_kind,
    source_prefix,
    run_kind,
) -> None:
    user = await _user(db)
    rebuild_run_id = uuid.uuid4().hex
    book = Book(
        user_id=user.id,
        title="Crashed dispatch",
        format="manual",
        s3_key="crashed-dispatch.txt",
        status="processing",
        is_editor_project=True,
        writer_workspace={
            "reprocess": {},
            "processing": {
                "status": "processing",
                "rebuild_run_id": rebuild_run_id,
            },
        },
    )
    db.add(book)
    await db.flush()
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind=run_kind,
        rebuild_run_id=rebuild_run_id,
        chapters_total=2,
    )
    db.add(run)
    await db.flush()
    queued = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="extraction_tasks.process_chapter",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        rebuild_run_id=rebuild_run_id,
        chapter_number=1,
        status="queued",
    )
    db.add(queued)
    await db.flush()
    stale_at = datetime.now(UTC) - timedelta(hours=2)
    linked = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind=usage_kind,
        source_id=f"{source_prefix}:{rebuild_run_id}:chapter-1",
        word_count=100,
        task_id=str(queued.id),
        status="reserved",
        reserved_at=datetime.now(UTC),
    )
    orphaned = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind=usage_kind,
        source_id=f"{source_prefix}:{rebuild_run_id}:chapter-2",
        word_count=100,
        status="reserved",
        reserved_at=stale_at,
    )
    db.add_all([linked, orphaned])
    await db.flush()

    released = await release_stale_processing_reservations(
        db,
        older_than=timedelta(hours=1),
    )
    await db.flush()

    await db.refresh(book)
    assert released == 2
    assert linked.status == RELEASED_STATUS
    assert orphaned.status == RELEASED_STATUS
    assert book.status == "failed"
    assert book.writer_workspace["processing"].get("rebuild_run_id") is None


async def test_concurrent_reservations_cannot_exceed_limit(db, monkeypatch) -> None:
    user = await _user(db)
    await db.commit()
    monkeypatch.setattr(settings, "PROCESSING_ALLOWANCES_MODE", "enforce")
    monkeypatch.setattr(settings, "AUTHOR_MONTHLY_PROCESSED_WORD_LIMIT", 1000)
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)

    async def reserve(source_id: str):
        async with sessions() as session:
            local_user = await session.get(User, user.id)
            try:
                await reserve_processing_words(
                    session,
                    local_user,
                    book_id=None,
                    usage_kind="concurrent-test",
                    source_id=source_id,
                    word_count=750,
                )
                await session.commit()
                return "reserved"
            except HTTPException:
                await session.rollback()
                return "blocked"

    results = await asyncio.gather(reserve("concurrent-a"), reserve("concurrent-b"))
    assert sorted(results) == ["blocked", "reserved"]
    counted = await db.scalar(
        select(func.coalesce(func.sum(ProcessingUsageEvent.word_count), 0)).where(
            ProcessingUsageEvent.user_id == user.id,
            ProcessingUsageEvent.status.in_(("reserved", "consumed")),
        )
    )
    assert int(counted or 0) == 750
