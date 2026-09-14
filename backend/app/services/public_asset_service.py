"""Versioned public chapter assets and their revocation lifecycle."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.core.redis import cache_del, key_public_chapter
from app.models.book import Book, Chapter
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.public.serialization import can_view_public_book
from app.utils.storage_utils import (
    STORAGE_IO_EXCEPTIONS,
    bounded_storage_map,
    delete_storage_keys_best_effort,
)

log = logging.getLogger("lorevia.public_assets")
PUBLIC_ASSET_PREFIX = "public-assets"


class PublicAssetRevocationError(RuntimeError):
    """Raised when a privacy transition cannot revoke every direct public asset."""


def direct_public_assets_available() -> bool:
    return bool(settings.DIRECT_PUBLIC_ASSETS_ENABLED and settings.PUBLIC_ASSET_BASE_URL)


def public_chapter_asset_key(book_id: object, chapter_id: object, content_version: int) -> str:
    return f"{PUBLIC_ASSET_PREFIX}/{book_id}/{chapter_id}/v{max(int(content_version), 1)}.txt"


def public_asset_url(storage_key: str) -> str | None:
    if not direct_public_assets_available():
        return None
    base_url = str(settings.PUBLIC_ASSET_BASE_URL or "").rstrip("/")
    return f"{base_url}/{quote(storage.validate_storage_key(storage_key), safe='/')}"


def public_chapter_content_url(book: Book, chapter: Chapter) -> str | None:
    if not direct_public_assets_available() or not can_view_public_book(book):
        return None
    content_version = max(int(chapter.content_version or 1), 1)
    if int(getattr(chapter, "public_asset_version", 0) or 0) != content_version:
        return None
    return public_asset_url(
        public_chapter_asset_key(book.id, chapter.id, content_version)
    )


async def publish_public_chapter_asset(
    *,
    book: Book,
    chapter: Chapter,
    db: AsyncSession | None = None,
) -> str | None:
    if not direct_public_assets_available() or not can_view_public_book(book):
        return None
    try:
        raw = await asyncio.to_thread(storage.download_book, chapter.s3_key)
        payload = deserialize_manuscript_content(raw)
        text = str(payload.get("text") or "")
        content_version = max(int(chapter.content_version or 1), 1)
        key = public_chapter_asset_key(book.id, chapter.id, content_version)
        await asyncio.to_thread(
            storage.upload_public_text_asset,
            key,
            text,
            cache_max_age=settings.PUBLIC_ASSET_CACHE_MAX_AGE_SECONDS,
        )
        chapter.public_asset_version = content_version
        if db is not None:
            await db.commit()
        await cache_del(key_public_chapter(str(book.id), int(chapter.number)))
        return key
    except STORAGE_IO_EXCEPTIONS:
        log.exception(
            "public_chapter_asset_publish_failed",
            extra={"book_id": str(book.id), "chapter_id": str(chapter.id)},
        )
        return None


async def publish_public_book_assets(db: AsyncSession, *, book: Book) -> int:
    if not direct_public_assets_available() or not can_view_public_book(book):
        return 0
    chapters = list(
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number)
            )
        )
        .scalars()
        .all()
    )

    async def publish(chapter: Chapter) -> str | None:
        return await publish_public_chapter_asset(book=book, chapter=chapter)

    publish_results = await bounded_storage_map(chapters, publish)
    published_keys = {key for key in publish_results if key is not None}
    await db.commit()
    if len(published_keys) != len(chapters):
        # Keep the last known-good versions when any replacement failed. The
        # hourly backfill will retry without turning a transient storage error
        # into a broken public chapter URL.
        return len(published_keys)
    existing_keys = await asyncio.to_thread(
        storage.list_object_keys,
        f"{PUBLIC_ASSET_PREFIX}/{book.id}",
        limit=10_000,
    )
    obsolete_keys = [key for key in existing_keys if key not in published_keys]
    if obsolete_keys:
        await delete_storage_keys_best_effort(obsolete_keys, context="public_asset_replace")
    return len(published_keys)


async def revoke_public_book_assets(
    book_id: object,
    *,
    db: AsyncSession | None = None,
    strict: bool = False,
) -> int:
    """Delete direct assets, optionally failing a privacy mutation unless all are gone."""
    deleted_count = 0
    max_batches = 100 if strict else 1
    for _batch in range(max_batches):
        try:
            keys = await asyncio.to_thread(
                storage.list_object_keys,
                f"{PUBLIC_ASSET_PREFIX}/{book_id}",
                limit=10_000,
            )
        except STORAGE_IO_EXCEPTIONS as exc:
            log.exception("public_asset_listing_failed", extra={"book_id": str(book_id)})
            if strict:
                raise PublicAssetRevocationError(
                    "Could not verify that public chapter assets were revoked."
                ) from exc
            return deleted_count
        if not keys:
            if db is not None:
                await db.execute(
                    update(Chapter)
                    .where(Chapter.book_id == book_id)
                    .values(public_asset_version=None)
                )
            return deleted_count
        deleted = await delete_storage_keys_best_effort(keys, context="public_asset_revoke")
        deleted_count += len(deleted)
        if strict and len(deleted) != len(keys):
            raise PublicAssetRevocationError(
                "Could not revoke every public chapter asset; the privacy change was not saved."
            )
        if not strict:
            if db is not None and len(deleted) == len(keys):
                await db.execute(
                    update(Chapter)
                    .where(Chapter.book_id == book_id)
                    .values(public_asset_version=None)
                )
            return deleted_count
    raise PublicAssetRevocationError(
        "Public chapter asset revocation exceeded the bounded deletion limit."
    )


async def backfill_public_book_assets_page(
    db: AsyncSession,
    *,
    after_book_id: object | None = None,
    limit: int = 10,
) -> tuple[int, str | None]:
    """Publish one bounded page of existing public books for staged rollout."""
    if not direct_public_assets_available():
        return 0, None
    page_limit = max(1, min(int(limit), 100))
    statement = (
        select(Book)
        .where(
            Book.is_public.is_(True),
            Book.public_status == "published",
            Book.hidden_at.is_(None),
            Book.archived_at.is_(None),
        )
        .order_by(Book.id.asc())
        .limit(page_limit)
    )
    if after_book_id is not None:
        statement = statement.where(Book.id > after_book_id)
    books = list((await db.execute(statement)).scalars().all())
    published = 0
    for book in books:
        published += await publish_public_book_assets(db, book=book)
    next_cursor = str(books[-1].id) if len(books) == page_limit else None
    return published, next_cursor
