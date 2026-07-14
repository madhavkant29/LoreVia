from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.models.book import Book, Chapter
from app.schemas.books import ManuscriptReprocessBody, ManuscriptReprocessOut
from app.services.processing_allowance_service import (
    consume_processing_reservation,
    ensure_project_writable,
    release_processing_reservation,
    reserve_processing_words,
)
from app.services.task_execution_service import (
    dispatch_pending_extraction_tasks,
    ensure_task_execution,
    get_or_create_processing_run,
)
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book
from app.utils.ingestion_utils import build_analysis_chapter_state, load_processing_chapter_payload
from app.utils.llm_usage_utils import (
    assert_manual_reprocess_token_capacity,
    estimate_manual_reprocess_tokens,
)

log = logging.getLogger(__name__)
MANUAL_REPROCESS_FINALIZATION_ERRORS = (RuntimeError, ValueError, SQLAlchemyError)
MANUAL_REPROCESS_CLEANUP_ERRORS = (RuntimeError, ValueError, SQLAlchemyError)


async def start_manual_manuscript_reprocess(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    body: ManuscriptReprocessBody,
) -> ManuscriptReprocessOut:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    ensure_project_writable(book)

    if not (body.confirm_processing_words or body.confirm_upload_charge):
        raise HTTPException(
            400,
            "Confirm that reprocessing will consume processed-word allowance before continuing.",
        )

    from app.services.editor_project_service import (
        dispatch_rebuild,
        fail_rebuild_if_active,
        get_rebuild_run_id,
        prepare_rebuild,
    )

    if get_rebuild_run_id(book) is not None:
        raise HTTPException(409, "A rebuild is already in progress for this project")

    chapters = (
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id, Chapter.word_count > 0)
            )
        )
        .scalars()
        .all()
    )

    if not chapters:
        raise HTTPException(400, "Save at least one chapter before reprocessing")

    requested_words = sum(int(chapter.word_count or 0) for chapter in chapters)
    reservation_source_id = f"manual:{uuid.uuid4().hex}"
    reservation, allowance = await reserve_processing_words(
        db,
        current_user,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=reservation_source_id,
        word_count=requested_words,
    )
    rebuild_run_id = await prepare_rebuild(db, book, reason="manual_reprocess")
    try:
        chapters_queued, total_words = await dispatch_rebuild(db, book)
        await consume_processing_reservation(db, reservation.id)
        await db.commit()
    except MANUAL_REPROCESS_FINALIZATION_ERRORS as exc:
        log.exception(
            "manual_reprocess_allowance_failed book_id=%s rebuild_run_id=%s",
            book.id,
            rebuild_run_id,
        )
        await db.rollback()
        try:
            await release_processing_reservation(db, reservation.id)
            await db.refresh(book)
            await fail_rebuild_if_active(
                db,
                book,
                expected_rebuild_run_id=rebuild_run_id,
                error="Unable to finalize the manual reprocess allowance reservation.",
            )
            await db.commit()
        except MANUAL_REPROCESS_CLEANUP_ERRORS:
            await db.rollback()
            log.exception(
                "manual_reprocess_allowance_cleanup_failed book_id=%s rebuild_run_id=%s",
                book.id,
                rebuild_run_id,
            )
        raise HTTPException(
            503,
            "Unable to finalize the reprocess allowance reservation. No rebuild was started.",
        ) from exc

    return ManuscriptReprocessOut(
        book_id=str(book.id),
        status="processing",
        chapters_queued=chapters_queued,
        total_words=total_words,
        upload_charge_consumed=False,
        charge_kind=None,
        processed_words_reserved=requested_words,
        processed_words_remaining=allowance.monthly_processed_words_remaining,
    )


async def start_manual_chapter_reprocess(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    chapter_number: int,
) -> ManuscriptReprocessOut:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    ensure_project_writable(book)

    from app.services.editor_project_service import (
        get_rebuild_run_id,
        purge_manual_chapter_reprocess_content,
        update_reprocess_metadata,
    )

    if get_rebuild_run_id(book) is not None:
        raise HTTPException(409, "A rebuild is already in progress for this project")
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(404, "Chapter not found")
    if not chapter.word_count or chapter.word_count <= 0:
        raise HTTPException(400, "Save chapter content before reprocessing")
    chapter_payload = await load_processing_chapter_payload(
        book.id,
        chapter_number,
        chapter_s3_key=chapter.s3_key,
        chapter_title=chapter.title,
    )
    if chapter_payload is None:
        raise HTTPException(400, "Save chapter content before reprocessing")

    estimated_tokens = estimate_manual_reprocess_tokens(str(chapter_payload.get("text") or ""))
    await assert_manual_reprocess_token_capacity(
        db,
        current_user,
        estimated_tokens=estimated_tokens,
    )
    reservation, allowance = await reserve_processing_words(
        db,
        current_user,
        book_id=book.id,
        usage_kind="chapter_reprocess",
        source_id=f"{book.id}:{chapter_number}:{chapter.content_version}:{uuid.uuid4().hex}",
        word_count=int(chapter.word_count or 0),
    )

    await purge_manual_chapter_reprocess_content(db, book=book, chapter=chapter)
    chapter.analysis_state = build_analysis_chapter_state(
        chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
        status="queued",
        increment_attempt=True,
    )
    update_reprocess_metadata(
        book,
        clear_pending_chapters=[chapter_number],
        last_manual_chapter_number=chapter_number,
    )
    processing_run = await get_or_create_processing_run(
        db,
        user_id=current_user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        chapters_total=1,
    )
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=processing_run,
        chapter_id=chapter.id,
        chapter_number=chapter_number,
        arguments={
            "book_id": str(book.id),
            "chapter_number": chapter_number,
            "processing_run_id": str(processing_run.id),
            "processing_reservation_id": str(reservation.id),
            "manual_reprocess": True,
        },
        identity_suffix=reservation.id,
    )
    reservation.task_id = str(execution.id)
    await db.commit()
    await db.refresh(book)
    await invalidate_advisor_caches_for_book(db, book_id=book.id)
    await mark_book_cache_dirty(str(book.id))

    await dispatch_pending_extraction_tasks(db)

    return ManuscriptReprocessOut(
        book_id=str(book.id),
        status="processing",
        chapters_queued=1,
        total_words=int(chapter.word_count or 0),
        upload_charge_consumed=False,
        charge_kind=None,
        processed_words_reserved=int(chapter.word_count or 0),
        processed_words_remaining=allowance.monthly_processed_words_remaining,
    )
