import asyncio

from app.workers.celery_app import celery_app


def _run_coro(coro):
    async def _wrapped():
        from app.core.database import engine

        await engine.dispose()
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


@celery_app.task(bind=True, name="embedding_tasks.update_character_embedding",
                 queue="embedding", max_retries=3)
def update_character_embedding_task(self, character_id: str):
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
                {k: v for k, v in (char.trait_state or {}).items()
                 if isinstance(v, dict) and v.get("confidence", 0) >= 0.45},
            )
            await db.execute(update(Character).where(Character.id == char.id).values(embedding=emb))
            await db.commit()
    try:
        _run_coro(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
