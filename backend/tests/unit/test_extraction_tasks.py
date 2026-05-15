from __future__ import annotations

import asyncio
import sys
import uuid
from types import SimpleNamespace

import pytest

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


def test_process_chapter_task_fails_cleanly_when_payload_missing(monkeypatch):
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, hidden_at=None)
    chapter = SimpleNamespace(title="Chapter 4", s3_key=f"chapters/{book_id}/4.txt")

    monkeypatch.setattr(extraction_tasks, "_run_coro", lambda coro: asyncio.run(coro))
    async def _visible(*_args, **_kwargs):
        return False

    async def _missing_payload(*_args, **_kwargs):
        return None

    monkeypatch.setattr(extraction_tasks, "is_book_hidden", _visible)
    monkeypatch.setattr(extraction_tasks, "load_processing_chapter_payload", _missing_payload)

    async def _unexpected_process(*_args, **_kwargs):
        raise AssertionError("_process_chapter should not run when payload is missing")

    monkeypatch.setattr(extraction_tasks, "_process_chapter", _unexpected_process)

    fake_database_module = SimpleNamespace(AsyncSessionLocal=lambda: _FakeSession(book, chapter))
    fake_models_module = SimpleNamespace(Book=object, Chapter=object)
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database_module)
    monkeypatch.setitem(sys.modules, "app.models.book", fake_models_module)

    request = SimpleNamespace(headers={})
    task_self = SimpleNamespace(request=request, retry=lambda exc=None: (_ for _ in ()).throw(exc))

    with pytest.raises(ValueError, match="missing_chapter_payload"):
        extraction_tasks.process_chapter_task(task_self, str(book_id), 4)
