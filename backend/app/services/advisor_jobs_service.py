from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.intelligence import AdvisorJob, AdvisorSuggestionJob
from app.utils.logging.errors import redact_sensitive_text

ADVISOR_SCOPE_BOOK = "book"
ADVISOR_SCOPE_BETA_READER = "book_beta_reader"
ADVISOR_SCOPE_FIRST_IMPRESSION = "book_first_impression"
ADVISOR_SCOPE_SERIES = "series"
ADVISOR_STATUS_QUEUED = "queued"
ADVISOR_STATUS_RUNNING = "running"
ADVISOR_STATUS_COMPLETE = "complete"
ADVISOR_STATUS_FAILED = "failed"
ADVISOR_EXECUTION_ID_KEY = "_execution_id"
ADVISOR_JOB_LEASE = timedelta(minutes=15)


def _job_expiry() -> datetime:
    ttl_seconds = max(int(settings.CELERY_RESULT_EXPIRES_SECONDS or 3600), 300)
    return datetime.now(UTC) + timedelta(seconds=ttl_seconds)


def serialize_advisor_job(job: AdvisorJob) -> dict[str, Any]:
    return {
        "task_id": str(job.id),
        "status": job.status,
        "result": public_advisor_job_result(job.result_json),
        "error": getattr(job, "error_detail", None) or getattr(job, "error_code", None),
    }


def public_advisor_job_result(result_json: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(result_json, dict):
        return result_json
    public_result = {
        key: value for key, value in result_json.items() if key != ADVISOR_EXECUTION_ID_KEY
    }
    return public_result or None


def advisor_job_execution_matches(
    job: AdvisorJob | AdvisorSuggestionJob,
    execution_id: str | None,
) -> bool:
    normalized_execution_id = str(execution_id or "").strip()
    if not normalized_execution_id:
        return True
    result_json = job.result_json if isinstance(job.result_json, dict) else {}
    return str(result_json.get(ADVISOR_EXECUTION_ID_KEY) or "") == normalized_execution_id


def advisor_job_is_claimable(
    job: AdvisorJob | AdvisorSuggestionJob,
    *,
    execution_id: str,
    now: datetime,
) -> bool:
    if job.status == ADVISOR_STATUS_QUEUED:
        return True
    if job.status != ADVISOR_STATUS_RUNNING:
        return False
    if advisor_job_execution_matches(job, execution_id):
        return True
    updated_at = job.updated_at
    if updated_at is None:
        return True
    updated = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=UTC)
    current = now if now.tzinfo else now.replace(tzinfo=UTC)
    return current - updated >= ADVISOR_JOB_LEASE


async def create_advisor_job(
    db: AsyncSession,
    *,
    scope: str,
    user_id: uuid.UUID,
    book_id: uuid.UUID | None = None,
    series_id: uuid.UUID | None = None,
    commit: bool = True,
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
    if commit:
        await db.commit()
        await db.refresh(job)
    else:
        await db.flush()
    return job


async def get_advisor_job(db: AsyncSession, *, job_id: uuid.UUID) -> AdvisorJob | None:
    return await db.get(AdvisorJob, job_id)


async def mark_advisor_job_running(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    execution_id: str | None = None,
    now: datetime | None = None,
) -> AdvisorJob | None:
    job = await db.get(AdvisorJob, job_id, with_for_update=True)
    if job is None:
        return None
    current = now or datetime.now(UTC)
    normalized_execution_id = str(execution_id or "").strip()
    if job.status not in {ADVISOR_STATUS_QUEUED, ADVISOR_STATUS_RUNNING}:
        return None
    if normalized_execution_id and not advisor_job_is_claimable(
        job,
        execution_id=normalized_execution_id,
        now=current,
    ):
        return None
    job.status = ADVISOR_STATUS_RUNNING
    job.result_json = (
        {ADVISOR_EXECUTION_ID_KEY: normalized_execution_id} if normalized_execution_id else None
    )
    job.error_code = None
    job.error_detail = None
    job.updated_at = current
    await db.commit()
    await db.refresh(job)
    return job


async def update_advisor_job_progress(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    progress: dict[str, Any],
    execution_id: str | None = None,
) -> AdvisorJob | None:
    job = await db.get(AdvisorJob, job_id, with_for_update=True)
    if job is None:
        return None
    if not advisor_job_execution_matches(job, execution_id):
        return None
    job.status = ADVISOR_STATUS_RUNNING
    result_json = {"progress": progress}
    normalized_execution_id = str(execution_id or "").strip()
    if normalized_execution_id:
        result_json[ADVISOR_EXECUTION_ID_KEY] = normalized_execution_id
    job.result_json = result_json
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job


async def mark_advisor_job_complete(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    result_payload: dict[str, Any],
    execution_id: str | None = None,
) -> AdvisorJob | None:
    job = await db.get(AdvisorJob, job_id, with_for_update=True)
    if job is None:
        return None
    if not advisor_job_execution_matches(job, execution_id):
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
    execution_id: str | None = None,
) -> AdvisorJob | None:
    job = await db.get(AdvisorJob, job_id, with_for_update=True)
    if job is None:
        return None
    if not advisor_job_execution_matches(job, execution_id):
        return None
    job.status = ADVISOR_STATUS_FAILED
    job.error_code = error_code
    job.error_detail = redact_sensitive_text(error_detail)
    job.result_json = None
    job.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job


async def purge_expired_advisor_jobs(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    cutoff = now or datetime.now(UTC)
    result = await db.execute(
        delete(AdvisorJob).where(
            AdvisorJob.expires_at.is_not(None),
            AdvisorJob.expires_at < cutoff,
        )
    )
    await db.commit()
    return int(result.rowcount or 0)
