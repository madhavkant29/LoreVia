import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_manuscript_import_rate_limit, rate_limit_upload
from app.core.config import settings
from app.core.database import get_db
from app.schemas.books import (
    EmptyProjectBody,
    EmptyProjectOut,
    ManuscriptImportJobOut,
    ManuscriptImportResult,
    ManuscriptReprocessBody,
    ManuscriptReprocessOut,
    ReadabilityMetricsOut,
    ReadabilityRequestBody,
)
from app.services.book_service import create_empty_editor_project_with_series
from app.services.book_upload_service import create_uploaded_book_from_raw
from app.services.manuscript_import_job_service import (
    cancel_manuscript_import_job,
    get_manuscript_import_job,
    manuscript_import_job_out,
    retry_manuscript_import_job,
)
from app.services.manuscript_import_request_service import execute_manuscript_import_request
from app.services.manuscript_reprocess_service import (
    start_manual_chapter_reprocess,
    start_manual_manuscript_reprocess,
)
from app.services.processing_allowance_service import (
    ensure_active_word_capacity,
    ensure_project_writable,
    ensure_source_storage_capacity,
    summarize_processing_allowances,
)
from app.services.upload_preview_service import load_or_build_upload_preview
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    assert_editor_project_not_rebuilding,
)
from app.utils.books.continuity import as_bool
from app.utils.books.normalization import (
    normalize_book_work_type,
    resolve_upload_format_and_work_type,
)
from app.utils.books.notes import (
    get_owned_book,
    resolve_owned_series_ids,
)
from app.utils.books.story_health import estimate_readability
from app.utils.upload_security_utils import validate_document_upload_bytes

from .core import (
    _clean_optional_text,
    _clean_text,
    log,
)
from .lifecycle import _read_upload_bounded, _validate_cover_magic

router = APIRouter()


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

    raw = await _read_upload_bounded(file, settings.BOOK_UPLOAD_MAX_BYTES, "Book file")
    if not raw:
        raise HTTPException(400, "Uploaded file is empty")
    validate_document_upload_bytes(file.filename, raw, fmt)
    preview = await load_or_build_upload_preview(
        user_id=current_user.id,
        raw=raw,
        format_name=fmt,
        work_type=resolved_work_type,
    )
    total_words = int(preview.get("total_words") or 0)
    await ensure_source_storage_capacity(db, current_user, len(raw))
    await ensure_active_word_capacity(db, current_user, total_words)
    cover_raw = None
    cover_suffix = None
    cover_content_type = None
    if not as_bool(auto_extract_cover) and cover_file is not None and cover_file.filename:
        cover_raw = await _read_upload_bounded(
            cover_file, settings.COVER_UPLOAD_MAX_BYTES, "Cover image"
        )
        if cover_raw:
            cover_suffix, cover_content_type = _validate_cover_magic(cover_raw)

    return await create_uploaded_book_from_raw(
        db,
        current_user=current_user,
        filename=file.filename,
        raw=raw,
        title=title,
        genre=genre,
        author=author,
        resolved_work_type=resolved_work_type,
        fmt=fmt,
        selected_series=selected_series,
        visibility=visibility,
        description=description,
        mode=mode,
        cover_raw=cover_raw,
        cover_suffix=cover_suffix,
        cover_content_type=cover_content_type,
        preserve_chapter_numbers=as_bool(preserve_chapter_numbers),
        preserve_source_chapters=as_bool(preserve_source_chapters),
        force_single_manuscript=as_bool(force_single_manuscript),
    )


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

    preview = await load_or_build_upload_preview(
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

    book = await create_empty_editor_project_with_series(
        db,
        current_user.id,
        title=title,
        genre=genre,
        author=author,
        work_type=work_type,
        selected_series=selected_series,
    )

    return EmptyProjectOut(
        book_id=str(book.id),
        status=book.status,
        mode=book.mode,
        is_editor_project=book.is_editor_project,
    )


@router.post(
    "/{book_id}/manuscript/import",
    response_model=ManuscriptImportResult | ManuscriptImportJobOut,
)
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
    response: Response = None,
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    ensure_project_writable(book)
    assert_editor_project_not_rebuilding(book)
    manuscript_files = [upload for upload in (files or []) if upload.filename]
    if manuscript_files:
        await enforce_manuscript_import_rate_limit(db, current_user.id)
    result, accepted = await execute_manuscript_import_request(
        db,
        book=book,
        current_user=current_user,
        files=manuscript_files,
        text=text,
        html=html,
        title=title,
        work_type=work_type,
        chapter_number=chapter_number,
        replace_existing=replace_existing,
        expected_content_version=expected_content_version,
        chunk_long_documents=chunk_long_documents,
        split_into_chapters=split_into_chapters,
    )
    if accepted and response is not None:
        response.status_code = 202
    return result


@router.get(
    "/{book_id}/manuscript/import/{job_id}",
    response_model=ManuscriptImportJobOut,
)
async def manuscript_import_job_status(
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_owned_book(db, book_id, current_user.id)
    job = await get_manuscript_import_job(
        db,
        job_id=job_id,
        book_id=book_id,
        user_id=current_user.id,
    )
    return manuscript_import_job_out(job)


@router.post(
    "/{book_id}/manuscript/import/{job_id}/cancel",
    response_model=ManuscriptImportJobOut,
)
async def cancel_queued_manuscript_import(
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_owned_book(db, book_id, current_user.id)
    job = await get_manuscript_import_job(
        db,
        job_id=job_id,
        book_id=book_id,
        user_id=current_user.id,
    )
    return await cancel_manuscript_import_job(db, job=job)


@router.post(
    "/{book_id}/manuscript/import/{job_id}/retry",
    response_model=ManuscriptImportJobOut,
)
async def retry_queued_manuscript_import(
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_owned_book(db, book_id, current_user.id)
    job = await get_manuscript_import_job(
        db,
        job_id=job_id,
        book_id=book_id,
        user_id=current_user.id,
    )
    return await retry_manuscript_import_job(db, job=job)


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
    return await start_manual_manuscript_reprocess(
        db=db,
        current_user=current_user,
        book_id=book_id,
        body=body,
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
    return await start_manual_chapter_reprocess(
        db=db,
        current_user=current_user,
        book_id=book_id,
        chapter_number=chapter_number,
    )
