from sqlalchemy import select

from app.models.operations import BookProcessingRun
from app.services.book_freeze_service import is_book_frozen
from app.services.task_execution_service import ensure_task_execution


async def dispatch_chapter_analysis_after_extraction(
    db,
    *,
    book,
    chapter,
    chapter_number: int,
    rebuild_run_id: str | None,
    manual_reprocess: bool,
) -> None:
    if is_book_frozen(book):
        return
    active_run = (
        (
            await db.execute(
                select(BookProcessingRun)
                .where(
                    BookProcessingRun.book_id == book.id,
                    BookProcessingRun.status.in_(("queued", "running", "paused")),
                )
                .order_by(BookProcessingRun.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if active_run is None:
        # The lookup opened a transaction. Close it here so callers do not
        # retain a checked-out connection after a no-op dispatch.
        await db.commit()
        return

    await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=active_run,
        chapter_id=chapter.id,
        chapter_number=chapter_number,
        rebuild_run_id=rebuild_run_id,
        arguments={
            "chapter_id": str(chapter.id),
            "book_id": str(book.id),
            "manual_reprocess": manual_reprocess,
        },
        feature="analysis",
    )
    await db.commit()

    from app.services.task_execution_service import dispatch_pending_analysis_tasks

    await dispatch_pending_analysis_tasks(db)
