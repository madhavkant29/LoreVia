from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

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
