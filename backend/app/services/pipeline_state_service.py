from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    cache_set_if_absent,
    mark_book_cache_dirty,
    mark_user_dashboard_cache_dirty,
)
from app.models.book import Book, Chapter
from app.models.intelligence import BookChunk, ChapterSummary
from app.models.operations import BookProcessingRun, TaskExecution
from app.models.user import User
from app.schemas.books import WriterWorkspaceOut
from app.utils.books.writer_workspace import (
    build_book_processing_payload,
    build_writer_workspace_payload,
    normalize_writer_workspace,
)
from app.utils.ingestion_utils import (
    get_processing_started_at,
    merge_processing_pipeline,
    update_book_processing_state,
)

log = logging.getLogger("lorevia.pipeline_state")

STALE_PROCESSING_REQUEUE_AFTER = timedelta(minutes=5)
PROCESSING_REPAIR_ENQUEUE_TTL_SECONDS = 60


def build_writer_workspace_response(book: Book) -> WriterWorkspaceOut:
    return WriterWorkspaceOut(**build_writer_workspace_payload(book))


def build_writer_workspace_update(book: Book, updates: dict[str, Any]) -> dict[str, Any]:
    return normalize_writer_workspace(
        {
            **build_writer_workspace_payload(book),
            **updates,
        }
    )


async def enqueue_processing_state_repair_if_needed(book: Book) -> bool:
    if book.status != "processing":
        return False
    key = f"processing_state_repair_enqueue:{book.id}"
    if not await cache_set_if_absent(key, "1", ttl=PROCESSING_REPAIR_ENQUEUE_TTL_SECONDS):
        return False
    from app.workers.tasks.maintenance_tasks import repair_processing_books_task

    repair_processing_books_task.apply_async(kwargs={"book_id": str(book.id)}, queue="intelligence")
    return True


def _book_processing_retry_actions(book: Book) -> list[str]:
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = (
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    actions = processing.get("retry_actions") if isinstance(processing, dict) else []
    return [
        " ".join(str(action).split()).strip()
        for action in (actions if isinstance(actions, list) else [])
        if " ".join(str(action).split()).strip()
    ]


def _book_processing_last_error(book: Book) -> str | None:
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = (
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    last_error = " ".join(str((processing or {}).get("last_error") or "").split()).strip()
    return last_error or None


def _book_has_retryable_processing_state(book: Book) -> bool:
    if book.status == "failed":
        return True
    actions = [
        action for action in _book_processing_retry_actions(book) if action != "wait_for_analysis"
    ]
    return bool(actions or _book_processing_last_error(book))


async def _dispatch_durable_book_processing(
    db: AsyncSession,
    book: Book,
    *,
    run_kind: str,
    identity_suffix: str | None = None,
) -> TaskExecution:
    from app.services.task_execution_service import (
        dispatch_pending_extraction_tasks,
        ensure_task_execution,
        get_or_create_processing_run,
    )

    run = await get_or_create_processing_run(
        db,
        user_id=book.user_id,
        book_id=book.id,
        run_kind=run_kind,
        rebuild_run_id=identity_suffix,
        chapters_total=int(book.total_chapters or 0),
    )
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=run,
        rebuild_run_id=identity_suffix,
        arguments={
            "book_id": str(book.id),
            "processing_run_id": str(run.id),
            "rebuild_run_id": identity_suffix,
        },
    )
    if execution.status in {"succeeded", "dismissed", "queued", "running"}:
        return execution
    execution.status = "pending_dispatch"
    execution.error_category = None
    execution.error_detail = None
    run.status = "queued"
    await db.commit()
    await dispatch_pending_extraction_tasks(db)
    return execution


async def retry_book_processing(db: AsyncSession, book: Book) -> dict[str, Any] | None:
    from fastapi import HTTPException

    from app.services.book_freeze_service import (
        LEGACY_INCOMPLETE_MESSAGE,
        book_is_legacy_incomplete,
        frozen_conflict_message,
        is_book_frozen,
        load_persisted_freeze_cutoff,
    )

    if is_book_frozen(book):
        raise HTTPException(409, frozen_conflict_message())
    cutoff = await load_persisted_freeze_cutoff(db)
    if book_is_legacy_incomplete(book, cutoff):
        # Deployment transition gate: pre-cutoff incomplete books await the
        # one-time freeze and must not restart paid processing.
        raise HTTPException(409, LEGACY_INCOMPLETE_MESSAGE)
    if not _book_has_retryable_processing_state(book):
        return None

    actions = set(_book_processing_retry_actions(book))
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = (
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    processing_status = str((processing or {}).get("status") or "").strip().lower()
    should_restart_extraction = (
        book.status == "failed"
        or processing_status in {"failed", "cancelled", "canceled"}
        or "retry_extraction" in actions
        or "retry_analysis" in actions
    )

    if should_restart_extraction:
        if getattr(book, "is_editor_project", False):
            from app.services.editor_project_service import (
                dispatch_manual_rebuild_with_reservations,
            )

            await dispatch_manual_rebuild_with_reservations(db, book)
        else:
            book.status = "processing"
            book.writer_workspace = update_book_processing_state(
                book,
                status="processing",
                stage="queued",
                total_chapters=book.total_chapters,
                completed_chapters=0,
                started_at=datetime.now(UTC),
                last_error=None,
                progress_pct=0,
            )
            await _dispatch_durable_book_processing(db, book, run_kind="manual_retry")
    else:
        book.status = "processing"
        await enqueue_processing_state_repair_if_needed(book)

    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    await mark_user_dashboard_cache_dirty(str(book.user_id))
    processing = build_book_processing_payload(book)
    return processing if processing is not None else {}


async def continue_book_processing(db: AsyncSession, book: Book) -> dict[str, Any]:
    from fastapi import HTTPException

    from app.services.book_freeze_service import (
        LEGACY_INCOMPLETE_MESSAGE,
        book_is_legacy_incomplete,
        frozen_conflict_message,
        is_book_frozen,
        load_persisted_freeze_cutoff,
    )
    from app.services.processing_allowance_service import reserve_processing_words
    from app.services.task_execution_service import (
        dispatch_pending_analysis_tasks,
        dispatch_pending_extraction_tasks,
        ensure_task_execution,
    )

    if is_book_frozen(book):
        raise HTTPException(409, frozen_conflict_message())
    cutoff = await load_persisted_freeze_cutoff(db)
    if book_is_legacy_incomplete(book, cutoff):
        raise HTTPException(409, LEGACY_INCOMPLETE_MESSAGE)

    run = (
        (
            await db.execute(
                select(BookProcessingRun)
                .where(BookProcessingRun.book_id == book.id, BookProcessingRun.status == "paused")
                .order_by(BookProcessingRun.created_at.desc())
                .with_for_update()
            )
        )
        .scalars()
        .first()
    )
    if run is None:
        raise HTTPException(409, "Processing is not paused for this book.")
    user = await db.get(User, book.user_id)
    if user is None:
        raise HTTPException(404, "Book owner not found.")
    chapters = (
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number)
            )
        )
        .scalars()
        .all()
    )
    queued_extraction = 0
    blocker: dict[str, Any] | None = None
    for chapter in chapters:
        if chapter.processed:
            continue
        existing = (
            await db.execute(
                select(TaskExecution).where(
                    TaskExecution.processing_run_id == run.id,
                    TaskExecution.task_name == "extraction_tasks.process_chapter",
                    TaskExecution.chapter_id == chapter.id,
                )
            )
        ).scalar_one_or_none()
        try:
            await reserve_processing_words(
                db,
                user,
                book_id=book.id,
                usage_kind="initial_ingestion_chapter",
                source_id=f"{run.id}:{chapter.number}",
                word_count=int(chapter.word_count or 0),
            )
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
            blocker = {"kind": "monthly_processed_words", "detail": str(exc.detail)}
            run.next_chapter_number = chapter.number
            break
        if existing is None:
            existing = await ensure_task_execution(
                db,
                task_name="extraction_tasks.process_chapter",
                processing_run=run,
                chapter_id=chapter.id,
                chapter_number=chapter.number,
                arguments={
                    "book_id": str(book.id),
                    "chapter_number": chapter.number,
                    "processing_run_id": str(run.id),
                },
            )
        elif existing.status == "paused":
            existing.status = "pending_dispatch"
            existing.error_category = None
            existing.error_detail = None
        if existing.status == "pending_dispatch":
            queued_extraction += 1
    paused_analysis = (
        (
            await db.execute(
                select(TaskExecution).where(
                    TaskExecution.processing_run_id == run.id,
                    TaskExecution.task_name == "analysis_tasks.analyse_chapter",
                    TaskExecution.status == "paused",
                )
            )
        )
        .scalars()
        .all()
    )
    for execution in paused_analysis:
        execution.status = "pending_dispatch"
        execution.error_category = None
        execution.error_detail = None
        execution.completed_at = None
    queued_analysis = len(paused_analysis)
    if queued_extraction + queued_analysis == 0:
        run.resume_blockers = [blocker] if blocker else run.resume_blockers
        await db.commit()
        raise HTTPException(
            409,
            {
                "message": "Processing cannot continue until allowance is available.",
                "resume_blockers": run.resume_blockers,
            },
        )
    remains_paused = blocker is not None
    run.status = "paused" if remains_paused else "running"
    run.pause_reason = "monthly_processed_words" if remains_paused else None
    run.resume_blockers = [blocker] if blocker else []
    run.paused_at = datetime.now(UTC) if remains_paused else None
    if not remains_paused:
        run.next_chapter_number = None
    book.status = "processing"
    workspace = dict(book.writer_workspace or {})
    processing = dict(workspace.get("processing") or {})
    processing.update(
        {
            "status": "paused" if remains_paused else "processing",
            "stage": "usage_limited" if remains_paused else "queued",
            "processing_run_id": str(run.id),
            "pause_reason": run.pause_reason,
            "resume_available": remains_paused,
            "resume_blockers": run.resume_blockers,
            "next_chapter_number": run.next_chapter_number,
            "retry_actions": ["continue_processing"] if remains_paused else [],
            "last_error": None,
        }
    )
    workspace["processing"] = processing
    book.writer_workspace = workspace
    await db.commit()
    await dispatch_pending_extraction_tasks(db)
    await dispatch_pending_analysis_tasks(db)
    await mark_book_cache_dirty(str(book.id))
    await mark_user_dashboard_cache_dirty(str(book.user_id))
    return build_book_processing_payload(book) or {}


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
    chapters: list[Chapter] | None = None,
) -> bool:
    if book.status != "processing":
        return False

    from app.services.book_freeze_service import (
        book_created_before_cutoff,
        load_persisted_freeze_cutoff,
    )

    cutoff = await load_persisted_freeze_cutoff(db)
    if book_created_before_cutoff(book, cutoff):
        # Deployment transition gate: automatic recovery must not restart
        # processing for pre-cutoff books before the one-time freeze runs.
        return False

    processing_started_at = get_processing_started_at(book)
    if processing_started_at is None:
        return False

    current_time = now or datetime.now(UTC)
    if current_time - processing_started_at < STALE_PROCESSING_REQUEUE_AFTER:
        return False

    if chapters is None:
        chapters = list(
            (
                await db.execute(
                    select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc())
                )
            )
            .scalars()
            .all()
        )
    if not chapters or any(chapter.processed for chapter in chapters):
        return False

    pending_statuses = {
        str((chapter.analysis_state or {}).get("status") or "").strip().lower()
        for chapter in chapters
    }
    if pending_statuses - {"", "queued", "pending"}:
        return False

    latest_update_at = max(
        (
            timestamp
            for chapter in chapters
            if (timestamp := _parse_chapter_status_updated_at(chapter)) is not None
        ),
        default=processing_started_at,
    )
    if current_time - latest_update_at < STALE_PROCESSING_REQUEUE_AFTER:
        return False

    chunk_count = (
        await db.scalar(
            select(func.count()).select_from(BookChunk).where(BookChunk.book_id == book.id)
        )
        or 0
    )
    if chunk_count:
        return False

    await _dispatch_durable_book_processing(
        db,
        book,
        run_kind="stalled_recovery",
        identity_suffix=f"stalled-{int(current_time.timestamp())}",
    )
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


def book_processing_has_blocking_failure(book: Book) -> bool:
    """Whether the stored pipeline for a book contains a failed stage or chapter."""
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = (
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    return _processing_pipeline_has_blocking_failure(processing)


async def repair_stale_completed_processing_state(db: AsyncSession, book: Book) -> bool:
    """Mark a normal uploaded book ready when persisted chapter intelligence is complete."""
    if getattr(book, "is_editor_project", False) or book.status != "processing":
        return False

    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = dict(
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    if processing.get("rebuild_run_id") or _processing_pipeline_has_blocking_failure(processing):
        return False

    chapter_count, processed_count, detailed_summary_count = (
        await db.execute(
            select(
                func.count(func.distinct(Chapter.number)).filter(Chapter.word_count > 0),
                func.count(func.distinct(Chapter.number)).filter(
                    Chapter.word_count > 0,
                    Chapter.processed.is_(True),
                ),
                func.count(func.distinct(Chapter.number)).filter(
                    Chapter.word_count > 0,
                    Chapter.processed.is_(True),
                    ChapterSummary.mode == "detailed",
                ),
            )
            .select_from(Chapter)
            .outerjoin(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id)
        )
    ).one()
    chapter_count = int(chapter_count or 0)
    if chapter_count <= 0:
        return False
    processed_count = int(processed_count or 0)
    detailed_summary_count = int(detailed_summary_count or 0)
    if processed_count < chapter_count or detailed_summary_count < chapter_count:
        return False

    await _write_ready_book_state(
        db,
        book,
        chapter_count=chapter_count,
        processed_count=processed_count,
        detailed_summary_count=detailed_summary_count,
    )
    log.warning(
        "repaired_stale_completed_processing_state book_id=%s chapters=%s", book.id, chapter_count
    )
    return True


async def complete_book_after_analysis(db: AsyncSession, *, book_id: Any) -> bool:
    """Finalize a normal upload as ready as soon as the last analysis succeeds.

    The 5-minute stale-processing repair is a safety net, not the primary
    completion path. Without this, books whose extraction finished before
    analysis waited for the repair cycle to flip them to ready.
    """
    book = await db.get(Book, book_id, with_for_update=True)
    if book is None or getattr(book, "is_editor_project", False):
        return False
    if book.status != "processing":
        return False

    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = dict(
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    if processing.get("rebuild_run_id") or _processing_pipeline_has_blocking_failure(processing):
        # Rebuilds finalize through the editor-project flow, and blocking
        # failures must stay visible instead of being promoted to ready.
        return False

    chapter_count, processed_count, detailed_summary_count = (
        await db.execute(
            select(
                func.count(func.distinct(Chapter.number)).filter(Chapter.word_count > 0),
                func.count(func.distinct(Chapter.number)).filter(
                    Chapter.word_count > 0,
                    Chapter.processed.is_(True),
                ),
                func.count(func.distinct(Chapter.number)).filter(
                    Chapter.word_count > 0,
                    Chapter.processed.is_(True),
                    ChapterSummary.mode == "detailed",
                ),
            )
            .select_from(Chapter)
            .outerjoin(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id)
        )
    ).one()
    chapter_count = int(chapter_count or 0)
    processed_count = int(processed_count or 0)
    detailed_summary_count = int(detailed_summary_count or 0)
    if chapter_count <= 0 or processed_count < chapter_count:
        return False
    if detailed_summary_count < chapter_count:
        return False

    await _write_ready_book_state(
        db,
        book,
        chapter_count=chapter_count,
        processed_count=processed_count,
        detailed_summary_count=detailed_summary_count,
    )
    log.info("book_processing_completed book_id=%s chapters=%s", book.id, chapter_count)
    return True


async def _write_ready_book_state(
    db: AsyncSession,
    book: Book,
    *,
    chapter_count: int,
    processed_count: int,
    detailed_summary_count: int,
) -> None:
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = dict(
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
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
    processing["last_error"] = None
    workspace["processing"] = processing
    book.writer_workspace = workspace
    book.status = "ready"
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    await mark_user_dashboard_cache_dirty(str(book.user_id))
