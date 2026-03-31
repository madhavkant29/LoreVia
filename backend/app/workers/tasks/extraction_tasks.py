import asyncio
from app.workers.celery_app import celery_app
from app.workers.consumers.extraction_consumer import process_book, _process_chapter


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
        return _run_coro(process_book(book_id))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="extraction_tasks.process_chapter",
                 queue="extraction", max_retries=3)
def process_chapter_task(self, book_id: str, chapter_num: int, title: str, text: str):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.storage import download_book
        from app.models.book import Book, Chapter
        from app.parsers.epub_parser import parse_epub
        from app.parsers.pdf_parser import parse_pdf
        from sqlalchemy import select
        import uuid
        async with AsyncSessionLocal() as db:
            book = await db.get(Book, uuid.UUID(book_id))
            if not book:
                return

            chapter_title = title
            chapter_text = text

            if not chapter_text.strip():
                chapter_row = (
                    await db.execute(
                        select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
                    )
                ).scalar()
                if chapter_row and chapter_row.s3_key:
                    try:
                        chapter_text = download_book(chapter_row.s3_key).decode("utf-8", errors="ignore")
                        chapter_title = chapter_row.title or title
                    except Exception:
                        chapter_text = ""

            if not chapter_text.strip():
                raw = download_book(book.s3_key)
                chapters = parse_pdf(raw) if book.format == "pdf" else parse_epub(raw)
                chapter_data = next((ch for ch in chapters if ch["number"] == chapter_num), None)
                if not chapter_data:
                    return
                chapter_title = chapter_data.get("title") or title
                chapter_text = chapter_data.get("text") or ""

            if chapter_text.strip():
                await _process_chapter(
                    db,
                    book,
                    {"number": chapter_num, "title": chapter_title, "text": chapter_text},
                )
    try:
        _run_coro(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
