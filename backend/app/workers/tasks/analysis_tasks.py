import asyncio

from app.workers.celery_app import celery_app
from app.workers.consumers.analysis_consumer import analyse_chapter
from app.utils.ingestion_utils import extract_queue_wait_ms


def _run_coro(coro):
    async def _wrapped():
        from app.core.database import engine

        await engine.dispose()
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


@celery_app.task(bind=True, name="analysis_tasks.analyse_chapter",
                 queue="analysis", max_retries=3)
def analyse_chapter_task(self, chapter_id: str, chapter_text: str, chapter_title: str = ""):
    try:
        queue_wait_ms = extract_queue_wait_ms(getattr(self.request, "headers", None))
        return _run_coro(analyse_chapter(chapter_id, chapter_text, chapter_title, queue_wait_ms=queue_wait_ms))
    except Exception as exc:
        raise self.retry(exc=exc)
