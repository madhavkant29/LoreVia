from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rate_limit import (
    rate_limit_internal_job,
    rate_limit_verified_internal_scheduler,
)
from app.core.database import get_db
from app.services.trial_email_service import send_due_trial_emails
from app.utils.beta_read_job_utils import run_beta_read_jobs
from app.utils.internal_job_utils import verify_internal_job_secret

router = APIRouter()


@router.post("/jobs/send-due-trial-emails")
async def run_send_due_trial_emails(
    limit: int = Query(100, ge=1, le=500),
    x_internal_job_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_internal_job),
):
    verify_internal_job_secret(x_internal_job_secret)
    await rate_limit_verified_internal_scheduler()
    result = await send_due_trial_emails(db, limit=limit)
    await db.commit()
    return result


@router.post("/jobs/process-beta-reads")
async def process_beta_reads(
    limit: int = Query(100, ge=1, le=500),
    x_internal_job_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_internal_job),
):
    verify_internal_job_secret(x_internal_job_secret)
    await rate_limit_verified_internal_scheduler()
    return await run_beta_read_jobs(db, limit=limit)
