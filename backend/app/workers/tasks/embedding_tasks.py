from app.utils.worker_async_utils import run_worker_coro
from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="embedding_tasks.update_character_embedding",
    queue="embedding",
    max_retries=3,
    ignore_result=True,
)
def update_character_embedding_task(self, character_id: str, execution_id: str | None = None):
    if execution_id:
        async def _claim_execution() -> bool:
            from app.core.database import AsyncSessionLocal
            from app.services.task_execution_service import claim_task_execution

            async with AsyncSessionLocal() as db:
                return await claim_task_execution(db, execution_id, self.request.id or execution_id)

        if not run_worker_coro(_claim_execution()):
            return {"skipped": "duplicate_or_active_execution"}
    async def _run():
        import uuid

        from sqlalchemy import update

        from app.core.database import AsyncSessionLocal
        from app.engine.embeddings.embedder import embed_character
        from app.models.character import Character

        async with AsyncSessionLocal() as db:
            char = await db.get(Character, uuid.UUID(character_id))
            if not char:
                return
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
    except Exception as exc:
        if execution_id:
            async def _record_failure(error: Exception = exc) -> None:
                from app.core.database import AsyncSessionLocal
                from app.services.task_execution_service import (
                    dispatch_pending_embedding_tasks,
                    fail_task_execution,
                )

                retries = int(getattr(self.request, "retries", 0) or 0)
                async with AsyncSessionLocal() as db:
                    await fail_task_execution(
                        db, execution_id, error=error, terminal=retries >= 3, category="embedding"
                    )
                    if retries >= 3:
                        await dispatch_pending_embedding_tasks(db)

            run_worker_coro(_record_failure())
        raise self.retry(exc=exc)
