"""Queue a fresh analysis run for extracted chapters that failed analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty, mark_user_dashboard_cache_dirty
from app.models.book import Book, Chapter
from app.services.book_freeze_service import is_book_frozen
from app.services.task_execution_service import (
    dispatch_pending_analysis_tasks,
    ensure_task_execution,
    get_or_create_processing_run,
)
from app.utils.books.writer_workspace import build_book_processing_payload
from app.utils.ingestion_utils import build_analysis_chapter_state, merge_processing_pipeline


async def retry_failed_analysis_only(
    db: AsyncSession,
    book: Book,
) -> dict[str, Any] | None:
    # Serialize double-clicks and concurrent API requests before creating a
    # fresh run, then reload the book so a stale request cannot queue twice.
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"processing_run:{book.id}"))))
    await db.refresh(book)
    if is_book_frozen(book):
        return None
    workspace = book.writer_workspace if isinstance(book.writer_workspace, dict) else {}
    processing = (
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    pipeline = processing.get("pipeline") if isinstance(processing.get("pipeline"), dict) else {}
    extraction = pipeline.get("extraction") if isinstance(pipeline.get("extraction"), dict) else {}
    actions = (
        processing.get("retry_actions") if isinstance(processing.get("retry_actions"), list) else []
    )
    if (
        "retry_analysis" not in actions
        or "retry_extraction" in actions
        or extraction.get("status") != "succeeded"
    ):
        return None
    chapters = list(
        (
            await db.execute(
                select(Chapter)
                .where(Chapter.book_id == book.id)
                .order_by(Chapter.number)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    failed_chapters = [
        chapter
        for chapter in chapters
        if chapter.processed
        and isinstance(chapter.analysis_state, dict)
        and chapter.analysis_state.get("status") == "failed"
    ]
    if not failed_chapters:
        return None
    run = await get_or_create_processing_run(
        db,
        user_id=book.user_id,
        book_id=book.id,
        run_kind="analysis_retry",
        chapters_total=len(failed_chapters),
        reuse_active=False,
    )
    for chapter in failed_chapters:
        chapter.analysis_state = build_analysis_chapter_state(
            chapter.analysis_state, status="queued", last_error=None
        )
        await ensure_task_execution(
            db,
            task_name="analysis_tasks.analyse_chapter",
            processing_run=run,
            chapter_id=chapter.id,
            chapter_number=chapter.number,
            arguments={"chapter_id": str(chapter.id), "book_id": str(book.id)},
            feature="analysis",
        )
    prior_analysis = pipeline.get("analysis") if isinstance(pipeline.get("analysis"), dict) else {}
    next_processing = merge_processing_pipeline(
        dict(processing),
        analysis={
            **prior_analysis,
            "status": "queued",
            "failed_chapters": [],
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    next_processing.update(
        {
            "status": "processing",
            "stage": "analysis",
            "last_error": None,
            "pause_reason": None,
            "auto_resume": False,
            "resume_available": False,
            "resume_blockers": [],
            "next_resume_at": None,
        }
    )
    book.status = "processing"
    book.writer_workspace = {**workspace, "processing": next_processing}
    await db.commit()
    await dispatch_pending_analysis_tasks(db)
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    await mark_user_dashboard_cache_dirty(str(book.user_id))
    return build_book_processing_payload(book) or {}
