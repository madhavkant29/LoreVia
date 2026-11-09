from __future__ import annotations

import asyncio
import sys
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from httpx import Request
from openai import APIConnectionError
from sqlalchemy.exc import OperationalError

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


def test_process_chapter_task_pauses_llm_usage_limit_without_replaying_paid_work(
    monkeypatch,
):
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
        raise AssertionError("usage limits must not replay the chapter task")

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

    result = extraction_tasks.process_chapter_task.run(str(book_id), 4)

    assert result == {"paused": "llm_usage_limit"}
    assert retry_calls == []
    assert book.writer_workspace["processing"]["stage"] == "usage_limited"
    assert book.writer_workspace["processing"]["chapters_completed"] == 3
    assert book.writer_workspace["processing"]["last_error"] == (
        "Token allowance reached. Processing will resume when the window refreshes."
    )
    assert fake_session.rollbacks == 1
    assert fake_session.commits == 1


def test_process_chapter_task_fails_unresumable_token_request(monkeypatch):
    error = HTTPException(
        429,
        {
            "kind": "llm_tokens",
            "detail": "Request exceeds every token window.",
            "auto_resume": False,
            "permanent": True,
            "next_resume_at": None,
        },
    )
    calls = 0

    def run(coro):
        nonlocal calls
        calls += 1
        if calls == 1:
            coro.close()
            return True
        if calls == 2:
            coro.close()
            raise error
        return asyncio.run(coro)

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    fail = AsyncMock()
    monkeypatch.setattr(extraction_tasks, "run_worker_coro", run)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr("app.services.task_execution_service.fail_task_execution", fail)
    extraction_tasks.process_chapter_task.request.retries = 0

    result = extraction_tasks.process_chapter_task.run(
        str(uuid.uuid4()),
        4,
        execution_id="11111111-1111-1111-1111-111111111111",
    )

    assert result == {"failed": "llm_token_limit"}
    fail.assert_awaited_once()
    assert fail.await_args.kwargs["terminal"] is True
    assert fail.await_args.kwargs["category"] == "llm_token_limit"


def test_process_chapter_task_stays_paused_regardless_of_previous_retry_count(
    monkeypatch,
):
    calls: list[str] = []

    def _fake_run_worker_coro(coro):
        coro.close()
        raise HTTPException(429, "LLM usage token limit exceeded for the 5-hour window.")

    def _retry(**_kwargs):
        calls.append("retry")
        raise AssertionError(
            "retry should not be called after the usage-limit retry budget is exhausted"
        )

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", _fake_run_worker_coro)
    monkeypatch.setattr(extraction_tasks.process_chapter_task, "retry", _retry)
    extraction_tasks.process_chapter_task.request.retries = 7

    result = extraction_tasks.process_chapter_task.run(str(uuid.uuid4()), 4)

    assert result == {"paused": "llm_usage_limit"}
    assert calls == []


def test_process_chapter_task_does_not_retry_transient_provider_failure(monkeypatch):
    retry_calls: list[dict] = []

    def _raise_provider_failure(coro):
        coro.close()
        raise APIConnectionError(request=Request("POST", "https://api.openai.com/v1/embeddings"))

    def _retry(**kwargs):
        retry_calls.append(kwargs)
        raise AssertionError("provider failures must not replay the chapter task")

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", _raise_provider_failure)
    monkeypatch.setattr(extraction_tasks.process_chapter_task, "retry", _retry)
    extraction_tasks.process_chapter_task.request.retries = 0

    with pytest.raises(APIConnectionError):
        extraction_tasks.process_chapter_task.run(str(uuid.uuid4()), 4)

    assert retry_calls == []


def test_process_chapter_task_retries_transient_db_failure_before_work_starts(
    monkeypatch,
):
    deadlock = OperationalError("SELECT books", {}, RuntimeError("deadlock detected"))
    retry_calls: list[dict] = []

    def _raise_before_work(coro):
        coro.close()
        raise deadlock

    def _retry(**kwargs):
        retry_calls.append(kwargs)
        raise RuntimeError("retry scheduled")

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", _raise_before_work)
    monkeypatch.setattr(extraction_tasks.process_chapter_task, "retry", _retry)
    extraction_tasks.process_chapter_task.request.retries = 0

    with pytest.raises(RuntimeError, match="retry scheduled"):
        extraction_tasks.process_chapter_task.run(str(uuid.uuid4()), 4)

    assert retry_calls[0]["exc"] is deadlock
    assert retry_calls[0]["countdown"] == 2


def test_process_chapter_task_does_not_retry_non_transient_failure(monkeypatch):
    retry_calls: list[dict] = []

    def _raise_permanent_failure(coro):
        coro.close()
        raise ValueError("parse failure")

    def _retry(**kwargs):
        retry_calls.append(kwargs)
        raise AssertionError("non-transient failures must not be retried")

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", _raise_permanent_failure)
    monkeypatch.setattr(extraction_tasks.process_chapter_task, "retry", _retry)
    extraction_tasks.process_chapter_task.request.retries = 0

    with pytest.raises(ValueError, match="parse failure"):
        extraction_tasks.process_chapter_task.run(str(uuid.uuid4()), 4)

    assert retry_calls == []


def test_process_book_task_uses_shared_worker_runner(monkeypatch):
    calls: list[object] = []

    async def _fake_process_book(
        book_id: str, queue_wait_ms: int | None = None, task_id: str | None = None
    ):
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


def test_process_chapter_task_successfully_processes_and_sets_reprocess_guard(
    monkeypatch,
):
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        hidden_at=None,
        work_type="novel",
        total_chapters=1,
        status="processing",
    )
    chapter = SimpleNamespace(title="Chapter 1", s3_key=f"chapters/{book_id}/1.txt")
    fake_session = _FakeSession(book, chapter)
    processed: list[dict] = []
    redis_sets: list[tuple] = []

    class Redis:
        async def exists(self, _key):
            return 0

        async def set(self, *args, **kwargs):
            redis_sets.append((args, kwargs))
            return True

    async def get_redis():
        return Redis()

    def run(coro):
        return asyncio.run(coro)

    async def visible(*_args, **_kwargs):
        return False

    async def payload(*_args, **_kwargs):
        return {"number": 1, "title": "Chapter 1", "text": "Chapter text."}

    async def process(_db, _book, chapter_payload, **kwargs):
        processed.append({"payload": chapter_payload, **kwargs})

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", run)
    monkeypatch.setattr(extraction_tasks, "is_book_hidden", visible)
    monkeypatch.setattr(extraction_tasks, "load_processing_chapter_payload", payload)
    monkeypatch.setattr(extraction_tasks, "extract_queue_wait_ms", lambda _headers: 23)
    monkeypatch.setattr(extraction_tasks, "_process_chapter", process)
    monkeypatch.setattr("app.core.redis.get_redis", get_redis)
    monkeypatch.setattr(sa, "select", lambda *_args, **_kwargs: _FakeSelect())
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        SimpleNamespace(AsyncSessionLocal=lambda: fake_session),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.models.book",
        SimpleNamespace(Book=object, Chapter=_FakeChapterModel),
    )

    result = extraction_tasks.process_chapter_task.run(str(book_id), 1, manual_reprocess=True)

    assert result is None
    assert processed[0]["payload"]["text"] == "Chapter text."
    assert processed[0]["queue_wait_ms"] == 23
    assert processed[0]["manual_reprocess"] is True
    assert redis_sets[0][0][0] == f"chapter_reprocess:{book_id}:1"


def test_process_chapter_task_does_not_retry_db_failure_after_work_starts(monkeypatch):
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        hidden_at=None,
        work_type="novel",
        total_chapters=1,
        status="processing",
    )
    chapter = SimpleNamespace(title="Chapter 1", s3_key=f"chapters/{book_id}/1.txt")
    fake_session = _FakeSession(book, chapter)
    retry_calls: list[dict] = []
    deadlock = OperationalError("INSERT book_chunks", {}, RuntimeError("deadlock detected"))

    class Redis:
        async def exists(self, _key):
            return 0

    async def get_redis():
        return Redis()

    async def visible(*_args, **_kwargs):
        return False

    async def payload(*_args, **_kwargs):
        return {"number": 1, "title": "Chapter 1", "text": "Chapter text."}

    async def process(*_args, **_kwargs):
        raise deadlock

    def retry(**kwargs):
        retry_calls.append(kwargs)
        raise AssertionError("database failure after paid work must not replay the task")

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", asyncio.run)
    monkeypatch.setattr(extraction_tasks, "is_book_hidden", visible)
    monkeypatch.setattr(extraction_tasks, "load_processing_chapter_payload", payload)
    monkeypatch.setattr(extraction_tasks, "extract_queue_wait_ms", lambda _headers: 0)
    monkeypatch.setattr(extraction_tasks, "_process_chapter", process)
    monkeypatch.setattr(extraction_tasks.process_chapter_task, "retry", retry)
    monkeypatch.setattr("app.core.redis.get_redis", get_redis)
    monkeypatch.setattr(sa, "select", lambda *_args, **_kwargs: _FakeSelect())
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        SimpleNamespace(AsyncSessionLocal=lambda: fake_session),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.models.book",
        SimpleNamespace(Book=object, Chapter=_FakeChapterModel),
    )

    with pytest.raises(OperationalError):
        extraction_tasks.process_chapter_task.run(str(book_id), 1)

    assert retry_calls == []


def test_repair_chapter_payload_task_covers_success_missing_and_hidden_paths(
    monkeypatch,
):
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id)
    chapter = SimpleNamespace(number=2)
    session = _FakeSession(book, chapter)
    repaired: list[object] = []

    def run(coro):
        return asyncio.run(coro)

    async def visible(*_args, **_kwargs):
        return False

    async def repair(db, *, book, chapter):
        repaired.append((db, book, chapter))

    monkeypatch.setattr(extraction_tasks, "run_worker_coro", run)
    monkeypatch.setattr(extraction_tasks, "is_book_hidden", visible)
    monkeypatch.setattr(extraction_tasks, "repair_chapter_payload_from_source", repair)
    monkeypatch.setattr(sa, "select", lambda *_args, **_kwargs: _FakeSelect())
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        SimpleNamespace(AsyncSessionLocal=lambda: session),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.models.book",
        SimpleNamespace(Book=object, Chapter=_FakeChapterModel),
    )

    assert extraction_tasks.repair_chapter_payload_task.run(str(book_id), 2) is None
    assert repaired == [(session, book, chapter)]

    session._book = None
    assert extraction_tasks.repair_chapter_payload_task.run(str(book_id), 2) is None
