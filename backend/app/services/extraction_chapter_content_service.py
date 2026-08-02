from __future__ import annotations

import asyncio
import re
import uuid

from sqlalchemy import delete, select

from app.core.storage import upload_binary
from app.models.book import Book, Chapter, ChapterMedia
from app.parsers.chunker import count_tokens
from app.utils.books.manuscript import (
    extract_inline_images_from_manuscript_html,
    manuscript_html_to_text,
)
from app.utils.books.normalization import normalize_chapter_kind


def _count_words(text: str) -> int:
    cleaned = re.sub(r"\[\[IMAGE:[^\]]+\]\]", " ", text or "")
    return len(re.findall(r"\b[\w']+\b", cleaned))


def _prepare_chapter_rich_content(ch_data: dict) -> dict:
    html = ch_data.get("html") if isinstance(ch_data.get("html"), str) else None
    if html is None:
        return ch_data

    prepared = dict(ch_data)
    prepared["_lorevia_persist_rich_content"] = True
    if "<img" not in html and "data:image/" not in html:
        return prepared

    cleaned_html, extracted_images, retained_markers = extract_inline_images_from_manuscript_html(
        html
    )
    if not extracted_images and not retained_markers:
        prepared["html"] = cleaned_html
        return prepared

    prepared["html"] = cleaned_html
    prepared["text"] = manuscript_html_to_text(cleaned_html) or str(prepared.get("text") or "")
    incoming_images = list(prepared.get("images") or [])
    retained_existing_images = [
        image
        for image in incoming_images
        if image.get("storage_key") and str(image.get("marker") or "") in retained_markers
    ]
    fresh_images = [image for image in incoming_images if image.get("bytes")]
    prepared["images"] = [*retained_existing_images, *extracted_images, *fresh_images]
    return prepared


async def _sync_chapter_media(db, book: Book, chapter: Chapter, ch_data: dict) -> None:
    images = ch_data.get("images") or []
    await db.execute(delete(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id))
    if not images:
        return

    for index, image in enumerate(images):
        raw = image.get("bytes")
        marker = image.get("marker")
        storage_key = str(image.get("storage_key") or "")
        if not marker:
            continue
        if raw:
            filename = image.get("filename") or f"{uuid.uuid4().hex}.bin"
            storage_key = f"chapter-media/{book.id}/{chapter.number}/{index}-{filename}"
            await asyncio.to_thread(upload_binary, storage_key, raw, image.get("content_type"))
        elif not storage_key:
            continue
        db.add(
            ChapterMedia(
                book_id=book.id,
                chapter_id=chapter.id,
                marker=marker,
                asset_type=image.get("asset_type") or "image",
                content_type=image.get("content_type"),
                storage_key=storage_key,
                caption=image.get("caption"),
                sort_order=index,
            )
        )


async def _ensure_chapter_stub(
    db,
    book: Book,
    ch_data: dict,
    *,
    s3_key: str,
    existing_chapter_map: dict[int, Chapter] | None = None,
) -> None:
    if existing_chapter_map is not None:
        existing = existing_chapter_map.get(int(ch_data["number"]))
    else:
        existing = (
            await db.execute(
                select(Chapter).where(
                    Chapter.book_id == book.id, Chapter.number == ch_data["number"]
                )
            )
        ).scalar()

    if existing is None:
        db.add(
            Chapter(
                book_id=book.id,
                number=ch_data["number"],
                title=ch_data.get("title"),
                description=ch_data.get("description"),
                chapter_kind=normalize_chapter_kind(
                    ch_data.get("chapter_kind") or ch_data.get("section_type")
                ),
                s3_key=s3_key,
                token_count=count_tokens(ch_data["text"]),
                word_count=_count_words(ch_data.get("text", "")),
                processed=False,
            )
        )
        await db.flush()
        return

    changed = False
    if ch_data.get("title") and (not existing.title or not existing.title.strip()):
        existing.title = ch_data["title"]
        changed = True
    if ch_data.get("description") and (
        not existing.description or not existing.description.strip()
    ):
        existing.description = ch_data["description"]
        changed = True
    next_chapter_kind = normalize_chapter_kind(
        ch_data.get("chapter_kind") or ch_data.get("section_type")
    )
    if next_chapter_kind != existing.chapter_kind:
        existing.chapter_kind = next_chapter_kind
        changed = True
    if ch_data.get("text") and not existing.token_count:
        existing.token_count = count_tokens(ch_data["text"])
        changed = True
    if s3_key and existing.s3_key != s3_key:
        existing.s3_key = s3_key
        changed = True
    next_word_count = _count_words(ch_data.get("text", ""))
    if next_word_count and existing.word_count != next_word_count:
        existing.word_count = next_word_count
        changed = True
    if changed:
        await db.flush()
