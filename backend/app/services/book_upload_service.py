import asyncio
import uuid
from typing import Any

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
) -> dict[str, str | bool]:
    book_id = uuid.uuid4()
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
        raise

    await clear_upload_intent(intent.intent_key)

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
