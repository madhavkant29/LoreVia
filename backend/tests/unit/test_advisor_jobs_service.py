from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import hash_password
from app.models.intelligence import AdvisorJob
from app.models.user import User
from app.services import advisor_jobs_service as jobs
from app.services.advisor_jobs_service import mark_advisor_job_failed, purge_expired_advisor_jobs


@pytest.mark.asyncio
async def test_purge_expired_advisor_jobs_deletes_only_expired_rows(db):
    user = User(
        email=f"advisor-jobs-{uuid.uuid4().hex[:8]}@lorevia.test",
        username=f"advisorjobs{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("SafePass123!@#"),
        token_version=1,
    )
    db.add(user)
    await db.flush()
    expired_job = AdvisorJob(
        user_id=user.id,
        scope="book",
        status="complete",
        expires_at=datetime.now(UTC) - timedelta(hours=2),
    )
    active_job = AdvisorJob(
        user_id=user.id,
        scope="series",
        status="running",
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )
    db.add_all([expired_job, active_job])
    await db.commit()

    deleted = await purge_expired_advisor_jobs(db)

    assert deleted == 1
    assert await db.get(AdvisorJob, expired_job.id) is None
    assert await db.get(AdvisorJob, active_job.id) is not None


@pytest.mark.asyncio
async def test_mark_advisor_job_failed_redacts_sensitive_error_detail(db):
    user = User(
        email=f"advisor-jobs-redact-{uuid.uuid4().hex[:8]}@lorevia.test",
        username=f"advisorjobsredact{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("SafePass123!@#"),
        token_version=1,
    )
    db.add(user)
    await db.flush()
    job = AdvisorJob(
        user_id=user.id,
        scope="book",
        status="running",
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )
    db.add(job)
    await db.commit()

    await mark_advisor_job_failed(
        db,
        job_id=job.id,
        error_code="advisor_generation_failed",
        error_detail="openai_api_key=sk-secret",
    )

    refreshed = await db.get(AdvisorJob, job.id)
    assert refreshed is not None
    assert refreshed.error_detail == "openai_api_key=[REDACTED]"


@pytest.mark.asyncio
async def test_advisor_job_execution_claim_blocks_duplicates_and_allows_recovery(db):
    user = User(
        email=f"advisor-claim-{uuid.uuid4().hex[:8]}@lorevia.test",
        username=f"advisorclaim{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("SafePass123!@#"),
        token_version=1,
    )
    db.add(user)
    await db.flush()
    job = AdvisorJob(
        user_id=user.id,
        scope="book",
        status="queued",
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )
    db.add(job)
    await db.commit()
    started_at = datetime.now(UTC)

    first = await jobs.mark_advisor_job_running(
        db,
        job_id=job.id,
        execution_id="execution-one",
        now=started_at,
    )
    duplicate = await jobs.mark_advisor_job_running(
        db,
        job_id=job.id,
        execution_id="execution-two",
        now=started_at + timedelta(minutes=1),
    )
    redelivery = await jobs.mark_advisor_job_running(
        db,
        job_id=job.id,
        execution_id="execution-one",
        now=started_at + timedelta(minutes=1),
    )
    recovered = await jobs.mark_advisor_job_running(
        db,
        job_id=job.id,
        execution_id="execution-two",
        now=started_at + timedelta(minutes=16),
    )
    stale_completion = await jobs.mark_advisor_job_complete(
        db,
        job_id=job.id,
        execution_id="execution-one",
        result_payload={"reply": "stale"},
    )
    completed = await jobs.mark_advisor_job_complete(
        db,
        job_id=job.id,
        execution_id="execution-two",
        result_payload={"reply": "current"},
    )

    assert first is job
    assert duplicate is None
    assert redelivery is job
    assert recovered is job
    assert stale_completion is None
    assert completed is job
    assert job.status == "complete"
    assert job.result_json == {"reply": "current"}


class _FakeJobDB:
    def __init__(self, stored=None):
        self.stored = stored
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshed.append(value)

    async def get(self, model, item_id, **_kwargs):
        assert model is AdvisorJob
        return self.stored if self.stored is not None and self.stored.id == item_id else None


@pytest.mark.asyncio
async def test_create_get_serialize_and_transition_advisor_job(monkeypatch):
    monkeypatch.setattr(jobs.settings, "CELERY_RESULT_EXPIRES_SECONDS", 10)
    db = _FakeJobDB()
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    job = await jobs.create_advisor_job(
        db,
        scope=jobs.ADVISOR_SCOPE_BOOK,
        user_id=user_id,
        book_id=book_id,
    )
    assert job.user_id == user_id and job.book_id == book_id
    assert job.scope == "book" and job.status == "queued"
    assert 299 <= (job.expires_at - datetime.now(UTC)).total_seconds() <= 300
    assert db.added == [job] and db.commits == 1 and db.refreshed == [job]

    db.stored = job
    assert await jobs.get_advisor_job(db, job_id=job.id) is job
    assert jobs.serialize_advisor_job(job) == {
        "task_id": str(job.id),
        "status": "queued",
        "result": None,
        "error": None,
    }

    job.status = "failed"
    job.error_code = "llm_budget"
    job.error_detail = "AI capacity resets on September 1."
    assert jobs.serialize_advisor_job(job)["error"] == job.error_detail
    assert await jobs.mark_advisor_job_running(db, job_id=job.id) is None

    job.status = "queued"
    await jobs.mark_advisor_job_running(db, job_id=job.id)
    assert job.status == "running" and job.error_code is None and job.error_detail is None

    payload = {"reply": "The gate should open later."}
    await jobs.mark_advisor_job_complete(db, job_id=job.id, result_payload=payload)
    assert job.status == "complete" and job.result_json == payload


@pytest.mark.asyncio
async def test_advisor_job_transitions_return_none_when_job_is_missing():
    db = _FakeJobDB()
    job_id = uuid.uuid4()
    assert await jobs.get_advisor_job(db, job_id=job_id) is None
    assert await jobs.mark_advisor_job_running(db, job_id=job_id) is None
    assert await jobs.mark_advisor_job_complete(db, job_id=job_id, result_payload={}) is None
    assert await jobs.mark_advisor_job_failed(db, job_id=job_id, error_code="missing") is None
    assert db.commits == 0
