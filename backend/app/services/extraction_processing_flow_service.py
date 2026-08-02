from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.models.book import Book, Chapter
from app.models.progress import ReadingProgress
from app.models.user import User
from app.parsers.chunker import count_tokens
from app.services.character_identity.resolver import reconcile_pending_first_name_alias_candidates
from app.services.editor_project_service import complete_rebuild_if_ready
from app.services.email_service import send_processing_complete_with_stats
from app.utils.ingestion_utils import (
    get_processing_started_at,
    processing_state_for_completed_extraction,
    update_book_processing_state,
)
from app.utils.notification_utils import collect_book_ready_stats, upsert_book_ready_notification
from app.utils.relationship_utils import reconcile_extracted_relationships

log = logging.getLogger("lorevia.extraction")


async def _book_processing_complete(db, book_id: uuid.UUID) -> bool:
    remaining_count: int | None = await db.scalar(
        select(func.count())
        .select_from(Chapter)
        .where(Chapter.book_id == book_id, Chapter.processed.is_(False))
    )
    return (remaining_count or 0) == 0


async def _claim_book_completion(db, book_id: uuid.UUID) -> bool:
    status = await db.scalar(select(Book.status).where(Book.id == book_id).with_for_update())
    if status is None or str(status or "") == "ready":
        return False
    return await _book_processing_complete(db, book_id)


async def finalize_book_completion_after_chapter(
    db,
    *,
    book: Book,
    chapter: Chapter,
    chapter_number: int,
    processed_count: int,
    processing_total: int | None,
    queue_wait_ms: int | None,
    extraction_diagnostics: dict[str, Any] | None,
) -> bool:
    if not await _claim_book_completion(db, book.id):
        # _claim_book_completion locks the shared book row. Do not return that
        # lock to callers: import/scene synchronization may lock a chapter
        # next, which would reverse the global chapter -> book lock order.
        await db.commit()
        return False

    final_reconciled_alias_count = await reconcile_pending_first_name_alias_candidates(
        db,
        book_id=book.id,
    )
    if final_reconciled_alias_count:
        log.info(
            "identity_alias_reconcile book_id=%s aliases=%s scope=book_complete",
            book.id,
            final_reconciled_alias_count,
        )
    relationship_reconcile_result = await reconcile_extracted_relationships(
        db,
        book_id=book.id,
    )
    if any(relationship_reconcile_result.values()):
        log.info(
            "relationship_reconcile book_id=%s result=%s",
            book.id,
            relationship_reconcile_result,
        )
    ready_stats = await collect_book_ready_stats(db, book)
    processing_status, processing_stage = processing_state_for_completed_extraction(
        analysis_complete=ready_stats.analysis_complete,
    )
    # Set book.status to "ready" only when both extraction AND analysis are complete
    # This ensures the frontend status dot (blue) matches the actual completion state
    book.status = "ready" if processing_status == "ready" else "processing"
    book.writer_workspace = update_book_processing_state(
        book,
        status=processing_status,
        stage=processing_stage,
        total_chapters=processing_total,
        completed_chapters=processed_count,
        started_at=get_processing_started_at(book),
        queue_wait_ms=queue_wait_ms,
        chapter_number=chapter_number,
        chapter_title=chapter.title,
        parser_diagnostics=extraction_diagnostics,
    )
    if processing_status == "ready":
        await complete_rebuild_if_ready(db, book)

    if book.mode == "author" and book.total_chapters:
        progress_result = await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == book.user_id,
                ReadingProgress.book_id == book.id,
            )
        )
        progress = progress_result.scalar()

        chapters_read = list(range(1, book.total_chapters + 1))
        if progress is None:
            progress = ReadingProgress(
                user_id=book.user_id,
                book_id=book.id,
                current_chapter=book.total_chapters,
                scroll_pct=1.0,
                chapters_read=chapters_read,
            )
            db.add(progress)
        else:
            progress.current_chapter = book.total_chapters
            progress.scroll_pct = 1.0
            progress.chapters_read = chapters_read

    _, created_ready_notification = await upsert_book_ready_notification(db, book, ready_stats)

    completion_email: str | None = None
    if created_ready_notification and ready_stats.analysis_complete:
        user = await db.get(User, book.user_id)
        if user and user.email:
            completion_email = user.email
    await db.commit()

    if completion_email:
        await send_processing_complete_with_stats(
            completion_email,
            book_title=book.title,
            character_count=ready_stats.character_count,
            relationship_count=ready_stats.relationship_count,
            plot_thread_count=ready_stats.plot_thread_count,
            continuity_issue_count=ready_stats.continuity_issue_count,
        )
    return True


def _group_chunks_for_extraction(chunks: list[str]) -> list[list[str]]:
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for chunk in chunks:
        chunk_tokens = count_tokens(chunk)
        exceeds_token_budget = current_tokens + chunk_tokens > settings.EXTRACTION_BATCH_MAX_TOKENS
        exceeds_chunk_budget = len(current_batch) >= settings.EXTRACTION_BATCH_MAX_CHUNKS
        if current_batch and (exceeds_token_budget or exceeds_chunk_budget):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
        current_batch.append(chunk)
        current_tokens += chunk_tokens

    if current_batch:
        batches.append(current_batch)
    return batches
