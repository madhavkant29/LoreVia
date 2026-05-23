from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.intelligence import AdvisorJob
from app.models.user import User
from app.core.security import hash_password
from app.services.advisor_jobs_service import purge_expired_advisor_jobs


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
