from __future__ import annotations

from app.workers.celery_app import celery_app
from app.utils.worker_async_utils import run_worker_coro


@celery_app.task(bind=True, name="maintenance_tasks.send_due_trial_emails", queue="intelligence", max_retries=2)
def send_due_trial_emails_task(self, *, limit: int = 100):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.services.trial_email_service import send_due_trial_emails

        async with AsyncSessionLocal() as db:
            result = await send_due_trial_emails(db, limit=limit)
            await db.commit()
            return result

    try:
        return run_worker_coro(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="maintenance_tasks.process_beta_reads", queue="intelligence", max_retries=2)
def process_beta_reads_task(self, *, limit: int = 100):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.utils.beta_read_utils import run_beta_read_jobs

        async with AsyncSessionLocal() as db:
            result = await run_beta_read_jobs(db, limit=limit)
            await db.commit()
            return result.model_dump()

    try:
        return run_worker_coro(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
