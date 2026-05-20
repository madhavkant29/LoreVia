from app.workers.celery_app import celery_app
from app.workers.consumers.extraction_consumer import _process_chapter, process_book
from app.services.chapter_recovery_service import repair_chapter_payload_from_source
from app.utils.ingestion_utils import (
    extract_queue_wait_ms,
    is_book_hidden,
    is_retryable_processing_error,
    load_processing_chapter_payload,
)
from app.utils.worker_async_utils import run_worker_coro


@celery_app.task(bind=True, name="extraction_tasks.process_book",
                 queue="extraction", max_retries=3)
def process_book_task(self, book_id: str):
    try:
        queue_wait_ms = extract_queue_wait_ms(getattr(self.request, "headers", None))
        return run_worker_coro(process_book(book_id, queue_wait_ms=queue_wait_ms))
    except Exception as exc:
        if not is_retryable_processing_error(exc):
            raise
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="extraction_tasks.process_chapter",
                 queue="extraction", max_retries=3)
def process_chapter_task(self, book_id: str, chapter_num: int):
    async def _run():
        import uuid

        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models.book import Book, Chapter
        queue_wait_ms = extract_queue_wait_ms(getattr(self.request, "headers", None))
        async with AsyncSessionLocal() as db:
            book = await db.get(Book, uuid.UUID(book_id))
            if not book:
                return

            chapter_row = (
                await db.execute(
                    select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
                )
            ).scalar()

            if await is_book_hidden(db, book.id):
                return

            chapter_payload = await load_processing_chapter_payload(
                book.id,
                chapter_num,
                chapter_s3_key=chapter_row.s3_key if chapter_row is not None else None,
                chapter_title=chapter_row.title if chapter_row is not None else None,
            )
            if chapter_payload is None:
                raise ValueError(f"missing_chapter_payload:{book.id}:{chapter_num}")

            await _process_chapter(
                db,
                book,
                chapter_payload,
                queue_wait_ms=queue_wait_ms,
            )
    try:
        run_worker_coro(_run())
    except Exception as exc:
        if not is_retryable_processing_error(exc):
            raise
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="extraction_tasks.repair_chapter_payload",
                 queue="extraction", max_retries=3)
def repair_chapter_payload_task(self, book_id: str, chapter_num: int):
    async def _run():
        import uuid

        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models.book import Book, Chapter

        async with AsyncSessionLocal() as db:
            book = await db.get(Book, uuid.UUID(book_id))
            if not book:
                return
            chapter = (
                await db.execute(
                    select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
                )
            ).scalar()
            if chapter is None:
                return
            if await is_book_hidden(db, book.id):
                return
            await repair_chapter_payload_from_source(db, book=book, chapter=chapter)
    try:
        run_worker_coro(_run())
    except Exception as exc:
        if not is_retryable_processing_error(exc):
            raise
        raise self.retry(exc=exc)
