"""Phase 3 intelligence tasks."""

import uuid

from app.utils.exception_boundaries import FATAL_TASK_BOUNDARY_EXCEPTIONS
from app.utils.ingestion_utils import is_llm_usage_limit_error, llm_usage_limit_blocker
from app.utils.logging.errors import public_error_message
from app.utils.retry_utils import NON_LLM_MAX_RETRIES, exponential_backoff_seconds
from app.utils.worker_async_utils import run_worker_coro
from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="intelligence_tasks.refresh_world_analysis",
    queue="intelligence",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def refresh_world_analysis_task(self, *, scope: str, target_id: str):
    job_id = str(self.request.id or f"world-analysis:{scope}:{target_id}")

    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, key_world_analysis_refresh
        from app.models.book import Book
        from app.services.world_analysis_state_service import (
            mark_book_world_analysis_running,
            mark_series_world_analysis_running,
            mark_world_analysis_failed,
        )
        from app.utils.world_building_utils import (
            detect_integration_analysis,
            detect_series_world_analysis,
            detect_world_gaps,
        )

        target_uuid = uuid.UUID(target_id)
        lock_key = key_world_analysis_refresh(scope, target_id)
        try:
            async with AsyncSessionLocal() as db:
                try:
                    if scope == "book":
                        book = await db.get(Book, target_uuid)
                        if book is None:
                            raise ValueError("world_analysis_book_not_found")
                        await mark_book_world_analysis_running(
                            db,
                            book_id=target_uuid,
                            refresh_job_id=job_id,
                        )
                        await detect_world_gaps(db, book)
                        await detect_integration_analysis(db, book)
                    elif scope == "series":
                        await mark_series_world_analysis_running(
                            db,
                            series_id=target_uuid,
                            refresh_job_id=job_id,
                        )
                        await detect_series_world_analysis(db, target_uuid)
                    else:
                        raise ValueError("world_analysis_scope_invalid")
                    await db.commit()
                except Exception as exc:
                    await db.rollback()
                    await mark_world_analysis_failed(
                        db,
                        book_id=target_uuid if scope == "book" else None,
                        series_id=target_uuid if scope == "series" else None,
                        refresh_job_id=job_id,
                        error_code="world_analysis_refresh_failed",
                        error_detail=str(exc),
                    )
                    await db.commit()
                    raise
        finally:
            await cache_delete_if_owner(lock_key, job_id)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


def _advisor_execution_id(task, job_id: str) -> str:
    request_id = str(getattr(task.request, "id", "") or "").strip()
    return request_id or f"{task.name}:{job_id}"


@celery_app.task(
    bind=True,
    name="intelligence_tasks.generate_wiki",
    queue="intelligence",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def generate_wiki_task(self, book_id: str):
    """Generate auto-wiki for all chapters of a book. Phase 3."""
    wiki_work_started = False

    async def _run():
        nonlocal wiki_work_started

        from app.core.database import AsyncSessionLocal
        from app.models.book import Book
        from app.utils.world_building_wiki_utils import generate_wiki_from_manuscript

        async with AsyncSessionLocal() as db:
            book = await db.get(Book, uuid.UUID(book_id))
            if not book:
                raise ValueError("wiki_book_not_found")
            wiki_work_started = True
            await generate_wiki_from_manuscript(db, book)
            await db.commit()

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        retries = int(getattr(self.request, "retries", 0) or 0)
        if wiki_work_started or retries >= NON_LLM_MAX_RETRIES:
            raise
        raise self.retry(exc=exc, countdown=exponential_backoff_seconds(retries))


@celery_app.task(
    bind=True,
    name="intelligence_tasks.generate_advisor_reply",
    queue="intelligence",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def generate_advisor_reply_task(
    self,
    *,
    job_id: str,
    book_id: str,
    user_id: str,
    messages: list[dict[str, str]],
    total_chapters: int,
):
    advisor_work_started = False
    execution_id = _advisor_execution_id(self, job_id)

    async def _run():
        nonlocal advisor_work_started

        from app.core.database import AsyncSessionLocal
        from app.models.book import Book
        from app.services.advisor_jobs_service import (
            ADVISOR_SCOPE_FIRST_IMPRESSION,
            mark_advisor_job_complete,
            mark_advisor_job_failed,
            mark_advisor_job_running,
        )
        from app.utils.advisor_chat_utils import build_advisor_reply_payload

        async with AsyncSessionLocal() as db:
            job_uuid = uuid.UUID(job_id)
            job = await mark_advisor_job_running(
                db,
                job_id=job_uuid,
                execution_id=execution_id,
            )
            if job is None:
                return None
            book = await db.get(Book, uuid.UUID(book_id))
            if not book or str(book.user_id) != user_id:
                await mark_advisor_job_failed(
                    db,
                    job_id=job_uuid,
                    error_code="advisor_book_not_found",
                    error_detail="Advisor book was missing or inaccessible.",
                    execution_id=execution_id,
                )
                raise ValueError("advisor_book_not_found")
            advisor_work_started = True
            payload = await build_advisor_reply_payload(
                db=db,
                book=book,
                user_id=uuid.UUID(user_id),
                messages=messages,
                total_chapters=total_chapters,
            )
            await mark_advisor_job_complete(
                db,
                job_id=job_uuid,
                result_payload=payload,
                execution_id=execution_id,
            )
            return payload

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        retries = int(getattr(self.request, "retries", 0) or 0)
        max_retries = self.max_retries if isinstance(self.max_retries, int) else NON_LLM_MAX_RETRIES
        retryable = not advisor_work_started and retries < max_retries
        if not retryable:
            limit_blocker = llm_usage_limit_blocker(exc) if is_llm_usage_limit_error(exc) else None

            async def _mark_failed():
                from app.core.database import AsyncSessionLocal
                from app.services.advisor_jobs_service import mark_advisor_job_failed

                async with AsyncSessionLocal() as db:
                    await mark_advisor_job_failed(
                        db,
                        job_id=uuid.UUID(job_id),
                        error_code=(
                            str(limit_blocker["kind"])
                            if limit_blocker
                            else "advisor_generation_failed"
                        ),
                        error_detail=(
                            str(limit_blocker["detail"])
                            if limit_blocker
                            else public_error_message(500)
                        ),
                        execution_id=execution_id,
                    )

            run_worker_coro(_mark_failed())
            if limit_blocker:
                return None
            raise
        raise self.retry(exc=exc, countdown=exponential_backoff_seconds(retries))


@celery_app.task(
    bind=True,
    name="intelligence_tasks.generate_beta_reader_report",
    queue="intelligence",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def generate_beta_reader_report_task(
    self,
    *,
    job_id: str,
    book_id: str,
    user_id: str,
    request_payload: dict,
):
    beta_reader_work_started = False
    beta_reader_terminal_failure = False
    execution_id = _advisor_execution_id(self, job_id)

    async def _run():
        nonlocal beta_reader_terminal_failure, beta_reader_work_started

        from fastapi import HTTPException

        from app.core.database import AsyncSessionLocal
        from app.models.user import User
        from app.schemas.advisor import BetaReaderAnalysisRequest
        from app.services.advisor_jobs_service import (
            ADVISOR_SCOPE_FIRST_IMPRESSION,
            mark_advisor_job_complete,
            mark_advisor_job_failed,
            mark_advisor_job_running,
            update_advisor_job_progress,
        )
        from app.services.beta_reader_analysis_service import (
            build_beta_reader_report,
            persist_beta_reader_report,
        )
        from app.services.first_impression_service import (
            mark_first_impression_complete,
            mark_first_impression_failed,
            mark_first_impression_running,
        )
        from app.utils.books.collaboration_access import get_book_with_ai_scan_access

        async with AsyncSessionLocal() as db:
            job_uuid = uuid.UUID(job_id)
            job = await mark_advisor_job_running(
                db,
                job_id=job_uuid,
                execution_id=execution_id,
            )
            if job is None:
                return None
            is_first_impression = bool(
                job is not None and job.scope == ADVISOR_SCOPE_FIRST_IMPRESSION
            )
            if is_first_impression:
                await mark_first_impression_running(db, book_id=uuid.UUID(book_id), job_id=job_uuid)
            user = await db.get(User, uuid.UUID(user_id))
            if user is None:
                beta_reader_terminal_failure = True
                await mark_advisor_job_failed(
                    db,
                    job_id=job_uuid,
                    error_code="beta_reader_access_denied",
                    error_detail="The requesting user is no longer available.",
                    execution_id=execution_id,
                )
                if is_first_impression:
                    await mark_first_impression_failed(
                        db,
                        book_id=uuid.UUID(book_id),
                        job_id=job_uuid,
                        error_code="beta_reader_access_denied",
                    )
                raise ValueError("beta_reader_access_denied")
            try:
                book, collaborator, _ = await get_book_with_ai_scan_access(
                    db, uuid.UUID(book_id), user
                )
            except HTTPException as exc:
                beta_reader_terminal_failure = True
                await mark_advisor_job_failed(
                    db,
                    job_id=job_uuid,
                    error_code="beta_reader_access_denied",
                    error_detail="Book access or AI scan permission is no longer available.",
                    execution_id=execution_id,
                )
                if is_first_impression:
                    await mark_first_impression_failed(
                        db,
                        book_id=uuid.UUID(book_id),
                        job_id=job_uuid,
                        error_code="beta_reader_access_denied",
                    )
                raise ValueError("beta_reader_access_denied") from exc

            beta_reader_work_started = True
            body = BetaReaderAnalysisRequest.model_validate(request_payload)

            async def report_progress(progress: dict):
                await update_advisor_job_progress(
                    db,
                    job_id=job_uuid,
                    progress=progress,
                    execution_id=execution_id,
                )

            report = await build_beta_reader_report(
                db,
                book=book,
                collaborator=collaborator,
                user_id=user.id,
                body=body,
                progress=report_progress,
            )
            await report_progress(
                {
                    "stage": "saving",
                    "completed": 1,
                    "total": 1,
                    "message": "Saving the completed beta reader report...",
                }
            )
            await persist_beta_reader_report(db, book_id=book.id, report=report)
            await mark_advisor_job_complete(
                db,
                job_id=job_uuid,
                result_payload=report,
                execution_id=execution_id,
            )
            if is_first_impression:
                await mark_first_impression_complete(
                    db,
                    book_id=book.id,
                    job_id=job_uuid,
                    report=report,
                )
            return report

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        retries = int(getattr(self.request, "retries", 0) or 0)
        max_retries = self.max_retries if isinstance(self.max_retries, int) else NON_LLM_MAX_RETRIES
        retryable = (
            not beta_reader_terminal_failure
            and not beta_reader_work_started
            and retries < max_retries
        )
        if not retryable:
            if not beta_reader_terminal_failure:
                limit_blocker = (
                    llm_usage_limit_blocker(exc) if is_llm_usage_limit_error(exc) else None
                )

                async def _mark_failed():
                    from app.core.database import AsyncSessionLocal
                    from app.services.advisor_jobs_service import (
                        ADVISOR_SCOPE_FIRST_IMPRESSION,
                        get_advisor_job,
                        mark_advisor_job_failed,
                    )
                    from app.services.first_impression_service import (
                        mark_first_impression_failed,
                    )

                    async with AsyncSessionLocal() as db:
                        failed_job = await get_advisor_job(db, job_id=uuid.UUID(job_id))
                        await mark_advisor_job_failed(
                            db,
                            job_id=uuid.UUID(job_id),
                            error_code=(
                                str(limit_blocker["kind"])
                                if limit_blocker
                                else "beta_reader_generation_failed"
                            ),
                            error_detail=(
                                str(limit_blocker["detail"])
                                if limit_blocker
                                else public_error_message(500)
                            ),
                            execution_id=execution_id,
                        )
                        if (
                            failed_job is not None
                            and failed_job.scope == ADVISOR_SCOPE_FIRST_IMPRESSION
                        ):
                            await mark_first_impression_failed(
                                db,
                                book_id=uuid.UUID(book_id),
                                job_id=uuid.UUID(job_id),
                                error_code=(
                                    str(limit_blocker["kind"])
                                    if limit_blocker
                                    else "beta_reader_generation_failed"
                                ),
                            )

                run_worker_coro(_mark_failed())
                if limit_blocker:
                    return None
            raise
        raise self.retry(exc=exc, countdown=exponential_backoff_seconds(retries))


@celery_app.task(
    bind=True,
    name="intelligence_tasks.generate_series_advisor_reply",
    queue="intelligence",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def generate_series_advisor_reply_task(
    self,
    *,
    job_id: str,
    series_id: str,
    user_id: str,
    messages: list[dict[str, str]],
):
    advisor_work_started = False
    execution_id = _advisor_execution_id(self, job_id)

    async def _run():
        nonlocal advisor_work_started

        from app.core.database import AsyncSessionLocal
        from app.models.book import Series
        from app.services.advisor_jobs_service import (
            mark_advisor_job_complete,
            mark_advisor_job_failed,
            mark_advisor_job_running,
        )
        from app.utils.advisor_chat_utils import build_series_advisor_reply_payload

        async with AsyncSessionLocal() as db:
            job_uuid = uuid.UUID(job_id)
            job = await mark_advisor_job_running(
                db,
                job_id=job_uuid,
                execution_id=execution_id,
            )
            if job is None:
                return None
            series = await db.get(Series, uuid.UUID(series_id))
            if not series or str(series.user_id) != user_id:
                await mark_advisor_job_failed(
                    db,
                    job_id=job_uuid,
                    error_code="advisor_series_not_found",
                    error_detail="Advisor series was missing or inaccessible.",
                    execution_id=execution_id,
                )
                raise ValueError("advisor_series_not_found")
            advisor_work_started = True
            payload = await build_series_advisor_reply_payload(
                db=db,
                series=series,
                user_id=uuid.UUID(user_id),
                messages=messages,
            )
            await mark_advisor_job_complete(
                db,
                job_id=job_uuid,
                result_payload=payload,
                execution_id=execution_id,
            )
            return payload

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        retries = int(getattr(self.request, "retries", 0) or 0)
        max_retries = self.max_retries if isinstance(self.max_retries, int) else NON_LLM_MAX_RETRIES
        retryable = not advisor_work_started and retries < max_retries
        if not retryable:
            limit_blocker = llm_usage_limit_blocker(exc) if is_llm_usage_limit_error(exc) else None

            async def _mark_failed():
                from app.core.database import AsyncSessionLocal
                from app.services.advisor_jobs_service import mark_advisor_job_failed

                async with AsyncSessionLocal() as db:
                    await mark_advisor_job_failed(
                        db,
                        job_id=uuid.UUID(job_id),
                        error_code=(
                            str(limit_blocker["kind"])
                            if limit_blocker
                            else "advisor_generation_failed"
                        ),
                        error_detail=(
                            str(limit_blocker["detail"])
                            if limit_blocker
                            else public_error_message(500)
                        ),
                        execution_id=execution_id,
                    )

            run_worker_coro(_mark_failed())
            if limit_blocker:
                return None
            raise
        raise self.retry(exc=exc, countdown=exponential_backoff_seconds(retries))


@celery_app.task(
    bind=True,
    name="intelligence_tasks.generate_advisor_suggestions",
    queue="intelligence",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def generate_advisor_suggestions_task(
    self,
    *,
    job_id: str,
    book_id: str,
    user_id: str,
    total_chapters: int,
):
    advisor_work_started = False
    execution_id = _advisor_execution_id(self, job_id)

    async def _run():
        nonlocal advisor_work_started

        from app.core.database import AsyncSessionLocal
        from app.core.redis import get_book_cache_version, set_suggestion_scan_cache
        from app.models.book import Book
        from app.services.advisor_suggestion_jobs_service import (
            mark_advisor_suggestion_job_complete,
            mark_advisor_suggestion_job_failed,
            mark_advisor_suggestion_job_running,
        )
        from app.utils.advisor_scan_utils import build_advisor_suggestions_payload
        from app.utils.advisor_utils import make_advisor_suggestions_cache_key

        async with AsyncSessionLocal() as db:
            job_uuid = uuid.UUID(job_id)
            job = await mark_advisor_suggestion_job_running(
                db,
                job_id=job_uuid,
                execution_id=execution_id,
            )
            if job is None:
                return None
            book = await db.get(Book, uuid.UUID(book_id))
            if not book or str(book.user_id) != user_id:
                await mark_advisor_suggestion_job_failed(
                    db,
                    job_id=job_uuid,
                    error_code="advisor_book_not_found",
                    error_detail="Advisor book was missing or inaccessible.",
                    execution_id=execution_id,
                )
                raise ValueError("advisor_book_not_found")

            advisor_work_started = True
            cache_version = await get_book_cache_version(str(book.id))

            async def report_audit_progress(completed: int, total: int) -> None:
                from app.services.advisor_suggestion_jobs_service import (
                    mark_advisor_suggestion_job_progress,
                )

                await mark_advisor_suggestion_job_progress(
                    db,
                    job_id=job_uuid,
                    completed=completed,
                    total=total,
                    execution_id=execution_id,
                )

            payload = await build_advisor_suggestions_payload(
                db=db,
                book=book,
                user_id=uuid.UUID(user_id),
                force_audit=True,
                on_audit_progress=report_audit_progress,
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
            from sqlalchemy import update as sa_update

            from app.models.intelligence import AdvisorSuggestionJob

            await db.execute(
                sa_update(AdvisorSuggestionJob)
                .where(AdvisorSuggestionJob.id == job_uuid)
                .values(cache_key=result_cache_key)
            )
            await db.commit()
            if not payload["meta"].get("audit_failure_category"):
                await set_suggestion_scan_cache(
                    str(book.id),
                    result_cache_key,
                    payload,
                    expected_version=cache_version,
                )
            await mark_advisor_suggestion_job_complete(
                db,
                job_id=job_uuid,
                result_payload=payload,
                execution_id=execution_id,
            )
            return payload

    try:
        return run_worker_coro(_run())
    except ValueError:
        raise
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        retries = int(getattr(self.request, "retries", 0) or 0)
        max_retries = self.max_retries if isinstance(self.max_retries, int) else NON_LLM_MAX_RETRIES
        retryable = not advisor_work_started and retries < max_retries
        if not retryable:
            limit_blocker = llm_usage_limit_blocker(exc) if is_llm_usage_limit_error(exc) else None

            async def _mark_failed():
                from app.core.database import AsyncSessionLocal
                from app.services.advisor_suggestion_jobs_service import (
                    mark_advisor_suggestion_job_failed,
                )

                async with AsyncSessionLocal() as db:
                    await mark_advisor_suggestion_job_failed(
                        db,
                        job_id=uuid.UUID(job_id),
                        error_code=(
                            str(limit_blocker["kind"])
                            if limit_blocker
                            else "advisor_suggestions_failed"
                        ),
                        error_detail=(
                            str(limit_blocker["detail"])
                            if limit_blocker
                            else public_error_message(500)
                        ),
                        execution_id=execution_id,
                    )

            run_worker_coro(_mark_failed())
            if limit_blocker:
                return None
            raise
        raise self.retry(exc=exc, countdown=exponential_backoff_seconds(retries))
