import logging

import httpx

from app.core.database import AsyncSessionLocal
from app.models.book import Chapter
from app.utils.db_utils import is_retryable_transaction_db_error
from app.utils.exception_boundaries import FATAL_TASK_BOUNDARY_EXCEPTIONS
from app.utils.ingestion_utils import (
    extract_queue_wait_ms,
    is_llm_coordination_retry_error,
    is_llm_usage_limit_error,
    llm_usage_limit_blocker,
    load_analysis_chapter_payload,
)
from app.utils.llm_usage_utils import is_transient_llm_provider_error
from app.utils.processing_error_utils import LLM_CAPACITY_MESSAGE
from app.utils.retry_utils import NON_LLM_MAX_RETRIES, exponential_backoff_seconds
from app.utils.worker_async_utils import run_worker_coro
from app.workers.celery_app import celery_app
from app.workers.consumers.analysis_consumer import analyse_chapter

log = logging.getLogger("lorevia.analysis_tasks")


def _is_retryable_analysis_error(exc: Exception) -> bool:
    if is_retryable_transaction_db_error(exc) or is_transient_llm_provider_error(exc):
        return True
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.ConnectError):
        return True
    if isinstance(exc, httpx.RemoteProtocolError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = getattr(exc.response, "status_code", None)
        if isinstance(status, int) and (status >= 500 or status == 429):
            return True
    status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(
        exc, "status_code", None
    )
    if isinstance(status_code, int) and (status_code >= 500 or status_code == 429):
        return True
    message = str(exc).lower()
    retryable_markers = (
        "rate_limit",
        "rate limit",
        "timeout",
        "timed out",
        "connection",
        "connection reset",
        "connection aborted",
        "broken pipe",
        "service_unavailable",
        "service unavailable",
        "temporarily unavailable",
        "gateway timeout",
    )
    return any(marker in message for marker in retryable_markers)


@celery_app.task(
    bind=True,
    name="analysis_tasks.analyse_chapter",
    queue="analysis",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def analyse_chapter_task(
    self,
    chapter_id: str,
    chapter_text_or_book_id: str | None = None,
    chapter_title: str = "",
    is_reprocessing: bool | None = None,
    rebuild_run_id: str | None = None,
    manual_reprocess: bool = False,
    execution_id: str | None = None,
):
    if execution_id:

        async def _claim_execution() -> bool:
            from app.services.task_execution_service import claim_task_execution

            async with AsyncSessionLocal() as db:
                return await claim_task_execution(db, execution_id, self.request.id or execution_id)

        if not run_worker_coro(_claim_execution()):
            return {"skipped": "duplicate_or_active_execution"}
    try:
        queue_wait_ms = extract_queue_wait_ms(getattr(self.request, "headers", None))
        if is_reprocessing is not None:

            async def analyse_stored_chapter() -> dict:
                async with AsyncSessionLocal() as db:
                    payload = await load_analysis_chapter_payload(
                        db,
                        chapter_id,
                        book_id=chapter_text_or_book_id,
                    )
                if payload is None:
                    raise ValueError(f"chapter content missing: {chapter_id}")
                return await analyse_chapter(
                    str(payload["chapter_id"]),
                    str(payload["text"]),
                    str(payload.get("title") or ""),
                    queue_wait_ms=queue_wait_ms,
                    rebuild_run_id=rebuild_run_id,
                    manual_reprocess=manual_reprocess,
                )

            result = run_worker_coro(analyse_stored_chapter())
        else:
            result = run_worker_coro(
                analyse_chapter(
                    chapter_id,
                    chapter_text_or_book_id or "",
                    chapter_title,
                    queue_wait_ms=queue_wait_ms,
                    rebuild_run_id=rebuild_run_id,
                    manual_reprocess=manual_reprocess,
                )
            )
        if execution_id:

            async def _complete_execution() -> None:
                from app.services.task_execution_service import (
                    complete_task_execution,
                    dispatch_pending_analysis_tasks,
                )

                async with AsyncSessionLocal() as db:
                    await complete_task_execution(db, execution_id)
                    await dispatch_pending_analysis_tasks(db)

            run_worker_coro(_complete_execution())
        return result
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        if is_llm_usage_limit_error(exc):
            usage_blocker = llm_usage_limit_blocker(exc)
            if usage_blocker.get("permanent"):
                if execution_id:
                    error_text = str(exc)

                    async def _fail_unresumable_execution(
                        detail: str = error_text,
                    ) -> None:
                        from app.services.task_execution_service import (
                            fail_task_execution,
                        )

                        async with AsyncSessionLocal() as db:
                            await fail_task_execution(
                                db,
                                execution_id,
                                error=RuntimeError(detail),
                                terminal=True,
                                category="llm_token_limit",
                            )

                    run_worker_coro(_fail_unresumable_execution())
                return {"failed": "llm_token_limit"}
            if execution_id:

                async def _pause_execution(blocker: dict = usage_blocker) -> None:
                    from app.services.task_execution_service import pause_task_execution

                    async with AsyncSessionLocal() as db:
                        await pause_task_execution(
                            db,
                            execution_id,
                            reason=(
                                "llm_budget"
                                if blocker.get("kind") == "llm_budget"
                                else "llm_token_limit"
                            ),
                            blocker=blocker,
                        )

                run_worker_coro(_pause_execution())
            return {"paused": "llm_usage_limit"}
        if is_llm_coordination_retry_error(exc):
            if execution_id:

                async def _pause_capacity_execution(
                    error_detail: str = LLM_CAPACITY_MESSAGE,
                ) -> None:
                    from app.services.task_execution_service import pause_task_execution

                    async with AsyncSessionLocal() as db:
                        await pause_task_execution(
                            db,
                            execution_id,
                            reason="llm_capacity",
                            blocker={"kind": "llm_capacity", "detail": error_detail},
                        )

                run_worker_coro(_pause_capacity_execution())
            return {"paused": "llm_capacity"}
        # Provider calls own their short in-request retry budget. If those
        # attempts are exhausted, Celery owns the bounded workflow retry. The
        # consumer persists generated state only in its final guarded
        # transaction, so retrying cannot expose partial analysis rows.
        retryable = _is_retryable_analysis_error(exc)
        error_text = str(exc)
        retries = int(getattr(self.request, "retries", 0) or 0)
        max_retries = self.max_retries if isinstance(self.max_retries, int) else NON_LLM_MAX_RETRIES
        if execution_id:

            async def _record_execution_failure(error: Exception = exc) -> None:
                from app.services.task_execution_service import fail_task_execution

                async with AsyncSessionLocal() as db:
                    await fail_task_execution(
                        db,
                        execution_id,
                        error=error,
                        terminal=not retryable or retries >= max_retries,
                        category="retryable" if retryable else "analysis",
                    )

            run_worker_coro(_record_execution_failure())
        if rebuild_run_id is not None and (not retryable or retries >= max_retries):

            async def _fail_terminal_rebuild() -> None:
                import uuid

                from app.services.editor_project_service import fail_rebuild_run

                async with AsyncSessionLocal() as db:
                    chapter = await db.get(Chapter, uuid.UUID(chapter_id))
                    if chapter is not None:
                        await fail_rebuild_run(
                            db,
                            chapter.book_id,
                            expected_rebuild_run_id=rebuild_run_id,
                            error=error_text,
                        )
                        await db.commit()

            run_worker_coro(_fail_terminal_rebuild())
        if not retryable or retries >= max_retries:
            log.error(
                "analysis_task_non_retryable chapter_id=%s error=%s",
                chapter_id,
                exc,
            )
            raise
        raise self.retry(exc=exc, countdown=exponential_backoff_seconds(retries))
