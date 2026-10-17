from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import Numeric, and_, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    cache_del,
    cache_set_version_marker,
    key_public_books,
    key_public_forum_cache_version,
    mark_public_catalog_cache_dirty,
    mark_public_profile_cache_dirty,
)
from app.models.beta_read import BetaReadAssignment
from app.models.book import (
    Book,
    BookForumComment,
    BookForumInterest,
    BookForumPost,
    BookForumPostReaction,
)
from app.models.user import User
from app.utils.beta_read_utils import (
    NEUTRAL_RATING_MIN,
    POSITIVE_RATING_MIN,
    RATED_ASSIGNMENT_STATES,
)
from app.utils.public.serialization import (
    can_view_public_book,
    ensure_public_mode_enabled,
    is_approved_user_public_share_book,
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


def get_public_forum_status() -> str:
    status = str(settings.PUBLIC_FORUM_STATUS or PUBLIC_FORUM_STATUS_DISABLED).strip().lower()
    if status not in VALID_PUBLIC_FORUM_STATUSES:
        raise HTTPException(
            500,
            "PUBLIC_FORUM_STATUS must be one of: disabled, internal, beta, public.",
        )
    return status


def ensure_public_forum_read_enabled() -> None:
    ensure_public_mode_enabled()
    status = get_public_forum_status()
    if status in {PUBLIC_FORUM_STATUS_DISABLED, PUBLIC_FORUM_STATUS_INTERNAL}:
        raise HTTPException(404, "Public forum is not available.")


def ensure_public_forum_write_enabled() -> None:
    ensure_public_mode_enabled()
    status = get_public_forum_status()
    if status == PUBLIC_FORUM_STATUS_PUBLIC:
        return
    if status == PUBLIC_FORUM_STATUS_BETA:
        raise HTTPException(403, "Public forum is currently read-only.")
    raise HTTPException(404, "Public forum is not available.")


def public_forum_discoverability_score(
    *,
    average_rating: float | None,
    rating_count: int,
    positive_rating_count: int,
    negative_rating_count: int,
    interest_count: int,
) -> float:
    rating_signal = (average_rating or 0.0) * 100
    volume_signal = min(max(rating_count, 0), 12) * 4
    sentiment_signal = (max(positive_rating_count, 0) * 12) - (max(negative_rating_count, 0) * 9)
    interest_signal = min(max(interest_count, 0), 20) * 2
    return round(rating_signal + volume_signal + sentiment_signal + interest_signal, 2)


def reputation_trust_level(score: int | None) -> str:
    value = int(score or 0)
    if value <= -10:
        return "Low trust"
    if value < 5:
        return "New member"
    if value < 25:
        return "Trusted"
    return "Highly trusted"


def _normalize_forum_status(value: str | None) -> str:
    status = str(value or FORUM_POST_OPEN).strip().lower()
    if status not in VALID_FORUM_POST_STATUSES:
        raise HTTPException(400, "Invalid forum post status.")
    return status


def _normalize_forum_thread_type(value: str | None) -> str:
    thread_type = str(value or FORUM_THREAD_TYPE_NOVEL).strip().lower()
    if thread_type not in VALID_FORUM_THREAD_TYPES:
        raise HTTPException(400, "Invalid forum thread type.")
    return thread_type


def _normalize_forum_comment_reaction(value: str | None) -> str:
    reaction = str(value or "").strip().lower()
    if reaction not in VALID_FORUM_COMMENT_REACTIONS:
        raise HTTPException(400, "Reaction must be like, dislike, or clear.")
    return reaction


def _reaction_score(reaction: str | None) -> int:
    if reaction == FORUM_COMMENT_REACTION_LIKE:
        return 1
    if reaction == FORUM_COMMENT_REACTION_DISLIKE:
        return -1
    return 0


def _reaction_delta(old_reaction: str | None, new_reaction: str | None) -> tuple[int, int, int]:
    old_like = 1 if old_reaction == FORUM_COMMENT_REACTION_LIKE else 0
    new_like = 1 if new_reaction == FORUM_COMMENT_REACTION_LIKE else 0
    old_dislike = 1 if old_reaction == FORUM_COMMENT_REACTION_DISLIKE else 0
    new_dislike = 1 if new_reaction == FORUM_COMMENT_REACTION_DISLIKE else 0
    return (
        new_like - old_like,
        new_dislike - old_dislike,
        _reaction_score(new_reaction) - _reaction_score(old_reaction),
    )


def _book_is_forum_eligible(book: Book | None) -> bool:
    if book is None:
        return False
    raw_mode = getattr(book, "mode", None)
    if raw_mode is not None and str(raw_mode or "").strip().lower() != "author":
        return False
    if (
        getattr(book, "hidden_at", None) is not None
        or getattr(book, "archived_at", None) is not None
    ):
        return False
    public_status = str(getattr(book, "public_status", "") or "").strip().lower()
    moderation_status = str(getattr(book, "moderation_status", "") or "").strip().lower()
    if public_status in {PUBLIC_STATUS_HIDDEN, PUBLIC_STATUS_REMOVED}:
        return False
    if moderation_status in {
        MODERATION_STATUS_HIDDEN,
        MODERATION_STATUS_REMOVED,
        MODERATION_STATUS_UNDER_REVIEW,
    }:
        return False
    if not bool(getattr(book, "is_public", False)):
        return True
    return can_view_public_book(book) and is_approved_user_public_share_book(book)


def _book_is_forum_eligible_expression():
    return or_(
        and_(
            Book.is_public.is_(False),
            Book.public_status.not_in([PUBLIC_STATUS_HIDDEN, PUBLIC_STATUS_REMOVED]),
            Book.moderation_status.not_in(
                [
                    MODERATION_STATUS_HIDDEN,
                    MODERATION_STATUS_REMOVED,
                    MODERATION_STATUS_UNDER_REVIEW,
                ]
            ),
        ),
        and_(
            Book.is_public.is_(True),
            Book.source_kind == USER_PUBLIC_SHARE_SOURCE_KIND,
            Book.public_share_status == PUBLIC_SHARE_STATUS_APPROVED,
            Book.public_status == PUBLIC_STATUS_PUBLISHED,
            Book.moderation_status == MODERATION_STATUS_CLEAN,
        ),
    )


def _forum_book_visibility_expression():
    return and_(
        Book.hidden_at.is_(None),
        Book.archived_at.is_(None),
        Book.mode == "author",
        _book_is_forum_eligible_expression(),
    )


def _forum_post_thread_type(post: BookForumPost | None) -> str:
    return _normalize_forum_thread_type(getattr(post, "thread_type", FORUM_THREAD_TYPE_NOVEL))


def _is_general_forum_post(post: BookForumPost | None) -> bool:
    return _forum_post_thread_type(post) == FORUM_THREAD_TYPE_GENERAL


def _validate_forum_book_metadata(book: Book) -> None:
    if not " ".join(str(getattr(book, "title", "") or "").split()).strip():
        raise HTTPException(400, "Novel discussions require a novel title.")
    if not " ".join(str(getattr(book, "genre", "") or "").split()).strip():
        raise HTTPException(400, "Novel discussions require a genre.")
    if not " ".join(str(getattr(book, "public_description", "") or "").split()).strip():
        raise HTTPException(400, "Novel discussions require a novel description.")


async def _get_forum_eligible_owned_book(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    author_user_id: uuid.UUID,
) -> Book:
    book = await db.get(Book, book_id)
    if book is None or book.user_id != author_user_id:
        raise HTTPException(404, "Book not found.")
    if not _book_is_forum_eligible(book):
        raise HTTPException(409, "This manuscript is not available for public beta discovery.")
    return book


async def _get_forum_post(db: AsyncSession, *, post_id: uuid.UUID) -> BookForumPost:
    post = await db.get(BookForumPost, post_id)
    if post is None:
        raise HTTPException(404, "Forum post not found.")
    return post


async def _get_visible_forum_post(
    db: AsyncSession, *, post_id: uuid.UUID
) -> tuple[BookForumPost, Book | None]:
    post = await _get_forum_post(db, post_id=post_id)
    if post.status != FORUM_POST_OPEN:
        raise HTTPException(404, "Forum post not found.")
    if _is_general_forum_post(post):
        return post, None
    book = await db.get(Book, post.book_id)
    if not _book_is_forum_eligible(book):
        raise HTTPException(404, "Forum post not found.")
    return post, book


async def _get_author_accessible_forum_post(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    author_user_id: uuid.UUID,
) -> tuple[BookForumPost, Book | None]:
    post = await _get_forum_post(db, post_id=post_id)
    if post.author_user_id != author_user_id:
        raise HTTPException(404, "Forum post not found.")
    if _is_general_forum_post(post):
        return post, None
    book = await db.get(Book, post.book_id)
    if not _book_is_forum_eligible(book):
        raise HTTPException(404, "Forum post not found.")
    return post, book


async def enforce_daily_general_forum_post_limit(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    count = int(
        (
            await db.execute(
                select(func.count(BookForumPost.id)).where(
                    BookForumPost.author_user_id == user_id,
                    BookForumPost.thread_type == FORUM_THREAD_TYPE_GENERAL,
                    BookForumPost.created_at >= since,
                )
            )
        ).scalar_one()
        or 0
    )
    if count >= GENERAL_PUBLIC_FORUM_DAILY_POST_LIMIT:
        raise HTTPException(429, "You have reached today's limit for general public discussions.")


async def _invalidate_public_forum_cache() -> None:
    await cache_set_version_marker(key_public_forum_cache_version())
    await cache_del(key_public_books())
    await mark_public_catalog_cache_dirty()


async def _invalidate_public_profile_cache_for_users(*user_ids: uuid.UUID | None) -> None:
    for user_id in user_ids:
        if user_id is None:
            continue
        await mark_public_profile_cache_dirty(str(user_id))


def _normalize_public_forum_pagination(page: int, page_size: int) -> tuple[int, int]:
    normalized_page = max(int(page or 1), 1)
    normalized_page_size = max(
        1, min(int(page_size or DEFAULT_PUBLIC_FORUM_PAGE_SIZE), MAX_PUBLIC_FORUM_PAGE_SIZE)
    )
    return normalized_page, normalized_page_size


def _public_forum_visibility_filters() -> tuple:
    return (
        or_(
            and_(
                BookForumPost.thread_type == FORUM_THREAD_TYPE_GENERAL,
                BookForumPost.status == FORUM_POST_OPEN,
            ),
            and_(
                BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
                BookForumPost.status == FORUM_POST_OPEN,
                _forum_book_visibility_expression(),
            ),
        ),
    )


def _public_profile_forum_visibility_expression():
    return or_(
        BookForumPost.thread_type == FORUM_THREAD_TYPE_GENERAL,
        and_(
            BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
            _forum_book_visibility_expression(),
        ),
    )


def _public_forum_search_clause(query: str | None):
    normalized_query = " ".join((query or "").split()).strip()
    if not normalized_query:
        return None
    like = f"%{normalized_query}%"
    return or_(
        Book.title.ilike(like),
        Book.author.ilike(like),
        Book.genre.ilike(like),
        BookForumPost.headline.ilike(like),
        BookForumPost.body.ilike(like),
        User.username.ilike(like),
    )


def _public_forum_rating_summary_subquery():
    average_rating = func.round(cast(func.avg(BetaReadAssignment.final_rating), Numeric), 2).label(
        "average_rating"
    )
    rating_count = func.count(BetaReadAssignment.id).label("rating_count")
    positive_rating_count = func.sum(
        case(
            (
                BetaReadAssignment.final_rating >= POSITIVE_RATING_MIN,
                1,
            ),
            else_=0,
        )
    ).label("positive_rating_count")
    neutral_rating_count = func.sum(
        case(
            (
                (BetaReadAssignment.final_rating >= NEUTRAL_RATING_MIN)
                & (BetaReadAssignment.final_rating < POSITIVE_RATING_MIN),
                1,
            ),
            else_=0,
        )
    ).label("neutral_rating_count")
    negative_rating_count = func.sum(
        case(
            (
                BetaReadAssignment.final_rating < NEUTRAL_RATING_MIN,
                1,
            ),
            else_=0,
        )
    ).label("negative_rating_count")
    return (
        select(
            BetaReadAssignment.book_id.label("book_id"),
            average_rating,
            rating_count,
            positive_rating_count,
            neutral_rating_count,
            negative_rating_count,
        )
        .where(
            BetaReadAssignment.state.in_(list(RATED_ASSIGNMENT_STATES)),
            BetaReadAssignment.final_rating.is_not(None),
        )
        .group_by(BetaReadAssignment.book_id)
        .subquery()
    )


def _public_forum_comment_count_subquery():
    return (
        select(
            BookForumComment.post_id.label("post_id"),
            func.count(BookForumComment.id).label("comment_count"),
        )
        .group_by(BookForumComment.post_id)
        .subquery()
    )


def _public_forum_interest_count_subquery():
    return (
        select(
            BookForumInterest.post_id.label("post_id"),
            func.count(BookForumInterest.id).label("interest_count"),
        )
        .group_by(BookForumInterest.post_id)
        .subquery()
    )


def _public_forum_interest_state_subquery(user_id: uuid.UUID | None):
    if user_id is None:
        return None
    return (
        select(
            BookForumInterest.post_id.label("post_id"),
            BookForumInterest.status.label("viewer_interest_status"),
        )
        .where(BookForumInterest.interested_user_id == user_id)
        .subquery()
    )


def _public_forum_post_reaction_state_subquery(user_id: uuid.UUID | None):
    if user_id is None:
        return None
    return (
        select(
            BookForumPostReaction.post_id.label("post_id"),
            BookForumPostReaction.reaction.label("viewer_reaction"),
        )
        .where(BookForumPostReaction.user_id == user_id)
        .subquery()
    )


def _public_forum_discoverability_expression(rating_subquery, interest_subquery):
    average_rating = func.coalesce(rating_subquery.c.average_rating, 0.0)
    rating_count = func.coalesce(rating_subquery.c.rating_count, 0)
    positive_rating_count = func.coalesce(rating_subquery.c.positive_rating_count, 0)
    negative_rating_count = func.coalesce(rating_subquery.c.negative_rating_count, 0)
    interest_count = func.coalesce(interest_subquery.c.interest_count, 0)
    score = (
        (average_rating * 100)
        + (func.least(rating_count, 12) * 4)
        + (positive_rating_count * 12)
        - (negative_rating_count * 9)
        + (func.least(interest_count, 20) * 2)
    )
    return func.round(cast(score, Numeric), 2)


def _public_forum_post_select_statement(
    *,
    q: str | None = None,
    viewer_user_id: uuid.UUID | None = None,
    post_id: uuid.UUID | None = None,
    thread_type: str | None = None,
):
    rating_subquery = _public_forum_rating_summary_subquery()
    comment_subquery = _public_forum_comment_count_subquery()
    interest_subquery = _public_forum_interest_count_subquery()
    viewer_interest_subquery = _public_forum_interest_state_subquery(viewer_user_id)
    viewer_post_reaction_subquery = _public_forum_post_reaction_state_subquery(viewer_user_id)
    discoverability_score = _public_forum_discoverability_expression(
        rating_subquery, interest_subquery
    ).label("discoverability_score")
    statement = (
        select(
            BookForumPost,
            Book,
            User,
            func.coalesce(comment_subquery.c.comment_count, 0).label("comment_count"),
            func.coalesce(interest_subquery.c.interest_count, 0).label("interest_count"),
            rating_subquery.c.average_rating.label("average_rating"),
            func.coalesce(rating_subquery.c.rating_count, 0).label("rating_count"),
            func.coalesce(rating_subquery.c.positive_rating_count, 0).label(
                "positive_rating_count"
            ),
            func.coalesce(rating_subquery.c.neutral_rating_count, 0).label("neutral_rating_count"),
            func.coalesce(rating_subquery.c.negative_rating_count, 0).label(
                "negative_rating_count"
            ),
            (
                viewer_interest_subquery.c.viewer_interest_status
                if viewer_interest_subquery is not None
                else literal(None)
            ).label("viewer_interest_status"),
            (
                viewer_post_reaction_subquery.c.viewer_reaction
                if viewer_post_reaction_subquery is not None
                else literal(None)
            ).label("viewer_reaction"),
            discoverability_score,
        )
        .outerjoin(Book, Book.id == BookForumPost.book_id)
        .join(User, User.id == BookForumPost.author_user_id)
        .outerjoin(comment_subquery, comment_subquery.c.post_id == BookForumPost.id)
        .outerjoin(interest_subquery, interest_subquery.c.post_id == BookForumPost.id)
        .outerjoin(rating_subquery, rating_subquery.c.book_id == BookForumPost.book_id)
    )
    if viewer_interest_subquery is not None:
        statement = statement.outerjoin(
            viewer_interest_subquery, viewer_interest_subquery.c.post_id == BookForumPost.id
        )
    if viewer_post_reaction_subquery is not None:
        statement = statement.outerjoin(
            viewer_post_reaction_subquery,
            viewer_post_reaction_subquery.c.post_id == BookForumPost.id,
        )

    statement = statement.where(*_public_forum_visibility_filters())
    if thread_type and thread_type in VALID_FORUM_THREAD_TYPES:
        statement = statement.where(BookForumPost.thread_type == thread_type)
    search_clause = _public_forum_search_clause(q)
    if search_clause is not None:
        statement = statement.where(search_clause)
    if post_id is not None:
        statement = statement.where(BookForumPost.id == post_id)
    return statement


def _author_forum_post_select_statement(
    *,
    author_user_id: uuid.UUID,
    post_id: uuid.UUID | None = None,
):
    rating_subquery = _public_forum_rating_summary_subquery()
    comment_subquery = _public_forum_comment_count_subquery()
    interest_subquery = _public_forum_interest_count_subquery()
    discoverability_score = _public_forum_discoverability_expression(
        rating_subquery, interest_subquery
    ).label("discoverability_score")
    statement = (
        select(
            BookForumPost,
            Book,
            User,
            func.coalesce(comment_subquery.c.comment_count, 0).label("comment_count"),
            func.coalesce(interest_subquery.c.interest_count, 0).label("interest_count"),
            rating_subquery.c.average_rating.label("average_rating"),
            func.coalesce(rating_subquery.c.rating_count, 0).label("rating_count"),
            func.coalesce(rating_subquery.c.positive_rating_count, 0).label(
                "positive_rating_count"
            ),
            func.coalesce(rating_subquery.c.neutral_rating_count, 0).label("neutral_rating_count"),
            func.coalesce(rating_subquery.c.negative_rating_count, 0).label(
                "negative_rating_count"
            ),
            literal(None).label("viewer_interest_status"),
            literal(None).label("viewer_reaction"),
            discoverability_score,
        )
        .outerjoin(Book, Book.id == BookForumPost.book_id)
        .join(User, User.id == BookForumPost.author_user_id)
        .outerjoin(comment_subquery, comment_subquery.c.post_id == BookForumPost.id)
        .outerjoin(interest_subquery, interest_subquery.c.post_id == BookForumPost.id)
        .outerjoin(rating_subquery, rating_subquery.c.book_id == BookForumPost.book_id)
        .where(
            BookForumPost.author_user_id == author_user_id,
            or_(
                BookForumPost.thread_type == FORUM_THREAD_TYPE_GENERAL,
                and_(
                    BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
                    _forum_book_visibility_expression(),
                ),
            ),
        )
    )
    if post_id is not None:
        statement = statement.where(BookForumPost.id == post_id)
    return statement
