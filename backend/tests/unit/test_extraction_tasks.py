from __future__ import annotations

import asyncio
import sys
import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

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

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *_args, **_kwargs):
        return self._book

    async def execute(self, *_args, **_kwargs):
        return _Result(self._chapter)


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


def test_process_book_task_uses_shared_worker_runner(monkeypatch):
    calls: list[object] = []

    async def _fake_process_book(book_id: str, queue_wait_ms: int | None = None):
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
