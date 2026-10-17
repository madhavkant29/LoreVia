from app.utils.worker_async_utils import run_worker_coro
from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="export_tasks.process_manuscript_export_job",
    queue="maintenance",
    max_retries=0,
    ignore_result=True,
)
def process_manuscript_export_job_task(self, *, job_id: str):
    async def _run() -> dict:
        import uuid

        from app.core.database import AsyncSessionLocal
        from app.services.manuscript_export_service import process_manuscript_export_job

        async with AsyncSessionLocal() as db:
            return await process_manuscript_export_job(db, uuid.UUID(job_id))

    return run_worker_coro(_run())
