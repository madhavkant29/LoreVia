"""Focused book scene sync workflows."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book, upload_text
from app.models.book import (
    Book,
    Chapter,
    NovelScene,
)
from app.utils.books import (
    manuscript,
    writer_workspace,
)
from app.utils.books.chapter_titles import (
    _count_words,
)
from app.utils.books.scene_metadata import (
    build_workspace_chapter_text_from_scenes,
    strip_scene_metadata_from_manuscript_text,
)


def _chapter_storage_key(book_id: uuid.UUID, chapter_number: int) -> str:
    return f"chapters/{book_id}/{chapter_number}.txt"


async def _ensure_syncable_chapter(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
) -> tuple[Chapter, bool]:
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar_one_or_none()
    if chapter is not None:
        if not chapter.s3_key:
            chapter.s3_key = _chapter_storage_key(book.id, chapter_number)
        if not chapter.title:
            chapter.title = f"Chapter {chapter_number}"
        await db.flush()
        return chapter, False

    chapter = Chapter(
        book_id=book.id,
        number=chapter_number,
        title=f"Chapter {chapter_number}",
        s3_key=_chapter_storage_key(book.id, chapter_number),
        content_version=1,
        word_count=0,
        processed=False,
    )
    db.add(chapter)
    await db.flush()
    return chapter, True


async def sync_chapter_content_from_novel_scenes(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
    increment_content_version: bool = True,
) -> dict[str, Any]:
    from app.utils.advisor_utils import invalidate_advisor_caches_for_book

    chapter, chapter_created = await _ensure_syncable_chapter(
        db,
        book=book,
        chapter_number=chapter_number,
    )
    chapter_scenes = (
        (
            await db.execute(
                select(NovelScene)
                .where(
                    NovelScene.book_id == book.id,
                    NovelScene.chapter_number == chapter_number,
                    NovelScene.status != "archived",
                )
                .order_by(
                    NovelScene.sort_order.asc(),
                    NovelScene.created_at.asc(),
                    NovelScene.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    next_text = build_workspace_chapter_text_from_scenes(list(chapter_scenes))
    next_html = (
        manuscript.clean_manuscript_html(manuscript.manuscript_text_to_html(next_text))
        if next_text
        else None
    )
    previous_payload = {"text": "", "html": None}
    if chapter.s3_key:
        try:
            previous_payload = manuscript.deserialize_manuscript_content(
                await asyncio.to_thread(download_book, chapter.s3_key)
            )
        except Exception:
            previous_payload = {"text": "", "html": None}
    stored_key = await asyncio.to_thread(
        upload_text,
        chapter.s3_key or _chapter_storage_key(book.id, chapter_number),
        manuscript.serialize_manuscript_content(next_text, next_html),
    )
    chapter.s3_key = stored_key
    chapter.word_count = _count_words(strip_scene_metadata_from_manuscript_text(next_text))
    previous_text = str(previous_payload.get("text") or "")
    previous_html = (
        manuscript.clean_manuscript_html(cast(str | None, previous_payload.get("html")))
        if previous_payload.get("html")
        else None
    )
    if (
        increment_content_version
        and not chapter_created
        and (previous_text != next_text or previous_html != next_html)
    ):
        chapter.content_version = int(chapter.content_version or 1) + 1
    if not chapter.title:
        chapter.title = f"Chapter {chapter_number}"
    content_changed = chapter_created or previous_text != next_text or previous_html != next_html
    if content_changed:
        writer_workspace.touch_public_book_updated_at(book)
    await db.flush()
    if content_changed:
        await invalidate_advisor_caches_for_book(db, book_id=book.id)
    return {
        "chapter": chapter,
        "text": next_text,
        "html": next_html,
    }
