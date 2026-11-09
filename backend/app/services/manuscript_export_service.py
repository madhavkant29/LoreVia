"""Storage orchestration for manuscript exports."""

from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO, cast

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.models.book import Book, Chapter, VaultNoteSource
from app.models.operations import ManuscriptExportJob
from app.models.user import User
from app.schemas.books import (
    ManuscriptExportJobOut,
    ManuscriptExportPreparationOut,
    ManuscriptExportRequest,
)
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_can_export,
    get_book_with_collaboration_access,
)
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
    load_novel_cover_image,
    load_novel_export_chapters,
)
from app.utils.books.scene_metadata import strip_scene_metadata_from_manuscript_text
from app.utils.books.scene_records import list_novel_scenes
from app.utils.books.vault_storage import list_vault_notes
from app.utils.books.writer_workspace import build_writer_workspace_payload
from app.utils.export_utils import (
    export_filename_base,
    manuscript_docx,
    manuscript_epub_compiled,
    manuscript_pdf_compiled,
    normalize_export_font_family,
    novel_docx,
    novel_epub_compiled,
    novel_pdf_compiled,
    write_manuscript_vault_zip,
)
from app.utils.logging.errors import (
    public_error_message,
    public_stored_error_message,
    report_caught_failure,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS, bounded_storage_map

log = logging.getLogger("lorevia.manuscript_export_jobs")

MANUSCRIPT_PRESETS = {"standard_manuscript", "trade_paperback", "kdp_paperback"}
NOVEL_PRESETS = {"standard_novel", "trade_novel", "large_print", "ebook_optimized"}
TERMINAL_EXPORT_JOB_STATUSES = {"completed", "failed", "expired"}


@dataclass
class GeneratedExportArtifact:
    stream: BinaryIO
    filename: str
    media_type: str
    size_bytes: int


async def load_manuscript_export_chapters(
    chapter_rows: Iterable[Any],
    *,
    include_scene_metadata: bool,
) -> list[dict[str, Any]]:
    """Load export chapter bodies concurrently while preserving query order."""

    async def load_chapter(row: Any) -> dict[str, Any]:
        number, chapter_title, s3_key = row
        if not s3_key:
            raise HTTPException(409, "A chapter is missing its saved source. Contact support.")
        chapter_html = None
        try:
            raw = await asyncio.to_thread(storage.download_book, s3_key)
        except STORAGE_IO_EXCEPTIONS as exc:
            report_caught_failure("manuscript_export_chapter_storage_failed", exc)
            raise HTTPException(503, "A chapter could not be loaded. Retry the export.") from exc
        stored = deserialize_manuscript_content(raw)
        chapter_text = str(stored.get("text") or "")
        chapter_html = str(stored.get("html") or "") or None
        if not include_scene_metadata:
            chapter_text = strip_scene_metadata_from_manuscript_text(chapter_text)
            chapter_html = None
        return {
            "number": number,
            "title": chapter_title,
            "text": chapter_text,
            "html": chapter_html,
        }

    return await bounded_storage_map(chapter_rows, load_chapter)


def _validate_export_request(request: ManuscriptExportRequest) -> None:
    if request.export_kind == "manuscript":
        if request.preset not in MANUSCRIPT_PRESETS:
            raise HTTPException(422, "Invalid manuscript export preset")
        return
    if request.format == "vault":
        raise HTTPException(422, "Vault export is only available for manuscripts")
    if request.preset not in NOVEL_PRESETS:
        raise HTTPException(422, "Invalid novel export preset")


async def _accessible_chapter_stats(
    db: AsyncSession, *, book: Book, collaborator: Any
) -> tuple[int, int]:
    rows = (
        await db.execute(
            select(Chapter.number, Chapter.word_count).where(Chapter.book_id == book.id)
        )
    ).all()
    if collaborator is not None:
        rows = [row for row in rows if collaboration_allows_chapter(collaborator, int(row.number))]
    return len(rows), sum(max(int(row.word_count or 0), 0) for row in rows)


async def should_queue_manuscript_export(
    db: AsyncSession,
    *,
    book: Book,
    collaborator: Any,
    request: ManuscriptExportRequest,
) -> bool:
    """Return whether an export exceeds the configured synchronous budget."""
    if request.preview_chapters is not None:
        return False
    chapter_count, word_count = await _accessible_chapter_stats(
        db, book=book, collaborator=collaborator
    )
    return (
        chapter_count >= settings.MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_CHAPTERS
        or word_count >= settings.MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_WORDS
    )


def manuscript_export_job_out(job: ManuscriptExportJob) -> ManuscriptExportJobOut:
    download_url = None
    if job.status == "completed" and job.artifact_storage_key:
        download_url = f"/api/v1/books/{job.book_id}/exports/{job.id}/download"
    return ManuscriptExportJobOut(
        id=job.id,
        book_id=job.book_id,
        status=cast(Any, job.status),
        export_kind=cast(Any, job.export_kind),
        format=cast(Any, job.export_format),
        progress_completed=int(job.progress_completed or 0),
        progress_total=int(job.progress_total or 0),
        filename=job.artifact_filename,
        media_type=job.artifact_media_type,
        size_bytes=job.artifact_size_bytes,
        download_url=download_url,
        error=public_stored_error_message(job.error_detail)
        if job.status == "failed"
        else job.error_detail,
        expires_at=job.expires_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def prepare_manuscript_export(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    current_user: User,
    request: ManuscriptExportRequest,
) -> ManuscriptExportPreparationOut:
    _validate_export_request(request)
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is not None and not collaboration_can_export(collaborator):
        raise HTTPException(403, "This share cannot export the manuscript.")
    if not await should_queue_manuscript_export(
        db,
        book=book,
        collaborator=collaborator,
        request=request,
    ):
        return ManuscriptExportPreparationOut(delivery="synchronous")

    options_json = request.model_dump(mode="json")
    active_job_statement = (
        select(ManuscriptExportJob)
        .where(
            ManuscriptExportJob.user_id == current_user.id,
            ManuscriptExportJob.book_id == book.id,
            ManuscriptExportJob.status.in_(("queued", "running")),
            ManuscriptExportJob.export_kind == request.export_kind,
            ManuscriptExportJob.export_format == request.format,
            ManuscriptExportJob.options_json == options_json,
        )
        .order_by(ManuscriptExportJob.created_at.desc())
        .limit(1)
    )
    existing_job = (await db.execute(active_job_statement)).scalar_one_or_none()
    if existing_job is not None:
        if existing_job.status == "queued" and not existing_job.celery_task_id:
            await dispatch_manuscript_export_job(db, existing_job)
            await db.refresh(existing_job)
        return ManuscriptExportPreparationOut(
            delivery="job",
            job=manuscript_export_job_out(existing_job),
        )

    chapter_count, _word_count = await _accessible_chapter_stats(
        db, book=book, collaborator=collaborator
    )
    job = ManuscriptExportJob(
        id=uuid.uuid4(),
        user_id=current_user.id,
        book_id=book.id,
        status="queued",
        export_kind=request.export_kind,
        export_format=request.format,
        options_json=options_json,
        progress_total=max(chapter_count + 2, 2),
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # A concurrent request may have inserted the same active export after
        # our initial lookup. The partial unique index elects one winner; all
        # other requests reuse it instead of duplicating worker work.
        existing_job = (await db.execute(active_job_statement)).scalar_one_or_none()
        if existing_job is None:
            raise
        if existing_job.status == "queued" and not existing_job.celery_task_id:
            await dispatch_manuscript_export_job(db, existing_job)
            await db.refresh(existing_job)
        return ManuscriptExportPreparationOut(
            delivery="job",
            job=manuscript_export_job_out(existing_job),
        )
    await db.refresh(job)
    await dispatch_manuscript_export_job(db, job)
    await db.refresh(job)
    return ManuscriptExportPreparationOut(delivery="job", job=manuscript_export_job_out(job))


async def dispatch_manuscript_export_job(db: AsyncSession, job: ManuscriptExportJob) -> bool:
    if job.status != "queued" or job.celery_task_id:
        return False
    from app.workers.tasks.export_tasks import process_manuscript_export_job_task

    task_id = str(uuid.uuid4())
    try:
        process_manuscript_export_job_task.apply_async(
            kwargs={"job_id": str(job.id)},
            task_id=task_id,
            queue="maintenance",
        )
    except Exception as exc:
        log.exception("manuscript_export_job_dispatch_failed", extra={"job_id": str(job.id)})
        report_caught_failure("manuscript_export_job_dispatch_failed", exc)
        return False
    job.celery_task_id = task_id
    await db.commit()
    return True


async def dispatch_pending_manuscript_export_jobs(
    db: AsyncSession,
    *,
    limit: int = 25,
) -> int:
    now = datetime.now(UTC)
    queued_dispatch_cutoff = now - timedelta(minutes=10)
    running_recovery_cutoff = now - timedelta(hours=2)
    jobs = list(
        (
            await db.execute(
                select(ManuscriptExportJob)
                .where(
                    or_(
                        and_(
                            ManuscriptExportJob.status == "queued",
                            or_(
                                ManuscriptExportJob.celery_task_id.is_(None),
                                ManuscriptExportJob.updated_at < queued_dispatch_cutoff,
                            ),
                        ),
                        and_(
                            ManuscriptExportJob.status == "running",
                            ManuscriptExportJob.updated_at < running_recovery_cutoff,
                        ),
                    )
                )
                .order_by(ManuscriptExportJob.created_at.asc())
                .limit(max(1, min(limit, 100)))
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    dispatched = 0
    for job in jobs:
        job.status = "queued"
        job.celery_task_id = None
        job.started_at = None
        await db.commit()
        if await dispatch_manuscript_export_job(db, job):
            dispatched += 1
    return dispatched


async def get_manuscript_export_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ManuscriptExportJob:
    job = (
        await db.execute(
            select(ManuscriptExportJob).where(
                ManuscriptExportJob.id == job_id,
                ManuscriptExportJob.book_id == book_id,
                ManuscriptExportJob.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Manuscript export job not found")
    if (
        job.status == "completed"
        and job.expires_at is not None
        and job.expires_at <= datetime.now(UTC)
    ):
        await expire_manuscript_export_job(db, job)
    return job


def _new_artifact_stream() -> BinaryIO:
    stream = tempfile.SpooledTemporaryFile(
        max_size=settings.MANUSCRIPT_EXPORT_SPOOL_MAX_MEMORY_BYTES,
        mode="w+b",
        dir=settings.MANUSCRIPT_EXPORT_SPOOL_DIRECTORY or None,
    )
    return stream


async def _render_export_to_stream(renderer: Any, kwargs: dict[str, Any]) -> BinaryIO:
    """Render directly to a spooled stream, retaining compatibility with byte renderers."""
    stream = _new_artifact_stream()
    try:
        raw = await asyncio.to_thread(renderer, output=stream, **kwargs)
        if isinstance(raw, bytes):
            # Third-party or test renderers may still implement the legacy bytes
            # contract. Production renderers write directly into ``stream``.
            stream.write(raw)
        stream.seek(0)
        return stream
    except Exception:
        stream.close()
        raise


def _artifact_result(
    stream: BinaryIO,
    *,
    filename: str,
    media_type: str,
) -> GeneratedExportArtifact:
    stream.seek(0, 2)
    size_bytes = stream.tell()
    stream.seek(0)
    return GeneratedExportArtifact(
        stream=stream,
        filename=filename,
        media_type=media_type,
        size_bytes=size_bytes,
    )


async def generate_manuscript_export_artifact(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    current_user: User,
    request: ManuscriptExportRequest,
) -> GeneratedExportArtifact:
    """Build one export into a seekable spooled stream."""
    _validate_export_request(request)
    selected_font = normalize_export_font_family(request.font_family)
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is not None and not collaboration_can_export(collaborator):
        raise HTTPException(403, "This share cannot export the manuscript.")

    workspace = build_writer_workspace_payload(book)
    front_matter = workspace.get("manuscript_front_matter") if isinstance(workspace, dict) else None
    index_format = (
        (workspace.get("index_format") or "arabic") if isinstance(workspace, dict) else "arabic"
    )
    filename_base = export_filename_base(book.title)

    if request.export_kind == "novel":
        chapters = await load_novel_export_chapters(
            db,
            book=book,
            collaborator=collaborator,
            include_images=request.include_images,
        )
        if request.preview_chapters is not None:
            chapters = chapters[: request.preview_chapters]
        if not chapters:
            raise HTTPException(404, "No chapters available to export")
        preface = str(workspace.get("novel_preface") or "") if isinstance(workspace, dict) else ""
        novel_front_matter = (
            workspace.get("novel_front_matter") if isinstance(workspace, dict) else None
        )
        epub_metadata = (
            workspace.get("novel_epub_metadata") if isinstance(workspace, dict) else None
        )
        cover_image = await load_novel_cover_image(book)
        common_kwargs = {
            "title": book.title or "LoreVia Novel",
            "chapters": chapters,
            "preset": request.preset,
            "front_matter": cast(dict | None, front_matter),
            "preface": preface,
            "novel_front_matter": cast(dict | None, novel_front_matter),
            "epub_metadata": cast(dict | None, epub_metadata),
            "cover_image": cover_image,
            "font_family": selected_font,
            "include_images": request.include_images,
            "image_placement": request.image_placement,
            "include_image_captions": request.include_image_captions,
            "index_format": index_format,
        }
        renderer = {
            "pdf": novel_pdf_compiled,
            "docx": novel_docx,
            "epub": novel_epub_compiled,
        }[request.format]
        stream = await _render_export_to_stream(renderer, common_kwargs)
        suffix = "novel-preview" if request.preview_chapters is not None else "novel"
        media_type = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "epub": "application/epub+zip",
        }[request.format]
        return _artifact_result(
            stream,
            filename=f"{filename_base}-{suffix}.{request.format}",
            media_type=media_type,
        )

    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    if collaborator is not None:
        chapter_rows = [
            row for row in chapter_rows if collaboration_allows_chapter(collaborator, int(row[0]))
        ]
    if not chapter_rows:
        raise HTTPException(404, "No chapters available to export")
    chapters = await load_manuscript_export_chapters(
        chapter_rows,
        include_scene_metadata=request.include_scene_metadata,
    )
    common_kwargs = {
        "title": book.title or "LoreVia Manuscript",
        "chapters": chapters,
        "scenes": [],
        "preset": request.preset,
        "front_matter": cast(dict | None, front_matter),
        "font_family": selected_font,
        "include_toc": request.include_toc,
        "index_format": index_format,
    }
    if request.format == "vault":
        manuscript_scenes = [
            scene
            for scene in await list_novel_scenes(db, book=book, collaborator=collaborator)
            if scene.get("source") == "manual" and scene.get("status") != "archived"
        ]
        notes = await list_vault_notes(
            db,
            book=book,
            user_id=current_user.id,
            source=VaultNoteSource.USER_NOTES.value,
        )
        stream = _new_artifact_stream()
        await asyncio.to_thread(
            write_manuscript_vault_zip,
            stream,
            title=book.title or "LoreVia Manuscript",
            chapters=chapters,
            scenes=manuscript_scenes,
            notes=notes,
            front_matter=cast(dict | None, front_matter),
            font_family=selected_font,
            index_format=index_format,
        )
        return _artifact_result(
            stream,
            filename=f"{filename_base}-manuscript-vault.zip",
            media_type="application/zip",
        )
    renderer = {
        "pdf": manuscript_pdf_compiled,
        "docx": manuscript_docx,
        "epub": manuscript_epub_compiled,
    }[request.format]
    stream = await _render_export_to_stream(renderer, common_kwargs)
    media_type = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "epub": "application/epub+zip",
    }[request.format]
    return _artifact_result(
        stream,
        filename=f"{filename_base}-manuscript.{request.format}",
        media_type=media_type,
    )


async def process_manuscript_export_job(
    db: AsyncSession,
    job_id: uuid.UUID,
) -> dict[str, Any]:
    job = (
        await db.execute(
            select(ManuscriptExportJob).where(ManuscriptExportJob.id == job_id).with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        return {"status": "missing", "job_id": str(job_id)}
    if job.status in TERMINAL_EXPORT_JOB_STATUSES:
        return {"status": job.status, "job_id": str(job_id)}
    if job.status != "queued":
        return {"status": job.status, "job_id": str(job_id)}

    job.status = "running"
    job.started_at = job.started_at or datetime.now(UTC)
    job.error_detail = None
    await db.commit()

    artifact: GeneratedExportArtifact | None = None
    artifact_key: str | None = None
    try:
        user = await db.get(User, job.user_id)
        if user is None:
            raise ValueError("The user account is no longer available.")
        request = ManuscriptExportRequest.model_validate(job.options_json or {})
        artifact = await generate_manuscript_export_artifact(
            db,
            book_id=job.book_id,
            current_user=user,
            request=request,
        )
        artifact_key = f"exports/{job.user_id}/{job.book_id}/{job.id}/{artifact.filename}"
        artifact.stream.seek(0)
        await asyncio.to_thread(
            storage.upload_fileobj,
            artifact_key,
            artifact.stream,
            artifact.media_type,
        )
        job = await db.get(ManuscriptExportJob, job_id)
        if job is None:
            await asyncio.to_thread(storage.delete_object, artifact_key)
            return {"status": "missing", "job_id": str(job_id)}
        job.status = "completed"
        job.artifact_storage_key = artifact_key
        job.artifact_filename = artifact.filename
        job.artifact_media_type = artifact.media_type
        job.artifact_size_bytes = artifact.size_bytes
        job.progress_completed = job.progress_total
        job.completed_at = datetime.now(UTC)
        job.expires_at = job.completed_at + timedelta(
            seconds=settings.MANUSCRIPT_EXPORT_ARTIFACT_TTL_SECONDS
        )
        await db.commit()
        return {"status": "completed", "job_id": str(job_id)}
    except Exception as exc:
        await db.rollback()
        if artifact_key:
            try:
                await asyncio.to_thread(storage.delete_object, artifact_key)
            except STORAGE_IO_EXCEPTIONS:
                log.exception(
                    "manuscript_export_partial_artifact_cleanup_failed",
                    extra={"job_id": str(job_id)},
                )
        job = await db.get(ManuscriptExportJob, job_id)
        if job is not None:
            job.status = "failed"
            job.error_detail = public_error_message(500)
            job.completed_at = datetime.now(UTC)
            job.expires_at = job.completed_at + timedelta(
                seconds=settings.MANUSCRIPT_EXPORT_ARTIFACT_TTL_SECONDS
            )
            await db.commit()
        log.exception("manuscript_export_job_failed", extra={"job_id": str(job_id)})
        try:
            import sentry_sdk

            with sentry_sdk.new_scope() as scope:
                scope.set_tag("job_id", str(job_id))
                scope.set_tag("failure_type", type(exc).__name__)
                sentry_sdk.capture_message("manuscript_export_job_failed", level="error")
        except Exception:
            log.warning("manuscript_export_sentry_report_failed job_id=%s", job_id, exc_info=True)
        return {"status": "failed", "job_id": str(job_id)}
    finally:
        if artifact is not None:
            artifact.stream.close()


async def expire_manuscript_export_job(
    db: AsyncSession,
    job: ManuscriptExportJob,
) -> None:
    storage_key = job.artifact_storage_key
    artifact_deleted = storage_key is None
    if storage_key:
        try:
            await asyncio.to_thread(storage.delete_object, storage_key)
            artifact_deleted = True
        except STORAGE_IO_EXCEPTIONS:
            log.exception(
                "manuscript_export_artifact_cleanup_failed",
                extra={"job_id": str(job.id)},
            )
    job.status = "expired"
    if artifact_deleted:
        job.artifact_storage_key = None
    await db.commit()


async def cleanup_expired_manuscript_export_jobs(
    db: AsyncSession,
    *,
    limit: int = 250,
) -> int:
    now = datetime.now(UTC)
    jobs = list(
        (
            await db.execute(
                select(ManuscriptExportJob)
                .where(
                    or_(
                        ManuscriptExportJob.status.in_(("completed", "failed")),
                        and_(
                            ManuscriptExportJob.status == "expired",
                            ManuscriptExportJob.artifact_storage_key.is_not(None),
                        ),
                    ),
                    ManuscriptExportJob.expires_at.is_not(None),
                    ManuscriptExportJob.expires_at <= now,
                )
                .order_by(ManuscriptExportJob.expires_at.asc())
                .limit(max(1, min(limit, 1000)))
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    expired = 0
    for job in jobs:
        previous_status = job.status
        await expire_manuscript_export_job(db, job)
        if job.status == "expired" and previous_status != "expired":
            expired += 1
    return expired
