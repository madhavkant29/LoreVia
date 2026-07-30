from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from app.models.book import Book, Chapter
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.ingestion_utils import (
    get_processing_started_at,
    update_book_processing_state,
)

log = logging.getLogger("lorevia.extraction")


async def update_chapter_processing_progress(
    db,
    *,
    book: Book,
    chapter: Chapter,
    chapter_number: int,
    queue_wait_ms: int | None,
    extraction_diagnostics: dict[str, Any] | None,
) -> tuple[int, int | None]:
    processed_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Chapter)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.processed.is_(True),
                )
            )
        ).scalar_one()
    )
    processing_total = int(book.total_chapters or processed_count or 0) or None
    book.writer_workspace = update_book_processing_state(
        book,
        status="processing",
        stage="chapter_complete",
        total_chapters=processing_total,
        completed_chapters=processed_count,
        started_at=get_processing_started_at(book),
        queue_wait_ms=queue_wait_ms,
        chapter_number=chapter_number,
        chapter_title=chapter.title,
        parser_diagnostics=extraction_diagnostics,
    )
    await db.commit()
    await invalidate_advisor_caches_for_book(db, book_id=book.id)
    # Cache target discovery performs a database read. End that read
    # transaction before returning to provider or scene-processing code.
    await db.commit()

    processing_state = (
        book.writer_workspace.get("processing") if isinstance(book.writer_workspace, dict) else None
    )
    log.info(
        "ingestion_progress book_id=%s chapter=%s completed=%s total=%s progress_pct=%s eta_seconds=%s queue_wait_ms=%s",
        book.id,
        chapter_number,
        processed_count,
        processing_total,
        (processing_state or {}).get("progress_pct")
        if isinstance(processing_state, dict)
        else None,
        (processing_state or {}).get("eta_seconds") if isinstance(processing_state, dict) else None,
        queue_wait_ms,
    )
    return processed_count, processing_total
