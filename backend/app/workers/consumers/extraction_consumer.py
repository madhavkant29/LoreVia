"""
Full book processing: parse -> chunk -> extract characters + relationships -> embed.
Lazy: first N chapters immediately, rest queued.
"""

import logging

from app.core.database import AsyncSessionLocal
from app.core.redis import (
    INFLIGHT_BOOK_TTL_SECONDS,
    cache_delete_if_owner,
    cache_set_if_absent,
    key_extraction_inflight_book,
)
from app.services.extraction_book_processing_service import process_book_ingestion_and_queue
from app.services.extraction_chapter_processing_service import _process_chapter

log = logging.getLogger("lorevia.extraction")


async def process_book(
    book_id: str, queue_wait_ms: int | None = None, task_id: str | None = None
) -> dict:
    inflight_key = key_extraction_inflight_book(book_id)
    owner_token = task_id or "unknown"
    if not await cache_set_if_absent(inflight_key, owner_token, INFLIGHT_BOOK_TTL_SECONDS):
        log.info("book_processing_already_inflight book_id=%s", book_id)
        return {"skipped": "already_inflight"}

    try:
        return await _process_book_impl(book_id, queue_wait_ms=queue_wait_ms)
    finally:
        await cache_delete_if_owner(inflight_key, owner_token)


async def _process_book_impl(book_id: str, queue_wait_ms: int | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        return await process_book_ingestion_and_queue(
            db,
            book_id=book_id,
            queue_wait_ms=queue_wait_ms,
        )
