from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    Chapter,
    PublicBookAnalyticsEvent,
)
from app.schemas.public import (
    PublicAuthorAnalyticsOut,
    PublicBookAnalyticsOut,
    PublicBookOut,
    PublicUploadsBreakdownEntryOut,
    PublicUploadsOverviewOut,
)
from app.utils.public.catalog import (
    _book_word_counts,
    _creator_public_book_forum_stats_map,
    list_visible_creator_public_books,
)
from app.utils.public.requests import (
    build_public_visitor_fingerprint,
)
from app.utils.public.serialization import (
    build_public_book_out,
    can_view_public_book,
    normalize_public_analytics_event_type,
)

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


async def list_visible_creator_public_book_outs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
) -> list[PublicBookOut]:
    rows = await list_visible_creator_public_books(db, user_id=user_id)
    book_ids = [book.id for book, _username in rows]
    forum_stats = await _creator_public_book_forum_stats_map(db, book_ids=book_ids)
    analytics_map = await build_public_book_analytics_map(db, book_ids=book_ids)
    return [
        build_public_book_out(
            book,
            author_username=username,
            active_forum_post_id=forum_stats.get(book.id, {}).get("active_forum_post_id"),
            analytics=analytics_map.get(book.id),
        )
        for book, username in rows
    ]


async def build_public_book_analytics_map(
    db: AsyncSession,
    *,
    book_ids: list[uuid.UUID],
) -> dict[uuid.UUID, PublicBookAnalyticsOut]:
    if not book_ids:
        return {}

    base_map = {book_id: PublicBookAnalyticsOut() for book_id in book_ids}
    counts = (
        await db.execute(
            select(
                PublicBookAnalyticsEvent.book_id,
                func.sum(
                    case(
                        (
                            PublicBookAnalyticsEvent.event_type == PUBLIC_ANALYTICS_EVENT_BOOK_VIEW,
                            1,
                        ),
                        else_=0,
                    )
                ).label("book_view_count"),
                func.sum(
                    case(
                        (
                            PublicBookAnalyticsEvent.event_type
                            == PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW,
                            1,
                        ),
                        else_=0,
                    )
                ).label("chapter_view_count"),
            )
            .where(PublicBookAnalyticsEvent.book_id.in_(book_ids))
            .group_by(PublicBookAnalyticsEvent.book_id)
        )
    ).all()
    for book_id, book_view_count, chapter_view_count in counts:
        payload = base_map.setdefault(book_id, PublicBookAnalyticsOut())
        payload.book_view_count = int(book_view_count or 0)
        payload.chapter_view_count = int(chapter_view_count or 0)

    unique_since = datetime.now(UTC).date() - timedelta(days=29)
    unique_counts = (
        await db.execute(
            select(
                PublicBookAnalyticsEvent.book_id,
                func.count(func.distinct(PublicBookAnalyticsEvent.visitor_fingerprint_hash)).label(
                    "unique_reader_count_30d"
                ),
            )
            .where(
                PublicBookAnalyticsEvent.book_id.in_(book_ids),
                PublicBookAnalyticsEvent.event_date >= unique_since,
            )
            .group_by(PublicBookAnalyticsEvent.book_id)
        )
    ).all()
    for book_id, unique_reader_count in unique_counts:
        payload = base_map.setdefault(book_id, PublicBookAnalyticsOut())
        payload.unique_reader_count_30d = int(unique_reader_count or 0)

    return base_map


async def build_public_book_analytics(
    db: AsyncSession,
    *,
    book: Book,
) -> PublicBookAnalyticsOut:
    analytics_map = await build_public_book_analytics_map(db, book_ids=[book.id])
    word_counts = await _book_word_counts(db, book_ids=[book.id])
    forum_stats = await _creator_public_book_forum_stats_map(db, book_ids=[book.id])
    book_forum_stats = forum_stats.get(book.id, {})
    base = analytics_map.get(book.id, PublicBookAnalyticsOut())
    return PublicBookAnalyticsOut(
        book_view_count=base.book_view_count,
        unique_reader_count_30d=base.unique_reader_count_30d,
        chapter_view_count=base.chapter_view_count,
        published_at=getattr(book, "published_at", None),
        chapter_count=int(book.total_chapters or 0),
        total_words=word_counts.get(book.id, 0),
        has_open_discussion=bool(book_forum_stats.get("has_open_discussion", False)),
        open_discussion_count=int(book_forum_stats.get("open_discussion_count", 0) or 0),
        discussion_comment_count=int(book_forum_stats.get("discussion_comment_count", 0) or 0),
        discussion_interest_count=int(book_forum_stats.get("discussion_interest_count", 0) or 0),
    )


async def build_public_author_analytics(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> tuple[list[PublicBookOut], PublicAuthorAnalyticsOut]:
    rows = await list_visible_creator_public_books(db, user_id=user_id)
    book_ids = [book.id for book, _username in rows]
    forum_stats = await _creator_public_book_forum_stats_map(db, book_ids=book_ids)
    word_counts = await _book_word_counts(db, book_ids=book_ids)
    analytics_map = await build_public_book_analytics_map(db, book_ids=book_ids)
    unique_since = datetime.now(UTC).date() - timedelta(days=29)
    public_books = [
        build_public_book_out(
            book,
            author_username=username,
            active_forum_post_id=forum_stats.get(book.id, {}).get("active_forum_post_id"),
            analytics=analytics_map.get(book.id),
        )
        for book, username in rows
    ]
    latest_published_at = max(
        (
            getattr(book, "published_at", None)
            for book, _username in rows
            if getattr(book, "published_at", None) is not None
        ),
        default=None,
    )
    total_unique_readers_30d = 0
    if book_ids:
        total_unique_readers_30d = int(
            (
                await db.execute(
                    select(
                        func.count(func.distinct(PublicBookAnalyticsEvent.visitor_fingerprint_hash))
                    ).where(
                        PublicBookAnalyticsEvent.book_id.in_(book_ids),
                        PublicBookAnalyticsEvent.event_date >= unique_since,
                    )
                )
            ).scalar_one()
            or 0
        )
    analytics = PublicAuthorAnalyticsOut(
        total_book_views=sum(
            int(analytics_map.get(book.id, PublicBookAnalyticsOut()).book_view_count or 0)
            for book, _username in rows
        ),
        total_unique_readers_30d=total_unique_readers_30d,
        total_chapter_views=sum(
            int(analytics_map.get(book.id, PublicBookAnalyticsOut()).chapter_view_count or 0)
            for book, _username in rows
        ),
        total_public_books=len(rows),
        total_chapters=sum(int(book.total_chapters or 0) for book, _username in rows),
        total_words=sum(word_counts.get(book.id, 0) for book, _username in rows),
        latest_published_at=latest_published_at,
        open_forum_discussions_count=sum(
            int(forum_stats.get(book.id, {}).get("open_discussion_count", 0) or 0)
            for book, _username in rows
        ),
    )
    return public_books, analytics


async def record_public_book_analytics_event(
    db: AsyncSession,
    *,
    book: Book,
    request: Request,
    event_type: str,
    chapter_number: int | None = None,
) -> bool:
    if not can_view_public_book(book):
        raise HTTPException(404, "Public book not found")
    normalized_event_type = normalize_public_analytics_event_type(event_type)
    if normalized_event_type == PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW:
        if chapter_number is None:
            raise HTTPException(400, "Chapter number is required for chapter analytics events.")
        chapter_exists = (
            await db.execute(
                select(Chapter.id).where(
                    Chapter.book_id == book.id,
                    Chapter.number == chapter_number,
                )
            )
        ).scalar_one_or_none()
        if chapter_exists is None:
            raise HTTPException(404, "Chapter not found")
    else:
        chapter_number = 0

    visitor_fingerprint_hash = build_public_visitor_fingerprint(request)
    if not visitor_fingerprint_hash:
        return False

    inserted_event_id = (
        await db.execute(
            pg_insert(PublicBookAnalyticsEvent)
            .values(
                id=uuid.uuid4(),
                book_id=book.id,
                chapter_number=chapter_number,
                event_type=normalized_event_type,
                visitor_fingerprint_hash=visitor_fingerprint_hash,
                event_date=datetime.now(UTC).date(),
            )
            .on_conflict_do_nothing(
                constraint="uq_public_book_analytics_events_daily_fingerprint",
            )
            .returning(PublicBookAnalyticsEvent.id)
        )
    ).scalar_one_or_none()
    return inserted_event_id is not None


async def build_public_uploads_overview(db: AsyncSession) -> PublicUploadsOverviewOut:
    rows = await list_visible_creator_public_books(db)
    public_books = []
    book_ids = [book.id for book, _username in rows]
    forum_stats = await _creator_public_book_forum_stats_map(db, book_ids=book_ids)
    word_counts = await _book_word_counts(db, book_ids=book_ids)
    now = datetime.now(UTC)
    genre_counts: dict[str, int] = {}
    work_type_counts: dict[str, int] = {}

    for book, username in rows:
        public_books.append(
            build_public_book_out(
                book,
                author_username=username,
                active_forum_post_id=forum_stats.get(book.id, {}).get("active_forum_post_id"),
            )
        )
        genre_label = (book.genre or "Unspecified").strip() or "Unspecified"
        work_type_label = (book.work_type or "other").strip() or "other"
        genre_counts[genre_label] = genre_counts.get(genre_label, 0) + 1
        work_type_counts[work_type_label] = work_type_counts.get(work_type_label, 0) + 1

    return PublicUploadsOverviewOut(
        total_public_books=len(rows),
        total_authors=len({str(book.user_id) for book, _username in rows}),
        total_visible_chapters=sum(int(book.total_chapters or 0) for book, _username in rows),
        total_visible_words=sum(word_counts.get(book.id, 0) for book, _username in rows),
        uploads_last_30_days=sum(
            1
            for book, _username in rows
            if getattr(book, "published_at", None) is not None
            and getattr(book, "published_at") >= (now - timedelta(days=30))
        ),
        genre_breakdown=[
            PublicUploadsBreakdownEntryOut(
                key=label.lower().replace(" ", "-"), label=label, count=count
            )
            for label, count in sorted(
                genre_counts.items(), key=lambda item: (-item[1], item[0].lower())
            )
        ],
        work_type_breakdown=[
            PublicUploadsBreakdownEntryOut(
                key=label.lower().replace(" ", "-"), label=label, count=count
            )
            for label, count in sorted(
                work_type_counts.items(), key=lambda item: (-item[1], item[0].lower())
            )
        ],
        recent_uploads=public_books[:8],
    )
