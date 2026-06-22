import asyncio
import hashlib
import logging
import sys
import uuid
from typing import Any, cast

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_manuscript_import_rate_limit, rate_limit_upload
from app.core import storage
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import (
    cache_get,
    cache_set,
    mark_book_cache_dirty,
    mark_user_dashboard_cache_dirty,
)
from app.models.book import Book, Chapter, ChapterMedia, Series, SeriesBook
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
from app.services.book_service import create_editor_project
from app.services.processing_allowance_service import (
    consume_processing_reservation,
    ensure_active_word_capacity,
    ensure_project_writable,
    ensure_source_storage_capacity,
    release_processing_reservation,
    reserve_processing_words,
    summarize_processing_allowances,
)
from app.services.task_execution_service import (
    dispatch_pending_extraction_tasks,
    enqueue_analysis_execution,
    ensure_task_execution,
    get_or_create_processing_run,
)
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.billing_utils import require_author_access
from app.utils.books.chapter_titles import normalize_chapter_title
from app.utils.books.chapter_versions import snapshot_chapter_version
from app.utils.books.collaboration_access import (
    assert_editor_project_not_rebuilding,
)
from app.utils.books.continuity import as_bool
from app.utils.books.imports import (
    next_chapter_number,
    normalize_imported_chapters,
    parse_book_upload_for_ingestion,
    parse_screenplay_upload,
)
from app.utils.books.manuscript import (
    chapter_media_storage_payload,
    clean_manuscript_html,
    deserialize_manuscript_content,
    persist_editor_chapter_content,
)
from app.utils.books.normalization import (
    SCENE_BREAK_LINE_RE,
    normalize_book_work_type,
    resolve_upload_format_and_work_type,
    story_unit_name,
)
from app.utils.books.notes import (
    get_owned_book,
    resolve_owned_series_ids,
)
from app.utils.books.scene_metadata import (
    extract_novel_scene_candidates,
    refresh_screenplay_scene_rows,
)
from app.utils.books.scene_ordering import replace_chapter_novel_scenes
from app.utils.books.scene_sync import sync_chapter_content_from_novel_scenes
from app.utils.books.story_health import estimate_readability
from app.utils.books.writer_workspace import (
    _append_recent_revision_edit,
    touch_public_book_updated_at,
)
from app.utils.ingestion_utils import build_analysis_chapter_state, load_processing_chapter_payload
from app.utils.llm_usage_utils import (
    assert_manual_reprocess_token_capacity,
    estimate_manual_reprocess_tokens,
)
from app.utils.notification_utils import build_upload_processing_notification
from app.utils.upload_security_utils import validate_document_upload_bytes
from app.utils.user_utils import add_daily_word_progress, build_writing_activity_entry
from app.workers.consumers.extraction_consumer import _process_chapter

from .core import (
    _clean_optional_text,
    _clean_text,
    log,
)
from .lifecycle import _read_upload_bounded, _validate_cover_magic

router = APIRouter()
UPLOAD_PREVIEW_CACHE_TTL_SECONDS = 15 * 60


def _upload_preview_cache_key(user_id: uuid.UUID, raw: bytes) -> str:
    return f"upload-preview:{user_id}:{hashlib.sha256(raw).hexdigest()}"


async def _load_or_build_upload_preview(
    *,
    user_id: uuid.UUID,
    raw: bytes,
    format_name: str,
    work_type: str,
) -> dict[str, Any]:
    key = _upload_preview_cache_key(user_id, raw)
    cached = await cache_get(key)
    if isinstance(cached, dict):
        return cached
    from app.utils.books.imports import build_import_preview

    preview = await asyncio.to_thread(
        lambda: build_import_preview(
            format_name=format_name, work_type=work_type, raw=raw, language=None
        )
    )
    await cache_set(key, preview, UPLOAD_PREVIEW_CACHE_TTL_SECONDS)
    return preview


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
    require_author_access(current_user)
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
    if not title.strip():
        raise HTTPException(400, "Title is required")

    fmt, resolved_work_type = resolve_upload_format_and_work_type(file.filename, work_type)

    selected_series = await resolve_owned_series_ids(db, current_user.id, series_ids)

    is_public = False
    raw = await _read_upload_bounded(file, settings.BOOK_UPLOAD_MAX_BYTES, "Book file")
    if not raw:
        raise HTTPException(400, "Uploaded file is empty")
    validate_document_upload_bytes(file.filename, raw, fmt)
    preview = await _load_or_build_upload_preview(
        user_id=current_user.id,
        raw=raw,
        format_name=fmt,
        work_type=resolved_work_type,
    )
    total_words = int(preview.get("total_words") or 0)
    await ensure_source_storage_capacity(db, current_user, len(raw))
    await ensure_active_word_capacity(db, current_user, total_words)
    book_id = uuid.uuid4()
    cover_raw = None
    if not as_bool(auto_extract_cover) and cover_file is not None and cover_file.filename:
        cover_raw = await _read_upload_bounded(
            cover_file, settings.COVER_UPLOAD_MAX_BYTES, "Cover image"
        )
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
        source_size_bytes=len(raw),
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
    processing_run = await get_or_create_processing_run(
        db, user_id=current_user.id, book_id=book.id, chapters_total=0
    )
    await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=processing_run,
        arguments={"book_id": str(book.id), "processing_run_id": str(processing_run.id)},
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

    notification = build_upload_processing_notification(book, mode, len(raw))
    db.add(notification)
    await db.commit()

    await dispatch_pending_extraction_tasks(db)
    return {
        "book_id": str(book.id),
        "status": "processing",
        "copyright_warning": False,
        "visibility": visibility,
        "mode": mode,
    }


@router.post("/upload/preview")
async def preview_upload_endpoint(
    file: UploadFile = File(...),
    work_type: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    __=Depends(rate_limit_upload),
):
    """Parse a manuscript file and return a structure preview without creating any DB records."""
    require_author_access(current_user)
    if not file.filename:
        raise HTTPException(400, "No file")

    raw = await _read_upload_bounded(
        file, settings.MANUSCRIPT_IMPORT_MAX_BYTES, "Manuscript preview"
    )
    fmt, resolved_work_type = resolve_upload_format_and_work_type(
        file.filename,
        normalize_book_work_type(work_type, default="novel"),
    )
    validate_document_upload_bytes(file.filename, raw, fmt)
    log.info(
        "preview_request",
        extra={"format": fmt, "work_type": resolved_work_type, "user_id": str(current_user.id)},
    )

    preview = await _load_or_build_upload_preview(
        user_id=current_user.id,
        raw=raw,
        format_name=fmt,
        work_type=resolved_work_type,
    )
    allowance = await summarize_processing_allowances(db, current_user)
    total_words = int(preview.get("total_words") or 0)
    preview.update(
        {
            "source_size_bytes": len(raw),
            "projected_active_words": allowance.active_analyzed_words + total_words,
            "active_word_limit": allowance.active_word_limit,
            "projected_monthly_processed_words": allowance.monthly_processed_words + total_words,
            "monthly_processed_word_limit": allowance.monthly_processed_word_limit,
            "projected_source_storage_bytes": allowance.source_storage_bytes + len(raw),
            "source_storage_limit_bytes": allowance.source_storage_limit_bytes,
            "allowance_allowed": (
                not allowance.allowances_enforced
                or (
                    total_words <= allowance.active_words_remaining
                    and len(raw) <= allowance.source_storage_remaining_bytes
                )
            ),
        }
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
    ensure_project_writable(book)
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
    from app.services.editor_project_service import (
        auto_reprocess_enabled,
        update_reprocess_metadata,
    )

    should_auto_reprocess = auto_reprocess_enabled(book)

    cleaned_html = clean_manuscript_html(html) if html else None

    total_file_size = 0

    if text and text.strip():
        if resolved_book_work_type == "screenplay":
            screenplay_payload = await parse_screenplay_upload(
                "inline.fountain", text.encode("utf-8")
            )
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
                    [
                        {
                            "title": normalized_title
                            or f"{story_unit_name(book)} {chapter_number or next_number}",
                            "text": text,
                            "html": cleaned_html,
                            "number": chapter_number or next_number,
                        }
                    ],
                    chapter_number=chapter_number,
                    start_number=chapter_number or next_number,
                    replace_existing=replace_flag,
                    chunk_long_documents=chunk_flag,
                    preserve_exact_structure=preserve_exact_structure,
                )
            )

    manuscript_files = [upload for upload in (files or []) if upload.filename]
    if len(manuscript_files) > settings.MANUSCRIPT_IMPORT_MAX_FILES:
        raise HTTPException(
            413,
            f"Manuscript import accepts at most {settings.MANUSCRIPT_IMPORT_MAX_FILES} files at once.",
        )

    if manuscript_files:
        await enforce_manuscript_import_rate_limit(db, current_user.id)

    for upload in manuscript_files:
        if not upload.filename:
            continue
        raw = await _read_upload_bounded(
            upload, settings.MANUSCRIPT_IMPORT_MAX_BYTES, "Manuscript file"
        )
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
        screenplay_payload = (
            parsed_payload.get("screenplay_payload") if upload_work_type == "screenplay" else None
        )
        parsed = list(cast(list[dict[str, object]], parsed_payload["chapters"]))
        if upload_work_type != "screenplay" and not split_flag:
            merged_text = "\n\n".join(
                str(chapter.get("text") or "").strip() for chapter in parsed if chapter.get("text")
            )
            merged_html_parts = [
                str(chapter.get("html") or "").strip() for chapter in parsed if chapter.get("html")
            ]
            merged_images = [
                image for chapter in parsed for image in list(chapter.get("images") or [])
            ]
            parsed = [
                {
                    "title": normalized_title
                    or (
                        upload.filename.rsplit(".", 1)[0]
                        if "." in upload.filename
                        else upload.filename
                    ),
                    "text": merged_text,
                    "html": clean_manuscript_html(
                        "\n".join(part for part in merged_html_parts if part)
                    )
                    if merged_html_parts
                    else None,
                    "images": merged_images,
                    "number": 1,
                }
            ]
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

    imported_word_counts = {
        int(cast(Any, job["number"])): len(str(job.get("text") or "").split())
        for job in import_jobs
    }
    existing_word_counts: dict[int, int] = {}
    if replace_flag:
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

    imported_numbers: list[int] = []
    for job in import_jobs:
        job_number = int(cast(Any, job["number"]))
        next_text = str(job.get("text") or "")
        next_word_count = len(next_text.split()) if next_text.strip() else 0
        previous_word_count = 0
        previous_text = ""
        source_version_id: str | None = None
        existing_media_payloads: list[dict[str, Any]] = []
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
                images=[*list(job.get("images") or []), *existing_media_payloads],
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
                    "images": [*list(job.get("images") or []), *existing_media_payloads],
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
        except Exception:
            log.warning(
                "manuscript_import_cover_extraction_failed book_id=%s", book.id, exc_info=True
            )
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
    except Exception as exc:
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
        except Exception:
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


@router.post(
    "/{book_id}/manuscript/chapters/{chapter_number}/reprocess",
    response_model=ManuscriptReprocessOut,
)
async def reprocess_manuscript_chapter(
    book_id: uuid.UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
