"""Phase 3 intelligence tasks."""
import uuid

from app.utils.logging.errors import public_error_message
from app.workers.celery_app import celery_app
from app.utils.worker_async_utils import run_worker_coro


@celery_app.task(bind=True, name="intelligence_tasks.generate_wiki",
                 queue="intelligence", max_retries=2, ignore_result=True)
def generate_wiki_task(self, book_id: str):
    """Generate auto-wiki for all chapters of a book. Phase 3."""
    # Placeholder — implemented in Phase 3
    pass


@celery_app.task(bind=True, name="intelligence_tasks.generate_advisor_reply",
                 queue="intelligence", max_retries=2, ignore_result=True)
def generate_advisor_reply_task(
    self,
    *,
    job_id: str,
    book_id: str,
    user_id: str,
    messages: list[dict[str, str]],
    total_chapters: int,
):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.book import Book
        from app.services.advisor_jobs_service import (
            mark_advisor_job_complete,
            mark_advisor_job_failed,
            mark_advisor_job_running,
        )
        from app.utils.advisor_utils import build_advisor_reply_payload

        async with AsyncSessionLocal() as db:
            job_uuid = uuid.UUID(job_id)
            await mark_advisor_job_running(db, job_id=job_uuid)
            book = await db.get(Book, uuid.UUID(book_id))
            if not book or str(book.user_id) != user_id:
                await mark_advisor_job_failed(
                    db,
                    job_id=job_uuid,
                    error_code="advisor_book_not_found",
                    error_detail="Advisor book was missing or inaccessible.",
                )
                raise ValueError("advisor_book_not_found")
            payload = await build_advisor_reply_payload(
                db=db,
                book=book,
                user_id=uuid.UUID(user_id),
                messages=messages,
                total_chapters=total_chapters,
            )
            await mark_advisor_job_complete(db, job_id=job_uuid, result_payload=payload)
            return payload

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            async def _mark_failed():
                from app.core.database import AsyncSessionLocal
                from app.services.advisor_jobs_service import mark_advisor_job_failed

                async with AsyncSessionLocal() as db:
                    await mark_advisor_job_failed(
                        db,
                        job_id=uuid.UUID(job_id),
                        error_code="advisor_generation_failed",
                        error_detail=public_error_message(500),
                    )

            run_worker_coro(_mark_failed())
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="intelligence_tasks.generate_series_advisor_reply",
                 queue="intelligence", max_retries=2, ignore_result=True)
def generate_series_advisor_reply_task(
    self,
    *,
    job_id: str,
    series_id: str,
    user_id: str,
    messages: list[dict[str, str]],
):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.models.book import Series
        from app.services.advisor_jobs_service import (
            mark_advisor_job_complete,
            mark_advisor_job_failed,
            mark_advisor_job_running,
        )
        from app.utils.advisor_utils import build_series_advisor_reply_payload

        async with AsyncSessionLocal() as db:
            job_uuid = uuid.UUID(job_id)
            await mark_advisor_job_running(db, job_id=job_uuid)
            series = await db.get(Series, uuid.UUID(series_id))
            if not series or str(series.user_id) != user_id:
                await mark_advisor_job_failed(
                    db,
                    job_id=job_uuid,
                    error_code="advisor_series_not_found",
                    error_detail="Advisor series was missing or inaccessible.",
                )
                raise ValueError("advisor_series_not_found")
            payload = await build_series_advisor_reply_payload(
                db=db,
                series=series,
                user_id=uuid.UUID(user_id),
                messages=messages,
            )
            await mark_advisor_job_complete(db, job_id=job_uuid, result_payload=payload)
            return payload

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            async def _mark_failed():
                from app.core.database import AsyncSessionLocal
                from app.services.advisor_jobs_service import mark_advisor_job_failed

                async with AsyncSessionLocal() as db:
                    await mark_advisor_job_failed(
                        db,
                        job_id=uuid.UUID(job_id),
                        error_code="advisor_generation_failed",
                        error_detail=public_error_message(500),
                    )

            run_worker_coro(_mark_failed())
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="intelligence_tasks.generate_advisor_suggestions",
                 queue="intelligence", max_retries=2, ignore_result=True)
def generate_advisor_suggestions_task(
    self,
    *,
    job_id: str,
    book_id: str,
    user_id: str,
    total_chapters: int,
):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import get_suggestion_scan_cache, set_suggestion_scan_cache
        from app.models.book import Book
        from app.services.advisor_suggestion_jobs_service import (
            mark_advisor_suggestion_job_complete,
            mark_advisor_suggestion_job_failed,
            mark_advisor_suggestion_job_running,
        )
        from app.utils.advisor_utils import (
            build_advisor_suggestions_payload,
            make_advisor_suggestions_cache_key,
        )

        async with AsyncSessionLocal() as db:
            job_uuid = uuid.UUID(job_id)
            await mark_advisor_suggestion_job_running(db, job_id=job_uuid)
            book = await db.get(Book, uuid.UUID(book_id))
            if not book or str(book.user_id) != user_id:
                await mark_advisor_suggestion_job_failed(
                    db,
                    job_id=job_uuid,
                    error_code="advisor_book_not_found",
                    error_detail="Advisor book was missing or inaccessible.",
                )
                raise ValueError("advisor_book_not_found")

            payload = await build_advisor_suggestions_payload(
                db=db,
                book=book,
                user_id=uuid.UUID(user_id),
            )
            payload["cached"] = False

            result_cache_key = make_advisor_suggestions_cache_key(
                book_id=book.id,
                total_chapters=total_chapters,
                character_count=payload["meta"]["character_count"],
                thread_count=payload["meta"]["open_thread_count"],
                state_count=payload["meta"]["state_count"],
                relationship_count=payload["meta"]["relationship_count"],
                world_element_count=payload["meta"]["world_element_count"],
            )
            from app.models.intelligence import AdvisorSuggestionJob
            from sqlalchemy import update as sa_update
            await db.execute(
                sa_update(AdvisorSuggestionJob)
                .where(AdvisorSuggestionJob.id == job_uuid)
                .values(cache_key=result_cache_key)
            )
            await db.commit()
            await set_suggestion_scan_cache(str(book.id), result_cache_key, payload)
            await mark_advisor_suggestion_job_complete(db, job_id=job_uuid, result_payload=payload)
            return payload

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            async def _mark_failed():
                from app.core.database import AsyncSessionLocal
                from app.services.advisor_suggestion_jobs_service import mark_advisor_suggestion_job_failed

                async with AsyncSessionLocal() as db:
                    await mark_advisor_suggestion_job_failed(
                        db,
                        job_id=uuid.UUID(job_id),
                        error_code="advisor_suggestions_failed",
                        error_detail=public_error_message(500),
                    )

            run_worker_coro(_mark_failed())
        raise self.retry(exc=exc)
