import asyncio
from app.workers.celery_app import celery_app
from app.workers.consumers.analysis_consumer import analyse_chapter


@celery_app.task(bind=True, name="analysis_tasks.analyse_chapter",
                 queue="analysis", max_retries=3)
def analyse_chapter_task(self, chapter_id: str, chapter_text: str, chapter_title: str = ""):
    try:
        return asyncio.run(analyse_chapter(chapter_id, chapter_text, chapter_title))
    except Exception as exc:
        raise self.retry(exc=exc)
