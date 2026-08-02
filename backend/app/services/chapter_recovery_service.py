from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_del, cache_set_if_absent, key_chapter_recovery_inflight
from app.core.storage import download_book, get_presigned_url, upload_binary, upload_text
from app.models.book import Book, Chapter, ChapterMedia, NovelScene
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
    manuscript_text_to_html,
    serialize_manuscript_content,
)
from app.utils.books.scene_metadata import (
    build_workspace_chapter_text_from_scenes,
    chapter_body_needs_scene_workspace_fallback,
)
from app.utils.ingestion_utils import (
    CHAPTER_RECOVERY_INFLIGHT_TTL_SECONDS,
    build_analysis_chapter_state,
    build_source_integrity_state,
)
from app.utils.reader_utils import (
    chapter_analysis_status,
    chapter_source_integrity,
    extract_media_markers,
    merge_media_items,
    parse_chapter_from_source,
    serialize_chapter_media,
    serialize_inline_images,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS


def chapter_needs_source_recovery(
    *,
    book: Book,
    stored_text_content: str | None,
    stored_media: list[dict[str, Any]],
) -> bool:
    stored_markers = extract_media_markers(stored_text_content)
    return bool(
        book.format == "pdf"
        and (
            not stored_text_content
            or ("[[IMAGE:" in str(stored_text_content or "") and not stored_media)
            or (stored_media and not stored_markers)
            or (stored_markers and len(stored_markers) != len(stored_media))
        )
    )


async def queue_chapter_repair_if_needed(
    db: AsyncSession,
    *,
    book: Book,
    chapter: Chapter,
    current_user=None,
    reason: str = "source_integrity_mismatch",
) -> bool:
    analysis_state = chapter.analysis_state if isinstance(chapter.analysis_state, dict) else {}
    source_integrity = (
        analysis_state.get("source_integrity")
        if isinstance(analysis_state.get("source_integrity"), dict)
        else {}
    )
    if str(source_integrity.get("recovery_status") or "").strip() == "queued":
        return False

    inflight_key = key_chapter_recovery_inflight(str(chapter.id))
    if not await cache_set_if_absent(
        inflight_key,
        {"book_id": str(book.id), "chapter_id": str(chapter.id), "chapter_number": chapter.number},
        CHAPTER_RECOVERY_INFLIGHT_TTL_SECONDS,
    ):
        return False

    next_integrity = build_source_integrity_state(
        text_present=bool(source_integrity.get("text_present")),
        media_marker_count=int(source_integrity.get("media_marker_count") or 0),
        stored_media_count=int(source_integrity.get("stored_media_count") or 0),
        recovery_status="queued",
        last_recovery_error=reason,
    )
    chapter.analysis_state = build_analysis_chapter_state(
        analysis_state,
        status=str(analysis_state.get("status") or "pending"),
        source_integrity=next_integrity,
    )
    await db.commit()

    from app.services.task_execution_service import enqueue_chapter_repair_execution

    await enqueue_chapter_repair_execution(
        db,
        book_id=book.id,
        user_id=book.user_id,
        chapter_id=chapter.id,
        chapter_number=chapter.number,
        chapters_total=int(getattr(book, "total_chapters", None) or 0),
        reason=reason,
    )
    return True


async def repair_chapter_payload_from_source(
    db: AsyncSession,
    *,
    book: Book,
    chapter: Chapter,
) -> bool:
    inflight_key = key_chapter_recovery_inflight(str(chapter.id))
    try:
        fallback = parse_chapter_from_source(book, chapter.number)
        if not fallback:
            chapter.analysis_state = build_analysis_chapter_state(
                chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
                status=str(
                    (
                        (chapter.analysis_state or {})
                        if isinstance(chapter.analysis_state, dict)
                        else {}
                    ).get("status")
                    or "pending"
                ),
                source_integrity=build_source_integrity_state(
                    text_present=bool(str(download_stored_text_or_empty(chapter) or "").strip()),
                    media_marker_count=0,
                    stored_media_count=0,
                    recovery_status="failed",
                    last_recovery_error="source_recovery_unavailable",
                ),
            )
            await db.commit()
            return False

        repaired_text = str(fallback.get("text") or "").strip()
        if not repaired_text:
            chapter.analysis_state = build_analysis_chapter_state(
                chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
                status=str(
                    (
                        (chapter.analysis_state or {})
                        if isinstance(chapter.analysis_state, dict)
                        else {}
                    ).get("status")
                    or "pending"
                ),
                source_integrity=build_source_integrity_state(
                    text_present=False,
                    media_marker_count=0,
                    stored_media_count=0,
                    recovery_status="failed",
                    last_recovery_error="source_recovery_empty",
                ),
            )
            await db.commit()
            return False

        if not chapter.s3_key:
            chapter.s3_key = f"chapters/{book.id}/{chapter.number}.txt"
        repaired_html = fallback.get("html")
        await asyncio.to_thread(
            upload_text,
            chapter.s3_key,
            serialize_manuscript_content(repaired_text, repaired_html),
        )
        await _sync_repaired_chapter_media(
            db, book=book, chapter=chapter, images=fallback.get("images") or []
        )
        if not chapter.title and fallback.get("title"):
            chapter.title = str(fallback.get("title") or "").strip() or chapter.title

        repaired_media_count = len(fallback.get("images") or [])
        chapter.analysis_state = build_analysis_chapter_state(
            chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
            status=str(
                (
                    (chapter.analysis_state or {})
                    if isinstance(chapter.analysis_state, dict)
                    else {}
                ).get("status")
                or "pending"
            ),
            source_integrity=build_source_integrity_state(
                text_present=True,
                media_marker_count=len(extract_media_markers(repaired_text)),
                stored_media_count=repaired_media_count,
                recovery_status="recovered",
                last_recovery_error=None,
            ),
        )
        await db.commit()
        await invalidate_advisor_caches_for_book(db, book_id=book.id)
        return True
    finally:
        await cache_del(inflight_key)


def download_stored_text_or_empty(chapter: Chapter) -> str:
    if not chapter.s3_key:
        return ""
    try:
        payload = deserialize_manuscript_content(download_book(chapter.s3_key))
    except STORAGE_IO_EXCEPTIONS:
        return ""
    return str(payload.get("text") or "")


async def resolve_reader_chapter_payload(
    db: AsyncSession,
    *,
    book: Book,
    chapter: Chapter | None,
    chapter_num: int,
    current_user=None,
) -> dict[str, Any] | None:
    if chapter is None:
        fallback = parse_chapter_from_source(book, chapter_num)
        if not fallback:
            return None
        fallback_media = serialize_inline_images(fallback.get("images", []))
        return {
            "chapter_title": fallback.get("title"),
            "content_version": None,
            "text_url": None,
            "text_content": fallback.get("text"),
            "html_content": None,
            "media": fallback_media,
            "analysis_status": None,
            "source_integrity": None,
        }

    stored_text_content: str | None = None
    stored_html_content: str | None = None
    if chapter.s3_key:
        try:
            stored_payload = deserialize_manuscript_content(download_book(chapter.s3_key))
            stored_text_content = str(stored_payload.get("text") or "")
            stored_html_content = str(stored_payload.get("html") or "") or None
        except STORAGE_IO_EXCEPTIONS:
            stored_text_content = None
            stored_html_content = None

    stored_media = await serialize_chapter_media(
        db, chapter.id, book_id=book.id, chapter_text=stored_text_content
    )
    fallback_payload = None
    needs_source_recovery = chapter_needs_source_recovery(
        book=book,
        stored_text_content=stored_text_content,
        stored_media=stored_media,
    )
    if needs_source_recovery:
        fallback_payload = parse_chapter_from_source(book, chapter_num)
        current_integrity = chapter_source_integrity(chapter) or {}
        await queue_chapter_repair_if_needed(
            db,
            book=book,
            chapter=chapter,
            current_user=current_user,
            reason="source_integrity_mismatch",
        )
        if not stored_text_content:
            stored_text_content = str((fallback_payload or {}).get("text") or "")
        if not stored_html_content:
            stored_html_content = (fallback_payload or {}).get("html")
        fallback_media = serialize_inline_images(list((fallback_payload or {}).get("images") or []))
        stored_media = merge_media_items(stored_media, fallback_media)
        current_integrity["recovery_status"] = "queued"
        current_integrity["last_recovery_error"] = "source_integrity_mismatch"
    elif not stored_media and stored_text_content and extract_media_markers(stored_text_content):
        fallback_payload = parse_chapter_from_source(book, chapter_num)
        stored_media = merge_media_items(
            stored_media,
            serialize_inline_images(list((fallback_payload or {}).get("images") or [])),
        )

    if chapter_body_needs_scene_workspace_fallback(
        stored_text_content,
        chapter_number=chapter_num,
        chapter_title=chapter.title,
    ):
        manual_scenes = (
            (
                await db.execute(
                    select(NovelScene)
                    .where(
                        NovelScene.book_id == book.id,
                        NovelScene.chapter_number == chapter_num,
                        NovelScene.status != "archived",
                    )
                    .order_by(NovelScene.sort_order.asc(), NovelScene.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        compiled_text = build_workspace_chapter_text_from_scenes(list(manual_scenes))
        if compiled_text:
            stored_text_content = compiled_text
            stored_html_content = manuscript_text_to_html(compiled_text)

    return {
        "chapter_title": chapter.title,
        "content_version": int(chapter.content_version or 1),
        "text_url": get_presigned_url(chapter.s3_key) if chapter.s3_key else None,
        "text_content": stored_text_content,
        "html_content": stored_html_content,
        "media": stored_media,
        "analysis_status": chapter_analysis_status(chapter),
        "source_integrity": chapter_source_integrity(chapter),
    }


async def _sync_repaired_chapter_media(
    db: AsyncSession,
    *,
    book: Book,
    chapter: Chapter,
    images: list[dict[str, Any]],
) -> None:
    await db.execute(delete(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id))
    for index, image in enumerate(images):
        raw = image.get("bytes")
        marker = image.get("marker")
        if not raw or not marker:
            continue
        filename = image.get("filename") or f"{uuid.uuid4().hex}.bin"
        storage_key = f"chapter-media/{book.id}/{chapter.number}/{index}-{filename}"
        await asyncio.to_thread(upload_binary, storage_key, raw, image.get("content_type"))
        db.add(
            ChapterMedia(
                book_id=book.id,
                chapter_id=chapter.id,
                marker=str(marker),
                asset_type="image",
                content_type=image.get("content_type"),
                storage_key=storage_key,
                caption=None,
                sort_order=index,
            )
        )
    await db.flush()
