"""Phase 3 intelligence tasks."""
import uuid

from app.workers.celery_app import celery_app
from app.utils.worker_async_utils import run_worker_coro


@celery_app.task(bind=True, name="intelligence_tasks.generate_wiki",
                 queue="intelligence", max_retries=2, ignore_result=True)
def generate_wiki_task(self, book_id: str):
    """Generate auto-wiki for all chapters of a book. Phase 3."""
    # Placeholder — implemented in Phase 3
    pass


@celery_app.task(bind=True, name="intelligence_tasks.generate_advisor_reply",
                 queue="intelligence", max_retries=2)
def generate_advisor_reply_task(
    self,
    *,
    book_id: str,
    user_id: str,
    messages: list[dict[str, str]],
    total_chapters: int,
):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.book import Book
        from app.utils.advisor_utils import build_advisor_reply_payload

        async with AsyncSessionLocal() as db:
            book = await db.get(Book, uuid.UUID(book_id))
            if not book or str(book.user_id) != user_id:
                raise ValueError("advisor_book_not_found")
            return await build_advisor_reply_payload(
                db=db,
                book=book,
                user_id=uuid.UUID(user_id),
                messages=messages,
                total_chapters=total_chapters,
            )

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="intelligence_tasks.generate_series_advisor_reply",
                 queue="intelligence", max_retries=2)
def generate_series_advisor_reply_task(
    self,
    *,
    series_id: str,
    user_id: str,
    messages: list[dict[str, str]],
):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.book import Series
        from app.utils.advisor_utils import build_series_advisor_reply_payload

        async with AsyncSessionLocal() as db:
            series = await db.get(Series, uuid.UUID(series_id))
            if not series or str(series.user_id) != user_id:
                raise ValueError("advisor_series_not_found")
            return await build_series_advisor_reply_payload(
                db=db,
                series=series,
                user_id=uuid.UUID(user_id),
                messages=messages,
            )

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except Exception as exc:
        raise self.retry(exc=exc)
