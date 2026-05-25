from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.intelligence import AdvisorJob
from app.models.user import User
from app.core.security import hash_password
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
