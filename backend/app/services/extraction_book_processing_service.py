from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.core.config import settings
from app.core.storage import download_book, upload_binary
from app.models.book import Book, Chapter
from app.models.user import User
from app.services.extraction_budget_service import apply_ingestion_token_budget
from app.services.extraction_chapter_content_service import _ensure_chapter_stub
from app.services.extraction_chapter_queue_service import queue_initial_extraction_chapters
from app.services.task_execution_service import get_or_create_processing_run
from app.utils.books.imports import parse_book_upload_for_ingestion
from app.utils.books.scene_metadata import refresh_screenplay_scene_rows
from app.utils.books.serialization import build_blank_cover_image
from app.utils.compliance.copyright_check import evaluate_document_copyright
from app.utils.ingestion_utils import (
    apply_chapter_number_strategy,
    elapsed_ms,
    is_book_hidden,
    mark_book_processing_cancelled,
    persist_chapter_payloads,
    update_book_processing_state,
)

log = logging.getLogger("lorevia.extraction")

COVER_GENERATION_EXCEPTIONS = (OSError, RuntimeError, TypeError, ValueError)
COVER_UPLOAD_EXCEPTIONS = (BotoCoreError, ClientError, OSError, RuntimeError, TypeError, ValueError)


async def ensure_ingested_book_cover(book: Book, raw: bytes) -> bool:
    if book.cover_s3_key:
        return False

    cover: tuple[bytes, str] | None = None
    if book.format == "pdf":
        from app.parsers.pdf_parser import extract_first_page_cover

        try:
            cover = await asyncio.to_thread(extract_first_page_cover, raw)
        except COVER_GENERATION_EXCEPTIONS:
            log.warning("cover_extraction_failed book_id=%s", book.id, exc_info=True)

    if cover is None:
        try:
            cover = await asyncio.to_thread(build_blank_cover_image, book.title, book.author)
        except COVER_GENERATION_EXCEPTIONS:
            log.warning("blank_cover_generation_failed book_id=%s", book.id, exc_info=True)
            return False

    cover_bytes, content_type = cover
    try:
        book.cover_s3_key = await asyncio.to_thread(
            upload_binary,
            f"covers/{book.user_id}/{uuid.uuid4()}.png",
            cover_bytes,
            content_type,
        )
        return True
    except COVER_UPLOAD_EXCEPTIONS:
        log.warning("cover_upload_failed book_id=%s", book.id, exc_info=True)
        return False


async def process_book_ingestion_and_queue(
    db,
    *,
    book_id: str,
    queue_wait_ms: int | None = None,
) -> dict:
    started_at = time.perf_counter()
    processing_started_at = datetime.now(UTC)
    book = await db.get(Book, uuid.UUID(book_id))
    if not book:
        return {"error": "not found"}

    if await is_book_hidden(db, book.id):
        log.info("Skipping processing for unavailable book %s", book_id)
        return {"skipped": "book_unavailable"}

    book.status = "processing"
    book.writer_workspace = update_book_processing_state(
        book,
        status="processing",
        stage="queued",
        total_chapters=book.total_chapters,
        completed_chapters=0,
        started_at=processing_started_at,
        queue_wait_ms=queue_wait_ms,
    )
    await db.commit()

    download_started = time.perf_counter()
    raw = await asyncio.to_thread(download_book, book.s3_key)
    log.info(
        "ingestion_timing stage=download book_id=%s elapsed_ms=%s queue_wait_ms=%s",
        book_id,
        elapsed_ms(download_started),
        queue_wait_ms,
    )

    cover_started = time.perf_counter()
    cover_generated = await ensure_ingested_book_cover(book, raw)
    log.info(
        "ingestion_timing stage=cover book_id=%s elapsed_ms=%s generated=%s",
        book_id,
        elapsed_ms(cover_started),
        cover_generated,
    )

    copyright_started = time.perf_counter()
    copyright_info = await evaluate_document_copyright(
        format_name=book.format,
        raw=raw,
        existing_isbn=book.isbn,
    )
    if copyright_info.get("isbn"):
        book.isbn = str(copyright_info["isbn"])
    book.copyright_warning = bool(copyright_info.get("copyright_warning", False))
    await db.commit()
    log.info(
        "ingestion_timing stage=copyright book_id=%s elapsed_ms=%s warning=%s isbn_found=%s",
        book_id,
        elapsed_ms(copyright_started),
        book.copyright_warning,
        bool(copyright_info.get("isbn")),
    )

    parse_started = time.perf_counter()
    parsed_payload = await parse_book_upload_for_ingestion(
        format_name=book.format,
        work_type=book.work_type,
        raw=raw,
        preserve_chapter_numbers=book.preserve_chapter_numbers,
        preserve_source_chapters=book.preserve_source_chapters,
    )
    chapters = cast(list[dict[str, Any]], parsed_payload["chapters"])
    screenplay_payload = cast(dict[str, Any] | None, parsed_payload.get("screenplay_payload"))
    parser_diagnostics = cast(dict[str, Any] | None, parsed_payload.get("parser_diagnostics"))

    detected_language = parsed_payload.get("detected_language", "en")
    if detected_language and detected_language != "en":
        book.language = detected_language
        await db.commit()

    if parser_diagnostics:
        sections = []
        for ch in chapters:
            sections.append(
                {
                    "title": ch.get("title", ""),
                    "type": ch.get("section_type", "unknown"),
                    "number": ch.get("number"),
                    "include_in_analysis": ch.get("section_type")
                    not in {
                        "toc",
                        "copyright",
                        "dedication",
                        "acknowledgements",
                        "glossary",
                        "notes",
                        "title_page",
                    },
                }
            )
        book.import_structure = {
            "detected_language": detected_language,
            "chapter_count": len(chapters),
            "toc_detected": parser_diagnostics.get("toc_detected", False),
            "front_matter_count": parser_diagnostics.get("front_matter_count", 0),
            "sections": sections,
        }
        await db.commit()

    all_chapters = apply_chapter_number_strategy(
        chapters,
        preserve_chapter_numbers=(book.preserve_chapter_numbers or book.preserve_source_chapters)
        and book.work_type != "screenplay",
        generic_titles=book.work_type != "screenplay"
        and not (book.preserve_chapter_numbers or book.preserve_source_chapters),
    )

    if book.force_single_manuscript and len(all_chapters) > 1:
        merged_text = "\n\n".join(
            ch.get("text", "") for ch in all_chapters if ch.get("text", "").strip()
        )
        all_chapters = [
            {
                "number": 1,
                "title": book.title or "Full Manuscript",
                "text": merged_text,
            }
        ]
        log.info(
            "ingestion_merged_single_manuscript book_id=%s original_chapters=%s",
            book_id,
            len(chapters),
        )

    log.info(
        "ingestion_timing stage=parse book_id=%s elapsed_ms=%s chapters=%s",
        book_id,
        elapsed_ms(parse_started),
        len(all_chapters),
    )

    if await is_book_hidden(db, book.id):
        await mark_book_processing_cancelled(
            db,
            book,
            stage="parse",
            queue_wait_ms=queue_wait_ms,
            last_error="Book was removed while processing.",
        )
        return {"skipped": "book_hidden"}

    user = await db.get(User, book.user_id)

    budget_started = time.perf_counter()
    budget_result = await apply_ingestion_token_budget(
        db,
        book=book,
        user=user,
        all_chapters=all_chapters,
    )
    log.info(
        "ingestion_timing stage=budget book_id=%s elapsed_ms=%s outcome=%s",
        book_id,
        elapsed_ms(budget_started),
        budget_result.get("error") or "accepted",
    )
    if budget_result.get("error") == "budget_exhausted":
        log.warning(
            "User %s has exhausted free token budget: %s used.",
            book.user_id,
            budget_result.get("used_so_far"),
        )
        return {"error": "budget_exhausted"}
    if budget_result.get("error") == "insufficient_remaining_budget":
        log.warning(
            "Remaining budget (%s) too small for even first chapter.",
            budget_result.get("remaining_budget"),
        )
        return {"error": "insufficient_remaining_budget"}

    processed_tokens = int(budget_result["processed_tokens"])
    was_truncated = bool(budget_result["was_truncated"])
    ai_chapters = cast(list[dict[str, Any]], budget_result["ai_chapters"])

    await db.execute(
        sa_update(Book)
        .where(Book.id == book.id)
        .values(
            total_chapters=len(all_chapters),
            total_tokens=processed_tokens,
            is_truncated=was_truncated,
            writer_workspace=update_book_processing_state(
                book,
                status="processing",
                stage="parsed",
                total_chapters=len(all_chapters),
                completed_chapters=0,
                started_at=processing_started_at,
                queue_wait_ms=queue_wait_ms,
                parser_diagnostics=parser_diagnostics,
            ),
        )
    )
    await db.commit()

    stage_started = time.perf_counter()
    stored_chapter_keys = await persist_chapter_payloads(
        book.id,
        all_chapters,
        concurrency=settings.INGESTION_CHAPTER_UPLOAD_CONCURRENCY,
    )

    if await is_book_hidden(db, book.id):
        await mark_book_processing_cancelled(
            db,
            book,
            stage="staged",
            queue_wait_ms=queue_wait_ms,
            last_error="Book was removed while processing.",
        )
        return {"skipped": "book_hidden"}

    existing_chapters = (
        (await db.execute(select(Chapter).where(Chapter.book_id == book.id))).scalars().all()
    )
    existing_chapter_map: dict[int, Chapter] = {
        ch.number: ch for ch in existing_chapters if ch.number is not None
    }
    for ch_data in all_chapters:
        await _ensure_chapter_stub(
            db,
            book,
            ch_data,
            s3_key=stored_chapter_keys.get(int(ch_data["number"]), ""),
            existing_chapter_map=existing_chapter_map,
        )
    if screenplay_payload is not None:
        await refresh_screenplay_scene_rows(
            db,
            book=book,
            parsed_scenes=cast(list[Any], screenplay_payload["scenes"]),
        )
    await db.commit()
    log.info(
        "ingestion_timing stage=stage_chapters book_id=%s elapsed_ms=%s stored=%s",
        book_id,
        elapsed_ms(stage_started),
        len(stored_chapter_keys),
    )

    if await is_book_hidden(db, book.id):
        await mark_book_processing_cancelled(
            db,
            book,
            stage="staged",
            rollback=True,
            queue_wait_ms=queue_wait_ms,
            last_error="Book was removed while processing.",
        )
        return {"skipped": "book_hidden"}

    chapter_rows = (
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number)
            )
        )
        .scalars()
        .all()
    )
    chapters_by_number = {int(chapter.number): chapter for chapter in chapter_rows}
    processing_run = await get_or_create_processing_run(
        db,
        user_id=book.user_id,
        book_id=book.id,
        chapters_total=len(ai_chapters),
    )
    processing_run.status = "running"
    processing_run.started_at = processing_run.started_at or datetime.now(UTC)
    queue_started = time.perf_counter()
    queue_result = await queue_initial_extraction_chapters(
        db,
        book=book,
        user=user,
        processing_run=processing_run,
        ai_chapters=ai_chapters,
        chapter_rows=chapter_rows,
        chapters_by_number=chapters_by_number,
        processing_started_at=processing_started_at,
        queue_wait_ms=queue_wait_ms,
    )
    if queue_result.get("skipped") == "book_hidden":
        return {"skipped": "book_hidden"}
    queued_count = int(queue_result.get("queued_count") or 0)
    log.info(
        "ingestion_timing stage=queue_chapters book_id=%s elapsed_ms=%s queued=%s",
        book_id,
        elapsed_ms(queue_started),
        queued_count,
    )

    if await is_book_hidden(db, book.id):
        await mark_book_processing_cancelled(
            db,
            book,
            stage="queue_complete",
            queue_wait_ms=queue_wait_ms,
            last_error="Book was removed while processing.",
        )
        return {"skipped": "book_hidden"}

    if was_truncated:
        book.status = "ready"
        await db.commit()

    if settings.DEBUG:
        log.info("book_processed %s chapters=%s", book_id, len(all_chapters))
    log.info(
        "ingestion_timing stage=process_book_total book_id=%s elapsed_ms=%s processed_chapters=%s truncated=%s",
        book_id,
        elapsed_ms(started_at),
        len(ai_chapters),
        was_truncated,
    )
    return {"book_id": book_id, "chapters": len(all_chapters)}
