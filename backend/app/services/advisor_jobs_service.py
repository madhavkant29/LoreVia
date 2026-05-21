from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.intelligence import AdvisorJob

ADVISOR_SCOPE_BOOK = "book"
ADVISOR_SCOPE_SERIES = "series"
ADVISOR_STATUS_QUEUED = "queued"
ADVISOR_STATUS_RUNNING = "running"
ADVISOR_STATUS_COMPLETE = "complete"
ADVISOR_STATUS_FAILED = "failed"


def _job_expiry() -> datetime:
    ttl_seconds = max(int(settings.CELERY_RESULT_EXPIRES_SECONDS or 3600), 300)
    return datetime.now(UTC) + timedelta(seconds=ttl_seconds)


def serialize_advisor_job(job: AdvisorJob) -> dict[str, Any]:
    return {
        "task_id": str(job.id),
        "status": job.status,
        "result": job.result_json,
        "error": job.error_code,
    }


async def create_advisor_job(
    db: AsyncSession,
    *,
    scope: str,
    user_id: uuid.UUID,
    book_id: uuid.UUID | None = None,
    series_id: uuid.UUID | None = None,
) -> AdvisorJob:
    job = AdvisorJob(
        id=uuid.uuid4(),
        user_id=user_id,
        book_id=book_id,
        series_id=series_id,
        scope=scope,
        status=ADVISOR_STATUS_QUEUED,
        expires_at=_job_expiry(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_advisor_job(db: AsyncSession, *, job_id: uuid.UUID) -> AdvisorJob | None:
    return await db.get(AdvisorJob, job_id)


async def mark_advisor_job_running(db: AsyncSession, *, job_id: uuid.UUID) -> AdvisorJob | None:
    job = await db.get(AdvisorJob, job_id)
    if job is None:
        return None
    job.status = ADVISOR_STATUS_RUNNING
    job.error_code = None
    job.error_detail = None
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job


async def mark_advisor_job_complete(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    result_payload: dict[str, Any],
) -> AdvisorJob | None:
    job = await db.get(AdvisorJob, job_id)
    if job is None:
        return None
    job.status = ADVISOR_STATUS_COMPLETE
    job.result_json = result_payload
    job.error_code = None
    job.error_detail = None
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job


async def mark_advisor_job_failed(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    error_code: str,
    error_detail: str | None = None,
) -> AdvisorJob | None:
    job = await db.get(AdvisorJob, job_id)
    if job is None:
        return None
    job.status = ADVISOR_STATUS_FAILED
    job.error_code = error_code
    job.error_detail = error_detail
    job.result_json = None
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job
