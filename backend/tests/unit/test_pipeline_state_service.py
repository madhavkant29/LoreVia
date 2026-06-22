from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.intelligence import ChapterSummary
from app.models.operations import BookProcessingRun, TaskExecution
from app.models.user import User
from app.services import pipeline_state_service
from app.services.task_execution_service import ensure_task_execution, get_or_create_processing_run


class _FakeExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


class _FakeDB:
    def __init__(self, chapters, chunk_count: int):
        self._chapters = chapters
        self._chunk_count = chunk_count

    async def execute(self, *_args, **_kwargs):
        return _FakeExecuteResult(self._chapters)

    async def scalar(self, *_args, **_kwargs):
        return self._chunk_count


def _build_book(*, started_at: datetime):
    return SimpleNamespace(
        id=uuid.uuid4(),
        status="processing",
        writer_workspace={"processing": {"started_at": started_at.isoformat()}},
    )


def _build_chapter(*, status: str = "queued", updated_at: datetime, processed: bool = False):
    return SimpleNamespace(
        processed=processed,
        analysis_state={"status": status, "updated_at": updated_at.isoformat()},
    )


async def _create_user(db) -> uuid.UUID:
    user = User(
        email=f"pipeline-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"pipeline{uuid.uuid4().hex[:8]}",
        password_hash="fake",
    )
    db.add(user)
    await db.flush()
    return user.id


async def _paused_processing_book(db, *, chapter_count: int = 2):
    user = User(
        email=f"continue-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"continue{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Continue",
        format="txt",
        s3_key=f"books/{uuid.uuid4()}.txt",
        status="processing",
        total_chapters=chapter_count,
        writer_workspace={"processing": {"status": "paused", "stage": "usage_limited"}},
    )
    db.add(book)
    await db.flush()
    chapters = []
    for number in range(1, chapter_count + 1):
        chapter = Chapter(
            book_id=book.id,
            number=number,
            title=f"Chapter {number}",
            s3_key=f"chapters/{book.id}/{number}.txt",
            word_count=100,
            processed=False,
        )
        db.add(chapter)
        chapters.append(chapter)
    await db.flush()
    run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        chapters_total=chapter_count,
    )
    run.status = "paused"
    run.pause_reason = "monthly_processed_words"
    run.resume_blockers = [{"kind": "monthly_processed_words"}]
    run.next_chapter_number = 1
    await db.commit()
    return user, book, chapters, run


@pytest.mark.asyncio
async def test_continue_keeps_run_paused_when_only_some_chapters_fit(db, monkeypatch):
    _user, book, chapters, run = await _paused_processing_book(db)

    async def reserve(_db, _user, *, source_id, **_kwargs):
        if source_id.endswith(":2"):
            from fastapi import HTTPException

            raise HTTPException(403, "Monthly processed-word allowance reached")
        return SimpleNamespace()

    extraction_dispatch = AsyncMock(return_value=1)
    analysis_dispatch = AsyncMock(return_value=0)
    monkeypatch.setattr(
        "app.services.processing_allowance_service.reserve_processing_words", reserve
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.dispatch_pending_extraction_tasks",
        extraction_dispatch,
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.dispatch_pending_analysis_tasks", analysis_dispatch
    )

    payload = await pipeline_state_service.continue_book_processing(db, book)
    await db.refresh(run)

    assert run.status == "paused"
    assert run.next_chapter_number == 2
    assert run.resume_blockers[0]["kind"] == "monthly_processed_words"
    assert payload["resume_available"] is True
    execution = await db.scalar(
        select(TaskExecution).where(
            TaskExecution.processing_run_id == run.id,
            TaskExecution.chapter_id == chapters[0].id,
        )
    )
    assert execution is not None and execution.status == "pending_dispatch"


@pytest.mark.asyncio
async def test_continue_resumes_paused_analysis_without_reextracting(db, monkeypatch):
    _user, book, chapters, run = await _paused_processing_book(db, chapter_count=1)
    chapters[0].processed = True
    analysis = await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=run,
        chapter_id=chapters[0].id,
        chapter_number=1,
        arguments={"book_id": str(book.id), "chapter_id": str(chapters[0].id)},
        feature="analysis",
    )
    analysis.status = "paused"
    run.pause_reason = "llm_token_limit"
    run.resume_blockers = [{"kind": "llm_tokens"}]
    await db.commit()
    extraction_dispatch = AsyncMock(return_value=0)
    analysis_dispatch = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "app.services.task_execution_service.dispatch_pending_extraction_tasks",
        extraction_dispatch,
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.dispatch_pending_analysis_tasks", analysis_dispatch
    )

    payload = await pipeline_state_service.continue_book_processing(db, book)
    await db.refresh(run)
    await db.refresh(analysis)

    assert run.status == "running"
    assert analysis.status == "pending_dispatch"
    assert payload["resume_available"] is False
    analysis_dispatch.assert_awaited_once()


def test_build_writer_workspace_response_preserves_processing_pipeline_fields():
    book = SimpleNamespace(
        title="Atlas",
        author="M. Author",
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "chapter_complete",
                "chapters_completed": 2,
                "chapters_total": 4,
                "is_fully_ready": False,
                "retry_actions": ["retry_analysis"],
                "pipeline": {
                    "extraction": {
                        "status": "succeeded",
                        "completed_chapters": 4,
                        "total_chapters": 4,
                    },
                    "analysis": {"status": "running", "completed_chapters": 2, "total_chapters": 4},
                },
            }
        },
    )

    payload = pipeline_state_service.build_writer_workspace_response(book)

    assert payload.processing is not None
    assert payload.processing.pipeline is not None
    assert payload.processing.pipeline.extraction is not None
    assert payload.processing.pipeline.extraction.status == "succeeded"
    assert payload.processing.pipeline.analysis is not None
    assert payload.processing.pipeline.analysis.status == "running"
    assert payload.processing.retry_actions == ["retry_analysis"]


def test_build_writer_workspace_update_merges_existing_workspace_with_updates():
    book = SimpleNamespace(
        title="Atlas",
        author="M. Author",
        writer_workspace={
            "goal_calendar": [
                {"id": "g1", "title": "Draft", "due_date": "2026-05-20", "completed": False}
            ],
            "processing": {"status": "processing", "stage": "queued"},
        },
    )

    updated = pipeline_state_service.build_writer_workspace_update(
        book,
        {
            "goal_calendar": [],
            "processing": {"status": "ready", "stage": "complete", "is_fully_ready": True},
        },
    )

    assert updated["goal_calendar"] == []
    assert updated["processing"]["status"] == "ready"
    assert updated["processing"]["is_fully_ready"] is True


@pytest.mark.asyncio
async def test_requeue_stalled_book_processing_if_needed_requeues_old_queued_books(monkeypatch):
    now = datetime.now(UTC)
    book = _build_book(started_at=now - timedelta(minutes=15))
    chapters = [
        _build_chapter(updated_at=now - timedelta(minutes=12)),
        _build_chapter(updated_at=now - timedelta(minutes=11)),
    ]
    db = _FakeDB(chapters, chunk_count=0)
    dispatch = AsyncMock()
    monkeypatch.setattr(pipeline_state_service, "_dispatch_durable_book_processing", dispatch)

    queued = await pipeline_state_service.requeue_stalled_book_processing_if_needed(
        db,
        book=book,
        now=now,
    )

    assert queued is True
    dispatch.assert_awaited_once_with(
        db,
        book,
        run_kind="stalled_recovery",
        identity_suffix=f"stalled-{int(now.timestamp())}",
    )


@pytest.mark.asyncio
async def test_requeue_stalled_book_processing_if_needed_skips_recent_jobs(monkeypatch):
    now = datetime.now(UTC)
    book = _build_book(started_at=now - timedelta(minutes=2))
    chapters = [_build_chapter(updated_at=now - timedelta(minutes=1))]
    db = _FakeDB(chapters, chunk_count=0)
    dispatch = AsyncMock()
    monkeypatch.setattr(pipeline_state_service, "_dispatch_durable_book_processing", dispatch)

    queued = await pipeline_state_service.requeue_stalled_book_processing_if_needed(
        db,
        book=book,
        now=now,
    )

    assert queued is False
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_requeue_stalled_book_processing_if_needed_skips_books_with_chunks():
    now = datetime.now(UTC)
    book = _build_book(started_at=now - timedelta(minutes=15))
    chapters = [_build_chapter(updated_at=now - timedelta(minutes=10))]
    db = _FakeDB(chapters, chunk_count=4)

    queued = await pipeline_state_service.requeue_stalled_book_processing_if_needed(
        db,
        book=book,
        now=now,
    )

    assert queued is False


@pytest.mark.asyncio
async def test_repair_stale_completed_processing_state_marks_normal_upload_ready(db, monkeypatch):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Les",
        format="txt",
        s3_key="les.txt",
        status="processing",
        is_editor_project=False,
        total_chapters=2,
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "chapter_complete",
                "chapters_completed": 1,
                "chapters_total": 2,
                "pipeline": {
                    "extraction": {
                        "status": "running",
                        "completed_chapters": 1,
                        "total_chapters": 2,
                    },
                    "analysis": {
                        "status": "succeeded",
                        "completed_chapters": 2,
                        "total_chapters": 2,
                    },
                },
            }
        },
    )
    chapters = [
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=1,
            s3_key="ch1.txt",
            word_count=100,
            processed=True,
        ),
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=2,
            s3_key="ch2.txt",
            word_count=120,
            processed=True,
        ),
    ]
    db.add(book)
    db.add_all(chapters)
    await db.flush()
    db.add_all(
        [
            ChapterSummary(
                id=uuid.uuid4(), chapter_id=chapters[0].id, mode="detailed", content="One"
            ),
            ChapterSummary(
                id=uuid.uuid4(), chapter_id=chapters[1].id, mode="detailed", content="Two"
            ),
        ]
    )
    await db.commit()
    cache_dirty: list[str] = []
    dashboard_dirty: list[str] = []
    monkeypatch.setattr(
        pipeline_state_service,
        "mark_book_cache_dirty",
        lambda book_id: cache_dirty.append(str(book_id)) or _async_none(),
    )
    monkeypatch.setattr(
        pipeline_state_service,
        "mark_user_dashboard_cache_dirty",
        lambda user_id: dashboard_dirty.append(str(user_id)) or _async_none(),
    )

    repaired = await pipeline_state_service.repair_stale_completed_processing_state(db, book)

    assert repaired is True
    assert book.status == "ready"
    processing = book.writer_workspace["processing"]
    assert processing["status"] == "ready"
    assert processing["stage"] == "complete"
    assert processing["chapters_completed"] == 2
    assert processing["chapters_total"] == 2
    assert processing["progress_pct"] == 100.0
    assert processing["is_fully_ready"] is True
    assert processing["pipeline"]["extraction"]["status"] == "succeeded"
    assert processing["pipeline"]["analysis"]["status"] == "succeeded"
    assert processing["retry_actions"] == []
    assert cache_dirty == [str(book.id)]
    assert dashboard_dirty == [str(user_id)]


@pytest.mark.asyncio
async def test_repair_stale_completed_processing_state_waits_for_detailed_summaries(
    db, monkeypatch
):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Incomplete",
        format="txt",
        s3_key="incomplete.txt",
        status="processing",
        is_editor_project=False,
        total_chapters=2,
        writer_workspace={"processing": {"status": "processing", "stage": "analysis"}},
    )
    chapters = [
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=1,
            s3_key="ch1.txt",
            word_count=100,
            processed=True,
        ),
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=2,
            s3_key="ch2.txt",
            word_count=120,
            processed=True,
        ),
    ]
    db.add(book)
    db.add_all(chapters)
    await db.flush()
    db.add(
        ChapterSummary(id=uuid.uuid4(), chapter_id=chapters[0].id, mode="detailed", content="One")
    )
    await db.commit()
    monkeypatch.setattr(
        pipeline_state_service, "mark_book_cache_dirty", lambda *_args: _async_none()
    )
    monkeypatch.setattr(
        pipeline_state_service, "mark_user_dashboard_cache_dirty", lambda *_args: _async_none()
    )

    repaired = await pipeline_state_service.repair_stale_completed_processing_state(db, book)

    assert repaired is False
    assert book.status == "processing"


@pytest.mark.asyncio
async def test_repair_stale_completed_processing_state_counts_distinct_chapter_numbers(
    db, monkeypatch
):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Duplicated",
        format="txt",
        s3_key="duplicated.txt",
        status="processing",
        is_editor_project=False,
        total_chapters=2,
        writer_workspace={"processing": {"status": "processing", "stage": "chapter_complete"}},
    )
    chapters = [
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=1,
            s3_key="ch1-a.txt",
            word_count=100,
            processed=True,
        ),
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=1,
            s3_key="ch1-b.txt",
            word_count=100,
            processed=True,
        ),
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=1,
            s3_key="ch1-c.txt",
            word_count=100,
            processed=True,
        ),
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=2,
            s3_key="ch2-a.txt",
            word_count=120,
            processed=True,
        ),
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=2,
            s3_key="ch2-b.txt",
            word_count=120,
            processed=True,
        ),
        Chapter(
            id=uuid.uuid4(),
            book_id=book.id,
            number=2,
            s3_key="ch2-c.txt",
            word_count=120,
            processed=True,
        ),
    ]
    db.add(book)
    db.add_all(chapters)
    await db.flush()
    db.add_all(
        [
            ChapterSummary(
                id=uuid.uuid4(), chapter_id=chapters[0].id, mode="detailed", content="One"
            ),
            ChapterSummary(
                id=uuid.uuid4(), chapter_id=chapters[3].id, mode="detailed", content="Two"
            ),
        ]
    )
    await db.commit()
    monkeypatch.setattr(
        pipeline_state_service, "mark_book_cache_dirty", lambda *_args: _async_none()
    )
    monkeypatch.setattr(
        pipeline_state_service, "mark_user_dashboard_cache_dirty", lambda *_args: _async_none()
    )

    repaired = await pipeline_state_service.repair_stale_completed_processing_state(db, book)

    assert repaired is True
    assert book.status == "ready"
    assert book.writer_workspace["processing"]["chapters_total"] == 2
    assert book.writer_workspace["processing"]["chapters_completed"] == 2
    assert book.writer_workspace["processing"]["pipeline"]["analysis"]["completed_chapters"] == 2


async def _async_none():
    return None


class _RetryDB:
    def __init__(self):
        self.commits = 0
        self.refreshed = []

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshed.append(value)


def test_retry_state_helpers_normalize_actions_errors_and_chapter_timestamps():
    book = SimpleNamespace(
        status="processing",
        writer_workspace={
            "processing": {
                "retry_actions": [" retry_analysis ", "", None],
                "last_error": "  provider failed  ",
            }
        },
    )
    assert pipeline_state_service._book_processing_retry_actions(book) == ["retry_analysis", "None"]
    assert pipeline_state_service._book_processing_last_error(book) == "provider failed"
    assert pipeline_state_service._book_has_retryable_processing_state(book) is True
    assert (
        pipeline_state_service._book_has_retryable_processing_state(
            SimpleNamespace(status="failed", writer_workspace=None)
        )
        is True
    )

    aware = datetime.now(UTC)
    assert (
        pipeline_state_service._parse_chapter_status_updated_at(
            SimpleNamespace(analysis_state={"updated_at": aware.isoformat()})
        )
        == aware
    )
    naive = pipeline_state_service._parse_chapter_status_updated_at(
        SimpleNamespace(analysis_state={"updated_at": "2026-01-01T12:00:00"})
    )
    assert naive is not None and naive.tzinfo is UTC
    assert (
        pipeline_state_service._parse_chapter_status_updated_at(
            SimpleNamespace(analysis_state={"updated_at": "bad"})
        )
        is None
    )
    assert (
        pipeline_state_service._parse_chapter_status_updated_at(
            SimpleNamespace(analysis_state=None)
        )
        is None
    )


@pytest.mark.asyncio
async def test_enqueue_processing_state_repair_deduplicates_and_queues(monkeypatch):
    from app.workers.tasks import maintenance_tasks

    book = SimpleNamespace(id=uuid.uuid4(), status="ready")
    assert await pipeline_state_service.enqueue_processing_state_repair_if_needed(book) is False

    book.status = "processing"

    async def cache_miss(*_args, **_kwargs):
        return False

    monkeypatch.setattr(pipeline_state_service, "cache_set_if_absent", cache_miss)
    assert await pipeline_state_service.enqueue_processing_state_repair_if_needed(book) is False

    async def cache_claim(*_args, **_kwargs):
        return True

    apply_async = Mock()
    monkeypatch.setattr(pipeline_state_service, "cache_set_if_absent", cache_claim)
    monkeypatch.setattr(maintenance_tasks.repair_processing_books_task, "apply_async", apply_async)
    assert await pipeline_state_service.enqueue_processing_state_repair_if_needed(book) is True
    apply_async.assert_called_once_with(kwargs={"book_id": str(book.id)}, queue="intelligence")


@pytest.mark.asyncio
async def test_retry_book_processing_restarts_failed_extraction_and_invalidates_caches(monkeypatch):
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="failed",
        total_chapters=3,
        writer_workspace={
            "processing": {"last_error": "failure", "retry_actions": ["retry_extraction"]}
        },
    )
    db = _RetryDB()
    dispatch = AsyncMock()
    dirty = []
    monkeypatch.setattr(pipeline_state_service, "_dispatch_durable_book_processing", dispatch)
    monkeypatch.setattr(
        pipeline_state_service,
        "update_book_processing_state",
        lambda *_args, **_kwargs: {"processing": {"status": "processing"}},
    )
    monkeypatch.setattr(
        pipeline_state_service,
        "build_book_processing_payload",
        lambda _book: {"status": "processing"},
    )
    monkeypatch.setattr(
        pipeline_state_service,
        "mark_book_cache_dirty",
        lambda value: dirty.append(("book", value)) or _async_none(),
    )
    monkeypatch.setattr(
        pipeline_state_service,
        "mark_user_dashboard_cache_dirty",
        lambda value: dirty.append(("user", value)) or _async_none(),
    )

    result = await pipeline_state_service.retry_book_processing(db, book)
    assert result == {"status": "processing"}
    assert book.status == "processing"
    dispatch.assert_awaited_once_with(db, book, run_kind="manual_retry")
    assert db.commits == 1 and db.refreshed == [book]
    assert dirty == [("book", str(book.id)), ("user", str(book.user_id))]


@pytest.mark.asyncio
async def test_retry_book_processing_rebuilds_editor_project_from_saved_chapters(monkeypatch):
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="ready",
        total_chapters=2,
        is_editor_project=True,
        writer_workspace={
            "processing": {
                "status": "cancelled",
                "last_error": "chapter removed",
                "retry_actions": [],
            }
        },
    )
    db = _RetryDB()
    calls = []

    async def prepare(value_db, value_book, *, reason):
        calls.append(("prepare", value_db, value_book, reason))
        value_book.status = "processing"
        value_book.writer_workspace = {
            "processing": {"status": "processing", "stage": "extraction"}
        }
        return "run-current"

    async def dispatch(value_db, value_book):
        calls.append(("dispatch", value_db, value_book))
        return 2, 500

    from app.services import editor_project_service

    monkeypatch.setattr(editor_project_service, "prepare_rebuild", prepare)
    monkeypatch.setattr(editor_project_service, "dispatch_rebuild", dispatch)
    monkeypatch.setattr(
        pipeline_state_service,
        "_dispatch_durable_book_processing",
        AsyncMock(side_effect=AssertionError("upload pipeline must not run")),
    )
    monkeypatch.setattr(
        pipeline_state_service,
        "build_book_processing_payload",
        lambda _book: {"status": "processing"},
    )
    monkeypatch.setattr(
        pipeline_state_service, "mark_book_cache_dirty", lambda *_args: _async_none()
    )
    monkeypatch.setattr(
        pipeline_state_service, "mark_user_dashboard_cache_dirty", lambda *_args: _async_none()
    )

    assert await pipeline_state_service.retry_book_processing(db, book) == {"status": "processing"}
    assert [call[0] for call in calls] == ["prepare", "dispatch"]
    assert calls[0][3] == "manual_reprocess"


@pytest.mark.asyncio
async def test_retry_book_processing_uses_repair_path_and_handles_non_retryable(monkeypatch):
    no_retry = SimpleNamespace(
        status="processing", writer_workspace={"processing": {}}, id=uuid.uuid4()
    )
    assert await pipeline_state_service.retry_book_processing(_RetryDB(), no_retry) is None

    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="processing",
        total_chapters=2,
        writer_workspace={
            "processing": {"last_error": "stale", "retry_actions": ["wait_for_analysis"]}
        },
    )
    db = _RetryDB()
    repairs = []

    async def enqueue(value):
        repairs.append(value)
        return True

    monkeypatch.setattr(
        pipeline_state_service, "enqueue_processing_state_repair_if_needed", enqueue
    )
    monkeypatch.setattr(pipeline_state_service, "build_book_processing_payload", lambda _book: None)
    monkeypatch.setattr(
        pipeline_state_service, "mark_book_cache_dirty", lambda *_args: _async_none()
    )
    monkeypatch.setattr(
        pipeline_state_service, "mark_user_dashboard_cache_dirty", lambda *_args: _async_none()
    )
    assert await pipeline_state_service.retry_book_processing(db, book) == {}
    assert repairs == [book]


def test_processing_pipeline_failure_detection_handles_status_and_failed_chapters():
    assert (
        pipeline_state_service._processing_pipeline_has_blocking_failure(
            {"pipeline": {"analysis": {"status": "failed"}}}
        )
        is True
    )
    assert (
        pipeline_state_service._processing_pipeline_has_blocking_failure(
            {"pipeline": {"extraction": {"failed_chapters": [2]}}}
        )
        is True
    )
    assert (
        pipeline_state_service._processing_pipeline_has_blocking_failure(
            {"pipeline": {"analysis": {"status": "running"}}}
        )
        is False
    )
