import asyncio
import logging
import sys
import uuid
from typing import Any, cast

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .core import _clean_optional_text, _clean_text, _read_upload_bounded, _validate_cover_magic, log
from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_manuscript_import_rate_limit, rate_limit_upload
from app.api.deps.subscription import check_upload_limit
from app.core import storage
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import mark_book_cache_dirty, mark_user_dashboard_cache_dirty
from app.models.book import Book, Chapter, Series, SeriesBook
from app.models.progress import ReadingProgress
from app.schemas.books import (
    ChapterConsistencyReport,
    EmptyProjectBody,
    EmptyProjectOut,
    ManuscriptImportResult,
    ManuscriptReprocessBody,
    ManuscriptReprocessOut,
    ReadabilityMetricsOut,
    ReadabilityRequestBody,
)
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.billing_utils import record_book_upload_charge, require_author_access
from app.utils.book_utils import (
    SCENE_BREAK_LINE_RE,
    _append_recent_revision_edit,
    as_bool,
    assert_editor_project_not_rebuilding,
    clean_manuscript_html,
    deserialize_manuscript_content,
    estimate_readability,
    extract_novel_scene_candidates,
    get_owned_book,
    next_chapter_number,
    normalize_book_work_type,
    normalize_chapter_title,
    normalize_imported_chapters,
    parse_book_upload_for_ingestion,
    parse_screenplay_upload,
    persist_editor_chapter_content,
    refresh_screenplay_scene_rows,
    replace_chapter_novel_scenes,
    resolve_owned_series_ids,
    resolve_upload_format_and_work_type,
    snapshot_chapter_version,
    story_unit_name,
    sync_chapter_content_from_novel_scenes,
    touch_public_book_updated_at,
)
from app.utils.ingestion_utils import build_analysis_chapter_state
from app.utils.ingestion_utils import load_processing_chapter_payload
from app.utils.llm_usage_utils import (
    assert_manual_reprocess_token_capacity,
    estimate_manual_reprocess_tokens,
)
from app.utils.notification_utils import build_upload_processing_notification
from app.utils.queue_utils import queue_for_user
from app.utils.upload_security_utils import validate_document_upload_bytes
from app.utils.user_utils import add_daily_word_progress, build_writing_activity_entry
from app.workers.consumers.extraction_consumer import _process_chapter
from app.workers.tasks.analysis_tasks import analyse_chapter_task
from app.workers.tasks.extraction_tasks import process_book_task, process_chapter_task
from app.services.book_service import create_editor_project

router = APIRouter()


def _sync_books_package_monkeypatches() -> None:
    """Keep split route-module internals compatible with package-level route tests."""
    package = sys.modules.get("app.api.v1.routes.books")
    if package is None:
        return
    for name in (
        "get_owned_book",
        "require_author_access",
        "next_chapter_number",
        "normalize_book_work_type",
        "clean_manuscript_html",
        "normalize_imported_chapters",
        "parse_book_upload_for_ingestion",
        "_process_chapter",
        "extract_novel_scene_candidates",
        "replace_chapter_novel_scenes",
        "deserialize_manuscript_content",
        "sync_chapter_content_from_novel_scenes",
        "add_daily_word_progress",
        "invalidate_advisor_caches_for_book",
    ):
        if hasattr(package, name):
            globals()[name] = getattr(package, name)


@router.post("/upload", status_code=202)
async def upload_book_endpoint(
    file: UploadFile = File(...),
    cover_file: UploadFile | None = File(None),
    title: str = Form(...),
    genre: str | None = Form(None),
    author: str | None = Form(None),
    work_type: str | None = Form(None),
    series_ids: list[str] = Form(default=[]),
    visibility: str = Form("private"),
    description: str | None = Form(None),
    mode: str = Form("reader"),
    auto_extract_cover: str = Form("true"),
    preserve_chapter_numbers: str = Form("false"),
    preserve_source_chapters: str = Form("false"),
    force_single_manuscript: str = Form("false"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    __=Depends(rate_limit_upload),
):
    title = _clean_text(title) if title else ""
    if author:
        author = _clean_text(author)
    if genre:
        genre = _clean_text(genre)
    if description:
        description = _clean_text(description)
    if not file.filename:
        raise HTTPException(400, "No file")
    if visibility not in {"private", "public"}:
        raise HTTPException(400, "Invalid visibility")
    if visibility == "public":
        raise HTTPException(
            400,
            "Main upload flow only supports private manuscripts. Use the explicit public-sharing route after upload.",
        )
    if mode not in {"reader", "author"}:
        raise HTTPException(400, "Invalid mode")
    if mode == "author":
        require_author_access(current_user)
    if not title.strip():
        raise HTTPException(400, "Title is required")

    fmt, resolved_work_type = resolve_upload_format_and_work_type(file.filename, work_type)

    selected_series = await resolve_owned_series_ids(db, current_user.id, series_ids)
    await check_upload_limit(db, current_user, requested_uploads=1)

    is_public = False
    raw = await _read_upload_bounded(file, settings.BOOK_UPLOAD_MAX_BYTES, "Book file")
    if not raw:
        raise HTTPException(400, "Uploaded file is empty")
    validate_document_upload_bytes(file.filename, raw, fmt)
    book_id = uuid.uuid4()
    cover_raw = None
    if not as_bool(auto_extract_cover) and cover_file is not None and cover_file.filename:
        cover_raw = await _read_upload_bounded(cover_file, settings.COVER_UPLOAD_MAX_BYTES, "Cover image")
        if cover_raw:
            _validate_cover_magic(cover_raw)
    s3_key = storage.upload_book_bytes(raw, str(current_user.id), file.filename)
    cover_s3_key = None
    if cover_raw:
        suffix, content_type = _validate_cover_magic(cover_raw)
        cover_s3_key = storage.upload_binary(
            f"covers/{current_user.id}/{uuid.uuid4()}.{suffix}",
            cover_raw,
            content_type,
        )
    book = Book(
        id=book_id,
        user_id=current_user.id,
        title=title,
        genre=genre,
        author=author,
        format=fmt,
        work_type=resolved_work_type,
        s3_key=s3_key,
        cover_s3_key=cover_s3_key,
        status="pending",
        is_public=is_public,
        public_description=description,
        mode=mode,
        source_kind="single_upload",
        preserve_chapter_numbers=as_bool(preserve_chapter_numbers),
        preserve_source_chapters=as_bool(preserve_source_chapters),
        force_single_manuscript=as_bool(force_single_manuscript),
    )
    db.add(book)
    await db.flush()
    for index, series in enumerate(selected_series):
        membership = SeriesBook(series_id=series.id, book_id=book.id)
        db.add(membership)
        if index == 0:
            book.primary_series_id = series.id
            book.series_name = series.name
            book.series_order = None

    await db.commit()
    await db.refresh(book)

    notification = build_upload_processing_notification(book, mode, len(raw))
    db.add(notification)
    await db.commit()

    process_book_task.apply_async(args=[str(book.id)], queue=queue_for_user(current_user, "extraction"))
    return {"book_id": str(book.id), "status": "processing",
            "copyright_warning": False, "visibility": visibility, "mode": mode}


@router.post("/upload/preview")
async def preview_upload_endpoint(
    file: UploadFile = File(...),
    work_type: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    __=Depends(rate_limit_upload),
):
    """Parse a manuscript file and return a structure preview without creating any DB records."""
    _ = current_user  # auth check
    if not file.filename:
        raise HTTPException(400, "No file")

    raw = await _read_upload_bounded(file, settings.MANUSCRIPT_UPLOAD_MAX_BYTES, "Manuscript preview")
    fmt, resolved_work_type = resolve_upload_format_and_work_type(
        file.filename,
        normalize_book_work_type(work_type, default="novel"),
    )
    validate_document_upload_bytes(file.filename, raw, fmt)
    log.info(
        "preview_request",
        extra={"format": fmt, "work_type": resolved_work_type, "user_id": str(current_user.id)},
    )

    from app.utils.book_utils import build_import_preview
    preview = await asyncio.to_thread(
        lambda: build_import_preview(
            format_name=fmt,
            work_type=resolved_work_type,
            raw=raw,
            language=None,
        )
    )
    return preview


@router.post("/empty-project", response_model=EmptyProjectOut)
async def create_empty_project(
    body: EmptyProjectBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_author_access(current_user)
    title = _clean_text(body.title)
    if not title:
        raise HTTPException(400, "Title is required")
    author = _clean_optional_text(body.author)
    genre = _clean_optional_text(body.genre)
    work_type = normalize_book_work_type(body.work_type, default="novel")

    await check_upload_limit(db, current_user, requested_uploads=1)

    series_ids = body.series_ids or []
    selected_series = await resolve_owned_series_ids(db, current_user.id, series_ids)

    book_id = uuid.uuid4()
    book = await create_editor_project(
        db,
        current_user.id,
        book_id=book_id,
        title=title,
        genre=genre,
        author=author,
        work_type=work_type,
    )

    for index, series in enumerate(selected_series):
        membership = SeriesBook(series_id=series.id, book_id=book.id)
        db.add(membership)
        if index == 0:
            book.primary_series_id = series.id
            book.series_name = series.name
            book.series_order = None

    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    await mark_user_dashboard_cache_dirty(current_user.id)

    return EmptyProjectOut(
        book_id=str(book.id),
        status=book.status,
        mode=book.mode,
        is_editor_project=book.is_editor_project,
    )


@router.post("/{book_id}/manuscript/import", response_model=ManuscriptImportResult)
async def import_manuscript_content(
    book_id: uuid.UUID,
    files: list[UploadFile] | None = File(None),
    text: str | None = Form(None),
    html: str | None = Form(None),
    title: str | None = Form(None),
    work_type: str | None = Form(None),
    chapter_number: int | None = Form(None),
    replace_existing: str = Form("false"),
    expected_content_version: int | None = Form(None),
    chunk_long_documents: str = Form("false"),
    split_into_chapters: str = Form("true"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _: Any = None,
):
    _sync_books_package_monkeypatches()
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    assert_editor_project_not_rebuilding(book)
    if not text and not files:
        raise HTTPException(400, "Provide text or one or more files")

    import_jobs: list[dict[str, object]] = []
    screenplay_batches: list[dict[str, object]] = []
    daily_words_added = 0
    imported_content_versions: dict[int, int] = {}
    normalized_title = normalize_chapter_title(title) if title is not None else None
    next_number = await next_chapter_number(db, book.id)
    replace_flag = as_bool(replace_existing)
    chunk_flag = as_bool(chunk_long_documents)
    split_flag = as_bool(split_into_chapters)
    preserve_exact_structure = bool(book.preserve_chapter_numbers or book.preserve_source_chapters)
    resolved_book_work_type = normalize_book_work_type(work_type, default=book.work_type or "novel")
    resolved_import_format: str | None = None
    first_pdf_raw_for_cover: bytes | None = None
    from app.services.editor_project_service import auto_reprocess_enabled, update_reprocess_metadata

    should_auto_reprocess = auto_reprocess_enabled(book)

    cleaned_html = clean_manuscript_html(html) if html else None

    total_file_size = 0

    if text and text.strip():
        if resolved_book_work_type == "screenplay":
            screenplay_payload = await parse_screenplay_upload("inline.fountain", text.encode("utf-8"))
            new_jobs = normalize_imported_chapters(
                screenplay_payload["chapters"],
                chapter_number=chapter_number,
                start_number=chapter_number or next_number,
                replace_existing=replace_flag,
                chunk_long_documents=False,
                preserve_exact_structure=False,
            )
            import_jobs.extend(new_jobs)
            screenplay_batches.append(
                {
                    "parsed_scenes": screenplay_payload["scenes"],
                    "starting_number": min(int(cast(Any, job["number"])) for job in new_jobs),
                    "scene_numbers": {int(cast(Any, job["number"])) for job in new_jobs},
                }
            )
        else:
            import_jobs.extend(
                normalize_imported_chapters(
                    [{
                        "title": normalized_title or f"{story_unit_name(book)} {chapter_number or next_number}",
                        "text": text,
                        "html": cleaned_html,
                        "number": chapter_number or next_number,
                    }],
                    chapter_number=chapter_number,
                    start_number=chapter_number or next_number,
                    replace_existing=replace_flag,
                    chunk_long_documents=chunk_flag,
                    preserve_exact_structure=preserve_exact_structure,
                )
            )

    manuscript_files = [upload for upload in (files or []) if upload.filename]
    if len(manuscript_files) > settings.MANUSCRIPT_IMPORT_MAX_FILES:
        raise HTTPException(413, f"Manuscript import accepts at most {settings.MANUSCRIPT_IMPORT_MAX_FILES} files at once.")

    if manuscript_files:
        await enforce_manuscript_import_rate_limit(db, current_user.id)

    for upload in manuscript_files:
        if not upload.filename:
            continue
        raw = await _read_upload_bounded(upload, settings.MANUSCRIPT_IMPORT_MAX_BYTES, "Manuscript file")
        if not raw:
            continue
        total_file_size += len(raw)
        if total_file_size > settings.MANUSCRIPT_IMPORT_MAX_TOTAL_BYTES:
            raise HTTPException(413, "Manuscript import exceeds the maximum aggregate upload size.")
        fmt, upload_work_type = resolve_upload_format_and_work_type(
            upload.filename,
            work_type if work_type is not None else book.work_type,
        )
        validate_document_upload_bytes(upload.filename, raw, fmt)
        resolved_import_format = resolved_import_format or fmt
        if fmt == "pdf" and first_pdf_raw_for_cover is None:
            first_pdf_raw_for_cover = raw
        parsed_payload = await parse_book_upload_for_ingestion(
            format_name=fmt,
            work_type=upload_work_type,
            raw=raw,
            preserve_chapter_numbers=bool(book.preserve_chapter_numbers),
            preserve_source_chapters=bool(book.preserve_source_chapters),
        )
        screenplay_payload = parsed_payload.get("screenplay_payload") if upload_work_type == "screenplay" else None
        parsed = list(cast(list[dict[str, object]], parsed_payload["chapters"]))
        if upload_work_type != "screenplay" and not split_flag:
            merged_text = "\n\n".join(str(chapter.get("text") or "").strip() for chapter in parsed if chapter.get("text"))
            merged_html_parts = [str(chapter.get("html") or "").strip() for chapter in parsed if chapter.get("html")]
            merged_images = [image for chapter in parsed for image in list(chapter.get("images") or [])]
            parsed = [{
                "title": normalized_title or (upload.filename.rsplit(".", 1)[0] if "." in upload.filename else upload.filename),
                "text": merged_text,
                "html": clean_manuscript_html("\n".join(part for part in merged_html_parts if part)) if merged_html_parts else None,
                "images": merged_images,
                "number": 1,
            }]
        base_number = chapter_number if replace_flag and chapter_number else next_number
        new_jobs = normalize_imported_chapters(
            parsed,
            chapter_number=chapter_number,
            start_number=base_number,
            replace_existing=replace_flag and len(parsed) == 1,
            chunk_long_documents=False if upload_work_type == "screenplay" else chunk_flag,
            preserve_exact_structure=preserve_exact_structure,
        )
        import_jobs.extend(new_jobs)
        if upload_work_type == "screenplay":
            screenplay_batches.append(
                {
                    "parsed_scenes": screenplay_payload["scenes"],
                    "starting_number": min(int(cast(Any, job["number"])) for job in new_jobs),
                    "scene_numbers": {int(cast(Any, job["number"])) for job in new_jobs},
                }
            )
            resolved_book_work_type = "screenplay"
        next_number = max(
            next_number,
            max((int(cast(Any, job["number"])) for job in import_jobs), default=next_number) + 1,
        )

    if not import_jobs:
        raise HTTPException(400, "No importable manuscript content was found")

    imported_numbers: list[int] = []
    for job in import_jobs:
        job_number = int(cast(Any, job["number"]))
        next_text = str(job.get("text") or "")
        next_word_count = len(next_text.split()) if next_text.strip() else 0
        previous_word_count = 0
        previous_text = ""
        source_version_id: str | None = None
        if replace_flag:
            existing = (
                await db.execute(
                    select(Chapter)
                    .where(Chapter.book_id == book.id, Chapter.number == job_number)
                    .with_for_update()
                )
            ).scalar()
            if existing is not None:
                current_content_version = int(existing.content_version or 1)
                if expected_content_version is not None and len(import_jobs) == 1 and job_number == (chapter_number or job_number):
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
                    existing_payload = deserialize_manuscript_content(await asyncio.to_thread(storage.download_book, existing.s3_key))
                    previous_text = str(existing_payload.get("text") or "")
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
                    "images": list(job.get("images") or []),
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

    total_chapters = await db.scalar(select(func.count()).select_from(Chapter).where(Chapter.book_id == book.id)) or 0
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
        except Exception:
            log.warning("manuscript_import_cover_extraction_failed book_id=%s", book.id, exc_info=True)
    book.source_kind = "chapter_wise" if len(import_jobs) == 1 and not files else "batch_upload"
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
                    ReadingProgress.user_id == current_user.id,
                    ReadingProgress.book_id == book.id
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

        auto_reprocess_dispatched, _auto_chapters_queued, _auto_total_words = await maybe_auto_reprocess_editor_project(db, book)
        if auto_reprocess_dispatched:
            await db.refresh(book)

    chapter_reports: list[ChapterConsistencyReport] = []
    chapters_for_analysis: list[tuple[int, str]] = []
    for number in ([] if getattr(book, "is_editor_project", False) else imported_numbers):
        chapter = (
            await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == number))
        ).scalar()
        if chapter is not None:
            chapter.analysis_state = build_analysis_chapter_state(
                chapter.analysis_state if isinstance(getattr(chapter, "analysis_state", None), dict) else None,
                status="queued",
                increment_attempt=True,
            )
            chapters_for_analysis.append((number, str(chapter.id)))

    if chapters_for_analysis:
        await db.commit()

    analysis_tasks: list[dict[str, str | int]] = []
    for number, chapter_id in chapters_for_analysis:
        task_result = analyse_chapter_task.apply_async(
            args=[chapter_id, str(book.id)],
            kwargs={"is_reprocessing": False},
            queue="analysis",
        )
        analysis_tasks.append(
            {
                "chapter_id": chapter_id,
                "chapter_number": number,
                "task_id": str(getattr(task_result, "id", "")),
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


@router.post("/{book_id}/manuscript/readability", response_model=ReadabilityMetricsOut)
async def manuscript_readability(
    book_id: uuid.UUID,
    body: ReadabilityRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    _ = book
    return ReadabilityMetricsOut(**estimate_readability(body.text))


@router.post("/{book_id}/manuscript/reprocess", response_model=ManuscriptReprocessOut)
async def reprocess_manuscript(
    book_id: uuid.UUID,
    body: ManuscriptReprocessBody = Body(default_factory=ManuscriptReprocessBody),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)

    if not body.confirm_upload_charge:
        raise HTTPException(400, "Confirm that reprocessing will consume 1 book upload before continuing.")

    from app.services.editor_project_service import (
        fail_rebuild_if_active,
        get_rebuild_run_id,
        prepare_rebuild,
        dispatch_rebuild,
    )

    if get_rebuild_run_id(book) is not None:
        raise HTTPException(409, "A rebuild is already in progress for this project")

    chapters = (
        await db.execute(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.word_count > 0)
        )
    ).scalars().all()

    if not chapters:
        raise HTTPException(400, "Save at least one chapter before reprocessing")

    await check_upload_limit(
        db,
        current_user,
        requested_uploads=1,
        context="Manual manuscript reprocessing consumes 1 additional book upload.",
    )

    rebuild_run_id = await prepare_rebuild(db, book, reason="manual_reprocess")
    chapters_queued, total_words = await dispatch_rebuild(db, book)
    try:
        await record_book_upload_charge(
            db,
            user_id=current_user.id,
            book_id=book.id,
            charge_kind="manual_reprocess",
            source_id=rebuild_run_id,
            quantity=1,
            metadata={
                "chapters_queued": chapters_queued,
                "total_words": total_words,
            },
        )
        await db.commit()
    except Exception as exc:
        log.exception(
            "manual_reprocess_charge_failed book_id=%s rebuild_run_id=%s",
            book.id,
            rebuild_run_id,
        )
        await db.rollback()
        try:
            await db.refresh(book)
            await fail_rebuild_if_active(
                db,
                book,
                expected_rebuild_run_id=rebuild_run_id,
                error="Unable to record the manual reprocess upload charge.",
            )
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception(
                "manual_reprocess_charge_cleanup_failed book_id=%s rebuild_run_id=%s",
                book.id,
                rebuild_run_id,
            )
        raise HTTPException(
            503,
            "Unable to record the reprocess upload charge. No rebuild was started.",
        ) from exc

    return ManuscriptReprocessOut(
        book_id=str(book.id),
        status="processing",
        chapters_queued=chapters_queued,
        total_words=total_words,
        upload_charge_consumed=True,
        charge_kind="manual_reprocess",
    )


@router.post("/{book_id}/manuscript/chapters/{chapter_number}/reprocess", response_model=ManuscriptReprocessOut)
async def reprocess_manuscript_chapter(
    book_id: uuid.UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)

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
    await db.commit()
    await db.refresh(book)
    await invalidate_advisor_caches_for_book(db, book_id=book.id)
    await mark_book_cache_dirty(str(book.id))

    process_chapter_task.apply_async(
        args=[str(book.id), chapter_number],
        kwargs={"manual_reprocess": True},
        queue=queue_for_user(current_user, "extraction"),
    )

    return ManuscriptReprocessOut(
        book_id=str(book.id),
        status="processing",
        chapters_queued=1,
        total_words=int(chapter.word_count or 0),
        upload_charge_consumed=False,
        charge_kind=None,
    )
