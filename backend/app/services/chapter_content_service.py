from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.redis import (
    cache_del,
    key_public_chapter,
    mark_book_cache_dirty,
    mark_user_dashboard_cache_dirty,
)
from app.models.book import Book, BookCollaborator, Chapter
from app.schemas.books import ChapterContentSaveBody, ChapterContentSaveOut
from app.services.editor_project_service import get_rebuild_run_id, update_reprocess_metadata
from app.services.notification_service import enqueue_revision_digest_refresh
from app.services.processing_allowance_service import ensure_active_word_capacity
from app.services.public_asset_service import publish_public_chapter_asset
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.billing_utils import require_author_access
from app.utils.books.chapter_versions import snapshot_chapter_version_reference
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_can_edit,
    get_book_with_collaboration_access,
)
from app.utils.books.manuscript import (
    apply_staged_editor_chapter_content,
    clean_manuscript_html,
    deserialize_manuscript_content,
    stage_editor_chapter_content,
)
from app.utils.books.writer_workspace import touch_public_book_updated_at
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS, delete_storage_keys_best_effort

log = logging.getLogger("lorevia.chapter_content")


def chapter_save_error(
    status_code: int, code: str, message: str, **details: object
) -> HTTPException:
    return HTTPException(status_code, {"code": code, "message": message, **details})


async def save_chapter_content(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    current_user,
    body: ChapterContentSaveBody,
) -> ChapterContentSaveOut:
    if chapter_number < 1:
        raise chapter_save_error(
            400, "invalid_chapter_number", "Chapter number must be at least 1."
        )
    text = body.text.replace("\x00", "").strip()
    if not text:
        raise chapter_save_error(400, "empty_content", "Add chapter text before saving.")
    if len(text.encode("utf-8")) > 5_000_000:
        raise chapter_save_error(
            413, "content_too_large", "This chapter is too large to save at once."
        )

    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is not None:
        if not collaboration_can_edit(collaborator) or not collaboration_allows_chapter(
            collaborator, chapter_number
        ):
            raise chapter_save_error(
                403,
                "permission_denied",
                "Your collaboration access does not allow editing this chapter.",
            )
    else:
        try:
            require_author_access(current_user)
        except HTTPException:
            raise chapter_save_error(
                403,
                "plan_locked",
                "Writing workspace access is required to save manuscript chapters.",
            )
    if getattr(book, "is_editor_project", False) and get_rebuild_run_id(book) is not None:
        raise chapter_save_error(
            409,
            "project_rebuilding",
            "This project is rebuilding. Your local draft is safe; retry when processing finishes.",
        )

    observed_chapter = (
        await db.execute(
            select(Chapter).where(
                Chapter.book_id == book.id,
                Chapter.number == chapter_number,
            )
        )
    ).scalar_one_or_none()
    cleaned_html = clean_manuscript_html(body.sanitized_html) if body.sanitized_html else None
    normalized_title = body.title.strip() if body.title and body.title.strip() else None
    current_text = ""
    current_html: str | None = None
    if observed_chapter is not None:
        try:
            payload = deserialize_manuscript_content(
                await asyncio.to_thread(storage.download_book, observed_chapter.s3_key)
            )
        except STORAGE_IO_EXCEPTIONS:
            log.exception(
                "chapter_save_existing_content_unavailable",
                extra={"book_id": str(book.id), "chapter_number": chapter_number},
            )
            raise chapter_save_error(
                503,
                "storage_failure",
                "LoreVia could not read the current chapter. Your local draft is safe; please retry.",
            )
        current_text = str(payload.get("text") or "").strip()
        current_html = clean_manuscript_html(str(payload.get("html") or "")) or None
        html_matches = cleaned_html is None or current_html == cleaned_html
        identical = (
            current_text == text
            and html_matches
            and (observed_chapter.title or None) == normalized_title
        )
        if identical:
            return ChapterContentSaveOut(
                status="unchanged",
                book_id=str(book.id),
                chapter_number=chapter_number,
                content_version=int(observed_chapter.content_version or 1),
                client_mutation_id=body.client_mutation_id,
                saved_at=datetime.now(UTC),
                story_memory_status=(
                    "queued" if not observed_chapter.processed else "not_required"
                ),
            )
        current_version = int(observed_chapter.content_version or 1)
        if current_version != body.expected_content_version:
            raise chapter_save_error(
                409,
                "version_conflict",
                "This chapter changed elsewhere. Compare the server copy with your local draft.",
                chapter_number=chapter_number,
                current_content_version=current_version,
            )
    elif body.expected_content_version not in {0, 1}:
        raise chapter_save_error(
            409,
            "version_conflict",
            "The chapter no longer exists at the version you edited.",
            chapter_number=chapter_number,
            current_content_version=0,
        )

    previous_words = int(observed_chapter.word_count or 0) if observed_chapter is not None else 0
    next_words = len(text.split())
    await ensure_active_word_capacity(db, current_user, max(next_words - previous_words, 0))
    next_version = (
        int(observed_chapter.content_version or 1) + 1 if observed_chapter is not None else 1
    )

    try:
        staged = await stage_editor_chapter_content(
            book,
            chapter_number=chapter_number,
            text=text,
            html=cleaned_html,
        )
    except STORAGE_IO_EXCEPTIONS:
        log.exception(
            "chapter_save_storage_failed",
            extra={"book_id": str(book.id), "chapter_number": chapter_number},
        )
        raise chapter_save_error(
            503,
            "storage_failure",
            "LoreVia could not store the chapter. Your local draft is safe; please retry.",
        )

    lock_started = time.perf_counter()
    try:
        await db.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtext(f"chapter-save:{book.id}:{chapter_number}")
                )
            )
        )
        locked_book = (
            await db.execute(select(Book).where(Book.id == book.id).with_for_update())
        ).scalar_one_or_none()
        if locked_book is None:
            raise chapter_save_error(404, "book_not_found", "Book not found.")
        book = locked_book
        if collaborator is not None:
            locked_collaborator = await db.get(
                BookCollaborator,
                collaborator.id,
                with_for_update=True,
            )
            if (
                locked_collaborator is None
                or not collaboration_can_edit(locked_collaborator)
                or not collaboration_allows_chapter(locked_collaborator, chapter_number)
            ):
                raise chapter_save_error(
                    403,
                    "permission_denied",
                    "Your collaboration access no longer allows editing this chapter.",
                )
        else:
            require_author_access(current_user)
        if getattr(book, "is_editor_project", False) and get_rebuild_run_id(book) is not None:
            raise chapter_save_error(
                409,
                "project_rebuilding",
                "This project started rebuilding. Your local draft is safe; retry when processing finishes.",
            )
        chapter = (
            await db.execute(
                select(Chapter)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.number == chapter_number,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if observed_chapter is None:
            if chapter is not None or body.expected_content_version not in {0, 1}:
                raise chapter_save_error(
                    409,
                    "version_conflict",
                    "This chapter changed elsewhere. Compare the server copy with your local draft.",
                    chapter_number=chapter_number,
                    current_content_version=(
                        int(chapter.content_version or 1) if chapter is not None else 0
                    ),
                )
        elif (
            chapter is None
            or chapter.id != observed_chapter.id
            or int(chapter.content_version or 1) != body.expected_content_version
            or chapter.s3_key != observed_chapter.s3_key
        ):
            raise chapter_save_error(
                409,
                "version_conflict",
                "This chapter changed elsewhere. Compare the server copy with your local draft.",
                chapter_number=chapter_number,
                current_content_version=(
                    int(chapter.content_version or 1) if chapter is not None else 0
                ),
            )

        locked_previous_words = int(chapter.word_count or 0) if chapter is not None else 0
        await ensure_active_word_capacity(
            db,
            current_user,
            max(next_words - locked_previous_words, 0),
        )
        if chapter is not None:
            await snapshot_chapter_version_reference(
                db,
                book,
                chapter,
                note=f"Snapshot before editor save for Chapter {chapter_number}",
                snapshot_kind="pre_replace",
            )
        saved = await apply_staged_editor_chapter_content(
            db,
            book,
            chapter=chapter,
            chapter_number=chapter_number,
            title=normalized_title,
            staged=staged,
            content_version=next_version,
        )
        update_reprocess_metadata(book, add_pending_chapters=[chapter_number])
        book.total_chapters = int(
            await db.scalar(
                select(func.count()).select_from(Chapter).where(Chapter.book_id == book.id)
            )
            or 0
        )
        book.mode = "author"
        book.source_kind = book.source_kind or "chapter_wise"
        touch_public_book_updated_at(book)
        await db.commit()
    except Exception:
        await db.rollback()
        await delete_storage_keys_best_effort(
            staged.uploaded_keys,
            context="chapter_save_rollback",
        )
        raise
    finally:
        log.info(
            "chapter_save_transaction_finished",
            extra={
                "book_id": str(book.id),
                "chapter_number": chapter_number,
                "duration_ms": round((time.perf_counter() - lock_started) * 1000, 2),
            },
        )

    try:
        await invalidate_advisor_caches_for_book(db, book_id=book.id)
        await db.commit()
    except Exception:
        await db.rollback()
        log.exception(
            "chapter_save_advisor_cache_invalidation_failed",
            extra={"book_id": str(book.id), "chapter_number": chapter_number},
        )
    try:
        await mark_book_cache_dirty(str(book.id))
        await mark_user_dashboard_cache_dirty(str(current_user.id))
        await cache_del(key_public_chapter(str(book.id), chapter_number))
    except Exception:
        log.exception(
            "chapter_save_cache_dirty_mark_failed",
            extra={"book_id": str(book.id), "chapter_number": chapter_number},
        )
    if bool(book.is_public) and str(book.public_status or "") == "published":
        await publish_public_chapter_asset(book=book, chapter=saved, db=db)
    await enqueue_revision_digest_refresh(user_id=book.user_id, book_id=book.id)
    return ChapterContentSaveOut(
        status="updated" if observed_chapter is not None else "created",
        book_id=str(book.id),
        chapter_number=chapter_number,
        content_version=int(saved.content_version or next_version),
        client_mutation_id=body.client_mutation_id,
        saved_at=datetime.now(UTC),
        story_memory_status="queued",
    )
