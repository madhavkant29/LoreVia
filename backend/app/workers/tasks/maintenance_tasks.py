from __future__ import annotations

from app.workers.celery_app import celery_app
from app.utils.worker_async_utils import run_worker_coro


@celery_app.task(bind=True, name="maintenance_tasks.send_due_trial_emails", queue="intelligence", max_retries=2, ignore_result=True)
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


@celery_app.task(bind=True, name="maintenance_tasks.process_beta_reads", queue="intelligence", max_retries=2, ignore_result=True)
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


@celery_app.task(bind=True, name="maintenance_tasks.cleanup_expired_advisor_jobs", queue="intelligence", max_retries=2, ignore_result=True)
def cleanup_expired_advisor_jobs_task(self, *, limit: int = 1000):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.intelligence import AdvisorJob
        from app.services.advisor_jobs_service import purge_expired_advisor_jobs
        from sqlalchemy import delete, func, select

        async with AsyncSessionLocal() as db:
            # Keep each cleanup run bounded so periodic maintenance does not monopolize the worker.
            expired_count = await db.scalar(
                select(func.count())
                .select_from(AdvisorJob)
                .where(AdvisorJob.expires_at.is_not(None), AdvisorJob.expires_at < func.now())
            )
            if int(expired_count or 0) > limit:
                # Delete only up to the cutoff population in repeated hourly runs.
                rows = (
                    await db.execute(
                        select(AdvisorJob.id)
                        .where(AdvisorJob.expires_at.is_not(None), AdvisorJob.expires_at < func.now())
                        .order_by(AdvisorJob.expires_at.asc())
                        .limit(limit)
                    )
                ).scalars().all()
                if rows:
                    await db.execute(
                        delete(AdvisorJob).where(AdvisorJob.id.in_(list(rows)))
                    )
                    await db.commit()
                    return {"deleted": len(rows), "limited": True}
                return {"deleted": 0, "limited": True}
            deleted = await purge_expired_advisor_jobs(db)
            return {"deleted": deleted, "limited": False}

    try:
        return run_worker_coro(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="maintenance_tasks.refresh_public_rankings", queue="intelligence", max_retries=2, ignore_result=True)
def refresh_public_rankings_task(self):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.utils.public_utils import rebuild_public_book_rankings_snapshot

        async with AsyncSessionLocal() as db:
            result = await rebuild_public_book_rankings_snapshot(db)
            await db.commit()
            return result

    try:
        return run_worker_coro(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
