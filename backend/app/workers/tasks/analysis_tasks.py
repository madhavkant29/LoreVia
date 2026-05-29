import logging

import httpx

from app.core.database import AsyncSessionLocal
from app.workers.celery_app import celery_app
from app.workers.consumers.analysis_consumer import analyse_chapter
from app.utils.ingestion_utils import extract_queue_wait_ms, load_analysis_chapter_payload
from app.utils.worker_async_utils import run_worker_coro

log = logging.getLogger("lorevia.analysis_tasks")


def _is_retryable_analysis_error(exc: Exception) -> bool:
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
    status_code = getattr(getattr(exc, "response", None), "status_code", None) or getattr(exc, "status_code", None)
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


@celery_app.task(bind=True, name="analysis_tasks.analyse_chapter",
                 queue="analysis", max_retries=3, ignore_result=True)
def analyse_chapter_task(
    self,
    chapter_id: str,
    chapter_text_or_book_id: str | None = None,
    chapter_title: str = "",
    is_reprocessing: bool | None = None,
):
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
                    return {"error": "chapter content missing"}
                return await analyse_chapter(
                    str(payload["chapter_id"]),
                    str(payload["text"]),
                    str(payload.get("title") or ""),
                    queue_wait_ms=queue_wait_ms,
                )

            return run_worker_coro(analyse_stored_chapter())
        return run_worker_coro(
            analyse_chapter(
                chapter_id,
                chapter_text_or_book_id or "",
                chapter_title,
                queue_wait_ms=queue_wait_ms,
            )
        )
    except Exception as exc:
        if not _is_retryable_analysis_error(exc):
            log.error(
                "analysis_task_non_retryable chapter_id=%s error=%s",
                chapter_id,
                exc,
            )
            raise
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
