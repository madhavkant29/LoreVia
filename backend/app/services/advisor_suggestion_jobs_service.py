from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.intelligence import AdvisorSuggestionJob
from app.utils.logging.errors import redact_sensitive_text

ADVISOR_SUGGESTION_STATUS_QUEUED = "queued"
ADVISOR_SUGGESTION_STATUS_RUNNING = "running"
ADVISOR_SUGGESTION_STATUS_COMPLETE = "complete"
ADVISOR_SUGGESTION_STATUS_FAILED = "failed"


def _job_expiry() -> datetime:
    ttl_seconds = max(int(settings.CELERY_RESULT_EXPIRES_SECONDS or 3600), 300)
    return datetime.now(UTC) + timedelta(seconds=ttl_seconds)


def serialize_advisor_suggestion_job(job: AdvisorSuggestionJob) -> dict[str, Any]:
    return {
        "job_id": str(job.id),
        "status": job.status,
        "result": job.result_json,
        "error": job.error_code,
    }


async def create_advisor_suggestion_job(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    cache_key: str | None = None,
) -> AdvisorSuggestionJob:
    job = AdvisorSuggestionJob(
        id=uuid.uuid4(),
        user_id=user_id,
        book_id=book_id,
        status=ADVISOR_SUGGESTION_STATUS_QUEUED,
        cache_key=cache_key,
        expires_at=_job_expiry(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_advisor_suggestion_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
) -> AdvisorSuggestionJob | None:
    return await db.get(AdvisorSuggestionJob, job_id)


async def mark_advisor_suggestion_job_running(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
) -> AdvisorSuggestionJob | None:
    job = await db.get(AdvisorSuggestionJob, job_id)
    if job is None:
        return None
    job.status = ADVISOR_SUGGESTION_STATUS_RUNNING
    job.error_code = None
    job.error_detail = None
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job


async def mark_advisor_suggestion_job_complete(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    result_payload: dict[str, Any],
) -> AdvisorSuggestionJob | None:
    job = await db.get(AdvisorSuggestionJob, job_id)
    if job is None:
        return None
    job.status = ADVISOR_SUGGESTION_STATUS_COMPLETE
    job.result_json = result_payload
    job.error_code = None
    job.error_detail = None
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job


async def mark_advisor_suggestion_job_failed(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    error_code: str,
    error_detail: str | None = None,
) -> AdvisorSuggestionJob | None:
    job = await db.get(AdvisorSuggestionJob, job_id)
    if job is None:
        return None
    job.status = ADVISOR_SUGGESTION_STATUS_FAILED
    job.error_code = error_code
    job.error_detail = redact_sensitive_text(error_detail)
    job.result_json = None
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job


async def purge_expired_advisor_suggestion_jobs(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    cutoff = now or datetime.now(UTC)
    result = await db.execute(
        delete(AdvisorSuggestionJob).where(
            AdvisorSuggestionJob.expires_at.is_not(None),
            AdvisorSuggestionJob.expires_at < cutoff,
        )
    )
    await db.commit()
    return int(result.rowcount or 0)
