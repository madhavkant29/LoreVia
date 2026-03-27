import asyncio
from app.workers.celery_app import celery_app
from app.workers.consumers.extraction_consumer import process_book, _process_chapter


@celery_app.task(bind=True, name="extraction_tasks.process_book",
                 queue="extraction", max_retries=3)
def process_book_task(self, book_id: str):
    try:
        return asyncio.run(process_book(book_id))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="extraction_tasks.process_chapter",
                 queue="extraction", max_retries=3)
def process_chapter_task(self, book_id: str, chapter_num: int, title: str, text: str):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.book import Book
        import uuid
        async with AsyncSessionLocal() as db:
            book = await db.get(Book, uuid.UUID(book_id))
            if book:
                await _process_chapter(db, book, {"number": chapter_num, "title": title, "text": text})
    try:
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
