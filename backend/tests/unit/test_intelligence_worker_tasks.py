from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.workers.tasks import embedding_tasks, intelligence_tasks


def _run_coro(coro):
    return asyncio.run(coro)


class _SessionFactory:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Db:
    def __init__(self, *, value=None):
        self.value = value
        self.commits = 0
        self.executed = []

    async def get(self, model, requested_id):
        return self.value

    async def execute(self, statement):
        self.executed.append(statement)
        return SimpleNamespace()

    async def commit(self):
        self.commits += 1


class _DbByModel(_Db):
    def __init__(self, values_by_model_name):
        super().__init__()
        self.values_by_model_name = values_by_model_name

    async def get(self, model, requested_id):
        return self.values_by_model_name.get(model.__name__)


def test_generate_wiki_task_loads_book_generates_and_commits(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    db = _Db(value=book)
    generated = []

    async def fake_generate_wiki(session, loaded_book):
        generated.append((session, loaded_book))
        return []

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr(
        "app.utils.world_building_wiki_utils.generate_wiki_from_manuscript", fake_generate_wiki
    )

    assert intelligence_tasks.generate_wiki_task.run(str(book.id)) is None
    assert generated == [(db, book)]
    assert db.commits == 1


def test_generate_wiki_task_raises_value_error_when_book_missing(monkeypatch):
    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr(
        "app.core.database.AsyncSessionLocal", lambda: _SessionFactory(_Db(value=None))
    )

    with pytest.raises(ValueError, match="wiki_book_not_found"):
        intelligence_tasks.generate_wiki_task.run(str(uuid.uuid4()))


def test_generate_wiki_task_does_not_retry_after_paid_work_starts(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    db = _Db(value=book)

    async def fail_during_generation(*_args, **_kwargs):
        raise ConnectionError("provider disconnected")

    def retry(**_kwargs):
        raise AssertionError("paid wiki work must not be replayed")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr(
        "app.utils.world_building_wiki_utils.generate_wiki_from_manuscript",
        fail_during_generation,
    )
    monkeypatch.setattr(intelligence_tasks.generate_wiki_task, "retry", retry)
    intelligence_tasks.generate_wiki_task.request.retries = 0

    with pytest.raises(ConnectionError, match="provider disconnected"):
        intelligence_tasks.generate_wiki_task.run(str(book.id))


def test_generate_advisor_reply_task_marks_running_and_complete(monkeypatch):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id)
    db = _Db(value=book)
    calls = []
    payload = {"reply": "Use the gate earlier."}

    async def mark_running(session, *, job_id, execution_id):
        calls.append(("running", session, job_id))
        return SimpleNamespace(scope="book")

    async def mark_failed(session, **kwargs):
        calls.append(("failed", kwargs))

    async def mark_complete(session, **kwargs):
        calls.append(("complete", kwargs))

    async def build_payload(**kwargs):
        calls.append(("build", kwargs))
        return payload

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", mark_running)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)
    monkeypatch.setattr(
        "app.services.advisor_jobs_service.mark_advisor_job_complete", mark_complete
    )
    monkeypatch.setattr("app.utils.advisor_chat_utils.build_advisor_reply_payload", build_payload)

    result = intelligence_tasks.generate_advisor_reply_task.run(
        job_id=str(job_id),
        book_id=str(book_id),
        user_id=str(user_id),
        messages=[{"role": "user", "content": "Where should I foreshadow?"}],
        total_chapters=9,
    )

    assert result == payload
    assert calls[0] == ("running", db, job_id)
    assert calls[1][0] == "build"
    assert calls[2][0] == "complete"
    assert calls[2][1]["result_payload"] == payload


def test_generate_advisor_reply_task_skips_work_when_execution_claim_is_held(monkeypatch):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=book_id, user_id=user_id))

    async def deny_claim(*_args, **_kwargs):
        return None

    async def should_not_build(**_kwargs):
        raise AssertionError("a duplicate worker must not call the AI provider")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr(
        "app.services.advisor_jobs_service.mark_advisor_job_running",
        deny_claim,
    )
    monkeypatch.setattr(
        "app.utils.advisor_chat_utils.build_advisor_reply_payload",
        should_not_build,
    )

    assert (
        intelligence_tasks.generate_advisor_reply_task.run(
            job_id=str(job_id),
            book_id=str(book_id),
            user_id=str(user_id),
            messages=[{"role": "user", "content": "Question"}],
            total_chapters=1,
        )
        is None
    )


def test_generate_advisor_reply_task_marks_failed_for_inaccessible_book(monkeypatch):
    job_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4()))
    calls = []

    async def mark_running(session, *, job_id, execution_id):
        calls.append(("running", job_id))
        return SimpleNamespace(scope="book")

    async def mark_failed(session, **kwargs):
        calls.append(("failed", kwargs))

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", mark_running)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)

    with pytest.raises(ValueError, match="advisor_book_not_found"):
        intelligence_tasks.generate_advisor_reply_task.run(
            job_id=str(job_id),
            book_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            messages=[{"role": "user", "content": "Question"}],
            total_chapters=1,
        )

    assert calls[-1][0] == "failed"
    assert calls[-1][1]["error_code"] == "advisor_book_not_found"


def test_generate_advisor_reply_task_does_not_replay_after_provider_work_starts(monkeypatch):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=book_id, user_id=user_id))
    calls = []

    async def mark_running(*_args, **_kwargs):
        return SimpleNamespace(scope="book")

    async def mark_failed(*_args, **kwargs):
        calls.append(("failed", kwargs))

    async def build_payload(**_kwargs):
        raise ConnectionError("provider disconnected")

    def retry(**_kwargs):
        raise AssertionError("paid advisor work must not be replayed")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", mark_running)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)
    monkeypatch.setattr("app.utils.advisor_chat_utils.build_advisor_reply_payload", build_payload)
    monkeypatch.setattr(intelligence_tasks.generate_advisor_reply_task, "retry", retry)
    intelligence_tasks.generate_advisor_reply_task.request.retries = 0

    with pytest.raises(ConnectionError, match="provider disconnected"):
        intelligence_tasks.generate_advisor_reply_task.run(
            job_id=str(job_id),
            book_id=str(book_id),
            user_id=str(user_id),
            messages=[{"role": "user", "content": "Question"}],
            total_chapters=1,
        )

    assert calls[-1][0] == "failed"
    assert calls[-1][1]["error_code"] == "advisor_generation_failed"


def test_generate_advisor_reply_task_surfaces_budget_limit_without_task_retry(monkeypatch):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=book_id, user_id=user_id))
    failed = []

    async def noop(*_args, **_kwargs):
        return SimpleNamespace(scope="book")

    async def mark_failed(*_args, **kwargs):
        failed.append(kwargs)

    async def build_payload(**_kwargs):
        raise HTTPException(
            429,
            detail={
                "kind": "llm_budget",
                "detail": "AI capacity resets on September 1.",
                "next_resume_at": "2026-09-01T00:00:00+00:00",
            },
        )

    def retry(**_kwargs):
        raise AssertionError("budget limits must not trigger a task retry")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", noop)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)
    monkeypatch.setattr("app.utils.advisor_chat_utils.build_advisor_reply_payload", build_payload)
    monkeypatch.setattr(intelligence_tasks.generate_advisor_reply_task, "retry", retry)
    intelligence_tasks.generate_advisor_reply_task.request.retries = 0

    assert (
        intelligence_tasks.generate_advisor_reply_task.run(
            job_id=str(job_id),
            book_id=str(book_id),
            user_id=str(user_id),
            messages=[{"role": "user", "content": "Question"}],
            total_chapters=1,
        )
        is None
    )
    assert failed[-1]["error_code"] == "llm_budget"
    assert failed[-1]["error_detail"] == "AI capacity resets on September 1."


def test_generate_advisor_reply_task_retries_failure_before_paid_work(monkeypatch):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=book_id, user_id=user_id))
    provider_calls = []

    class RetryRequested(Exception):
        pass

    async def mark_running(*_args, **_kwargs):
        raise ConnectionError("database unavailable")

    async def build_payload(**_kwargs):
        provider_calls.append(True)
        return {"reply": "unexpected"}

    def retry(*, exc, countdown):
        assert isinstance(exc, ConnectionError)
        assert countdown == 2
        return RetryRequested("retry requested")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", mark_running)
    monkeypatch.setattr("app.utils.advisor_chat_utils.build_advisor_reply_payload", build_payload)
    monkeypatch.setattr(intelligence_tasks.generate_advisor_reply_task, "retry", retry)
    intelligence_tasks.generate_advisor_reply_task.request.retries = 0

    with pytest.raises(RetryRequested, match="retry requested"):
        intelligence_tasks.generate_advisor_reply_task.run(
            job_id=str(job_id),
            book_id=str(book_id),
            user_id=str(user_id),
            messages=[{"role": "user", "content": "Question"}],
            total_chapters=1,
        )

    assert provider_calls == []


def test_generate_series_advisor_reply_task_marks_complete(monkeypatch):
    job_id = uuid.uuid4()
    series_id = uuid.uuid4()
    user_id = uuid.uuid4()
    series = SimpleNamespace(id=series_id, user_id=user_id)
    db = _Db(value=series)
    calls = []

    async def mark_running(session, *, job_id, execution_id):
        calls.append(("running", job_id))
        return SimpleNamespace(scope="series")

    async def mark_failed(session, **kwargs):
        calls.append(("failed", kwargs))

    async def mark_complete(session, **kwargs):
        calls.append(("complete", kwargs))

    async def build_payload(**kwargs):
        return {"reply": "Series answer"}

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", mark_running)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)
    monkeypatch.setattr(
        "app.services.advisor_jobs_service.mark_advisor_job_complete", mark_complete
    )
    monkeypatch.setattr(
        "app.utils.advisor_chat_utils.build_series_advisor_reply_payload", build_payload
    )

    assert intelligence_tasks.generate_series_advisor_reply_task.run(
        job_id=str(job_id),
        series_id=str(series_id),
        user_id=str(user_id),
        messages=[{"role": "user", "content": "Series question"}],
    ) == {"reply": "Series answer"}
    assert calls[-1][0] == "complete"


def test_generate_series_advisor_reply_task_does_not_replay_paid_work(monkeypatch):
    job_id = uuid.uuid4()
    series_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=series_id, user_id=user_id))
    failed = []

    async def noop(*_args, **_kwargs):
        return SimpleNamespace(scope="series")

    async def mark_failed(*_args, **kwargs):
        failed.append(kwargs)

    async def build_payload(**_kwargs):
        raise ConnectionError("provider disconnected")

    def retry(**_kwargs):
        raise AssertionError("paid series advisor work must not be replayed")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", noop)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)
    monkeypatch.setattr(
        "app.utils.advisor_chat_utils.build_series_advisor_reply_payload", build_payload
    )
    monkeypatch.setattr(intelligence_tasks.generate_series_advisor_reply_task, "retry", retry)
    intelligence_tasks.generate_series_advisor_reply_task.request.retries = 0

    with pytest.raises(ConnectionError, match="provider disconnected"):
        intelligence_tasks.generate_series_advisor_reply_task.run(
            job_id=str(job_id),
            series_id=str(series_id),
            user_id=str(user_id),
            messages=[{"role": "user", "content": "Question"}],
        )

    assert failed[-1]["error_code"] == "advisor_generation_failed"


@pytest.mark.parametrize("audit_failure_category", [None, "invalid_ai_response"])
def test_generate_advisor_suggestions_task_builds_cache_key_and_payload(
    monkeypatch, audit_failure_category
):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id)
    db = _Db(value=book)
    calls = []
    payload = {
        "meta": {
            "character_count": 2,
            "open_thread_count": 3,
            "state_count": 4,
            "relationship_count": 5,
            "world_element_count": 6,
            "audit_failure_category": audit_failure_category,
        }
    }

    async def mark_running(session, *, job_id, execution_id):
        calls.append(("running", job_id))
        return SimpleNamespace()

    async def mark_failed(session, **kwargs):
        calls.append(("failed", kwargs))

    async def mark_complete(session, **kwargs):
        calls.append(("complete", kwargs))

    async def mark_progress(session, **kwargs):
        calls.append(("progress", kwargs["completed"], kwargs["total"]))
        return True

    async def build_payload(**kwargs):
        calls.append(("build", kwargs.get("force_audit")))
        await kwargs["on_audit_progress"](0, 3)
        await kwargs["on_audit_progress"](1, 3)
        return dict(payload)

    async def cache_version(*_args, **_kwargs):
        return 0

    async def set_cache(book_id, cache_key, payload, **_kwargs):
        calls.append(("cache", book_id, cache_key, payload["cached"]))

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.mark_advisor_suggestion_job_running",
        mark_running,
    )
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.mark_advisor_suggestion_job_failed",
        mark_failed,
    )
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.mark_advisor_suggestion_job_complete",
        mark_complete,
    )
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.mark_advisor_suggestion_job_progress",
        mark_progress,
    )
    monkeypatch.setattr(
        "app.utils.advisor_scan_utils.build_advisor_suggestions_payload", build_payload
    )
    monkeypatch.setattr(
        "app.utils.advisor_utils.make_advisor_suggestions_cache_key",
        lambda **kwargs: f"scan:{kwargs['total_chapters']}:{kwargs['character_count']}",
    )
    monkeypatch.setattr("app.core.redis.get_book_cache_version", cache_version)
    monkeypatch.setattr("app.core.redis.set_suggestion_scan_cache", set_cache)

    result = intelligence_tasks.generate_advisor_suggestions_task.run(
        job_id=str(job_id),
        book_id=str(book_id),
        user_id=str(user_id),
        total_chapters=12,
    )

    assert result["cached"] is False
    assert ("build", True) in calls
    assert ("progress", 0, 3) in calls
    assert ("progress", 1, 3) in calls
    assert db.commits == 1
    if audit_failure_category is None:
        assert calls[-2] == ("cache", str(book_id), "scan:12:2", False)
    else:
        assert not any(call[0] == "cache" for call in calls)
    assert calls[-1][0] == "complete"


def test_generate_advisor_suggestions_task_does_not_replay_paid_scan(monkeypatch):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=book_id, user_id=user_id))
    failed = []

    async def noop(*_args, **_kwargs):
        return SimpleNamespace()

    async def mark_failed(*_args, **kwargs):
        failed.append(kwargs)

    async def build_payload(**_kwargs):
        raise ConnectionError("provider disconnected")

    def retry(**_kwargs):
        raise AssertionError("paid advisor scan must not be replayed")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.mark_advisor_suggestion_job_running", noop
    )
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.mark_advisor_suggestion_job_failed",
        mark_failed,
    )
    monkeypatch.setattr(
        "app.utils.advisor_scan_utils.build_advisor_suggestions_payload", build_payload
    )
    monkeypatch.setattr(intelligence_tasks.generate_advisor_suggestions_task, "retry", retry)
    intelligence_tasks.generate_advisor_suggestions_task.request.retries = 0

    with pytest.raises(ConnectionError, match="provider disconnected"):
        intelligence_tasks.generate_advisor_suggestions_task.run(
            job_id=str(job_id),
            book_id=str(book_id),
            user_id=str(user_id),
            total_chapters=12,
        )

    assert failed[-1]["error_code"] == "advisor_suggestions_failed"


def test_generate_advisor_suggestions_task_surfaces_budget_limit_without_retry(monkeypatch):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=book_id, user_id=user_id))
    failed = []

    async def noop(*_args, **_kwargs):
        return SimpleNamespace()

    async def mark_failed(*_args, **kwargs):
        failed.append(kwargs)

    async def build_payload(**_kwargs):
        raise HTTPException(
            429,
            detail={"kind": "llm_budget", "detail": "Monthly AI capacity is exhausted."},
        )

    def retry(**_kwargs):
        raise AssertionError("budget limits must not trigger a task retry")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.mark_advisor_suggestion_job_running", noop
    )
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.mark_advisor_suggestion_job_failed",
        mark_failed,
    )
    monkeypatch.setattr(
        "app.utils.advisor_scan_utils.build_advisor_suggestions_payload", build_payload
    )
    monkeypatch.setattr(intelligence_tasks.generate_advisor_suggestions_task, "retry", retry)
    intelligence_tasks.generate_advisor_suggestions_task.request.retries = 0

    assert (
        intelligence_tasks.generate_advisor_suggestions_task.run(
            job_id=str(job_id),
            book_id=str(book_id),
            user_id=str(user_id),
            total_chapters=12,
        )
        is None
    )
    assert failed[-1]["error_code"] == "llm_budget"
    assert failed[-1]["error_detail"] == "Monthly AI capacity is exhausted."


def test_update_character_embedding_task_filters_low_confidence_traits(monkeypatch):
    character_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    character = SimpleNamespace(
        id=character_id,
        book_id=book_id,
        name="Mira",
        trait_state={
            "eyes": {"value": "green", "confidence": 0.8},
            "hair": {"value": "black", "confidence": 0.2},
            "note": "ignored",
        },
    )
    book = SimpleNamespace(id=book_id, user_id=user_id)
    db = _DbByModel({"Character": character, "Book": book})
    embedded = []

    async def embed_character(name, traits, **kwargs):
        embedded.append((name, traits, kwargs))
        return [0.1, 0.2]

    monkeypatch.setattr(embedding_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.engine.embeddings.embedder.embed_character", embed_character)

    assert embedding_tasks.update_character_embedding_task.run(str(character_id)) is None
    assert embedded == [
        (
            "Mira",
            {"eyes": {"value": "green", "confidence": 0.8}},
            {"user_id": user_id, "book_id": book_id},
        )
    ]
    assert len(db.executed) == 1
    assert db.commits == 1


def test_update_character_embedding_task_does_not_replay_paid_embedding(monkeypatch):
    character_id = uuid.uuid4()
    book_id = uuid.uuid4()
    db = _DbByModel(
        {
            "Character": SimpleNamespace(
                id=character_id,
                book_id=book_id,
                name="Mira",
                trait_state={},
            ),
            "Book": SimpleNamespace(id=book_id, user_id=uuid.uuid4()),
        }
    )

    async def embed_character(*_args, **_kwargs):
        raise ConnectionError("provider disconnected")

    def retry(**_kwargs):
        raise AssertionError("paid embedding work must not be replayed")

    monkeypatch.setattr(embedding_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.engine.embeddings.embedder.embed_character", embed_character)
    monkeypatch.setattr(embedding_tasks.update_character_embedding_task, "retry", retry)
    embedding_tasks.update_character_embedding_task.request.retries = 0

    with pytest.raises(ConnectionError, match="provider disconnected"):
        embedding_tasks.update_character_embedding_task.run(str(character_id))


def test_update_character_embedding_task_retries_failure_before_paid_work(monkeypatch):
    class FailingDb(_Db):
        async def get(self, model, requested_id):
            raise ConnectionError("database unavailable")

    class RetryRequested(Exception):
        pass

    provider_calls = []

    async def embed_character(*_args, **_kwargs):
        provider_calls.append(True)
        return [0.1]

    def retry(*, exc, countdown):
        assert isinstance(exc, ConnectionError)
        assert countdown == 2
        return RetryRequested("retry requested")

    monkeypatch.setattr(embedding_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(FailingDb()))
    monkeypatch.setattr("app.engine.embeddings.embedder.embed_character", embed_character)
    monkeypatch.setattr(embedding_tasks.update_character_embedding_task, "retry", retry)
    embedding_tasks.update_character_embedding_task.request.retries = 0

    with pytest.raises(RetryRequested, match="retry requested"):
        embedding_tasks.update_character_embedding_task.run(str(uuid.uuid4()))

    assert provider_calls == []
