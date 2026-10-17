from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    cache_del,
    cache_set_version_marker,
    key_public_book_detail,
    key_public_books,
    key_public_chapter,
    key_public_forum_cache_version,
    mark_public_catalog_cache_dirty,
    mark_public_profile_cache_dirty,
)
from app.models.book import (
    Book,
)
from app.models.moderation import ContentReport, CreatorStrike, ModerationAction
from app.models.user import User
from app.utils.public.serialization import can_view_public_book, is_admin_user

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


def _allowed_public_report_hosts() -> set[str]:
    try:
        configured_host = (urlparse(settings.APP_URL).hostname or "").strip().lower().rstrip(".")
    except ValueError:
        configured_host = ""
    if not configured_host:
        return set()
    allowed_hosts = {configured_host}
    if configured_host.startswith("www."):
        allowed_hosts.add(configured_host[4:])
    else:
        allowed_hosts.add(f"www.{configured_host}")
    return {host for host in allowed_hosts if host}


async def active_serious_strike_count(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    now = datetime.now(UTC)
    result = await db.execute(
        select(func.count(CreatorStrike.id)).where(
            CreatorStrike.user_id == user_id,
            CreatorStrike.is_active.is_(True),
            CreatorStrike.severity.in_(list(SERIOUS_STRIKE_SEVERITIES)),
            or_(CreatorStrike.expires_at.is_(None), CreatorStrike.expires_at > now),
        )
    )
    return int(result.scalar_one() or 0)


async def public_publish_limit_for_user(db: AsyncSession, *, user: User) -> int:
    if is_admin_user(user):
        return PUBLIC_PUBLISH_LIMIT_STANDARD
    serious_strikes = await active_serious_strike_count(db, user_id=user.id)
    if serious_strikes >= 3:
        raise HTTPException(
            403, "Public publishing is disabled for this account due to repeated policy violations."
        )
    if serious_strikes >= 2:
        raise HTTPException(
            403, "Public publishing is temporarily disabled for this account pending review."
        )
    user_book_count = int(
        (
            await db.execute(
                select(func.count(Book.id)).where(
                    Book.user_id == user.id,
                    Book.mode == "author",
                )
            )
        ).scalar_one()
        or 0
    )
    return PUBLIC_PUBLISH_LIMIT_NEW_USER if user_book_count <= 1 else PUBLIC_PUBLISH_LIMIT_STANDARD


async def enforce_daily_public_publish_limit(db: AsyncSession, *, user: User) -> None:
    limit = await public_publish_limit_for_user(db, user=user)
    since = datetime.now(UTC) - timedelta(days=1)
    published_count = int(
        (
            await db.execute(
                select(func.count(Book.id)).where(
                    Book.user_id == user.id,
                    Book.public_upload_counted_at.is_not(None),
                    Book.public_upload_counted_at >= since,
                )
            )
        ).scalar_one()
        or 0
    )
    if published_count >= limit:
        raise HTTPException(
            429,
            f"Daily public publishing limit reached. You can publish up to {limit} public book(s) per day.",
        )


def ensure_content_source_allowed_for_user(user: User, content_source_type: str) -> str:
    normalized = str(content_source_type or "").strip().lower()
    if normalized not in VALID_CONTENT_SOURCE_TYPES:
        raise HTTPException(400, "Invalid content source type.")
    if normalized != CONTENT_SOURCE_TYPE_USER_ORIGINAL and not is_admin_user(user):
        raise HTTPException(
            403, "Only admins can publish public-domain, licensed, or admin-seeded books."
        )
    return normalized


def ensure_report_type_supported(report_type: str) -> str:
    normalized = str(report_type or "").strip().lower()
    if normalized not in VALID_REPORT_TYPES:
        raise HTTPException(400, "Invalid report type.")
    return normalized


def validate_public_content_report_target(
    book: Book | None, reported_content_url: str | None
) -> str | None:
    if not can_view_public_book(book):
        raise HTTPException(404, "Book not found")
    normalized_url = " ".join(str(reported_content_url or "").split()).strip()
    if not normalized_url:
        return None
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, "Reported content URL must be a LoreVia public book URL.")
    parsed_host = (parsed.hostname or "").strip().lower().rstrip(".")
    if parsed_host not in _allowed_public_report_hosts():
        raise HTTPException(400, "Reported content URL must be a LoreVia public book URL.")
    expected_identifiers = {str(book.id)}
    public_slug = str(getattr(book, "public_slug", "") or "").strip().lower()
    if public_slug:
        expected_identifiers.add(public_slug)
    path_parts = {part.strip().lower() for part in parsed.path.split("/") if part.strip()}
    if not any(identifier.lower() in path_parts for identifier in expected_identifiers):
        raise HTTPException(400, "Reported content URL does not match the selected public book.")
    return normalized_url


async def ensure_public_content_report_not_duplicate(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    report_type: str,
    reporter_ip_hash: str | None,
) -> None:
    if not reporter_ip_hash:
        return
    existing = (
        await db.execute(
            select(ContentReport.id).where(
                ContentReport.reported_book_id == book_id,
                ContentReport.report_type == report_type,
                ContentReport.reporter_ip_hash == reporter_ip_hash,
                ContentReport.created_at >= datetime.now(UTC) - timedelta(hours=24),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            409, "A report for this public book has already been submitted recently."
        )


async def invalidate_public_book_caches(book: Book) -> None:
    await cache_del(key_public_books())
    await mark_public_catalog_cache_dirty()
    await cache_del(key_public_book_detail(str(book.id)))
    for chapter_number in range(1, int(getattr(book, "total_chapters", 0) or 0) + 1):
        await cache_del(key_public_chapter(str(book.id), chapter_number))
    await mark_public_profile_cache_dirty(str(book.user_id))
    await cache_set_version_marker(key_public_forum_cache_version())


async def add_moderation_action(
    db: AsyncSession,
    *,
    action_type: str,
    actor_user_id: uuid.UUID | None = None,
    target_user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
    previous_status: str | None = None,
    new_status: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> ModerationAction:
    action = ModerationAction(
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        book_id=book_id,
        report_id=report_id,
        action_type=action_type,
        previous_status=previous_status,
        new_status=new_status,
        reason=reason,
        metadata_json=metadata or {},
    )
    db.add(action)
    await db.flush()
    return action
