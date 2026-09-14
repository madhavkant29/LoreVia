from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    cache_del,
    key_public_book_detail,
    key_public_books,
    key_public_chapter,
    mark_public_catalog_cache_dirty,
    mark_public_profile_cache_dirty,
)
from app.core.storage import upload_text
from app.models.book import (
    Book,
    Chapter,
)
from app.models.user import User
from app.parsers.chunker import count_tokens
from app.schemas.public import (
    PublicBookCreateOut,
    PublicBookManualIn,
    PublicChapterAppendOut,
    PublicChapterIn,
)
from app.services.public_asset_service import publish_public_book_assets
from app.utils.public.serialization import ensure_public_mode_enabled, is_public_demo_book

FORUM_POST_OPEN = "open"
FORUM_POST_CLOSED = "closed"
VALID_FORUM_POST_STATUSES = {FORUM_POST_OPEN, FORUM_POST_CLOSED}
FORUM_THREAD_TYPE_NOVEL = "novel"
FORUM_THREAD_TYPE_GENERAL = "general"
VALID_FORUM_THREAD_TYPES = {FORUM_THREAD_TYPE_NOVEL, FORUM_THREAD_TYPE_GENERAL}
FORUM_COMMENT_REACTION_LIKE = "like"
FORUM_COMMENT_REACTION_DISLIKE = "dislike"
FORUM_COMMENT_REACTION_CLEAR = "clear"
VALID_FORUM_COMMENT_REACTIONS = {
    FORUM_COMMENT_REACTION_LIKE,
    FORUM_COMMENT_REACTION_DISLIKE,
    FORUM_COMMENT_REACTION_CLEAR,
}
PUBLIC_DEMO_SOURCE_KIND = "public_demo"
USER_PUBLIC_SHARE_SOURCE_KIND = "user_public_share"
PUBLIC_FORUM_STATUS_DISABLED = "disabled"
PUBLIC_FORUM_STATUS_INTERNAL = "internal"
PUBLIC_FORUM_STATUS_BETA = "beta"
PUBLIC_FORUM_STATUS_PUBLIC = "public"
PUBLIC_SHARE_STATUS_NOT_REQUESTED = "not_requested"
PUBLIC_SHARE_STATUS_PENDING = "pending"
PUBLIC_SHARE_STATUS_APPROVED = "approved"
VALID_PUBLIC_FORUM_STATUSES = {
    PUBLIC_FORUM_STATUS_DISABLED,
    PUBLIC_FORUM_STATUS_INTERNAL,
    PUBLIC_FORUM_STATUS_BETA,
    PUBLIC_FORUM_STATUS_PUBLIC,
}
VALID_PUBLIC_SHARE_STATUSES = {
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    PUBLIC_SHARE_STATUS_APPROVED,
}
DEFAULT_PUBLIC_FORUM_PAGE_SIZE = 20
MAX_PUBLIC_FORUM_PAGE_SIZE = 100
GENERAL_PUBLIC_FORUM_DAILY_POST_LIMIT = 5
MAX_PUBLIC_FORUM_IMAGE_BYTES = 5 * 1024 * 1024
PUBLIC_STATUS_DRAFT = "draft"
PUBLIC_STATUS_PENDING_REVIEW = "pending_review"
PUBLIC_STATUS_PUBLISHED = "published"
PUBLIC_STATUS_HIDDEN = "hidden"
PUBLIC_STATUS_REMOVED = "removed"
MODERATION_STATUS_CLEAN = "clean"
MODERATION_STATUS_REPORTED = "reported"
MODERATION_STATUS_UNDER_REVIEW = "under_review"
MODERATION_STATUS_HIDDEN = "hidden"
MODERATION_STATUS_REMOVED = "removed"
CONTENT_SOURCE_TYPE_USER_ORIGINAL = "user_original"
CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN = "public_domain"
CONTENT_SOURCE_TYPE_LICENSED = "licensed"
CONTENT_SOURCE_TYPE_ADMIN_SEEDED = "admin_seeded"
REPORT_TYPE_COPYRIGHT = "copyright"
REPORT_TYPE_PLAGIARISM = "plagiarism"
REPORT_TYPE_IMPERSONATION = "impersonation"
REPORT_TYPE_SPAM = "spam"
REPORT_TYPE_ILLEGAL_CONTENT = "illegal_content"
REPORT_TYPE_HARASSMENT = "harassment"
REPORT_TYPE_OTHER = "other"
REPORT_STATUS_OPEN = "open"
REPORT_STATUS_TRIAGED = "triaged"
REPORT_STATUS_CONTENT_HIDDEN = "content_hidden"
REPORT_STATUS_REJECTED = "rejected"
REPORT_STATUS_RESOLVED = "resolved"
STRIKE_SEVERITY_LOW = "low"
STRIKE_SEVERITY_MEDIUM = "medium"
STRIKE_SEVERITY_HIGH = "high"
STRIKE_SEVERITY_CRITICAL = "critical"
VALID_PUBLIC_STATUSES = {
    PUBLIC_STATUS_DRAFT,
    PUBLIC_STATUS_PENDING_REVIEW,
    PUBLIC_STATUS_PUBLISHED,
    PUBLIC_STATUS_HIDDEN,
    PUBLIC_STATUS_REMOVED,
}
VALID_MODERATION_STATUSES = {
    MODERATION_STATUS_CLEAN,
    MODERATION_STATUS_REPORTED,
    MODERATION_STATUS_UNDER_REVIEW,
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REMOVED,
}
VALID_CONTENT_SOURCE_TYPES = {
    CONTENT_SOURCE_TYPE_USER_ORIGINAL,
    CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN,
    CONTENT_SOURCE_TYPE_LICENSED,
    CONTENT_SOURCE_TYPE_ADMIN_SEEDED,
}
VALID_REPORT_TYPES = {
    REPORT_TYPE_COPYRIGHT,
    REPORT_TYPE_PLAGIARISM,
    REPORT_TYPE_IMPERSONATION,
    REPORT_TYPE_SPAM,
    REPORT_TYPE_ILLEGAL_CONTENT,
    REPORT_TYPE_HARASSMENT,
    REPORT_TYPE_OTHER,
}
VALID_REPORT_STATUSES = {
    REPORT_STATUS_OPEN,
    REPORT_STATUS_TRIAGED,
    REPORT_STATUS_CONTENT_HIDDEN,
    REPORT_STATUS_REJECTED,
    REPORT_STATUS_RESOLVED,
}
SERIOUS_STRIKE_SEVERITIES = {STRIKE_SEVERITY_HIGH, STRIKE_SEVERITY_CRITICAL}
PUBLIC_PUBLISH_LIMIT_NEW_USER = 1
PUBLIC_PUBLISH_LIMIT_STANDARD = 3
PUBLIC_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PUBLIC_ANALYTICS_EVENT_BOOK_VIEW = "book_view"
PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW = "chapter_view"
VALID_PUBLIC_ANALYTICS_EVENT_TYPES = {
    PUBLIC_ANALYTICS_EVENT_BOOK_VIEW,
    PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW,
}
PUBLIC_FORUM_IMAGE_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG": ("png", "image/png"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),
}


def normalize_public_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if len(slug) < 3 or len(slug) > 120 or not PUBLIC_SLUG_PATTERN.fullmatch(slug):
        raise HTTPException(
            400,
            "Public slug must be 3-120 characters and use lowercase letters, numbers, or hyphens.",
        )
    return slug


async def create_public_demo_book(
    db: AsyncSession,
    *,
    admin_user: User,
    body: PublicBookManualIn,
) -> tuple[Book, PublicBookCreateOut]:
    ensure_public_mode_enabled()
    if not body.chapters:
        raise HTTPException(400, "At least one chapter is required")

    public_slug = normalize_public_slug(body.title)
    existing = (
        await db.execute(select(Book.id).where(Book.public_slug == public_slug))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, "A public book with that slug already exists.")

    book = Book(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        title=body.title,
        author=body.author,
        genre=body.genre,
        format="manual",
        s3_key=f"public/manual/{admin_user.id}/{body.title}".replace(" ", "-").lower(),
        status="ready",
        is_public=True,
        source_kind=PUBLIC_DEMO_SOURCE_KIND,
        public_status=PUBLIC_STATUS_PUBLISHED,
        public_slug=public_slug,
        published_at=datetime.now(UTC),
        public_visibility="public",
        content_source_type=CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN,
        moderation_status=MODERATION_STATUS_CLEAN,
        source_title=body.title,
        source_author=body.author,
        source_public_domain_note="Public-domain demo book used to showcase LoreVia features.",
        public_description=body.description,
    )
    db.add(book)
    await db.flush()

    total_tokens = 0
    for index, chapter_in in enumerate(body.chapters, start=1):
        chapter_token_count = count_tokens(chapter_in.text)
        chapter_key = f"public_chapters/{book.id}/{index}.txt"
        await asyncio.to_thread(upload_text, chapter_key, chapter_in.text)
        total_tokens += chapter_token_count
        db.add(
            Chapter(
                book_id=book.id,
                number=index,
                title=chapter_in.title,
                description=chapter_in.description,
                s3_key=chapter_key,
                token_count=chapter_token_count,
                processed=False,
            )
        )

    book.total_chapters = len(body.chapters)
    book.total_tokens = total_tokens
    await db.flush()
    await publish_public_book_assets(db, book=book)
    await cache_del(key_public_books())
    await mark_public_catalog_cache_dirty()
    await mark_public_profile_cache_dirty(str(book.user_id))
    return book, PublicBookCreateOut(
        book_id=str(book.id),
        status="ready",
        visibility="public",
        public_kind=PUBLIC_DEMO_SOURCE_KIND,
        approval_status=PUBLIC_SHARE_STATUS_APPROVED,
        public_slug=book.public_slug,
        message="Public demo is live.",
    )


async def append_public_demo_book_chapter(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    body: PublicChapterIn,
) -> tuple[Book, PublicChapterAppendOut]:
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not is_public_demo_book(book):
        raise HTTPException(404, "Public book not found")

    next_number = (
        await db.execute(
            select(func.coalesce(func.max(Chapter.number), 0) + 1).where(Chapter.book_id == book.id)
        )
    ).scalar_one()
    token_count = count_tokens(body.text)
    chapter_key = f"public_chapters/{book.id}/{next_number}.txt"
    await asyncio.to_thread(upload_text, chapter_key, body.text)
    db.add(
        Chapter(
            book_id=book.id,
            number=next_number,
            title=body.title,
            description=body.description,
            s3_key=chapter_key,
            token_count=token_count,
            processed=False,
        )
    )
    book.total_chapters = next_number
    book.total_tokens = (book.total_tokens or 0) + token_count
    await db.flush()
    await publish_public_book_assets(db, book=book)
    await cache_del(key_public_book_detail(str(book.id)))
    await cache_del(key_public_chapter(str(book.id), next_number))
    await cache_del(key_public_books())
    await mark_public_catalog_cache_dirty()
    await mark_public_profile_cache_dirty(str(book.user_id))
    return book, PublicChapterAppendOut(
        book_id=str(book.id),
        chapter_number=next_number,
        saved=True,
    )


async def create_public_book_manual(
    db: AsyncSession,
    *,
    body: PublicBookManualIn,
    admin_user: User,
) -> dict[str, object]:
    ensure_public_mode_enabled()
    if not body.chapters:
        raise HTTPException(400, "At least one chapter is required")

    public_slug = normalize_public_slug(body.title)
    existing = (
        await db.execute(select(Book.id).where(Book.public_slug == public_slug))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, "A public book with that slug already exists.")

    book = Book(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        title=body.title,
        author=body.author,
        genre=body.genre,
        format="manual",
        s3_key=f"public/manual/{admin_user.id}/{body.title}".replace(" ", "-").lower(),
        status="ready",
        is_public=True,
        source_kind=PUBLIC_DEMO_SOURCE_KIND,
        public_status=PUBLIC_STATUS_PUBLISHED,
        public_slug=public_slug,
        published_at=datetime.now(UTC),
        public_visibility="public",
        content_source_type=CONTENT_SOURCE_TYPE_ADMIN_SEEDED,
        moderation_status=MODERATION_STATUS_CLEAN,
        source_title=body.title,
        source_author=body.author,
        source_public_domain_note="Public-domain demo book used to showcase LoreVia features.",
        public_description=body.description,
    )
    db.add(book)
    await db.flush()

    total_tokens = 0
    for index, chapter_in in enumerate(body.chapters, start=1):
        chapter_token_count = count_tokens(chapter_in.text)
        chapter_key = f"public_chapters/{book.id}/{index}.txt"
        await asyncio.to_thread(upload_text, chapter_key, chapter_in.text)
        total_tokens += chapter_token_count
        db.add(
            Chapter(
                book_id=book.id,
                number=index,
                title=chapter_in.title,
                description=chapter_in.description,
                s3_key=chapter_key,
                token_count=chapter_token_count,
                processed=False,
            )
        )

    book.total_chapters = len(body.chapters)
    book.total_tokens = total_tokens
    await db.flush()
    await publish_public_book_assets(db, book=book)
    await cache_del(key_public_books())
    await mark_public_catalog_cache_dirty()
    await mark_public_profile_cache_dirty(str(book.user_id))
    return {
        "book_id": str(book.id),
        "status": "ready",
        "visibility": "public",
        "public_kind": PUBLIC_DEMO_SOURCE_KIND,
        "approval_status": "approved",
        "public_slug": book.public_slug,
        "message": "Public demo is live.",
    }


async def append_public_chapter(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    body: PublicChapterIn,
    admin_user: User,
) -> dict[str, object]:
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not is_public_demo_book(book) or getattr(book, "user_id", None) != getattr(
        admin_user, "id", None
    ):
        raise HTTPException(404, "Public book not found")

    next_number = (
        await db.execute(
            select(func.coalesce(func.max(Chapter.number), 0) + 1).where(Chapter.book_id == book.id)
        )
    ).scalar_one()
    token_count = count_tokens(body.text)
    chapter_key = f"public_chapters/{book.id}/{next_number}.txt"
    await asyncio.to_thread(upload_text, chapter_key, body.text)
    db.add(
        Chapter(
            book_id=book.id,
            number=next_number,
            title=body.title,
            description=body.description,
            s3_key=chapter_key,
            token_count=token_count,
            processed=False,
        )
    )
    book.total_chapters = next_number
    book.total_tokens = (book.total_tokens or 0) + token_count
    await db.flush()
    await publish_public_book_assets(db, book=book)
    await cache_del(key_public_book_detail(str(book.id)))
    await cache_del(key_public_chapter(str(book.id), next_number))
    await cache_del(key_public_books())
    await mark_public_catalog_cache_dirty()
    await mark_public_profile_cache_dirty(str(book.user_id))
    return {
        "book_id": str(book.id),
        "chapter_number": next_number,
        "saved": True,
    }
