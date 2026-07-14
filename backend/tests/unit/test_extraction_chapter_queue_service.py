from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import extraction_chapter_queue_service as queue_service


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_queue_initial_extraction_chapters_creates_task_executions(monkeypatch):
    reserves: list[dict] = []
    executions: list[dict] = []
    dispatches = 0

    async def is_visible(_db, _book_id):
        return False

    async def reserve(_db, _user, **kwargs):
        reserves.append(kwargs)

    async def ensure(_db, **kwargs):
        executions.append(kwargs)

    async def dispatch(_db):
        nonlocal dispatches
        dispatches += 1
        return 2

    monkeypatch.setattr(queue_service, "is_book_hidden", is_visible)
    monkeypatch.setattr(queue_service, "reserve_processing_words", reserve)
    monkeypatch.setattr(queue_service, "ensure_task_execution", ensure)
    monkeypatch.setattr(queue_service, "dispatch_pending_extraction_tasks", dispatch)

    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), writer_workspace={})
    user = SimpleNamespace(id=book.user_id)
    processing_run = SimpleNamespace(id=uuid.uuid4())
    chapter_1 = SimpleNamespace(id=uuid.uuid4(), processed=False, word_count=25)
    chapter_2 = SimpleNamespace(id=uuid.uuid4(), processed=True, word_count=10)
    db = FakeDb()

    result = await queue_service.queue_initial_extraction_chapters(
        db,
        book=book,
        user=user,
        processing_run=processing_run,
        ai_chapters=[
            {"number": 1, "text": "chapter one"},
            {"number": 2, "text": "already done"},
        ],
        chapter_rows=[chapter_1, chapter_2],
        chapters_by_number={1: chapter_1, 2: chapter_2},
        processing_started_at=datetime(2026, 1, 1, tzinfo=UTC),
        queue_wait_ms=17,
    )

    assert result == {"queued_count": 1}
    assert db.commits == 1
    assert dispatches == 1
    assert reserves[0]["word_count"] == 25
    assert executions[0]["task_name"] == "extraction_tasks.process_chapter"
    assert executions[0]["chapter_id"] == chapter_1.id
    assert executions[0]["chapter_number"] == 1


@pytest.mark.asyncio
async def test_queue_initial_extraction_chapters_pauses_on_processing_allowance(monkeypatch):
    dispatches = 0

    async def is_visible(_db, _book_id):
        return False

    async def reserve(_db, _user, **_kwargs):
        raise HTTPException(status_code=403, detail="monthly limit reached")

    async def ensure(_db, **_kwargs):
        raise AssertionError("task execution should not be created after allowance denial")

    async def dispatch(_db):
        nonlocal dispatches
        dispatches += 1
        return 0

    def update_state(_book, **kwargs):
        return {"processing": {"stage": kwargs["stage"], "last_error": kwargs["last_error"]}}

    monkeypatch.setattr(queue_service, "is_book_hidden", is_visible)
    monkeypatch.setattr(queue_service, "reserve_processing_words", reserve)
    monkeypatch.setattr(queue_service, "ensure_task_execution", ensure)
    monkeypatch.setattr(queue_service, "dispatch_pending_extraction_tasks", dispatch)
    monkeypatch.setattr(queue_service, "update_book_processing_state", update_state)

    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), writer_workspace={})
    processing_run = SimpleNamespace(id=uuid.uuid4())
    chapter = SimpleNamespace(id=uuid.uuid4(), processed=False, word_count=25)
    db = FakeDb()

    result = await queue_service.queue_initial_extraction_chapters(
        db,
        book=book,
        user=SimpleNamespace(id=book.user_id),
        processing_run=processing_run,
        ai_chapters=[{"number": 3, "text": "chapter text"}],
        chapter_rows=[chapter],
        chapters_by_number={3: chapter},
        processing_started_at=datetime(2026, 1, 1, tzinfo=UTC),
        queue_wait_ms=None,
    )

    assert result == {"queued_count": 0}
    assert db.commits == 1
    assert dispatches == 1
    assert processing_run.status == "paused"
    assert processing_run.pause_reason == "processing_allowance"
    assert processing_run.next_chapter_number == 3
    assert processing_run.resume_blockers == [
        {"kind": "monthly_processed_words", "detail": "monthly limit reached"}
    ]
    assert book.writer_workspace["processing"]["resume_available"] is True
