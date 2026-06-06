from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.intelligence import ChapterSummary
from app.models.user import User
from app.services import pipeline_state_service


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
                    "extraction": {"status": "succeeded", "completed_chapters": 4, "total_chapters": 4},
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
            "goal_calendar": [{"id": "g1", "title": "Draft", "due_date": "2026-05-20", "completed": False}],
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
    apply_async = Mock()
    monkeypatch.setattr(pipeline_state_service.process_book_task, "apply_async", apply_async)

    queued = await pipeline_state_service.requeue_stalled_book_processing_if_needed(
        db,
        book=book,
        now=now,
    )

    assert queued is True
    apply_async.assert_called_once_with(args=[str(book.id)], queue="extraction")


@pytest.mark.asyncio
async def test_requeue_stalled_book_processing_if_needed_skips_recent_jobs(monkeypatch):
    now = datetime.now(UTC)
    book = _build_book(started_at=now - timedelta(minutes=2))
    chapters = [_build_chapter(updated_at=now - timedelta(minutes=1))]
    db = _FakeDB(chapters, chunk_count=0)
    apply_async = Mock()
    monkeypatch.setattr(pipeline_state_service.process_book_task, "apply_async", apply_async)

    queued = await pipeline_state_service.requeue_stalled_book_processing_if_needed(
        db,
        book=book,
        now=now,
    )

    assert queued is False
    apply_async.assert_not_called()


@pytest.mark.asyncio
async def test_requeue_stalled_book_processing_if_needed_skips_books_with_chunks(monkeypatch):
    now = datetime.now(UTC)
    book = _build_book(started_at=now - timedelta(minutes=15))
    chapters = [_build_chapter(updated_at=now - timedelta(minutes=10))]
    db = _FakeDB(chapters, chunk_count=4)
    apply_async = Mock()
    monkeypatch.setattr(pipeline_state_service.process_book_task, "apply_async", apply_async)

    queued = await pipeline_state_service.requeue_stalled_book_processing_if_needed(
        db,
        book=book,
        now=now,
    )

    assert queued is False
    apply_async.assert_not_called()


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
                    "extraction": {"status": "running", "completed_chapters": 1, "total_chapters": 2},
                    "analysis": {"status": "succeeded", "completed_chapters": 2, "total_chapters": 2},
                },
            }
        },
    )
    chapters = [
        Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1.txt", word_count=100, processed=True),
        Chapter(id=uuid.uuid4(), book_id=book.id, number=2, s3_key="ch2.txt", word_count=120, processed=True),
    ]
    db.add(book)
    db.add_all(chapters)
    await db.flush()
    db.add_all(
        [
            ChapterSummary(id=uuid.uuid4(), chapter_id=chapters[0].id, mode="detailed", content="One"),
            ChapterSummary(id=uuid.uuid4(), chapter_id=chapters[1].id, mode="detailed", content="Two"),
        ]
    )
    await db.commit()
    cache_dirty: list[str] = []
    dashboard_dirty: list[str] = []
    monkeypatch.setattr(pipeline_state_service, "mark_book_cache_dirty", lambda book_id: cache_dirty.append(str(book_id)) or _async_none())
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
async def test_repair_stale_completed_processing_state_waits_for_detailed_summaries(db, monkeypatch):
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
        Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1.txt", word_count=100, processed=True),
        Chapter(id=uuid.uuid4(), book_id=book.id, number=2, s3_key="ch2.txt", word_count=120, processed=True),
    ]
    db.add(book)
    db.add_all(chapters)
    await db.flush()
    db.add(ChapterSummary(id=uuid.uuid4(), chapter_id=chapters[0].id, mode="detailed", content="One"))
    await db.commit()
    monkeypatch.setattr(pipeline_state_service, "mark_book_cache_dirty", lambda *_args: _async_none())
    monkeypatch.setattr(pipeline_state_service, "mark_user_dashboard_cache_dirty", lambda *_args: _async_none())

    repaired = await pipeline_state_service.repair_stale_completed_processing_state(db, book)

    assert repaired is False
    assert book.status == "processing"


@pytest.mark.asyncio
async def test_repair_stale_completed_processing_state_counts_distinct_chapter_numbers(db, monkeypatch):
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
        Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1-a.txt", word_count=100, processed=True),
        Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1-b.txt", word_count=100, processed=True),
        Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1-c.txt", word_count=100, processed=True),
        Chapter(id=uuid.uuid4(), book_id=book.id, number=2, s3_key="ch2-a.txt", word_count=120, processed=True),
        Chapter(id=uuid.uuid4(), book_id=book.id, number=2, s3_key="ch2-b.txt", word_count=120, processed=True),
        Chapter(id=uuid.uuid4(), book_id=book.id, number=2, s3_key="ch2-c.txt", word_count=120, processed=True),
    ]
    db.add(book)
    db.add_all(chapters)
    await db.flush()
    db.add_all(
        [
            ChapterSummary(id=uuid.uuid4(), chapter_id=chapters[0].id, mode="detailed", content="One"),
            ChapterSummary(id=uuid.uuid4(), chapter_id=chapters[3].id, mode="detailed", content="Two"),
        ]
    )
    await db.commit()
    monkeypatch.setattr(pipeline_state_service, "mark_book_cache_dirty", lambda *_args: _async_none())
    monkeypatch.setattr(pipeline_state_service, "mark_user_dashboard_cache_dirty", lambda *_args: _async_none())

    repaired = await pipeline_state_service.repair_stale_completed_processing_state(db, book)

    assert repaired is True
    assert book.status == "ready"
    assert book.writer_workspace["processing"]["chapters_total"] == 2
    assert book.writer_workspace["processing"]["chapters_completed"] == 2
    assert book.writer_workspace["processing"]["pipeline"]["analysis"]["completed_chapters"] == 2


async def _async_none():
    return None
