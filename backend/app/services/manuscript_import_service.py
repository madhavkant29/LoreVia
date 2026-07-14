import asyncio
import logging
import uuid
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.redis import mark_user_dashboard_cache_dirty
from app.models.book import Book, Chapter, ChapterMedia
from app.models.progress import ReadingProgress
from app.schemas.books import ChapterConsistencyReport, ManuscriptImportResult
from app.services.processing_allowance_service import ensure_active_word_capacity
from app.services.task_execution_service import enqueue_analysis_execution
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.books.chapter_versions import snapshot_chapter_version
from app.utils.books.manuscript import (
    chapter_media_storage_payload,
    deserialize_manuscript_content,
    persist_editor_chapter_content,
)
from app.utils.books.normalization import SCENE_BREAK_LINE_RE
from app.utils.books.scene_metadata import extract_novel_scene_candidates, refresh_screenplay_scene_rows
from app.utils.books.scene_ordering import replace_chapter_novel_scenes
from app.utils.books.scene_sync import sync_chapter_content_from_novel_scenes
from app.utils.books.writer_workspace import _append_recent_revision_edit, touch_public_book_updated_at
from app.utils.ingestion_utils import build_analysis_chapter_state
from app.utils.notification_utils import build_upload_processing_notification
from app.utils.user_utils import add_daily_word_progress, build_writing_activity_entry
from app.workers.consumers.extraction_consumer import _process_chapter

log = logging.getLogger(__name__)

PDF_COVER_EXTRACTION_ERRORS = (RuntimeError, ValueError, OSError)


async def persist_manuscript_import(
    db: AsyncSession,
    *,
    book: Book,
    current_user: Any,
    import_jobs: list[dict[str, object]],
    screenplay_batches: list[dict[str, object]],
    replace_existing: bool,
    chapter_number: int | None,
    expected_content_version: int | None,
    should_auto_reprocess: bool,
    resolved_book_work_type: str,
    resolved_import_format: str | None,
    first_pdf_raw_for_cover: bytes | None,
    total_file_size: int,
    files_were_uploaded: bool,
) -> ManuscriptImportResult:
    imported_word_counts = {
        int(cast(Any, job["number"])): len(str(job.get("text") or "").split())
        for job in import_jobs
    }
    existing_word_counts: dict[int, int] = {}
    if replace_existing:
        rows = (
            await db.execute(
                select(Chapter.number, Chapter.word_count).where(
                    Chapter.book_id == book.id,
                    Chapter.number.in_(list(imported_word_counts)),
                )
            )
        ).all()
        existing_word_counts = {int(number): int(word_count or 0) for number, word_count in rows}

    active_words_added = sum(
        max(word_count - existing_word_counts.get(number, 0), 0)
        for number, word_count in imported_word_counts.items()
    )
    await ensure_active_word_capacity(db, current_user, active_words_added)

    daily_words_added = 0
    imported_content_versions: dict[int, int] = {}
    imported_numbers: list[int] = []

    from app.services.editor_project_service import update_reprocess_metadata

    for job in import_jobs:
        job_number = int(cast(Any, job["number"]))
        next_text = str(job.get("text") or "")
        next_word_count = len(next_text.split()) if next_text.strip() else 0
        previous_word_count = 0
        previous_text = ""
        source_version_id: str | None = None
        existing_media_payloads: list[dict[str, Any]] = []
        if replace_existing:
            existing = (
                await db.execute(
                    select(Chapter)
                    .where(Chapter.book_id == book.id, Chapter.number == job_number)
                    .with_for_update()
                )
            ).scalar()
            if existing is not None:
                current_content_version = int(existing.content_version or 1)
                if (
                    expected_content_version is not None
                    and len(import_jobs) == 1
                    and job_number == (chapter_number or job_number)
                ):
                    if current_content_version != expected_content_version:
                        raise HTTPException(
                            409,
                            {
                                "message": "Chapter content changed elsewhere. Reload the latest version or save again to intentionally overwrite it.",
                                "chapter_number": job_number,
                                "current_content_version": current_content_version,
                            },
                        )
                previous_word_count = int(existing.word_count or 0)
                if existing.s3_key:
                    existing_payload = deserialize_manuscript_content(
                        await asyncio.to_thread(storage.download_book, existing.s3_key)
                    )
                    previous_text = str(existing_payload.get("text") or "")
                existing_media_rows = (
                    (
                        await db.execute(
                            select(ChapterMedia)
                            .where(
                                ChapterMedia.chapter_id == existing.id,
                                ChapterMedia.asset_type == "image",
                            )
                            .order_by(ChapterMedia.sort_order.asc(), ChapterMedia.created_at.asc())
                        )
                    )
                    .scalars()
                    .all()
                )
                existing_media_payloads = [
                    chapter_media_storage_payload(media)
                    for media in existing_media_rows
                    if media.marker and media.storage_key
                ]
                snapshot = await snapshot_chapter_version(
                    db,
                    book,
                    existing,
                    note=f"Snapshot before replacing Chapter {job_number}",
                    snapshot_kind="pre_replace",
                )
                source_version_id = str(snapshot.id) if snapshot is not None else None
                job["content_version"] = current_content_version + 1
                await db.delete(existing)
                await db.flush()
            else:
                job["content_version"] = 1
        else:
            job["content_version"] = 1

        words_added = max(next_word_count - previous_word_count, 0)
        daily_words_added += words_added
        writing_activity = build_writing_activity_entry(
            current_user,
            book,
            words_added,
            chapter_number=job_number,
            title=str(job.get("title") or ""),
        )
        if writing_activity is not None:
            db.add(writing_activity)

        images = [*list(job.get("images") or []), *existing_media_payloads]
        if getattr(book, "is_editor_project", False) or not should_auto_reprocess:
            await persist_editor_chapter_content(
                db,
                book,
                chapter_number=job_number,
                title=str(job.get("title") or "") or None,
                text=next_text,
                html=job.get("html") if isinstance(job.get("html"), str) else None,
                description=str(job.get("description") or "") or None,
                chapter_kind=str(job.get("chapter_kind") or ""),
                content_version=int(job.get("content_version") or 1),
                images=images,
            )
            if not should_auto_reprocess:
                update_reprocess_metadata(book, add_pending_chapters=[job_number])
        else:
            await _process_chapter(
                db,
                book,
                {
                    "number": job_number,
                    "title": job.get("title"),
                    "text": next_text,
                    "html": job.get("html"),
                    "description": job.get("description"),
                    "chapter_kind": job.get("chapter_kind"),
                    "images": images,
                    "content_version": int(job.get("content_version") or 1),
                },
            )

        if resolved_book_work_type != "screenplay":
            extracted_scenes = extract_novel_scene_candidates(
                text=next_text,
                chapter_number=job_number,
                source="chapter_sync",
            )
            await replace_chapter_novel_scenes(
                db,
                book=book,
                chapter_number=job_number,
                scenes=extracted_scenes,
            )
            if SCENE_BREAK_LINE_RE.search(next_text):
                await sync_chapter_content_from_novel_scenes(
                    db,
                    book=book,
                    chapter_number=job_number,
                    increment_content_version=False,
                )

        _append_recent_revision_edit(
            book,
            kind="chapter",
            chapter_number=job_number,
            before_text=previous_text,
            after_text=next_text,
            source_version_id=source_version_id,
        )
        imported_content_versions[job_number] = int(job.get("content_version") or 1)
        imported_numbers.append(job_number)

    for batch in screenplay_batches:
        await refresh_screenplay_scene_rows(
            db,
            book=book,
            parsed_scenes=cast(list[Any], batch["parsed_scenes"]),
            starting_number=int(cast(Any, batch["starting_number"])),
            replace_scene_numbers=cast(set[int], batch["scene_numbers"]),
        )

    total_chapters = (
        await db.scalar(select(func.count()).select_from(Chapter).where(Chapter.book_id == book.id))
        or 0
    )
    book.total_chapters = total_chapters
    book.mode = "author"
    book.work_type = resolved_book_work_type
    if resolved_import_format:
        book.format = resolved_import_format
    if first_pdf_raw_for_cover and not book.cover_s3_key:
        try:
            from app.parsers.pdf_parser import extract_first_page_cover

            cover = await asyncio.to_thread(extract_first_page_cover, first_pdf_raw_for_cover)
            if cover:
                cover_bytes, content_type = cover
                book.cover_s3_key = await asyncio.to_thread(
                    storage.upload_binary,
                    f"covers/{book.user_id}/{uuid.uuid4()}.png",
                    cover_bytes,
                    content_type,
                )
        except PDF_COVER_EXTRACTION_ERRORS:
            log.warning(
                "manuscript_import_cover_extraction_failed book_id=%s", book.id, exc_info=True
            )
    book.source_kind = (
        "chapter_wise" if len(import_jobs) == 1 and not files_were_uploaded else "batch_upload"
    )
    touch_public_book_updated_at(book)
    if daily_words_added > 0:
        add_daily_word_progress(current_user, daily_words_added)
    await db.commit()
    if daily_words_added > 0:
        await mark_user_dashboard_cache_dirty(str(current_user.id))
    await db.refresh(book)

    if total_file_size > 0:
        notification = build_upload_processing_notification(book, "author", total_file_size)
        db.add(notification)
        await db.commit()

    if book.mode == "author" and total_chapters > 0:
        progress = (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book.id
                )
            )
        ).scalar()

        chapters_read = list(range(1, total_chapters + 1))
        if progress is None:
            progress = ReadingProgress(
                user_id=current_user.id,
                book_id=book.id,
                current_chapter=total_chapters,
                scroll_pct=1.0,
                chapters_read=chapters_read,
            )
            db.add(progress)
        else:
            progress.current_chapter = total_chapters
            progress.scroll_pct = 1.0
            progress.chapters_read = chapters_read
        await db.commit()

    auto_reprocess_dispatched = False
    if getattr(book, "is_editor_project", False):
        from app.services.editor_project_service import maybe_auto_reprocess_editor_project

        (
            auto_reprocess_dispatched,
            _auto_chapters_queued,
            _auto_total_words,
        ) = await maybe_auto_reprocess_editor_project(db, book)
        if auto_reprocess_dispatched:
            await db.refresh(book)

    chapter_reports: list[ChapterConsistencyReport] = []
    chapters_for_analysis: list[tuple[int, Chapter]] = []
    for number in [] if getattr(book, "is_editor_project", False) else imported_numbers:
        chapter = (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id, Chapter.number == number)
            )
        ).scalar()
        if chapter is not None:
            chapter.analysis_state = build_analysis_chapter_state(
                chapter.analysis_state
                if isinstance(getattr(chapter, "analysis_state", None), dict)
                else None,
                status="queued",
                increment_attempt=True,
            )
            chapters_for_analysis.append((number, chapter))

    if chapters_for_analysis:
        await db.commit()

    analysis_tasks: list[dict[str, str | int]] = []
    for number, chapter in chapters_for_analysis:
        execution = await enqueue_analysis_execution(
            db,
            chapter_id=chapter.id,
            book_id=book.id,
            user_id=book.user_id,
            chapter_number=number,
            chapters_total=len(chapters_for_analysis),
        )
        analysis_tasks.append(
            {
                "chapter_id": str(chapter.id),
                "chapter_number": number,
                "task_id": str(execution.id),
            }
        )

    await invalidate_advisor_caches_for_book(db, book_id=book.id)

    return ManuscriptImportResult(
        status="imported",
        book_id=str(book.id),
        imported_chapters=sorted(set(imported_numbers)),
        chapters_created=len(imported_numbers),
        analysis_dispatched=len(analysis_tasks),
        analysis_tasks=analysis_tasks,
        chapter_content_versions=imported_content_versions,
        total_chapters=book.total_chapters or total_chapters,
        mode=book.mode or "author",
        source_kind=book.source_kind or "chapter_wise",
        chapter_reports=chapter_reports,
    )
