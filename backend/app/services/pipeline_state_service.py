from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.intelligence import BookChunk
from app.schemas.books import WriterWorkspaceOut
from app.utils.book_utils import build_writer_workspace_payload, normalize_writer_workspace
from app.utils.ingestion_utils import get_processing_started_at
from app.workers.tasks.extraction_tasks import process_book_task

log = logging.getLogger("lorevia.pipeline_state")

STALE_PROCESSING_REQUEUE_AFTER = timedelta(minutes=5)


def build_writer_workspace_response(book: Book) -> WriterWorkspaceOut:
    return WriterWorkspaceOut(**build_writer_workspace_payload(book))


def build_writer_workspace_update(book: Book, updates: dict[str, Any]) -> dict[str, Any]:
    return normalize_writer_workspace(
        {
            **build_writer_workspace_payload(book),
            **updates,
        }
    )


def _parse_chapter_status_updated_at(chapter: Chapter) -> datetime | None:
    state = chapter.analysis_state if isinstance(chapter.analysis_state, dict) else {}
    updated_at = state.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        return None
    try:
        parsed = datetime.fromisoformat(updated_at.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


async def requeue_stalled_book_processing_if_needed(
    db: AsyncSession,
    *,
    book: Book,
    now: datetime | None = None,
) -> bool:
    if book.status != "processing":
        return False

    processing_started_at = get_processing_started_at(book)
    if processing_started_at is None:
        return False

    current_time = now or datetime.now(UTC)
    if current_time - processing_started_at < STALE_PROCESSING_REQUEUE_AFTER:
        return False

    chapters = (
        await db.execute(select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc()))
    ).scalars().all()
    if not chapters or any(chapter.processed for chapter in chapters):
        return False

    pending_statuses = {
        str((chapter.analysis_state or {}).get("status") or "").strip().lower()
        for chapter in chapters
    }
    if pending_statuses - {"", "queued", "pending"}:
        return False

    latest_update_at = max(
        (timestamp for chapter in chapters if (timestamp := _parse_chapter_status_updated_at(chapter)) is not None),
        default=processing_started_at,
    )
    if current_time - latest_update_at < STALE_PROCESSING_REQUEUE_AFTER:
        return False

    chunk_count = await db.scalar(select(func.count()).select_from(BookChunk).where(BookChunk.book_id == book.id)) or 0
    if chunk_count:
        return False

    process_book_task.apply_async(args=[str(book.id)], queue="extraction")
    log.warning("requeued_stalled_book_processing book_id=%s", book.id)
    return True
