import asyncio

from app.workers.celery_app import celery_app
from app.workers.consumers.extraction_consumer import _process_chapter, process_book
from app.utils.ingestion_utils import extract_queue_wait_ms, is_book_hidden, is_retryable_processing_error


def _run_coro(coro):
    async def _wrapped():
        from app.core.database import engine

        await engine.dispose()
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


@celery_app.task(bind=True, name="extraction_tasks.process_book",
                 queue="extraction", max_retries=3)
def process_book_task(self, book_id: str):
    try:
        queue_wait_ms = extract_queue_wait_ms(getattr(self.request, "headers", None))
        return _run_coro(process_book(book_id, queue_wait_ms=queue_wait_ms))
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
        from app.core.storage import download_book
        from app.models.book import Book, Chapter
        from app.utils.book_utils import deserialize_manuscript_content, parse_book_upload_for_ingestion
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
            chapter_title = chapter_row.title if chapter_row is not None else ""
            chapter_text = ""

            if await is_book_hidden(db, book.id):
                return

            if chapter_row and chapter_row.s3_key:
                try:
                    chapter_text = str(
                        deserialize_manuscript_content(
                            await asyncio.to_thread(download_book, chapter_row.s3_key)
                        ).get("text")
                        or ""
                    )
                    chapter_title = chapter_row.title or ""
                except Exception:
                    chapter_text = ""

            if not chapter_text.strip():
                raw = await asyncio.to_thread(download_book, book.s3_key)
                parsed_payload = await parse_book_upload_for_ingestion(
                    format_name=book.format,
                    work_type=book.work_type,
                    raw=raw,
                    preserve_chapter_numbers=book.preserve_chapter_numbers,
                    preserve_source_chapters=book.preserve_source_chapters,
                )
                chapters = parsed_payload["chapters"]
                chapter_data = next((ch for ch in chapters if ch["number"] == chapter_num), None)
                if not chapter_data:
                    return
                chapter_title = chapter_data.get("title") or chapter_title
                chapter_text = chapter_data.get("text") or ""

            if chapter_text.strip():
                await _process_chapter(
                    db,
                    book,
                    {"number": chapter_num, "title": chapter_title, "text": chapter_text},
                    queue_wait_ms=queue_wait_ms,
                )
    try:
        _run_coro(_run())
    except Exception as exc:
        if not is_retryable_processing_error(exc):
            raise
        raise self.retry(exc=exc)
