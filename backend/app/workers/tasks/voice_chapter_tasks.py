"""Checkpointed full-chapter voice review worker."""

from __future__ import annotations

import logging
import uuid

from app.utils.exception_boundaries import FATAL_TASK_BOUNDARY_EXCEPTIONS
from app.utils.worker_async_utils import run_worker_coro
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="intelligence_tasks.review_voice_chapter",
    queue="intelligence",
    ignore_result=True,
)
def review_voice_chapter_task(self, *, job_id: str):
    execution_id = str(self.request.id or uuid.uuid4())

    async def run() -> str:
        from app.core.database import AsyncSessionLocal
        from app.services.voice_chapter_review_jobs_service import (
            claim_voice_chapter_job,
            update_voice_chapter_job,
        )
        from app.services.voice_chapter_review_service import process_voice_chapter_job

        async with AsyncSessionLocal() as db:
            job = await claim_voice_chapter_job(
                db, job_id=uuid.UUID(job_id), execution_id=execution_id
            )
            if job is None:
                return "already_claimed_or_done"
            try:
                return await process_voice_chapter_job(db, job=job, execution_id=execution_id)
            except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
                log.exception("voice_chapter_review_failed job_id=%s", job_id)
                try:
                    import sentry_sdk

                    with sentry_sdk.new_scope() as scope:
                        scope.set_tag("job_id", job_id)
                        scope.set_tag("failure_type", type(exc).__name__)
                        sentry_sdk.capture_message("voice_chapter_review_failed", level="error")
                except Exception:
                    log.warning(
                        "voice_chapter_sentry_report_failed job_id=%s", job_id, exc_info=True
                    )
                await db.rollback()
                await update_voice_chapter_job(
                    db,
                    job_id=job.id,
                    execution_id=execution_id,
                    status="failed",
                    error_code="voice_review_failed",
                    error_detail="The review stopped unexpectedly. Retry the chapter.",
                )
                return "failed"

    return run_worker_coro(run())
