from app.workers.celery_app import celery_app
from app.workers.consumers.analysis_consumer import analyse_chapter
from app.utils.ingestion_utils import extract_queue_wait_ms
from app.utils.worker_async_utils import run_worker_coro


@celery_app.task(bind=True, name="analysis_tasks.analyse_chapter",
                 queue="analysis", max_retries=3, ignore_result=True)
def analyse_chapter_task(self, chapter_id: str, chapter_text: str, chapter_title: str = ""):
    try:
        queue_wait_ms = extract_queue_wait_ms(getattr(self.request, "headers", None))
        return run_worker_coro(
            analyse_chapter(chapter_id, chapter_text, chapter_title, queue_wait_ms=queue_wait_ms)
        )
    except Exception as exc:
        raise self.retry(exc=exc)
