from app.utils.exception_boundaries import FATAL_TASK_BOUNDARY_EXCEPTIONS
from app.utils.retry_utils import NON_LLM_MAX_RETRIES, exponential_backoff_seconds
from app.utils.worker_async_utils import run_worker_coro
from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="embedding_tasks.update_character_embedding",
    queue="embedding",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def update_character_embedding_task(self, character_id: str, execution_id: str | None = None):
    embedding_work_started = False

    if execution_id:

        async def _claim_execution() -> bool:
            from app.core.database import AsyncSessionLocal
            from app.services.task_execution_service import claim_task_execution

            async with AsyncSessionLocal() as db:
                return await claim_task_execution(db, execution_id, self.request.id or execution_id)

        if not run_worker_coro(_claim_execution()):
            return {"skipped": "duplicate_or_active_execution"}

    async def _run():
        nonlocal embedding_work_started

        import uuid

        from sqlalchemy import update

        from app.core.database import AsyncSessionLocal
        from app.engine.embeddings.embedder import embed_character
        from app.models.character import Character

        async with AsyncSessionLocal() as db:
            char = await db.get(Character, uuid.UUID(character_id))
            if not char:
                return
            embedding_work_started = True
            emb = await embed_character(
                char.name,
                {
                    k: v
                    for k, v in (char.trait_state or {}).items()
                    if isinstance(v, dict) and v.get("confidence", 0) >= 0.45
                },
            )
            await db.execute(update(Character).where(Character.id == char.id).values(embedding=emb))
            await db.commit()

    try:
        run_worker_coro(_run())
        if execution_id:

            async def _complete_execution() -> None:
                from app.core.database import AsyncSessionLocal
                from app.services.task_execution_service import (
                    complete_task_execution,
                    dispatch_pending_embedding_tasks,
                )

                async with AsyncSessionLocal() as db:
                    await complete_task_execution(db, execution_id)
                    await dispatch_pending_embedding_tasks(db)

            run_worker_coro(_complete_execution())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        retries = int(getattr(self.request, "retries", 0) or 0)
        max_retries = self.max_retries if isinstance(self.max_retries, int) else NON_LLM_MAX_RETRIES
        retryable = not embedding_work_started and retries < max_retries
        if execution_id:

            async def _record_failure(error: Exception = exc) -> None:
                from app.core.database import AsyncSessionLocal
                from app.services.task_execution_service import (
                    dispatch_pending_embedding_tasks,
                    fail_task_execution,
                )

                async with AsyncSessionLocal() as db:
                    await fail_task_execution(
                        db,
                        execution_id,
                        error=error,
                        terminal=not retryable,
                        category="retryable" if retryable else "embedding",
                    )
                    if not retryable:
                        await dispatch_pending_embedding_tasks(db)

            run_worker_coro(_record_failure())
        if not retryable:
            raise
        raise self.retry(exc=exc, countdown=exponential_backoff_seconds(retries))
