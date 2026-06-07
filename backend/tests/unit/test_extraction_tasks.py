from __future__ import annotations

import asyncio
import sys
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import HTTPException

from app.workers.tasks import extraction_tasks


class _Result:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar(self):
        return self._scalar


class _FakeSession:
    def __init__(self, book, chapter):
        self._book = book
        self._chapter = chapter
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *_args, **_kwargs):
        return self._book

    async def execute(self, *_args, **_kwargs):
        return _Result(self._chapter)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class _FakeSelect:
    def where(self, *_args, **_kwargs):
        return self


class _FakeColumn:
    def __eq__(self, _other):
        return self


class _FakeChapterModel:
    book_id = _FakeColumn()
    number = _FakeColumn()


def test_process_chapter_task_fails_cleanly_when_payload_missing(monkeypatch):
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, hidden_at=None)
    chapter = SimpleNamespace(title="Chapter 4", s3_key=f"chapters/{book_id}/4.txt")

    async def _run_awaitable(coro):
        return await coro

    def _fake_run_worker_coro(coro):
        return asyncio.run(_run_awaitable(coro))

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", _fake_run_worker_coro)
    async def _visible(*_args, **_kwargs):
        return False

    async def _missing_payload(*_args, **_kwargs):
        return None

    monkeypatch.setattr(extraction_tasks, "is_book_hidden", _visible)
    monkeypatch.setattr(extraction_tasks, "load_processing_chapter_payload", _missing_payload)
    monkeypatch.setattr(extraction_tasks, "extract_queue_wait_ms", lambda _headers: 0)
    monkeypatch.setattr(sa, "select", lambda *_args, **_kwargs: _FakeSelect())

    async def _unexpected_process(*_args, **_kwargs):
        raise AssertionError("_process_chapter should not run when payload is missing")

    monkeypatch.setattr(extraction_tasks, "_process_chapter", _unexpected_process)

    fake_database_module = SimpleNamespace(AsyncSessionLocal=lambda: _FakeSession(book, chapter))
    fake_models_module = SimpleNamespace(Book=object, Chapter=_FakeChapterModel)
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database_module)
    monkeypatch.setitem(sys.modules, "app.models.book", fake_models_module)

    with pytest.raises(ValueError, match="missing_chapter_payload"):
        extraction_tasks.process_chapter_task.run(str(book_id), 4)


def test_process_chapter_task_retries_llm_usage_limit_without_failing(monkeypatch):
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        user_id=uuid.uuid4(),
        hidden_at=None,
        total_chapters=8,
        status="processing",
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "chapter_complete",
                "chapters_completed": 3,
                "chapters_total": 8,
            }
        },
    )
    chapter = SimpleNamespace(title="Chapter 4", s3_key=f"chapters/{book_id}/4.txt")
    fake_session = _FakeSession(book, chapter)
    retry_calls: list[dict[str, object]] = []

    async def _run_awaitable(coro):
        return await coro

    def _fake_run_worker_coro(coro):
        return asyncio.run(_run_awaitable(coro))

    async def _visible(*_args, **_kwargs):
        return False

    async def _chapter_payload(*_args, **_kwargs):
        return {"number": 4, "title": "Chapter 4", "text": "Some chapter text."}

    async def _usage_limited(*_args, **_kwargs):
        raise HTTPException(429, "LLM usage token limit exceeded for the 5-hour window.")

    def _retry(**kwargs):
        retry_calls.append(kwargs)
        raise RuntimeError("retry scheduled")

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", _fake_run_worker_coro)
    monkeypatch.setattr(extraction_tasks, "is_book_hidden", _visible)
    monkeypatch.setattr(extraction_tasks, "load_processing_chapter_payload", _chapter_payload)
    monkeypatch.setattr(extraction_tasks, "extract_queue_wait_ms", lambda _headers: 0)
    monkeypatch.setattr(extraction_tasks, "_process_chapter", _usage_limited)
    monkeypatch.setattr(extraction_tasks.process_chapter_task, "retry", _retry)
    monkeypatch.setattr(sa, "select", lambda *_args, **_kwargs: _FakeSelect())

    fake_database_module = SimpleNamespace(AsyncSessionLocal=lambda: fake_session)
    fake_models_module = SimpleNamespace(Book=object, Chapter=_FakeChapterModel)
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database_module)
    monkeypatch.setitem(sys.modules, "app.models.book", fake_models_module)

    with pytest.raises(RuntimeError, match="retry scheduled"):
        extraction_tasks.process_chapter_task.run(str(book_id), 4)

    assert retry_calls
    assert retry_calls[0]["countdown"] == extraction_tasks.LLM_USAGE_LIMIT_RETRY_SECONDS
    assert retry_calls[0]["max_retries"] == extraction_tasks.LLM_USAGE_LIMIT_MAX_RETRIES
    assert book.writer_workspace["processing"]["stage"] == "usage_limited"
    assert book.writer_workspace["processing"]["chapters_completed"] == 3
    assert "token limit exceeded" in book.writer_workspace["processing"]["last_error"]
    assert fake_session.rollbacks == 1
    assert fake_session.commits == 1


def test_process_chapter_task_stays_paused_after_llm_usage_retry_budget(monkeypatch):
    calls: list[str] = []

    def _fake_run_worker_coro(coro):
        coro.close()
        raise HTTPException(429, "LLM usage token limit exceeded for the 5-hour window.")

    def _retry(**_kwargs):
        calls.append("retry")
        raise AssertionError("retry should not be called after the usage-limit retry budget is exhausted")

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", _fake_run_worker_coro)
    monkeypatch.setattr(extraction_tasks.process_chapter_task, "retry", _retry)
    extraction_tasks.process_chapter_task.request.retries = extraction_tasks.LLM_USAGE_LIMIT_MAX_RETRIES

    result = extraction_tasks.process_chapter_task.run(str(uuid.uuid4()), 4)

    assert result == {"paused": "llm_usage_limit"}
    assert calls == []


def test_process_book_task_uses_shared_worker_runner(monkeypatch):
    calls: list[object] = []

    async def _fake_process_book(book_id: str, queue_wait_ms: int | None = None, task_id: str | None = None):
        calls.append((book_id, queue_wait_ms))
        return {"book_id": book_id}

    def _fake_run_worker_coro(coro):
        calls.append(type(coro).__name__)
        coro.close()
        return {"ran": True}

    monkeypatch.setattr(extraction_tasks, "process_book", _fake_process_book)
    monkeypatch.setattr(extraction_tasks, "run_worker_coro", _fake_run_worker_coro)
    monkeypatch.setattr(extraction_tasks, "extract_queue_wait_ms", lambda _headers: 12)

    result = extraction_tasks.process_book_task.run("book-123")

    assert result == {"ran": True}
    assert calls == ["coroutine"]
