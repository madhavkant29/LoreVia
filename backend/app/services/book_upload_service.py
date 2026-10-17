import asyncio
import hashlib
import logging
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models.book import Book, SeriesBook
from app.services.task_execution_service import (
    dispatch_pending_extraction_tasks,
    ensure_task_execution,
    get_or_create_processing_run,
)
from app.services.upload_intent_service import (
    build_book_upload_intent,
    clear_upload_intent,
    persist_upload_intent,
)
from app.utils.notification_utils import build_upload_processing_notification
from app.utils.storage_utils import delete_storage_keys_best_effort

log = logging.getLogger("lorevia.upload")

DUPLICATE_UPLOAD_STATUSES = ("pending", "processing")
DUPLICATE_UPLOAD_MESSAGE = (
    "This exact manuscript is already being processed in another project. "
    "Wait for that import to finish, or upload a revised file."
)


def upload_source_fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


async def acquire_upload_fingerprint_lock(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    fingerprint: str,
) -> None:
    """Serialize identical uploads for one user within the current transaction."""
    await db.execute(
        select(
            func.pg_advisory_xact_lock(func.hashtext(f"upload_fingerprint:{user_id}:{fingerprint}"))
        )
    )


async def find_active_duplicate_upload(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    fingerprint: str,
) -> Book | None:
    """Find the caller's own book that is currently processing the same file.

    Scoped to the authenticated user; no information about other users'
    manuscripts is ever queried or returned. Only actively processing copies
    block a new upload so re-uploading after a failure or freeze stays possible.
    """
    if not fingerprint:
        return None
    return (
        (
            await db.execute(
                select(Book)
                .where(
                    Book.user_id == user_id,
                    Book.hidden_at.is_(None),
                    Book.status.in_(DUPLICATE_UPLOAD_STATUSES),
                    Book.writer_workspace["source_fingerprint"].astext == fingerprint,
                )
                .order_by(Book.created_at.desc())
            )
        )
        .scalars()
        .first()
    )


async def create_uploaded_book_from_raw(
    db: AsyncSession,
    *,
    current_user: Any,
    filename: str,
    raw: bytes,
    title: str,
    genre: str | None,
    author: str | None,
    resolved_work_type: str,
    fmt: str,
    selected_series: list[Any],
    visibility: str,
    description: str | None,
    mode: str,
    cover_raw: bytes | None,
    cover_suffix: str | None,
    cover_content_type: str | None,
    preserve_chapter_numbers: bool,
    preserve_source_chapters: bool,
    force_single_manuscript: bool,
    structure_plan: dict[str, Any] | None = None,
) -> dict[str, str | bool]:
    book_id = uuid.uuid4()
    fingerprint = upload_source_fingerprint(raw)
    # Serialize identical uploads for this user so two concurrent requests
    # cannot both pass the duplicate check and pay for two full analyses.
    await acquire_upload_fingerprint_lock(db, user_id=current_user.id, fingerprint=fingerprint)
    duplicate = await find_active_duplicate_upload(
        db, user_id=current_user.id, fingerprint=fingerprint
    )
    if duplicate is not None:
        raise HTTPException(409, DUPLICATE_UPLOAD_MESSAGE)
    intent = build_book_upload_intent(
        book_id=book_id,
        user_id=current_user.id,
        filename=filename,
        has_cover=bool(cover_raw),
        cover_suffix=cover_suffix if cover_raw else None,
    )
    uploaded_keys: list[str] = []
    try:
        await persist_upload_intent(intent)
        s3_key = await asyncio.to_thread(
            storage.upload_binary,
            intent.source_key,
            raw,
        )
        uploaded_keys.append(s3_key)
        cover_s3_key = None
        if cover_raw:
            cover_s3_key = await asyncio.to_thread(
                storage.upload_binary,
                intent.cover_key,
                cover_raw,
                cover_content_type,
            )
            uploaded_keys.append(cover_s3_key)

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
            is_public=False,
            public_description=description,
            mode=mode,
            source_kind="single_upload",
            preserve_chapter_numbers=preserve_chapter_numbers,
            preserve_source_chapters=preserve_source_chapters,
            force_single_manuscript=force_single_manuscript,
            import_structure=structure_plan,
            writer_workspace={"source_fingerprint": fingerprint},
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
    except Exception:
        await db.rollback()
        await delete_storage_keys_best_effort(uploaded_keys, context="book_upload")
        await clear_upload_intent(intent.intent_key)
        log.exception(
            "book_upload_failed book_id=%s user_id=%s format=%s size_bytes=%s",
            book_id,
            current_user.id,
            fmt,
            len(raw),
        )
        raise

    await clear_upload_intent(intent.intent_key)

    await db.refresh(book)

    notification = build_upload_processing_notification(book, mode, len(raw))
    db.add(notification)
    await db.commit()

    await dispatch_pending_extraction_tasks(db)
    log.info(
        "book_upload_stored book_id=%s user_id=%s format=%s size_bytes=%s mode=%s",
        book.id,
        current_user.id,
        fmt,
        len(raw),
        mode,
    )
    return {
        "book_id": str(book.id),
        "status": "processing",
        "copyright_warning": False,
        "visibility": visibility,
        "mode": mode,
    }
