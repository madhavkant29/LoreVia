import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.intelligence import AdvisorJob
from app.models.user import User
from app.services import first_impression_service
from app.services.advisor_jobs_service import ADVISOR_SCOPE_FIRST_IMPRESSION
from app.utils.first_impression_utils import normalize_first_impression_state


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Database:
    def __init__(self, book, user):
        self.book = book
        self.user = user
        self.job = None
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        if "pg_advisory_xact_lock" in str(statement):
            return _Result()
        return _Result(self.book)

    async def get(self, model, requested_id, **kwargs):
        if model is User:
            return self.user
        if model is AdvisorJob:
            return self.job
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, value):
        return None


def _eligible():
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, tier="author", created_at=None)
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        mode="author",
        work_type="novel",
        status="ready",
        total_chapters=2,
        writer_workspace={},
    )
    return book, user


def _report():
    return {
        "report_id": "report-1",
        "scope": "full_book",
        "request_hash": "request-hash",
        "source_fingerprint": "source-fingerprint",
        "created_at": "2026-08-31T00:00:00Z",
        "is_stale": False,
        "checks": ["reader_feedback"],
        "coverage": {
            "requested_chapters": [1, 2],
            "analyzed_chapters": [1, 2],
            "missing_chapters": [],
            "word_count": 4000,
            "character_count": 3,
        },
        "overall_impression": "The relationship turn is supported by the final scene.",
        "strengths": ["The chapter-two confrontation has clear emotional stakes."],
        "reader_questions": [],
        "prioritized_revisions": [],
        "overused_terms": [],
        "character_voices": [],
        "findings": [],
        "revision_candidates": [],
        "warnings": [],
    }


@pytest.mark.asyncio
async def test_automatic_first_read_is_idempotent_and_bypasses_manual_rate_limit(monkeypatch):
    book, user = _eligible()
    db = _Database(book, user)
    job = SimpleNamespace(
        id=uuid.uuid4(),
        scope=ADVISOR_SCOPE_FIRST_IMPRESSION,
        status="queued",
        result_json=None,
        error_code=None,
    )
    created = 0
    enqueued = 0
    manual_limit_calls = 0

    async def prepare(*args, **kwargs):
        return {
            "chapters": [SimpleNamespace(number=1), SimpleNamespace(number=2)],
            "request_hash": "request-hash",
            "source_fingerprint": "source-fingerprint",
            "cached": None,
        }

    async def create_job(*args, **kwargs):
        nonlocal created
        created += 1
        db.job = job
        return job

    async def get_job(*args, **kwargs):
        return db.job

    async def manual_rate_limit(*args, **kwargs):
        nonlocal manual_limit_calls
        manual_limit_calls += 1
        raise AssertionError("The automatic first read must not consume the manual allowance.")

    def enqueue(*args, **kwargs):
        nonlocal enqueued
        enqueued += 1

    monkeypatch.setattr(first_impression_service, "prepare_beta_reader_run", prepare)
    monkeypatch.setattr(first_impression_service, "create_advisor_job", create_job)
    monkeypatch.setattr(first_impression_service, "get_advisor_job", get_job)
    monkeypatch.setattr(
        first_impression_service,
        "enforce_continuity_rate_limit",
        manual_rate_limit,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.tasks.intelligence_tasks.generate_beta_reader_report_task.apply_async",
        enqueue,
    )

    first = await first_impression_service.queue_first_impression(
        db, book_id=book.id, user_id=user.id, strict=True
    )
    second = await first_impression_service.queue_first_impression(
        db, book_id=book.id, user_id=user.id, strict=True
    )

    assert first.status == "queued"
    assert second.status == "queued"
    assert created == 1
    assert enqueued == 1
    assert manual_limit_calls == 0
    assert book.writer_workspace["first_impression"]["job_id"] == str(job.id)


@pytest.mark.asyncio
async def test_cached_reader_feedback_report_completes_without_a_job(monkeypatch):
    book, user = _eligible()
    db = _Database(book, user)

    async def prepare(*args, **kwargs):
        return {
            "chapters": [SimpleNamespace(number=1), SimpleNamespace(number=2)],
            "request_hash": "request-hash",
            "source_fingerprint": "source-fingerprint",
            "cached": _report(),
        }

    async def unexpected_job(*args, **kwargs):
        raise AssertionError("A matching cached report should not create another job.")

    monkeypatch.setattr(first_impression_service, "prepare_beta_reader_run", prepare)
    monkeypatch.setattr(first_impression_service, "create_advisor_job", unexpected_job)

    result = await first_impression_service.queue_first_impression(
        db, book_id=book.id, user_id=user.id, strict=True
    )

    assert result.status == "complete"
    assert result.report is not None and result.report.report_id == "report-1"
    assert book.writer_workspace["first_impression"]["status"] == "complete"
    assert book.writer_workspace["first_impression"]["job_id"] is None


@pytest.mark.asyncio
async def test_completed_first_read_status_remains_viewable_during_later_reprocessing(monkeypatch):
    book, user = _eligible()
    book.status = "processing"
    book.writer_workspace = {
        "first_impression": {
            "status": "complete",
            "job_id": None,
            "report_id": "report-1",
            "request_hash": "request-hash",
            "source_fingerprint": "source-fingerprint",
            "started_at": "2026-08-31T00:00:00Z",
            "completed_at": "2026-08-31T00:01:00Z",
            "error_code": None,
        }
    }
    db = _Database(book, user)

    async def list_reports(*args, **kwargs):
        report = _report()
        report["is_stale"] = True
        return [report]

    monkeypatch.setattr(first_impression_service, "list_beta_reader_reports", list_reports)

    result = await first_impression_service.get_first_impression_status(db, book=book, user=user)

    assert result.status == "complete"
    assert result.report is not None and result.report.is_stale is True


@pytest.mark.parametrize(
    ("changes", "expected_status"),
    [
        ({"mode": "reader"}, 400),
        ({"work_type": "other"}, 400),
        ({"status": "processing"}, 409),
        ({"total_chapters": 0}, 409),
        ({"user_id": uuid.uuid4()}, 403),
    ],
)
def test_first_read_rejects_ineligible_manuscripts(changes, expected_status):
    book, user = _eligible()
    for key, value in changes.items():
        setattr(book, key, value)

    with pytest.raises(HTTPException) as exc_info:
        first_impression_service._ensure_eligible(book, user)

    assert exc_info.value.status_code == expected_status


def test_first_read_rejects_ineligible_plan(monkeypatch):
    book, user = _eligible()

    def deny_plan(value):
        raise HTTPException(403, "Author access required")

    monkeypatch.setattr(first_impression_service, "require_author_access", deny_plan)
    with pytest.raises(HTTPException) as exc_info:
        first_impression_service._ensure_eligible(book, user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "reader"},
        {"work_type": "other"},
        {"status": "processing"},
        {"total_chapters": 0},
        {"user_id": uuid.uuid4()},
    ],
)
async def test_automatic_queue_returns_quietly_for_ineligible_manuscripts(changes, monkeypatch):
    book, user = _eligible()
    for key, value in changes.items():
        setattr(book, key, value)
    db = _Database(book, user)

    async def unexpected_prepare(*args, **kwargs):
        raise AssertionError("Ineligible automatic calls must not prepare or enqueue a job.")

    monkeypatch.setattr(first_impression_service, "prepare_beta_reader_run", unexpected_prepare)

    result = await first_impression_service.queue_first_impression(
        db, book_id=book.id, user_id=user.id, strict=False
    )

    assert result is None
    assert db.rollbacks == 1


@pytest.mark.asyncio
async def test_automatic_queue_returns_quietly_for_ineligible_plan(monkeypatch):
    book, user = _eligible()
    db = _Database(book, user)

    def deny_plan(value):
        raise HTTPException(403, "Author access required")

    async def unexpected_prepare(*args, **kwargs):
        raise AssertionError("Ineligible plans must not prepare or enqueue a job.")

    monkeypatch.setattr(first_impression_service, "require_author_access", deny_plan)
    monkeypatch.setattr(first_impression_service, "prepare_beta_reader_run", unexpected_prepare)

    result = await first_impression_service.queue_first_impression(
        db, book_id=book.id, user_id=user.id, strict=False
    )

    assert result is None
    assert db.rollbacks == 1


@pytest.mark.asyncio
async def test_enqueue_failure_keeps_manuscript_ready_and_requires_explicit_retry(monkeypatch):
    book, user = _eligible()
    db = _Database(book, user)
    job = SimpleNamespace(
        id=uuid.uuid4(),
        scope=ADVISOR_SCOPE_FIRST_IMPRESSION,
        status="queued",
        result_json=None,
        error_code=None,
        error_detail=None,
        updated_at=None,
    )

    async def prepare(*args, **kwargs):
        return {
            "chapters": [SimpleNamespace(number=1)],
            "request_hash": "request-hash",
            "source_fingerprint": "source-fingerprint",
            "cached": None,
        }

    async def create_job(*args, **kwargs):
        db.job = job
        return job

    def fail_enqueue(*args, **kwargs):
        raise OSError("queue unavailable")

    monkeypatch.setattr(first_impression_service, "prepare_beta_reader_run", prepare)
    monkeypatch.setattr(first_impression_service, "create_advisor_job", create_job)
    monkeypatch.setattr(
        "app.workers.tasks.intelligence_tasks.generate_beta_reader_report_task.apply_async",
        fail_enqueue,
    )

    result = await first_impression_service.queue_first_impression(
        db, book_id=book.id, user_id=user.id, strict=False
    )

    assert result is not None and result.status == "failed" and result.can_retry is True
    assert book.status == "ready"
    assert book.writer_workspace["first_impression"]["status"] == "failed"
    assert book.writer_workspace["first_impression"]["completed_at"] is not None


def test_old_beta_reader_report_contract_defaults_new_optional_fields():
    from app.schemas.advisor import BetaReaderReportOut

    parsed = BetaReaderReportOut.model_validate(_report())
    assert parsed.reader_vibe == ""
    assert parsed.story_understanding == ""


def test_first_impression_state_normalization_handles_malformed_values():
    normalized = normalize_first_impression_state(
        {
            "status": " RUNNING ",
            "job_id": "  job-1  ",
            "report_id": "",
            "request_hash": "\n request-hash\t",
            "source_fingerprint": None,
            "started_at": " 2026-08-31T00:00:00Z ",
            "completed_at": [],
            "error_code": " provider_failed ",
        }
    )

    assert normalized == {
        "status": "running",
        "job_id": "job-1",
        "report_id": None,
        "request_hash": "request-hash",
        "source_fingerprint": None,
        "started_at": "2026-08-31T00:00:00Z",
        "completed_at": None,
        "error_code": "provider_failed",
    }
    assert normalize_first_impression_state({"status": "unknown"})["status"] == "not_started"
    assert normalize_first_impression_state(None)["status"] == "not_started"
