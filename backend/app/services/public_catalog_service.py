"""Bounded, cacheable public catalog read paths."""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, noload

from app.core.redis import (
    cache_get,
    cache_set,
    get_public_catalog_cache_version,
    key_public_book_analytics,
    key_public_catalog_page,
)
from app.models.book import Book
from app.models.user import User
from app.schemas.public import PublicBookAnalyticsOut, PublicBookPageOut
from app.utils.public.analytics import (
    build_public_book_analytics,
    build_public_book_analytics_map,
)
from app.utils.public.catalog import _active_forum_post_map
from app.utils.public.serialization import build_public_book_out
from app.utils.public_utils import (
    MODERATION_STATUS_CLEAN,
    MODERATION_STATUS_REPORTED,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_STATUS_PUBLISHED,
    USER_PUBLIC_SHARE_SOURCE_KIND,
)

DEFAULT_PUBLIC_BOOK_PAGE_LIMIT = 24
MAX_PUBLIC_BOOK_PAGE_LIMIT = 100
PUBLIC_BOOK_ANALYTICS_CACHE_TTL_SECONDS = 120


def encode_public_book_page_cursor(created_at: datetime, book_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(book_id)}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_public_book_page_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        if created_at.tzinfo is None:
            raise ValueError("Cursor timestamp must include a timezone")
        return created_at, uuid.UUID(str(payload["id"]))
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise HTTPException(400, "Invalid public book page cursor") from exc


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_PUBLIC_BOOK_PAGE_LIMIT))


def _normalized_catalog(value: str | None) -> str:
    return str(value or "").strip().lower()


def _normalized_search(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


async def get_public_book_display_analytics(
    db: AsyncSession,
    *,
    book: Book,
) -> PublicBookAnalyticsOut:
    """Cache display-only detail analytics without changing aggregate reads."""
    version = await get_public_catalog_cache_version()
    cache_key = key_public_book_analytics(str(book.id), version)
    cached = await cache_get(cache_key)
    if isinstance(cached, dict):
        try:
            return PublicBookAnalyticsOut.model_validate(cached)
        except (TypeError, ValueError):
            pass
    payload = await build_public_book_analytics(db, book=book)
    await cache_set(
        cache_key,
        payload.model_dump(mode="json"),
        PUBLIC_BOOK_ANALYTICS_CACHE_TTL_SECONDS,
    )
    return payload


def _catalog_statement(
    *,
    content_source_type: str | None,
    catalog: str | None,
    search: str | None,
):
    normalized_catalog = _normalized_catalog(catalog)
    normalized_source = str(content_source_type or "").strip().lower()
    normalized_search = _normalized_search(search)
    statement = (
        select(Book, User.username)
        .options(
            load_only(
                Book.id,
                Book.user_id,
                Book.title,
                Book.author,
                Book.genre,
                Book.format,
                Book.work_type,
                Book.status,
                Book.source_kind,
                Book.total_chapters,
                Book.is_public,
                Book.public_description,
                Book.public_status,
                Book.public_slug,
                Book.published_at,
                Book.public_updated_at,
                Book.moderation_status,
                Book.content_source_type,
                Book.source_title,
                Book.source_author,
                Book.source_public_domain_note,
                Book.source_url,
                Book.public_share_status,
                Book.copyright_warning,
                Book.created_at,
            ),
            noload(Book.vault_note_series_links),
        )
        .join(User, User.id == Book.user_id)
        .where(
            Book.is_public.is_(True),
            Book.hidden_at.is_(None),
            Book.archived_at.is_(None),
            Book.status.in_(["ready", "processing", "pending"]),
            Book.public_status == PUBLIC_STATUS_PUBLISHED,
            or_(
                Book.moderation_status.is_(None),
                Book.moderation_status.in_([MODERATION_STATUS_CLEAN, MODERATION_STATUS_REPORTED]),
            ),
        )
    )
    if normalized_catalog in {"creator_uploads", "creator-only", "creator_only"}:
        statement = statement.where(
            Book.source_kind == USER_PUBLIC_SHARE_SOURCE_KIND,
            or_(
                Book.public_share_status == PUBLIC_SHARE_STATUS_APPROVED,
                Book.public_share_status.is_(None),
                Book.public_share_status == "",
            ),
        )
    if normalized_source:
        statement = statement.where(Book.content_source_type == normalized_source)
    if normalized_search:
        needle = f"%{normalized_search}%"
        statement = statement.where(
            or_(
                Book.title.ilike(needle),
                Book.author.ilike(needle),
                User.username.ilike(needle),
                Book.genre.ilike(needle),
                Book.public_description.ilike(needle),
                Book.source_title.ilike(needle),
                Book.source_author.ilike(needle),
            )
        )
    return statement, normalized_catalog, normalized_source, normalized_search


async def list_public_books_page(
    db: AsyncSession,
    *,
    content_source_type: str | None = None,
    catalog: str | None = None,
    search: str | None = None,
    limit: int = DEFAULT_PUBLIC_BOOK_PAGE_LIMIT,
    cursor: str | None = None,
) -> PublicBookPageOut:
    """Return one public-catalog page and enrich only that page's books."""
    bounded_limit = _bounded_limit(limit)
    statement, normalized_catalog, normalized_source, normalized_search = _catalog_statement(
        content_source_type=content_source_type,
        catalog=catalog,
        search=search,
    )
    cache_key: str | None = None
    if not cursor:
        version = await get_public_catalog_cache_version()
        cache_key = key_public_catalog_page(
            version=version,
            catalog=normalized_catalog,
            content_source_type=normalized_source,
            search=normalized_search,
            limit=bounded_limit,
        )
        cached = await cache_get(cache_key)
        if isinstance(cached, dict):
            return PublicBookPageOut.model_validate(cached)

    if cursor:
        cursor_created_at, cursor_id = decode_public_book_page_cursor(cursor)
        statement = statement.where(
            or_(
                Book.created_at < cursor_created_at,
                and_(Book.created_at == cursor_created_at, Book.id < cursor_id),
            )
        )
    rows = list(
        (
            await db.execute(
                statement.order_by(Book.created_at.desc(), Book.id.desc()).limit(bounded_limit + 1)
            )
        ).all()
    )
    has_more = len(rows) > bounded_limit
    page_rows = rows[:bounded_limit]
    book_ids = [book.id for book, _username in page_rows]
    active_forum_post_ids = await _active_forum_post_map(db, book_ids=book_ids)
    analytics_map = await build_public_book_analytics_map(db, book_ids=book_ids)
    items = [
        build_public_book_out(
            book,
            author_username=username,
            active_forum_post_id=active_forum_post_ids.get(str(book.id)),
            analytics=analytics_map.get(book.id),
        )
        for book, username in page_rows
    ]
    payload = PublicBookPageOut(
        items=items,
        next_cursor=(
            encode_public_book_page_cursor(page_rows[-1][0].created_at, page_rows[-1][0].id)
            if has_more and page_rows
            else None
        ),
        has_more=has_more,
    )
    if cache_key:
        await cache_set(cache_key, payload.model_dump(mode="json"), 300)
    return payload
