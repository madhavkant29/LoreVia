"""Runtime coverage for persisted advisor suggestion jobs."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.intelligence import AdvisorSuggestionJob
from app.services import advisor_suggestion_jobs_service as jobs


class FakeDB:
    def __init__(self, stored=None, rowcount=0):
        self.stored = stored
        self.rowcount = rowcount
        self.added = []
        self.commits = 0
        self.refreshed = []
        self.executed = []

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshed.append(value)

    async def get(self, model, item_id, **_kwargs):
        assert model is AdvisorSuggestionJob
        return self.stored if self.stored is not None and self.stored.id == item_id else None

    async def execute(self, statement):
        self.executed.append(statement)
        return SimpleNamespace(rowcount=self.rowcount)


def build_job():
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=jobs.ADVISOR_SUGGESTION_STATUS_QUEUED,
        result_json=None,
        error_code="old_error",
        error_detail="old detail",
        updated_at=None,
    )


def test_job_expiry_uses_configured_ttl_and_enforces_minimum(monkeypatch):
    monkeypatch.setattr(jobs.settings, "CELERY_RESULT_EXPIRES_SECONDS", 10)
    short_expiry = jobs._job_expiry()
    assert 299 <= (short_expiry - datetime.now(UTC)).total_seconds() <= 300

    monkeypatch.setattr(jobs.settings, "CELERY_RESULT_EXPIRES_SECONDS", 7200)
    long_expiry = jobs._job_expiry()
    assert 7199 <= (long_expiry - datetime.now(UTC)).total_seconds() <= 7200


@pytest.mark.asyncio
async def test_create_get_and_serialize_advisor_suggestion_job():
    db = FakeDB()
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    created = await jobs.create_advisor_suggestion_job(
        db, user_id=user_id, book_id=book_id, cache_key="advisor:book-1"
    )

    assert created.user_id == user_id
    assert created.book_id == book_id
    assert created.status == jobs.ADVISOR_SUGGESTION_STATUS_QUEUED
    assert created.cache_key == "advisor:book-1"
    assert db.added == [created]
    assert db.commits == 1
    assert db.refreshed == [created]

    db.stored = created
    assert await jobs.get_advisor_suggestion_job(db, job_id=created.id) is created
    assert jobs.serialize_advisor_suggestion_job(created) == {
        "job_id": str(created.id),
        "status": "queued",
        "result": None,
        "error": None,
    }

    created.status = jobs.ADVISOR_SUGGESTION_STATUS_FAILED
    created.error_code = "llm_budget"
    created.error_detail = "AI capacity resets on September 1."
    assert jobs.serialize_advisor_suggestion_job(created)["error"] == created.error_detail


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["running", "complete", "failed"])
async def test_job_state_transitions_commit_and_refresh(operation):
    job = build_job()
    db = FakeDB(job)

    if operation == "running":
        result = await jobs.mark_advisor_suggestion_job_running(db, job_id=job.id)
        assert job.status == "running"
        assert job.error_code is None and job.error_detail is None
    elif operation == "complete":
        payload = {"suggestions": [{"title": "Clarify the gate"}]}
        result = await jobs.mark_advisor_suggestion_job_complete(
            db, job_id=job.id, result_payload=payload
        )
        assert job.status == "complete" and job.result_json == payload
        assert job.error_code is None and job.error_detail is None
    else:
        result = await jobs.mark_advisor_suggestion_job_failed(
            db,
            job_id=job.id,
            error_code="provider_error",
            error_detail="openai_api_key=secret-value request failed",
        )
        assert job.status == "failed"
        assert job.error_code == "provider_error"
        assert job.result_json is None
        assert "secret-value" not in job.error_detail

    assert result is job
    assert job.updated_at.tzinfo is UTC
    assert db.commits == 1 and db.refreshed == [job]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["running", "complete", "failed"])
async def test_job_state_transitions_return_none_for_missing_jobs(operation):
    db = FakeDB()
    job_id = uuid.uuid4()
    if operation == "running":
        result = await jobs.mark_advisor_suggestion_job_running(db, job_id=job_id)
    elif operation == "complete":
        result = await jobs.mark_advisor_suggestion_job_complete(
            db, job_id=job_id, result_payload={}
        )
    else:
        result = await jobs.mark_advisor_suggestion_job_failed(
            db, job_id=job_id, error_code="missing"
        )
    assert result is None
    assert db.commits == 0


@pytest.mark.asyncio
async def test_suggestion_job_claim_rejects_duplicate_and_stale_completion():
    job = build_job()
    db = FakeDB(job)

    claimed = await jobs.mark_advisor_suggestion_job_running(
        db,
        job_id=job.id,
        execution_id="scan-one",
    )
    duplicate = await jobs.mark_advisor_suggestion_job_running(
        db,
        job_id=job.id,
        execution_id="scan-two",
    )
    stale_completion = await jobs.mark_advisor_suggestion_job_complete(
        db,
        job_id=job.id,
        execution_id="scan-two",
        result_payload={"suggestions": ["stale"]},
    )
    completed = await jobs.mark_advisor_suggestion_job_complete(
        db,
        job_id=job.id,
        execution_id="scan-one",
        result_payload={"suggestions": ["current"]},
    )

    assert claimed is job
    assert duplicate is None
    assert stale_completion is None
    assert completed is job
    assert jobs.serialize_advisor_suggestion_job(job)["result"] == {"suggestions": ["current"]}


@pytest.mark.asyncio
async def test_purge_expired_jobs_returns_affected_count_and_commits():
    db = FakeDB(rowcount=4)
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    assert await jobs.purge_expired_advisor_suggestion_jobs(db, now=cutoff) == 4
    assert len(db.executed) == 1
    assert db.commits == 1

    empty_db = FakeDB(rowcount=None)
    assert await jobs.purge_expired_advisor_suggestion_jobs(empty_db) == 0
