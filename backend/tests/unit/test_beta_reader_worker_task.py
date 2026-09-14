import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.advisor_jobs_service import ADVISOR_SCOPE_FIRST_IMPRESSION
from app.workers.tasks import intelligence_tasks


def _run_coro(coro):
    return asyncio.run(coro)


class _SessionFactory:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Database:
    def __init__(self, user):
        self.user = user

    async def get(self, model, requested_id):
        return self.user


def test_beta_reader_worker_tracks_progress_persists_and_completes(monkeypatch):
    job_id, book_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=user_id)
    book = SimpleNamespace(id=book_id)
    db = _Database(user)
    calls: list[tuple[str, object]] = []
    report = {"report_id": "report-1"}

    async def mark_running(session, *, job_id, execution_id):
        calls.append(("running", job_id))
        return SimpleNamespace(id=job_id, scope="book")

    async def mark_failed(session, **kwargs):
        calls.append(("failed", kwargs))

    async def mark_complete(session, **kwargs):
        calls.append(("complete", kwargs))

    async def update_progress(session, **kwargs):
        calls.append(("progress", kwargs["progress"]))

    async def get_access(*args, **kwargs):
        return book, None, SimpleNamespace()

    async def build_report(*args, **kwargs):
        await kwargs["progress"](
            {"stage": "analysis", "completed": 0, "total": 1, "message": "Counting"}
        )
        return report

    async def persist_report(*args, **kwargs):
        calls.append(("persist", kwargs["report"]))
        return kwargs["report"]

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", mark_running)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)
    monkeypatch.setattr(
        "app.services.advisor_jobs_service.mark_advisor_job_complete", mark_complete
    )
    monkeypatch.setattr(
        "app.services.advisor_jobs_service.update_advisor_job_progress", update_progress
    )
    monkeypatch.setattr(
        "app.utils.books.collaboration_access.get_book_with_ai_scan_access", get_access
    )
    monkeypatch.setattr(
        "app.services.beta_reader_analysis_service.build_beta_reader_report", build_report
    )
    monkeypatch.setattr(
        "app.services.beta_reader_analysis_service.persist_beta_reader_report", persist_report
    )

    result = intelligence_tasks.generate_beta_reader_report_task.run(
        job_id=str(job_id),
        book_id=str(book_id),
        user_id=str(user_id),
        request_payload={
            "scope": "passage",
            "text": "A passage to analyze.",
            "checks": ["repetition"],
        },
    )

    assert result == report
    assert [name for name, _ in calls] == [
        "running",
        "progress",
        "progress",
        "persist",
        "complete",
    ]
    assert calls[-1][1]["result_payload"] == report


def test_first_impression_beta_reader_worker_updates_first_read_state(monkeypatch):
    job_id, book_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=user_id)
    book = SimpleNamespace(id=book_id)
    db = _Database(user)
    calls: list[tuple[str, object]] = []
    report = {
        "report_id": "report-1",
        "request_hash": "request-hash",
        "source_fingerprint": "source-fingerprint",
    }

    async def mark_running(session, *, job_id, execution_id):
        calls.append(("running", job_id))
        return SimpleNamespace(id=job_id, scope=ADVISOR_SCOPE_FIRST_IMPRESSION)

    async def mark_failed(session, **kwargs):
        calls.append(("failed", kwargs))

    async def mark_complete(session, **kwargs):
        calls.append(("complete", kwargs))

    async def mark_first_running(session, **kwargs):
        calls.append(("first_running", kwargs))

    async def mark_first_failed(session, **kwargs):
        calls.append(("first_failed", kwargs))

    async def mark_first_complete(session, **kwargs):
        calls.append(("first_complete", kwargs))

    async def update_progress(session, **kwargs):
        calls.append(("progress", kwargs["progress"]))

    async def get_access(*args, **kwargs):
        return book, None, SimpleNamespace()

    async def build_report(*args, **kwargs):
        return report

    async def persist_report(*args, **kwargs):
        calls.append(("persist", kwargs["report"]))
        return kwargs["report"]

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", mark_running)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)
    monkeypatch.setattr(
        "app.services.advisor_jobs_service.mark_advisor_job_complete", mark_complete
    )
    monkeypatch.setattr(
        "app.services.advisor_jobs_service.update_advisor_job_progress", update_progress
    )
    monkeypatch.setattr(
        "app.services.first_impression_service.mark_first_impression_running",
        mark_first_running,
    )
    monkeypatch.setattr(
        "app.services.first_impression_service.mark_first_impression_failed",
        mark_first_failed,
    )
    monkeypatch.setattr(
        "app.services.first_impression_service.mark_first_impression_complete",
        mark_first_complete,
    )
    monkeypatch.setattr(
        "app.utils.books.collaboration_access.get_book_with_ai_scan_access", get_access
    )
    monkeypatch.setattr(
        "app.services.beta_reader_analysis_service.build_beta_reader_report", build_report
    )
    monkeypatch.setattr(
        "app.services.beta_reader_analysis_service.persist_beta_reader_report", persist_report
    )

    result = intelligence_tasks.generate_beta_reader_report_task.run(
        job_id=str(job_id),
        book_id=str(book_id),
        user_id=str(user_id),
        request_payload={"scope": "full_book", "checks": ["reader_feedback"]},
    )

    assert result == report
    assert [name for name, _ in calls] == [
        "running",
        "first_running",
        "progress",
        "persist",
        "complete",
        "first_complete",
    ]
    assert calls[-1][1]["report"] == report


def test_beta_reader_worker_preserves_terminal_access_error_code(monkeypatch):
    job_id, book_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db = _Database(SimpleNamespace(id=user_id))
    failures: list[dict] = []

    async def mark_running(*args, **kwargs):
        return SimpleNamespace(scope="book")

    async def mark_failed(session, **kwargs):
        failures.append(kwargs)

    async def deny_access(*args, **kwargs):
        raise HTTPException(403, "Permission revoked")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _SessionFactory(db))
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_running", mark_running)
    monkeypatch.setattr("app.services.advisor_jobs_service.mark_advisor_job_failed", mark_failed)
    monkeypatch.setattr(
        "app.utils.books.collaboration_access.get_book_with_ai_scan_access", deny_access
    )

    with pytest.raises(ValueError, match="beta_reader_access_denied"):
        intelligence_tasks.generate_beta_reader_report_task.run(
            job_id=str(job_id),
            book_id=str(book_id),
            user_id=str(user_id),
            request_payload={"scope": "full_book", "checks": ["repetition"]},
        )

    assert len(failures) == 1
    assert failures[0]["error_code"] == "beta_reader_access_denied"


def test_beta_reader_worker_retries_only_before_analysis_work_starts(monkeypatch):
    class BrokenSessionFactory:
        async def __aenter__(self):
            raise OSError("database unavailable")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def retry(**kwargs):
        raise RuntimeError(f"retry:{type(kwargs['exc']).__name__}")

    monkeypatch.setattr(intelligence_tasks, "run_worker_coro", _run_coro)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", BrokenSessionFactory)
    monkeypatch.setattr(intelligence_tasks.generate_beta_reader_report_task, "retry", retry)
    intelligence_tasks.generate_beta_reader_report_task.request.retries = 0

    with pytest.raises(RuntimeError, match="retry:OSError"):
        intelligence_tasks.generate_beta_reader_report_task.run(
            job_id=str(uuid.uuid4()),
            book_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            request_payload={"scope": "full_book", "checks": ["repetition"]},
        )
