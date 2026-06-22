from __future__ import annotations

import re
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    BookForumComment,
    BookForumInterest,
    BookForumPost,
    Chapter,
)
from app.models.user import User
from app.utils.public.content import normalize_public_slug
from app.utils.public.serialization import can_view_public_book, is_visible_creator_public_book

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


async def _book_word_counts(db: AsyncSession, *, book_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not book_ids:
        return {}
    rows = (
        await db.execute(
            select(Chapter.book_id, func.coalesce(func.sum(Chapter.word_count), 0))
            .where(Chapter.book_id.in_(book_ids))
            .group_by(Chapter.book_id)
        )
    ).all()
    return {book_id: int(total_words or 0) for book_id, total_words in rows}


async def _creator_public_book_forum_stats_map(
    db: AsyncSession,
    *,
    book_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[str, int | bool | str | None]]:
    if not book_ids:
        return {}

    comment_subquery = (
        select(
            BookForumComment.post_id.label("post_id"),
            func.count(BookForumComment.id).label("comment_count"),
            func.coalesce(func.sum(BookForumComment.like_count), 0).label("like_count"),
            func.coalesce(func.sum(BookForumComment.dislike_count), 0).label("dislike_count"),
        )
        .group_by(BookForumComment.post_id)
        .subquery()
    )
    interest_subquery = (
        select(
            BookForumInterest.post_id.label("post_id"),
            func.count(BookForumInterest.id).label("interest_count"),
        )
        .group_by(BookForumInterest.post_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(
                BookForumPost.book_id,
                BookForumPost.id,
                BookForumPost.status,
                func.coalesce(comment_subquery.c.comment_count, 0),
                func.coalesce(interest_subquery.c.interest_count, 0),
            )
            .outerjoin(comment_subquery, comment_subquery.c.post_id == BookForumPost.id)
            .outerjoin(interest_subquery, interest_subquery.c.post_id == BookForumPost.id)
            .where(
                BookForumPost.book_id.in_(book_ids),
                BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
            )
            .order_by(BookForumPost.updated_at.desc(), BookForumPost.created_at.desc())
        )
    ).all()

    mapping: dict[uuid.UUID, dict[str, int | bool | str | None]] = {}
    for book_id, post_id, status, comment_count, interest_count in rows:
        existing = mapping.setdefault(
            book_id,
            {
                "active_forum_post_id": None,
                "open_discussion_count": 0,
                "discussion_comment_count": 0,
                "discussion_interest_count": 0,
                "has_open_discussion": False,
            },
        )
        if str(status or "").strip().lower() == FORUM_POST_OPEN:
            existing["open_discussion_count"] = int(existing["open_discussion_count"] or 0) + 1
            existing["has_open_discussion"] = True
            if existing["active_forum_post_id"] is None:
                existing["active_forum_post_id"] = str(post_id)
        existing["discussion_comment_count"] = int(existing["discussion_comment_count"] or 0) + int(
            comment_count or 0
        )
        existing["discussion_interest_count"] = int(
            existing["discussion_interest_count"] or 0
        ) + int(interest_count or 0)
    return mapping


async def list_visible_creator_public_books(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
) -> list[tuple[Book, str | None]]:
    statement = (
        select(Book, User.username)
        .join(User, User.id == Book.user_id)
        .where(
            Book.is_public.is_(True),
            Book.hidden_at.is_(None),
            Book.archived_at.is_(None),
            Book.status.in_(["ready", "processing", "pending"]),
        )
        .order_by(Book.created_at.desc())
    )
    if user_id is not None:
        statement = statement.where(Book.user_id == user_id)
    rows = (await db.execute(statement)).all()
    return [(book, username) for book, username in rows if is_visible_creator_public_book(book)]


def is_catalog_visible_public_book(book: Book | None) -> bool:
    return can_view_public_book(book)


def filter_public_books_catalog(
    books: list[dict],
    source: str,
    catalog_filter: str,
    search_term: str,
) -> list[dict]:
    items = list(books)
    if source:
        items = [
            item
            for item in items
            if str(item.get("content_source_type") or "").strip().lower() == source
        ]
    if search_term:
        items = [
            item
            for item in items
            if search_term
            in " ".join(
                str(item.get(field) or "")
                for field in (
                    "title",
                    "author",
                    "author_username",
                    "genre",
                    "description",
                    "source_title",
                    "source_author",
                )
            ).lower()
        ]
    return items


async def _active_forum_post_map(db: AsyncSession, *, book_ids: list[uuid.UUID]) -> dict[str, str]:
    if not book_ids:
        return {}
    rows = (
        await db.execute(
            select(BookForumPost.book_id, BookForumPost.id)
            .where(
                BookForumPost.book_id.in_(book_ids),
                BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
                BookForumPost.status == FORUM_POST_OPEN,
            )
            .order_by(BookForumPost.updated_at.desc(), BookForumPost.created_at.desc())
        )
    ).all()
    mapping: dict[str, str] = {}
    for book_id, post_id in rows:
        key = str(book_id)
        if key not in mapping:
            mapping[key] = str(post_id)
    return mapping


async def _get_public_book_by_slug_or_id(db: AsyncSession, book_slug: str) -> Book | None:
    if isinstance(book_slug, uuid.UUID):
        return await db.get(Book, book_slug)
    raw_value = str(book_slug or "").strip()
    try:
        return await db.get(Book, uuid.UUID(raw_value))
    except ValueError:
        pass
    try:
        normalized_slug = normalize_public_slug(raw_value)
    except HTTPException:
        return None
    return (
        await db.execute(select(Book).where(Book.public_slug == normalized_slug))
    ).scalar_one_or_none()
