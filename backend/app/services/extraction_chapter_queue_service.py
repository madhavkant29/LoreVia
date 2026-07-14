from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from app.models.book import Book, Chapter
from app.models.operations import BookProcessingRun
from app.models.user import User
from app.services.processing_allowance_service import reserve_processing_words
from app.services.task_execution_service import (
    dispatch_pending_extraction_tasks,
    ensure_task_execution,
)
from app.utils.ingestion_utils import (
    is_book_hidden,
    mark_book_processing_cancelled,
    update_book_processing_state,
)


async def queue_initial_extraction_chapters(
    db,
    *,
    book: Book,
    user: User | None,
    processing_run: BookProcessingRun,
    ai_chapters: list[dict[str, Any]],
    chapter_rows: list[Chapter],
    chapters_by_number: dict[int, Chapter],
    processing_started_at: datetime,
    queue_wait_ms: int | None,
) -> dict[str, Any]:
    queued_count = 0
    for chapter_data in ai_chapters:
        chapter_number = int(chapter_data["number"])
        if await is_book_hidden(db, book.id):
            await mark_book_processing_cancelled(
                db,
                book,
                stage="queue_chapters",
                queue_wait_ms=queue_wait_ms,
                last_error="Book was removed while processing.",
            )
            return {"skipped": "book_hidden", "queued_count": queued_count}
        chapter = chapters_by_number.get(chapter_number)
        if chapter is None or chapter.processed:
            continue
        try:
            await reserve_processing_words(
                db,
                user,
                book_id=book.id,
                usage_kind="initial_ingestion_chapter",
                source_id=f"{processing_run.id}:{chapter_number}",
                word_count=int(
                    chapter.word_count or len(str(chapter_data.get("text") or "").split())
                ),
            )
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
            _pause_run_for_processing_allowance(
                book=book,
                processing_run=processing_run,
                ai_chapters=ai_chapters,
                chapter_rows=chapter_rows,
                chapter_number=chapter_number,
                processing_started_at=processing_started_at,
                error_detail=str(exc.detail),
            )
            break
        await ensure_task_execution(
            db,
            task_name="extraction_tasks.process_chapter",
            processing_run=processing_run,
            chapter_id=chapter.id,
            chapter_number=chapter_number,
            arguments={
                "book_id": str(book.id),
                "chapter_number": chapter_number,
                "processing_run_id": str(processing_run.id),
            },
        )
        queued_count += 1
    await db.commit()
    await dispatch_pending_extraction_tasks(db)
    return {"queued_count": queued_count}


def _pause_run_for_processing_allowance(
    *,
    book: Book,
    processing_run: BookProcessingRun,
    ai_chapters: list[dict[str, Any]],
    chapter_rows: list[Chapter],
    chapter_number: int,
    processing_started_at: datetime,
    error_detail: str,
) -> None:
    processing_run.status = "paused"
    processing_run.pause_reason = "processing_allowance"
    processing_run.resume_blockers = [{"kind": "monthly_processed_words", "detail": error_detail}]
    processing_run.next_chapter_number = chapter_number
    processing_run.paused_at = datetime.now(UTC)
    book.writer_workspace = update_book_processing_state(
        book,
        status="processing",
        stage="allowance_paused",
        total_chapters=len(ai_chapters),
        completed_chapters=sum(1 for row in chapter_rows if row.processed),
        started_at=processing_started_at,
        last_error=error_detail,
    )
    paused_workspace = dict(book.writer_workspace or {})
    paused_processing = dict(paused_workspace.get("processing") or {})
    paused_processing.update(
        {
            "processing_run_id": str(processing_run.id),
            "pause_reason": "processing_allowance",
            "resume_available": True,
            "resume_blockers": list(processing_run.resume_blockers),
            "next_chapter_number": chapter_number,
            "retry_actions": ["continue_processing"],
        }
    )
    paused_workspace["processing"] = paused_processing
    book.writer_workspace = paused_workspace
