from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty, mark_user_dashboard_cache_dirty
from app.models.book import Book, Chapter
from app.models.intelligence import BookChunk, ChapterSummary
from app.schemas.books import WriterWorkspaceOut
from app.utils.book_utils import build_writer_workspace_payload, normalize_writer_workspace
from app.utils.ingestion_utils import get_processing_started_at, merge_processing_pipeline
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


def _processing_pipeline_has_blocking_failure(processing: dict[str, Any]) -> bool:
    pipeline = processing.get("pipeline") if isinstance(processing.get("pipeline"), dict) else {}
    for stage in ("extraction", "analysis"):
        stage_payload = pipeline.get(stage) if isinstance(pipeline.get(stage), dict) else {}
        status = str(stage_payload.get("status") or "").strip().lower()
        if status == "failed":
            return True
        failed_chapters = stage_payload.get("failed_chapters")
        if isinstance(failed_chapters, list) and failed_chapters:
            return True
    return False


async def repair_stale_completed_processing_state(db: AsyncSession, book: Book) -> bool:
    """Mark a normal uploaded book ready when persisted chapter intelligence is complete."""
    if getattr(book, "is_editor_project", False) or book.status != "processing":
        return False

    workspace = normalize_writer_workspace(book.writer_workspace if isinstance(book.writer_workspace, dict) else None)
    processing = dict(workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {})
    if processing.get("rebuild_run_id") or _processing_pipeline_has_blocking_failure(processing):
        return False

    chapter_count = int(
        (
            await db.execute(
                select(func.count(func.distinct(Chapter.number))).select_from(Chapter).where(
                    Chapter.book_id == book.id,
                    Chapter.word_count > 0,
                )
            )
        ).scalar_one()
    )
    if chapter_count <= 0:
        return False

    processed_count = int(
        (
            await db.execute(
                select(func.count(func.distinct(Chapter.number))).select_from(Chapter).where(
                    Chapter.book_id == book.id,
                    Chapter.word_count > 0,
                    Chapter.processed.is_(True),
                )
            )
        ).scalar_one()
    )
    detailed_summary_count = int(
        (
            await db.execute(
                select(func.count(func.distinct(Chapter.number)))
                .select_from(ChapterSummary)
                .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.word_count > 0,
                    Chapter.processed.is_(True),
                    ChapterSummary.mode == "detailed",
                )
            )
        ).scalar_one()
    )
    if processed_count < chapter_count or detailed_summary_count < chapter_count:
        return False

    now = datetime.now(UTC).isoformat()
    processing.update(
        {
            "status": "ready",
            "stage": "complete",
            "chapters_completed": processed_count,
            "chapters_total": chapter_count,
            "progress_pct": 100.0,
            "eta_seconds": 0,
            "is_fully_ready": True,
            "updated_at": now,
            "completed_at": now,
        }
    )
    processing = merge_processing_pipeline(
        processing,
        extraction={
            "status": "succeeded",
            "completed_chapters": processed_count,
            "total_chapters": chapter_count,
            "updated_at": now,
            "eta_seconds": 0,
        },
        analysis={
            "status": "succeeded",
            "completed_chapters": detailed_summary_count,
            "total_chapters": chapter_count,
            "updated_at": now,
        },
    )
    processing["status"] = "ready"
    processing["stage"] = "complete"
    processing["retry_actions"] = []
    workspace["processing"] = processing
    book.writer_workspace = workspace
    book.status = "ready"
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    await mark_user_dashboard_cache_dirty(str(book.user_id))
    log.warning("repaired_stale_completed_processing_state book_id=%s chapters=%s", book.id, chapter_count)
    return True
