from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

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


def test_generate_wiki_task_loads_book_generates_and_commits(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    db = _Db(value=book)
    generated = []

    async def fake_generate_wiki(session, loaded_book):
        generated.append((session, loaded_book))
        return []

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.utils.world_building_utils.generate_wiki_from_manuscript", fake_generate_wiki)

    assert intelligence_tasks.generate_wiki_task.run(str(book.id)) is None
    assert generated == [(db, book)]
    assert db.commits == 1


def test_generate_wiki_task_raises_value_error_when_book_missing(monkeypatch):
    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(_Db(value=None)))

    with pytest.raises(ValueError, match="wiki_book_not_found"):
        intelligence_tasks.generate_wiki_task.run(str(uuid.uuid4()))


def test_generate_advisor_reply_task_marks_running_and_complete(monkeypatch):
    job_id = uuid.uuid4()
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id)
    db = _Db(value=book)
    calls = []
    payload = {"reply": "Use the gate earlier."}

    async def mark_running(session, *, job_id):
        calls.append(("running", session, job_id))

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
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_complete", mark_complete)
    monkeypatch.setattr("app.utils.advisor_utils.build_advisor_reply_payload", build_payload)

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


def test_generate_advisor_reply_task_marks_failed_for_inaccessible_book(monkeypatch):
    job_id = uuid.uuid4()
    db = _Db(value=SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4()))
    calls = []

    async def mark_running(session, *, job_id):
        calls.append(("running", job_id))

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


def test_generate_series_advisor_reply_task_marks_complete(monkeypatch):
    job_id = uuid.uuid4()
    series_id = uuid.uuid4()
    user_id = uuid.uuid4()
    series = SimpleNamespace(id=series_id, user_id=user_id)
    db = _Db(value=series)
    calls = []

    async def mark_running(session, *, job_id):
        calls.append(("running", job_id))

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
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_complete", mark_complete)
    monkeypatch.setattr("app.utils.advisor_utils.build_series_advisor_reply_payload", build_payload)

    assert intelligence_tasks.generate_series_advisor_reply_task.run(
        job_id=str(job_id),
        series_id=str(series_id),
        user_id=str(user_id),
        messages=[{"role": "user", "content": "Series question"}],
    ) == {"reply": "Series answer"}
    assert calls[-1][0] == "complete"


def test_generate_advisor_suggestions_task_builds_cache_key_and_payload(monkeypatch):
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
        }
    }

    async def mark_running(session, *, job_id):
        calls.append(("running", job_id))

    async def mark_failed(session, **kwargs):
        calls.append(("failed", kwargs))

    async def mark_complete(session, **kwargs):
        calls.append(("complete", kwargs))

    async def build_payload(**kwargs):
        return dict(payload)

    async def set_cache(book_id, cache_key, payload):
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
    monkeypatch.setattr("app.utils.advisor_utils.build_advisor_suggestions_payload", build_payload)
    monkeypatch.setattr(
        "app.utils.advisor_utils.make_advisor_suggestions_cache_key",
        lambda **kwargs: f"scan:{kwargs['total_chapters']}:{kwargs['character_count']}",
    )
    monkeypatch.setattr("app.core.redis.set_suggestion_scan_cache", set_cache)

    result = intelligence_tasks.generate_advisor_suggestions_task.run(
        job_id=str(job_id),
        book_id=str(book_id),
        user_id=str(user_id),
        total_chapters=12,
    )

    assert result["cached"] is False
    assert db.commits == 1
    assert calls[-2] == ("cache", str(book_id), "scan:12:2", False)
    assert calls[-1][0] == "complete"


def test_update_character_embedding_task_filters_low_confidence_traits(monkeypatch):
    character_id = uuid.uuid4()
    character = SimpleNamespace(
        id=character_id,
        name="Mira",
        trait_state={
            "eyes": {"value": "green", "confidence": 0.8},
            "hair": {"value": "black", "confidence": 0.2},
            "note": "ignored",
        },
    )
    db = _Db(value=character)
    embedded = []

    async def embed_character(name, traits):
        embedded.append((name, traits))
        return [0.1, 0.2]

    monkeypatch.setattr(embedding_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.engine.embeddings.embedder.embed_character", embed_character)

    assert embedding_tasks.update_character_embedding_task.run(str(character_id)) is None
    assert embedded == [("Mira", {"eyes": {"value": "green", "confidence": 0.8}})]
    assert len(db.executed) == 1
    assert db.commits == 1

