from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.monetization_service import send_due_trial_emails
from app.utils.internal_job_utils import verify_internal_job_secret

router = APIRouter()


@router.post("/jobs/send-due-trial-emails")
async def run_send_due_trial_emails(
    limit: int = Query(100, ge=1, le=500),
    x_internal_job_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    verify_internal_job_secret(x_internal_job_secret)
    result = await send_due_trial_emails(db, limit=limit)
    await db.commit()
    return result
