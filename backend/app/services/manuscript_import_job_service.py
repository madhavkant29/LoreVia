from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from typing import Any, cast

from fastapi import HTTPException, UploadFile
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.models.book import Book
from app.models.operations import ManuscriptImportJob
from app.models.user import User
from app.schemas.books import ManuscriptImportJobOut, ManuscriptImportResult
from app.services.book_freeze_service import load_persisted_freeze_cutoff
from app.services.manuscript_import_service import persist_manuscript_import
from app.services.processing_allowance_service import ensure_source_storage_capacity
from app.utils.books.chapter_titles import normalize_chapter_title
from app.utils.books.continuity import as_bool
from app.utils.books.imports import (
    next_chapter_number,
    normalize_imported_chapters,
    parse_book_upload_for_ingestion,
    parse_screenplay_upload,
)
from app.utils.books.manuscript import clean_manuscript_html
from app.utils.books.normalization import (
    normalize_book_work_type,
    resolve_upload_format_and_work_type,
    story_unit_name,
)
from app.utils.storage_utils import (
    STORAGE_IO_EXCEPTIONS,
    delete_storage_keys_best_effort,
)
from app.utils.upload_security_utils import validate_document_upload_bytes

log = logging.getLogger("lorevia.manuscript_import_jobs")

TERMINAL_IMPORT_JOB_STATUSES = {"completed", "failed", "cancelled"}
MANUSCRIPT_IMPORT_STAGE_EXCEPTIONS = (HTTPException, *STORAGE_IO_EXCEPTIONS)


def should_queue_manuscript_import(files: list[UploadFile]) -> bool:
    if len(files) > 1:
        return True
    if not files:
        return False
    size = getattr(files[0], "size", None)
    return size is not None and int(size) >= settings.MANUSCRIPT_IMPORT_ASYNC_THRESHOLD_BYTES


def manuscript_import_job_out(job: ManuscriptImportJob) -> ManuscriptImportJobOut:
    result = (
        ManuscriptImportResult.model_validate(job.result_json)
        if isinstance(job.result_json, dict)
        else None
    )
    return ManuscriptImportJobOut(
        id=job.id,
        book_id=job.book_id,
        status=cast(Any, job.status),
        progress_completed=int(job.progress_completed or 0),
        progress_total=int(job.progress_total or 0),
        cancel_requested=bool(job.cancel_requested),
        result=result,
        error=job.error_detail,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _read_manuscript_upload(upload: UploadFile) -> bytes:
    raw = await upload.read(settings.MANUSCRIPT_IMPORT_MAX_BYTES + 1)
    if len(raw) > settings.MANUSCRIPT_IMPORT_MAX_BYTES:
        raise HTTPException(
            413,
            f"Manuscript file exceeds the {settings.MANUSCRIPT_IMPORT_MAX_BYTES // (1024 * 1024)} MB limit.",
        )
    return raw


def _safe_source_filename(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return cleaned[:180] or "manuscript.bin"


async def create_manuscript_import_job(
    db: AsyncSession,
    *,
    book: Book,
    current_user: User,
    files: list[UploadFile],
    text: str | None,
    html: str | None,
    title: str | None,
    work_type: str | None,
    chapter_number: int | None,
    replace_existing: str,
    expected_content_version: int | None,
    chunk_long_documents: str,
    split_into_chapters: str,
) -> ManuscriptImportJobOut:
    if not files:
        raise HTTPException(400, "Provide one or more manuscript files")
    if len(files) > settings.MANUSCRIPT_IMPORT_MAX_FILES:
        raise HTTPException(
            413,
            f"Manuscript import accepts at most {settings.MANUSCRIPT_IMPORT_MAX_FILES} files at once.",
        )
    normalized_title = normalize_chapter_title(title) if title is not None else None

    job = ManuscriptImportJob(
        id=uuid.uuid4(),
        user_id=current_user.id,
        book_id=book.id,
        status="queued",
        request_json={
            "text": text,
            "html": clean_manuscript_html(html) if html else None,
            "title": normalized_title,
            "work_type": work_type,
            "chapter_number": chapter_number,
            "replace_existing": as_bool(replace_existing),
            "expected_content_version": expected_content_version,
            "chunk_long_documents": as_bool(chunk_long_documents),
            "split_into_chapters": as_bool(split_into_chapters),
        },
        source_files_json=[],
        # Parsing each staged source and publishing the resulting chapters are
        # separate progress steps. This avoids reporting 100% while the final
        # database/storage publication is still running.
        progress_total=len(files) + 1,
    )
    uploaded_keys: list[str] = []
    total_bytes = 0
    sources: list[dict[str, Any]] = []
    try:
        for upload in files:
            filename = str(upload.filename or "").strip()
            if not filename:
                continue
            raw = await _read_manuscript_upload(upload)
            if not raw:
                continue
            total_bytes += len(raw)
            if total_bytes > settings.MANUSCRIPT_IMPORT_MAX_TOTAL_BYTES:
                raise HTTPException(
                    413,
                    "Manuscript import exceeds the maximum aggregate upload size.",
                )
            format_name, upload_work_type = resolve_upload_format_and_work_type(
                filename,
                work_type if work_type is not None else book.work_type,
            )
            validate_document_upload_bytes(filename, raw, format_name)
            safe_filename = _safe_source_filename(filename)
            source_key = (
                f"manuscript-imports/{current_user.id}/{book.id}/{job.id}/"
                f"{uuid.uuid4().hex}-{safe_filename}"
            )
            stored_key = await asyncio.to_thread(
                storage.upload_binary,
                source_key,
                raw,
                getattr(upload, "content_type", None),
            )
            uploaded_keys.append(stored_key)
            sources.append(
                {
                    "filename": filename,
                    "storage_key": stored_key,
                    "format": format_name,
                    "work_type": upload_work_type,
                    "size": len(raw),
                }
            )
    except MANUSCRIPT_IMPORT_STAGE_EXCEPTIONS:
        await delete_storage_keys_best_effort(uploaded_keys, context="manuscript_import_stage")
        raise

    if not sources:
        raise HTTPException(400, "No importable manuscript content was found")
    try:
        await ensure_source_storage_capacity(db, current_user, total_bytes)
    except Exception:
        await delete_storage_keys_best_effort(uploaded_keys, context="manuscript_import_stage")
        raise
    job.source_files_json = sources
    job.progress_total = len(sources) + 1
    db.add(job)
    try:
        await db.commit()
        await db.refresh(job)
    except Exception:
        await db.rollback()
        await delete_storage_keys_best_effort(uploaded_keys, context="manuscript_import_stage")
        raise

    await dispatch_manuscript_import_job(db, job)
    await db.refresh(job)
    return manuscript_import_job_out(job)


async def dispatch_manuscript_import_job(
    db: AsyncSession,
    job: ManuscriptImportJob,
) -> bool:
    if job.status != "queued" or job.celery_task_id:
        return False
    from app.workers.tasks.extraction_tasks import process_manuscript_import_job_task

    task_id = str(uuid.uuid4())
    try:
        process_manuscript_import_job_task.apply_async(
            kwargs={"job_id": str(job.id)},
            task_id=task_id,
            queue="extraction",
        )
    except Exception:
        log.exception("manuscript_import_job_dispatch_failed", extra={"job_id": str(job.id)})
        return False
    job.celery_task_id = task_id
    await db.commit()
    return True


async def dispatch_pending_manuscript_import_jobs(
    db: AsyncSession,
    *,
    limit: int = 25,
) -> int:
    now = datetime.now(UTC)
    queued_dispatch_cutoff = now - timedelta(minutes=10)
    running_recovery_cutoff = now - timedelta(hours=2)
    legacy_cutoff = await load_persisted_freeze_cutoff(db)
    job_statement = (
        select(ManuscriptImportJob)
        .where(
            or_(
                and_(
                    ManuscriptImportJob.status == "queued",
                    or_(
                        ManuscriptImportJob.celery_task_id.is_(None),
                        ManuscriptImportJob.updated_at < queued_dispatch_cutoff,
                    ),
                ),
                and_(
                    ManuscriptImportJob.status == "running",
                    ManuscriptImportJob.updated_at < running_recovery_cutoff,
                ),
                and_(
                    ManuscriptImportJob.status == "cancel_requested",
                    ManuscriptImportJob.updated_at < running_recovery_cutoff,
                ),
            )
        )
        .order_by(ManuscriptImportJob.created_at.asc())
        .limit(max(1, min(limit, 100)))
        .with_for_update(skip_locked=True)
    )
    if legacy_cutoff is not None:
        # Pre-cutoff imports are held for the one-time freeze; dispatch would
        # parse files and can trigger paid analysis.
        job_statement = job_statement.where(ManuscriptImportJob.created_at >= legacy_cutoff)
    jobs = list((await db.execute(job_statement)).scalars().all())
    dispatched = 0
    for job in jobs:
        if job.status == "cancel_requested":
            job.status = "cancelled"
            job.completed_at = now
            await db.commit()
            continue
        job.status = "queued"
        job.celery_task_id = None
        job.started_at = None
        await db.commit()
        if await dispatch_manuscript_import_job(db, job):
            dispatched += 1
    return dispatched


async def get_manuscript_import_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ManuscriptImportJob:
    job = (
        await db.execute(
            select(ManuscriptImportJob).where(
                ManuscriptImportJob.id == job_id,
                ManuscriptImportJob.book_id == book_id,
                ManuscriptImportJob.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Manuscript import job not found")
    return job


async def cancel_manuscript_import_job(
    db: AsyncSession,
    *,
    job: ManuscriptImportJob,
) -> ManuscriptImportJobOut:
    if job.status in TERMINAL_IMPORT_JOB_STATUSES:
        return manuscript_import_job_out(job)
    job.cancel_requested = True
    job.status = "cancelled" if job.status == "queued" else "cancel_requested"
    if job.status == "cancelled":
        job.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return manuscript_import_job_out(job)


async def retry_manuscript_import_job(
    db: AsyncSession,
    *,
    job: ManuscriptImportJob,
) -> ManuscriptImportJobOut:
    if job.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "Only failed or cancelled imports can be retried")
    if bool((job.request_json or {}).get("retry_blocked")):
        raise HTTPException(
            409,
            "This import failed validation or a version check and requires a new upload.",
        )
    if not job.source_files_json:
        raise HTTPException(409, "The staged manuscript files are no longer available")
    job.status = "queued"
    job.cancel_requested = False
    job.celery_task_id = None
    job.error_detail = None
    job.result_json = None
    job.progress_completed = 0
    job.started_at = None
    job.completed_at = None
    await db.commit()
    await dispatch_manuscript_import_job(db, job)
    await db.refresh(job)
    return manuscript_import_job_out(job)


async def _cancel_if_requested(db: AsyncSession, job: ManuscriptImportJob) -> bool:
    await db.refresh(job)
    if not job.cancel_requested:
        return False
    job.status = "cancelled"
    job.completed_at = datetime.now(UTC)
    await db.commit()
    return True


async def process_manuscript_import_job(db: AsyncSession, job_id: uuid.UUID) -> dict[str, Any]:
    job = (
        await db.execute(
            select(ManuscriptImportJob).where(ManuscriptImportJob.id == job_id).with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        return {"status": "missing", "job_id": str(job_id)}
    if job.status == "completed":
        return {"status": "completed", "job_id": str(job_id)}
    if job.cancel_requested or job.status in {"cancel_requested", "cancelled"}:
        job.status = "cancelled"
        job.completed_at = datetime.now(UTC)
        await db.commit()
        return {"status": "cancelled", "job_id": str(job_id)}
    if job.status != "queued":
        return {"status": job.status, "job_id": str(job_id)}

    legacy_cutoff = await load_persisted_freeze_cutoff(db)
    if legacy_cutoff is not None and job.created_at is not None and job.created_at < legacy_cutoff:
        # Deployment transition gate: a message delivered before the cutoff was
        # recorded must not parse files or queue paid analysis. The one-time
        # freeze cancels this job explicitly; leave it untouched here.
        log.warning("manuscript_import_job_held_by_legacy_cutoff job_id=%s", job_id)
        return {"status": "held_legacy_cutoff", "job_id": str(job_id)}

    job.status = "running"
    job.started_at = job.started_at or datetime.now(UTC)
    job.error_detail = None
    await db.commit()

    book = await db.get(Book, job.book_id)
    user = await db.get(User, job.user_id)
    if book is None or user is None:
        job.status = "failed"
        job.error_detail = "The book or user account is no longer available."
        job.completed_at = datetime.now(UTC)
        await db.commit()
        return {"status": "failed", "job_id": str(job_id)}

    request = dict(job.request_json or {})
    replace_existing = bool(request.get("replace_existing"))
    chapter_number = cast(int | None, request.get("chapter_number"))
    work_type = cast(str | None, request.get("work_type"))
    normalized_title = (
        normalize_chapter_title(str(request["title"])) if request.get("title") is not None else None
    )
    next_number = await next_chapter_number(db, book.id)
    preserve_exact_structure = bool(book.preserve_chapter_numbers or book.preserve_source_chapters)
    resolved_book_work_type = normalize_book_work_type(
        work_type,
        default=book.work_type or "novel",
    )
    import_jobs: list[dict[str, object]] = []
    screenplay_batches: list[dict[str, object]] = []
    first_pdf_raw_for_cover: bytes | None = None
    resolved_import_format: str | None = None
    total_file_size = 0

    inline_text = str(request.get("text") or "").strip()
    if inline_text:
        if resolved_book_work_type == "screenplay":
            screenplay_payload = await parse_screenplay_upload(
                "inline.fountain",
                inline_text.encode("utf-8"),
            )
            new_jobs = normalize_imported_chapters(
                screenplay_payload["chapters"],
                chapter_number=chapter_number,
                start_number=chapter_number or next_number,
                replace_existing=replace_existing,
                chunk_long_documents=False,
                preserve_exact_structure=False,
            )
            import_jobs.extend(new_jobs)
            screenplay_batches.append(
                {
                    "parsed_scenes": screenplay_payload["scenes"],
                    "starting_number": min(int(cast(Any, item["number"])) for item in new_jobs),
                    "scene_numbers": {int(cast(Any, item["number"])) for item in new_jobs},
                }
            )
        else:
            import_jobs.extend(
                normalize_imported_chapters(
                    [
                        {
                            "title": normalized_title
                            or f"{story_unit_name(book)} {chapter_number or next_number}",
                            "text": inline_text,
                            "html": request.get("html"),
                            "number": chapter_number or next_number,
                        }
                    ],
                    chapter_number=chapter_number,
                    start_number=chapter_number or next_number,
                    replace_existing=replace_existing,
                    chunk_long_documents=bool(request.get("chunk_long_documents")),
                    preserve_exact_structure=preserve_exact_structure,
                )
            )

    try:
        for index, source in enumerate(list(job.source_files_json or []), start=1):
            if await _cancel_if_requested(db, job):
                return {"status": "cancelled", "job_id": str(job_id)}
            raw = await asyncio.to_thread(storage.download_book, str(source["storage_key"]))
            total_file_size += len(raw)
            format_name = str(source["format"])
            upload_work_type = str(source["work_type"])
            filename = str(source["filename"])
            resolved_import_format = resolved_import_format or format_name
            if format_name == "pdf" and first_pdf_raw_for_cover is None:
                first_pdf_raw_for_cover = raw
            parsed_payload = await parse_book_upload_for_ingestion(
                format_name=format_name,
                work_type=upload_work_type,
                raw=raw,
                preserve_chapter_numbers=bool(book.preserve_chapter_numbers),
                preserve_source_chapters=bool(book.preserve_source_chapters),
                filename=filename,
            )
            screenplay_payload = (
                parsed_payload.get("screenplay_payload")
                if upload_work_type == "screenplay"
                else None
            )
            parsed = list(cast(list[dict[str, object]], parsed_payload["chapters"]))
            if upload_work_type != "screenplay" and not bool(
                request.get("split_into_chapters", True)
            ):
                merged_text = "\n\n".join(
                    str(chapter.get("text") or "").strip()
                    for chapter in parsed
                    if chapter.get("text")
                )
                merged_html_parts = [
                    str(chapter.get("html") or "").strip()
                    for chapter in parsed
                    if chapter.get("html")
                ]
                parsed = [
                    {
                        "title": normalized_title or PurePath(filename).stem,
                        "text": merged_text,
                        "html": (
                            clean_manuscript_html("\n".join(merged_html_parts))
                            if merged_html_parts
                            else None
                        ),
                        "images": [
                            image
                            for chapter in parsed
                            for image in list(chapter.get("images") or [])
                        ],
                        "number": 1,
                    }
                ]
            base_number = chapter_number if replace_existing and chapter_number else next_number
            new_jobs = normalize_imported_chapters(
                parsed,
                chapter_number=chapter_number,
                start_number=base_number,
                replace_existing=replace_existing and len(parsed) == 1,
                chunk_long_documents=(
                    False
                    if upload_work_type == "screenplay"
                    else bool(request.get("chunk_long_documents"))
                ),
                preserve_exact_structure=preserve_exact_structure,
            )
            import_jobs.extend(new_jobs)
            if upload_work_type == "screenplay" and screenplay_payload is not None:
                screenplay_batches.append(
                    {
                        "parsed_scenes": screenplay_payload["scenes"],
                        "starting_number": min(int(cast(Any, item["number"])) for item in new_jobs),
                        "scene_numbers": {int(cast(Any, item["number"])) for item in new_jobs},
                    }
                )
                resolved_book_work_type = "screenplay"
            next_number = max(
                next_number,
                max(
                    (int(cast(Any, item["number"])) for item in import_jobs),
                    default=next_number,
                )
                + 1,
            )
            job.progress_completed = index
            await db.commit()

        if not import_jobs:
            raise ValueError("No importable manuscript content was found")
        if await _cancel_if_requested(db, job):
            return {"status": "cancelled", "job_id": str(job_id)}

        assigned_numbers = [int(number) for number in list(request.get("assigned_numbers") or [])]
        retrying_persistence = bool(assigned_numbers)
        if assigned_numbers:
            if len(assigned_numbers) != len(import_jobs):
                raise ValueError("The staged import no longer matches its assigned chapters")
            number_map = {
                int(cast(Any, item["number"])): assigned_number
                for item, assigned_number in zip(import_jobs, assigned_numbers, strict=True)
            }
            for item, assigned_number in zip(import_jobs, assigned_numbers, strict=True):
                item["number"] = assigned_number
            for batch in screenplay_batches:
                batch["starting_number"] = number_map.get(
                    int(cast(Any, batch["starting_number"])),
                    int(cast(Any, batch["starting_number"])),
                )
                batch["scene_numbers"] = {
                    number_map.get(int(number), int(number))
                    for number in cast(set[int], batch["scene_numbers"])
                }
        else:
            assigned_numbers = [int(cast(Any, item["number"])) for item in import_jobs]
            request["assigned_numbers"] = assigned_numbers
            request["persistence_started"] = True
            job.request_json = request
            await db.commit()

        from app.services.editor_project_service import auto_reprocess_enabled

        result = await persist_manuscript_import(
            db,
            book=book,
            current_user=user,
            import_jobs=import_jobs,
            screenplay_batches=screenplay_batches,
            replace_existing=replace_existing or retrying_persistence,
            chapter_number=chapter_number,
            expected_content_version=(
                None
                if retrying_persistence
                else cast(int | None, request.get("expected_content_version"))
            ),
            should_auto_reprocess=auto_reprocess_enabled(book),
            resolved_book_work_type=resolved_book_work_type,
            resolved_import_format=resolved_import_format,
            first_pdf_raw_for_cover=first_pdf_raw_for_cover,
            total_file_size=total_file_size,
            files_were_uploaded=True,
        )
        job.status = "completed"
        job.result_json = result.model_dump(mode="json")
        job.error_detail = None
        job.progress_completed = job.progress_total
        job.completed_at = datetime.now(UTC)
        await db.commit()
        source_keys = [
            str(source.get("storage_key") or "")
            for source in list(job.source_files_json or [])
            if source.get("storage_key")
        ]
        deleted_keys = await delete_storage_keys_best_effort(
            source_keys,
            context="manuscript_import_complete",
        )
        if source_keys and set(deleted_keys) == set(source_keys):
            job.source_files_json = []
            await db.commit()
        return {"status": "completed", "job_id": str(job_id)}
    except Exception as exc:
        await db.rollback()
        job = await db.get(ManuscriptImportJob, job_id)
        if job is not None:
            job.status = "failed"
            job.error_detail = str(exc)[:2000] or exc.__class__.__name__
            job.completed_at = datetime.now(UTC)
            request_state = dict(job.request_json or {})
            request_state["retry_blocked"] = (
                isinstance(exc, HTTPException) and 400 <= int(exc.status_code) < 500
            )
            job.request_json = request_state
            await db.commit()
        log.exception("manuscript_import_job_failed", extra={"job_id": str(job_id)})
        try:
            import sentry_sdk

            sentry_sdk.set_tag("job_id", str(job_id))
            if job is not None:
                sentry_sdk.set_tag("book_id", str(job.book_id))
                sentry_sdk.set_tag("user_id", str(job.user_id))
            sentry_sdk.set_context(
                "manuscript_import_job",
                {
                    "job_id": str(job_id),
                    "file_count": len(job.source_files_json or []) if job is not None else 0,
                    "failure_category": (
                        "validation"
                        if isinstance(exc, HTTPException) and 400 <= int(exc.status_code) < 500
                        else "processing"
                    ),
                },
            )
            sentry_sdk.capture_exception(exc)
        except Exception:
            log.warning("import_job_sentry_report_failed job_id=%s", job_id, exc_info=True)
        return {"status": "failed", "job_id": str(job_id)}
