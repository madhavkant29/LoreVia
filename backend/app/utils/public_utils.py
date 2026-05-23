from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Numeric, and_, case, cast, func, literal, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    cache_del,
    cache_set_version_marker,
    get_public_profile_cache_version,
    get_public_user_profile_cache,
    key_public_books,
    key_public_forum_cache_version,
    mark_public_profile_cache_dirty,
    set_public_user_profile_cache,
)
from app.models.beta_read import BetaReadAssignment
from app.models.book import Book, BookForumComment, BookForumCommentReaction, BookForumInterest, BookForumPost, BookForumPostReaction, Chapter, PublicBookAnalyticsEvent
from app.models.intelligence import Notification
from app.models.moderation import ContentReport, CreatorStrike, ModerationAction
from app.models.user import User
from app.schemas.public import (
    PublicAuthorAnalyticsOut,
    PublicForumCommentCreateBody,
    PublicForumCommentOut,
    PublicForumInterestCreateBody,
    PublicForumInterestOut,
    PublicForumPostListOut,
    PublicForumPostCreateBody,
    PublicForumPostOut,
    PublicForumPostUpdateBody,
    PublicForumRatingSummaryOut,
    PublicUploadsBreakdownEntryOut,
    PublicUploadsOverviewOut,
    PublicUserActivityCommentOut,
    PublicUserActivityPostOut,
    PublicBookAnalyticsOut,
    PublicBookOut,
    PublicUserProfileOut,
    PublicUserProjectOut,
)
from app.utils.billing_utils import has_authoring_access
from app.utils.beta_read_utils import NEUTRAL_RATING_MIN, POSITIVE_RATING_MIN, RATED_ASSIGNMENT_STATES

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


def is_admin_user(user: User | None) -> bool:
    return bool(user is not None and str(getattr(user, "tier", "") or "").strip().lower() == "admin")


def normalize_public_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if len(slug) < 3 or len(slug) > 120 or not PUBLIC_SLUG_PATTERN.fullmatch(slug):
        raise HTTPException(400, "Public slug must be 3-120 characters and use lowercase letters, numbers, or hyphens.")
    return slug


def hash_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_public_visitor_fingerprint(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded_for = str(request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    client_host = forwarded_for or (request.client.host if request.client is not None else "")
    user_agent = " ".join(str(request.headers.get("user-agent") or "").split()).strip().lower()
    fingerprint_source = "|".join(part for part in (client_host, user_agent) if part)
    return hash_text(fingerprint_source)


def normalize_public_analytics_event_type(event_type: str) -> str:
    normalized = str(event_type or "").strip().lower()
    if normalized not in VALID_PUBLIC_ANALYTICS_EVENT_TYPES:
        raise HTTPException(400, "Invalid public analytics event type.")
    return normalized


def resolve_optional_user(user: User | None) -> User | None:
    if user is None:
        return None
    return user if getattr(user, "id", None) is not None else None


def can_view_public_book(book: Book | None) -> bool:
    if book is None or getattr(book, "hidden_at", None) is not None or getattr(book, "archived_at", None) is not None:
        return False
    if not bool(getattr(book, "is_public", False)):
        return False

    public_status = str(getattr(book, "public_status", "") or "").strip().lower()
    moderation_status = str(getattr(book, "moderation_status", "") or "").strip().lower()
    if public_status or moderation_status:
        return public_status == PUBLIC_STATUS_PUBLISHED and (
            not moderation_status or moderation_status == MODERATION_STATUS_CLEAN
        )

    # Backward-compatible fallback for older public records created before the
    # moderation-state columns existed.
    return is_public_demo_book(book) or is_approved_user_public_share_book(book)


def can_owner_or_admin_view_hidden_book(user: User | None, book: Book | None) -> bool:
    if user is None or book is None:
        return False
    owner_user_id = getattr(book, "user_id", None)
    viewer_user_id = getattr(user, "id", None)
    if owner_user_id is None or viewer_user_id is None:
        return False
    return is_admin_user(user) or owner_user_id == viewer_user_id


def public_visibility_notice(book: Book | None) -> str | None:
    if book is None:
        return None
    public_status = str(getattr(book, "public_status", "") or "").strip().lower()
    moderation_status = str(getattr(book, "moderation_status", "") or "").strip().lower()
    if public_status in {PUBLIC_STATUS_HIDDEN, PUBLIC_STATUS_REMOVED} or moderation_status in {
        MODERATION_STATUS_HIDDEN,
        MODERATION_STATUS_REMOVED,
        MODERATION_STATUS_UNDER_REVIEW,
        MODERATION_STATUS_REPORTED,
    }:
        return "This book is currently hidden from public view due to a policy or copyright report."
    if public_status == PUBLIC_STATUS_PENDING_REVIEW:
        return "This book is waiting for review before it can appear publicly."
    return None


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
        raise HTTPException(403, "Public publishing is disabled for this account due to repeated policy violations.")
    if serious_strikes >= 2:
        raise HTTPException(403, "Public publishing is temporarily disabled for this account pending review.")
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
        raise HTTPException(429, f"Daily public publishing limit reached. You can publish up to {limit} public book(s) per day.")


def ensure_content_source_allowed_for_user(user: User, content_source_type: str) -> str:
    normalized = str(content_source_type or "").strip().lower()
    if normalized not in VALID_CONTENT_SOURCE_TYPES:
        raise HTTPException(400, "Invalid content source type.")
    if normalized != CONTENT_SOURCE_TYPE_USER_ORIGINAL and not is_admin_user(user):
        raise HTTPException(403, "Only admins can publish public-domain, licensed, or admin-seeded books.")
    return normalized


def ensure_report_type_supported(report_type: str) -> str:
    normalized = str(report_type or "").strip().lower()
    if normalized not in VALID_REPORT_TYPES:
        raise HTTPException(400, "Invalid report type.")
    return normalized


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


def has_public_authoring_access(user: User | None) -> bool:
    if user is None:
        return False
    return has_authoring_access(user)


def ensure_public_authoring_access(user: User | None, *, action_label: str) -> None:
    if has_public_authoring_access(user):
        return
    raise HTTPException(
        403,
        f"{action_label} requires Trial, Author, or Architect access.",
    )


def ensure_public_mode_enabled() -> None:
    if not settings.PUBLIC_MODE_ENABLED:
        raise HTTPException(503, "Public mode is temporarily disabled")


def public_catalog_kind(book: Book | None) -> str | None:
    if book is None or not bool(book.is_public):
        return None

    source_kind = str(getattr(book, "source_kind", "") or "").strip().lower()
    if source_kind == PUBLIC_DEMO_SOURCE_KIND:
        return PUBLIC_DEMO_SOURCE_KIND
    if source_kind == USER_PUBLIC_SHARE_SOURCE_KIND:
        return USER_PUBLIC_SHARE_SOURCE_KIND
    if str(getattr(book, "format", "") or "").strip().lower() == "manual":
        return PUBLIC_DEMO_SOURCE_KIND
    return USER_PUBLIC_SHARE_SOURCE_KIND


def is_public_demo_book(book: Book | None) -> bool:
    return public_catalog_kind(book) == PUBLIC_DEMO_SOURCE_KIND


def is_user_public_share_book(book: Book | None) -> bool:
    return public_catalog_kind(book) == USER_PUBLIC_SHARE_SOURCE_KIND


def get_public_share_status(book: Book | None) -> str:
    value = str(getattr(book, "public_share_status", "") or "").strip().lower()
    if value in VALID_PUBLIC_SHARE_STATUSES:
        return value
    if bool(getattr(book, "is_public", False)) and str(getattr(book, "source_kind", "") or "").strip().lower() == USER_PUBLIC_SHARE_SOURCE_KIND:
        return PUBLIC_SHARE_STATUS_APPROVED
    return PUBLIC_SHARE_STATUS_NOT_REQUESTED


def is_approved_user_public_share_book(book: Book | None) -> bool:
    return (
        bool(getattr(book, "is_public", False))
        and str(getattr(book, "source_kind", "") or "").strip().lower() == USER_PUBLIC_SHARE_SOURCE_KIND
        and get_public_share_status(book) == PUBLIC_SHARE_STATUS_APPROVED
    )


def is_visible_creator_public_book(book: Book | None) -> bool:
    return can_view_public_book(book) and is_approved_user_public_share_book(book)


def build_public_book_out(
    book: Book,
    *,
    author_username: str | None,
    active_forum_post_id: str | None = None,
    analytics: PublicBookAnalyticsOut | None = None,
) -> PublicBookOut:
    creator_display_name = author_username or (book.author.strip() if isinstance(book.author, str) and book.author.strip() else None)
    return PublicBookOut(
        id=str(book.id),
        public_kind=PUBLIC_DEMO_SOURCE_KIND if is_public_demo_book(book) else USER_PUBLIC_SHARE_SOURCE_KIND,
        public_slug=getattr(book, "public_slug", None),
        title=book.title,
        author=book.author,
        author_username=author_username,
        creator_display_name=creator_display_name,
        genre=book.genre,
        description=book.public_description,
        format=book.format,
        work_type=book.work_type,
        status=book.status,
        public_status=getattr(book, "public_status", PUBLIC_STATUS_PUBLISHED),
        moderation_status=getattr(book, "moderation_status", MODERATION_STATUS_CLEAN),
        content_source_type=getattr(book, "content_source_type", CONTENT_SOURCE_TYPE_USER_ORIGINAL),
        source_title=getattr(book, "source_title", None),
        source_author=getattr(book, "source_author", None),
        source_public_domain_note=getattr(book, "source_public_domain_note", None),
        source_url=getattr(book, "source_url", None),
        total_chapters=book.total_chapters,
        copyright_warning=bool(book.copyright_warning),
        active_forum_post_id=active_forum_post_id,
        analytics=analytics,
        created_at=book.created_at,
        published_at=getattr(book, "published_at", None),
    )


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
    if getattr(book, "hidden_at", None) is not None or getattr(book, "archived_at", None) is not None:
        return False
    if not bool(getattr(book, "is_public", False)):
        return True
    return is_approved_user_public_share_book(book)


def _book_is_forum_eligible_expression():
    return or_(
        Book.is_public.is_(False),
        and_(
            Book.is_public.is_(True),
            Book.source_kind == USER_PUBLIC_SHARE_SOURCE_KIND,
            or_(
                Book.public_share_status == PUBLIC_SHARE_STATUS_APPROVED,
                Book.public_share_status.is_(None),
            ),
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


async def _get_visible_forum_post(db: AsyncSession, *, post_id: uuid.UUID) -> tuple[BookForumPost, Book | None]:
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


async def _invalidate_public_profile_cache_for_users(*user_ids: uuid.UUID | None) -> None:
    for user_id in user_ids:
        if user_id is None:
            continue
        await mark_public_profile_cache_dirty(str(user_id))


def _normalize_public_forum_pagination(page: int, page_size: int) -> tuple[int, int]:
    normalized_page = max(int(page or 1), 1)
    normalized_page_size = max(1, min(int(page_size or DEFAULT_PUBLIC_FORUM_PAGE_SIZE), MAX_PUBLIC_FORUM_PAGE_SIZE))
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
    average_rating = func.round(cast(func.avg(BetaReadAssignment.final_rating), Numeric), 2).label("average_rating")
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
):
    rating_subquery = _public_forum_rating_summary_subquery()
    comment_subquery = _public_forum_comment_count_subquery()
    interest_subquery = _public_forum_interest_count_subquery()
    viewer_interest_subquery = _public_forum_interest_state_subquery(viewer_user_id)
    viewer_post_reaction_subquery = _public_forum_post_reaction_state_subquery(viewer_user_id)
    discoverability_score = _public_forum_discoverability_expression(rating_subquery, interest_subquery).label(
        "discoverability_score"
    )
    statement = (
        select(
            BookForumPost,
            Book,
            User,
            func.coalesce(comment_subquery.c.comment_count, 0).label("comment_count"),
            func.coalesce(interest_subquery.c.interest_count, 0).label("interest_count"),
            rating_subquery.c.average_rating.label("average_rating"),
            func.coalesce(rating_subquery.c.rating_count, 0).label("rating_count"),
            func.coalesce(rating_subquery.c.positive_rating_count, 0).label("positive_rating_count"),
            func.coalesce(rating_subquery.c.neutral_rating_count, 0).label("neutral_rating_count"),
            func.coalesce(rating_subquery.c.negative_rating_count, 0).label("negative_rating_count"),
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
        statement = statement.outerjoin(viewer_interest_subquery, viewer_interest_subquery.c.post_id == BookForumPost.id)
    if viewer_post_reaction_subquery is not None:
        statement = statement.outerjoin(viewer_post_reaction_subquery, viewer_post_reaction_subquery.c.post_id == BookForumPost.id)

    statement = statement.where(*_public_forum_visibility_filters())
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
    discoverability_score = _public_forum_discoverability_expression(rating_subquery, interest_subquery).label(
        "discoverability_score"
    )
    statement = (
        select(
            BookForumPost,
            Book,
            User,
            func.coalesce(comment_subquery.c.comment_count, 0).label("comment_count"),
            func.coalesce(interest_subquery.c.interest_count, 0).label("interest_count"),
            rating_subquery.c.average_rating.label("average_rating"),
            func.coalesce(rating_subquery.c.rating_count, 0).label("rating_count"),
            func.coalesce(rating_subquery.c.positive_rating_count, 0).label("positive_rating_count"),
            func.coalesce(rating_subquery.c.neutral_rating_count, 0).label("neutral_rating_count"),
            func.coalesce(rating_subquery.c.negative_rating_count, 0).label("negative_rating_count"),
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


async def list_author_public_forum_posts(
    db: AsyncSession,
    *,
    author_user_id: uuid.UUID,
) -> list[PublicForumPostOut]:
    rows = (
        await db.execute(
            _author_forum_post_select_statement(author_user_id=author_user_id).order_by(
                BookForumPost.updated_at.desc(),
                BookForumPost.created_at.desc(),
            )
        )
    ).all()
    return [
        build_public_forum_post_out(
            post=post,
            book=book,
            author_user=author_user,
            rating_summary=PublicForumRatingSummaryOut(
                average_rating=float(average_rating) if average_rating is not None else None,
                rating_count=int(rating_count or 0),
                positive_rating_count=int(positive_rating_count or 0),
                neutral_rating_count=int(neutral_rating_count or 0),
                negative_rating_count=int(negative_rating_count or 0),
            ),
            interest_count=int(interest_count or 0),
            comment_count=int(comment_count or 0),
            viewer_interest_status=viewer_interest_status,
            viewer_reaction=viewer_reaction,
            discoverability_score=float(discoverability_score or 0.0),
        )
        for (
            post,
            book,
            author_user,
            comment_count,
            interest_count,
            average_rating,
            rating_count,
            positive_rating_count,
            neutral_rating_count,
            negative_rating_count,
            viewer_interest_status,
            viewer_reaction,
            discoverability_score,
        ) in rows
    ]


async def _comment_reaction_map(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> dict[uuid.UUID, str]:
    if user_id is None:
        return {}
    rows = (
        await db.execute(
            select(BookForumCommentReaction.comment_id, BookForumCommentReaction.reaction)
            .where(
                BookForumCommentReaction.post_id == post_id,
                BookForumCommentReaction.user_id == user_id,
            )
        )
    ).all()
    return {comment_id: reaction for comment_id, reaction in rows}


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
        existing["discussion_comment_count"] = int(existing["discussion_comment_count"] or 0) + int(comment_count or 0)
        existing["discussion_interest_count"] = int(existing["discussion_interest_count"] or 0) + int(interest_count or 0)
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

    base_map = {
        book_id: PublicBookAnalyticsOut()
        for book_id in book_ids
    }
    counts = (
        await db.execute(
            select(
                PublicBookAnalyticsEvent.book_id,
                func.sum(
                    case(
                        (PublicBookAnalyticsEvent.event_type == PUBLIC_ANALYTICS_EVENT_BOOK_VIEW, 1),
                        else_=0,
                    )
                ).label("book_view_count"),
                func.sum(
                    case(
                        (PublicBookAnalyticsEvent.event_type == PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW, 1),
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
                func.count(func.distinct(PublicBookAnalyticsEvent.visitor_fingerprint_hash)).label("unique_reader_count_30d"),
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
        (getattr(book, "published_at", None) for book, _username in rows if getattr(book, "published_at", None) is not None),
        default=None,
    )
    total_unique_readers_30d = 0
    if book_ids:
        total_unique_readers_30d = int(
            (
                await db.execute(
                    select(func.count(func.distinct(PublicBookAnalyticsEvent.visitor_fingerprint_hash))).where(
                        PublicBookAnalyticsEvent.book_id.in_(book_ids),
                        PublicBookAnalyticsEvent.event_date >= unique_since,
                    )
                )
            ).scalar_one()
            or 0
        )
    analytics = PublicAuthorAnalyticsOut(
        total_book_views=sum(int(analytics_map.get(book.id, PublicBookAnalyticsOut()).book_view_count or 0) for book, _username in rows),
        total_unique_readers_30d=total_unique_readers_30d,
        total_chapter_views=sum(int(analytics_map.get(book.id, PublicBookAnalyticsOut()).chapter_view_count or 0) for book, _username in rows),
        total_public_books=len(rows),
        total_chapters=sum(int(book.total_chapters or 0) for book, _username in rows),
        total_words=sum(word_counts.get(book.id, 0) for book, _username in rows),
        latest_published_at=latest_published_at,
        open_forum_discussions_count=sum(int(forum_stats.get(book.id, {}).get("open_discussion_count", 0) or 0) for book, _username in rows),
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
            if getattr(book, "published_at", None) is not None and getattr(book, "published_at") >= (now - timedelta(days=30))
        ),
        genre_breakdown=[
            PublicUploadsBreakdownEntryOut(key=label.lower().replace(" ", "-"), label=label, count=count)
            for label, count in sorted(genre_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        ],
        work_type_breakdown=[
            PublicUploadsBreakdownEntryOut(key=label.lower().replace(" ", "-"), label=label, count=count)
            for label, count in sorted(work_type_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        ],
        recent_uploads=public_books[:8],
    )


async def _project_progress_words(db: AsyncSession, *, book_id: uuid.UUID) -> int:
    total_words = await db.scalar(
        select(func.coalesce(func.sum(Chapter.word_count), 0)).where(Chapter.book_id == book_id)
    )
    return int(total_words or 0)


async def _build_public_user_project_out(db: AsyncSession, *, user_id: uuid.UUID) -> PublicUserProjectOut | None:
    latest_forum_project = (
        await db.execute(
            select(BookForumPost, Book)
            .join(Book, Book.id == BookForumPost.book_id)
            .where(
                BookForumPost.author_user_id == user_id,
                BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
                BookForumPost.status == FORUM_POST_OPEN,
                _forum_book_visibility_expression(),
            )
            .order_by(BookForumPost.last_activity_at.desc(), BookForumPost.updated_at.desc())
            .limit(1)
        )
    ).first()
    if latest_forum_project is not None:
        post, book = latest_forum_project
        return PublicUserProjectOut(
            book_id=str(book.id),
            title=book.title,
            genre=book.genre,
            # Forum-backed profiles should only surface the text explicitly shared in the forum.
            description=post.body,
            progress_words=await _project_progress_words(db, book_id=book.id),
            source="forum",
            forum_post_id=str(post.id),
        )

    latest_public_books = (
        await db.execute(
            select(Book)
            .where(
                Book.user_id == user_id,
                Book.is_public.is_(True),
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
            )
            .order_by(Book.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    latest_book = next((book for book in latest_public_books if is_approved_user_public_share_book(book)), None)
    if latest_book is None:
        return None

    return PublicUserProjectOut(
        book_id=str(latest_book.id),
        title=latest_book.title,
        genre=latest_book.genre,
        description=latest_book.public_description,
        progress_words=await _project_progress_words(db, book_id=latest_book.id),
        source="public_book",
        public_book_id=str(latest_book.id),
    )


async def public_profile_activity_counts(db: AsyncSession, *, user_id: uuid.UUID) -> tuple[int, int, int]:
    public_forum_post_count = (
        await db.execute(
            select(func.count(BookForumPost.id))
            .outerjoin(Book, Book.id == BookForumPost.book_id)
            .where(
                BookForumPost.author_user_id == user_id,
                _public_profile_forum_visibility_expression(),
            )
        )
    ).scalar_one()
    public_forum_comment_count = (
        await db.execute(
            select(func.count(BookForumComment.id))
            .join(BookForumPost, BookForumPost.id == BookForumComment.post_id)
            .outerjoin(Book, Book.id == BookForumComment.book_id)
            .where(
                BookForumComment.author_user_id == user_id,
                _public_profile_forum_visibility_expression(),
            )
        )
    ).scalar_one()
    public_books = (
        await db.execute(
            select(Book).where(
                Book.user_id == user_id,
                Book.is_public.is_(True),
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
            )
        )
    ).scalars().all()
    return (
        int(public_forum_post_count or 0),
        int(public_forum_comment_count or 0),
        sum(1 for book in public_books if is_approved_user_public_share_book(book)),
    )


async def _user_has_public_profile_presence(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    return any(await public_profile_activity_counts(db, user_id=user_id))


async def list_public_user_activity_posts(db: AsyncSession, *, user_id: uuid.UUID) -> list[PublicUserActivityPostOut]:
    comment_subquery = _public_forum_comment_count_subquery()
    interest_subquery = _public_forum_interest_count_subquery()
    reaction_subquery = (
        select(
            BookForumComment.post_id.label("post_id"),
            func.coalesce(func.sum(BookForumComment.like_count), 0).label("like_count"),
            func.coalesce(func.sum(BookForumComment.dislike_count), 0).label("dislike_count"),
        )
        .group_by(BookForumComment.post_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(
                BookForumPost,
                Book,
                func.coalesce(comment_subquery.c.comment_count, 0).label("comment_count"),
                func.coalesce(interest_subquery.c.interest_count, 0).label("interest_count"),
                func.coalesce(reaction_subquery.c.like_count, 0).label("like_count"),
                func.coalesce(reaction_subquery.c.dislike_count, 0).label("dislike_count"),
            )
            .outerjoin(Book, Book.id == BookForumPost.book_id)
            .outerjoin(comment_subquery, comment_subquery.c.post_id == BookForumPost.id)
            .outerjoin(interest_subquery, interest_subquery.c.post_id == BookForumPost.id)
            .outerjoin(reaction_subquery, reaction_subquery.c.post_id == BookForumPost.id)
            .where(
                BookForumPost.author_user_id == user_id,
                _public_profile_forum_visibility_expression(),
            )
            .order_by(BookForumPost.updated_at.desc(), BookForumPost.created_at.desc())
        )
    ).all()
    return [
        PublicUserActivityPostOut(
            id=str(post.id),
            thread_type=_forum_post_thread_type(post),
            status=post.status,
            headline=post.headline,
            body=post.body,
            title=getattr(book, "title", None),
            genre=getattr(book, "genre", None),
            work_type=getattr(book, "work_type", None),
            book_id=str(post.book_id) if post.book_id is not None else None,
            comment_count=int(comment_count or 0),
            interest_count=int(interest_count or 0) if _forum_post_thread_type(post) == FORUM_THREAD_TYPE_NOVEL else 0,
            like_count=int(like_count or 0),
            dislike_count=int(dislike_count or 0),
            created_at=post.created_at,
            updated_at=post.updated_at,
        )
        for post, book, comment_count, interest_count, like_count, dislike_count in rows
    ]


async def list_public_user_activity_comments(db: AsyncSession, *, user_id: uuid.UUID) -> list[PublicUserActivityCommentOut]:
    rows = (
        await db.execute(
            select(BookForumComment, BookForumPost, Book)
            .join(BookForumPost, BookForumPost.id == BookForumComment.post_id)
            .outerjoin(Book, Book.id == BookForumComment.book_id)
            .where(
                BookForumComment.author_user_id == user_id,
                _public_profile_forum_visibility_expression(),
            )
            .order_by(BookForumComment.updated_at.desc(), BookForumComment.created_at.desc())
        )
    ).all()
    return [
        PublicUserActivityCommentOut(
            id=str(comment.id),
            post_id=str(post.id),
            thread_type=_forum_post_thread_type(post),
            post_status=post.status,
            post_headline=post.headline,
            post_title=getattr(book, "title", None),
            book_id=str(comment.book_id) if comment.book_id is not None else None,
            body=comment.body,
            like_count=int(comment.like_count or 0),
            dislike_count=int(comment.dislike_count or 0),
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
        for comment, post, book in rows
    ]


async def build_public_user_profile_out(
    db: AsyncSession,
    *,
    user: User,
) -> PublicUserProfileOut:
    forum_post_count, forum_comment_count, _public_book_count = await public_profile_activity_counts(db, user_id=user.id)
    public_books, public_analytics = await build_public_author_analytics(db, user_id=user.id)
    posts = await list_public_user_activity_posts(db, user_id=user.id)
    comments = await list_public_user_activity_comments(db, user_id=user.id)
    return PublicUserProfileOut(
        user_id=str(user.id),
        username=user.username or "",
        reputation_score=int(user.reputation_score or 0),
        reputation_likes_received=int(user.reputation_likes_received or 0),
        reputation_dislikes_received=int(user.reputation_dislikes_received or 0),
        trust_level=reputation_trust_level(user.reputation_score),
        forum_post_count=forum_post_count,
        forum_comment_count=forum_comment_count,
        current_project=await _build_public_user_project_out(db, user_id=user.id),
        public_books_count=len(public_books),
        public_books=public_books,
        public_analytics=public_analytics,
        posts=posts,
        comments=comments,
        created_at=user.created_at,
    )


def build_public_forum_post_out(
    *,
    post: BookForumPost,
    book: Book | None,
    author_user: User,
    rating_summary: PublicForumRatingSummaryOut | None = None,
    interest_count: int = 0,
    comment_count: int = 0,
    viewer_interest_status: str | None = None,
    viewer_reaction: str | None = None,
    discoverability_score: float | None = None,
) -> PublicForumPostOut:
    thread_type = _forum_post_thread_type(post)
    rating_payload = rating_summary or PublicForumRatingSummaryOut()
    resolved_discoverability_score = discoverability_score
    if resolved_discoverability_score is None:
        resolved_discoverability_score = public_forum_discoverability_score(
            average_rating=rating_payload.average_rating,
            rating_count=rating_payload.rating_count,
            positive_rating_count=rating_payload.positive_rating_count,
            negative_rating_count=rating_payload.negative_rating_count,
            interest_count=interest_count,
        )
    return PublicForumPostOut(
        id=str(post.id),
        thread_type=thread_type,
        book_id=str(post.book_id) if post.book_id is not None else None,
        author_user_id=str(post.author_user_id),
        author_username=author_user.username,
        author_reputation_score=int(author_user.reputation_score or 0),
        author_trust_level=reputation_trust_level(author_user.reputation_score),
        title=getattr(book, "title", None),
        author=getattr(book, "author", None),
        genre=getattr(book, "genre", None),
        description=getattr(book, "public_description", None),
        work_type=getattr(book, "work_type", None),
        headline=post.headline,
        body=post.body,
        desired_beta_reader_count=post.desired_beta_reader_count if thread_type == FORUM_THREAD_TYPE_NOVEL else None,
        allow_contact_requests=bool(post.allow_contact_requests) if thread_type == FORUM_THREAD_TYPE_NOVEL else False,
        status=post.status,
        viewer_interest_status=viewer_interest_status if thread_type == FORUM_THREAD_TYPE_NOVEL else None,
        reaction=viewer_reaction,
        interest_count=interest_count if thread_type == FORUM_THREAD_TYPE_NOVEL else 0,
        comment_count=comment_count,
        like_count=int(post.like_count or 0),
        dislike_count=int(post.dislike_count or 0),
        rating_summary=rating_payload if thread_type == FORUM_THREAD_TYPE_NOVEL else PublicForumRatingSummaryOut(),
        discoverability_score=float(resolved_discoverability_score),
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


async def create_public_forum_post(
    db: AsyncSession,
    *,
    current_user: User,
    body: PublicForumPostCreateBody,
) -> PublicForumPostOut:
    thread_type = _normalize_forum_thread_type(body.thread_type)
    headline = " ".join(body.headline.split()).strip()
    description = body.body.strip()
    if not headline or not description:
        raise HTTPException(400, "Forum headline and body are required.")
    book = None
    desired_beta_reader_count = None
    allow_contact_requests = False
    if thread_type == FORUM_THREAD_TYPE_NOVEL:
        ensure_public_authoring_access(current_user, action_label="Opening a public discussion")
        if body.book_id is None:
            raise HTTPException(400, "Novel discussions require a manuscript.")
        book = await _get_forum_eligible_owned_book(db, book_id=body.book_id, author_user_id=current_user.id)
        _validate_forum_book_metadata(book)
        existing_open_post = (
            await db.execute(
                select(BookForumPost).where(
                    BookForumPost.book_id == book.id,
                    BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
                    BookForumPost.status == FORUM_POST_OPEN,
                )
            )
        ).scalar_one_or_none()
        if existing_open_post is not None:
            raise HTTPException(409, "This manuscript already has a beta forum post. Update it instead.")
        desired_beta_reader_count = body.desired_beta_reader_count
        allow_contact_requests = bool(body.allow_contact_requests)
    else:
        if body.book_id is not None:
            raise HTTPException(400, "General discussions cannot be attached to a manuscript.")
        await enforce_daily_general_forum_post_limit(db, user_id=current_user.id)

    post = BookForumPost(
        book_id=book.id if book is not None else None,
        author_user_id=current_user.id,
        thread_type=thread_type,
        headline=headline,
        body=description,
        desired_beta_reader_count=desired_beta_reader_count,
        allow_contact_requests=allow_contact_requests,
        status=FORUM_POST_OPEN,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    await _invalidate_public_forum_cache()
    await _invalidate_public_profile_cache_for_users(current_user.id)
    return await get_public_forum_post_detail(db, post_id=post.id, current_user=current_user)


async def update_public_forum_post(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    current_user: User,
    body: PublicForumPostUpdateBody,
) -> PublicForumPostOut:
    post = await _get_forum_post(db, post_id=post_id)
    if post.author_user_id != current_user.id:
        raise HTTPException(404, "Forum post not found.")
    thread_type = _forum_post_thread_type(post)
    requested_thread_type = _normalize_forum_thread_type(body.thread_type)
    if requested_thread_type != thread_type:
        raise HTTPException(400, "Forum thread type cannot be changed.")
    book = None
    if thread_type == FORUM_THREAD_TYPE_NOVEL:
        if post.book_id is None:
            raise HTTPException(409, "Novel discussion is missing its manuscript link.")
        book = await _get_forum_eligible_owned_book(db, book_id=post.book_id, author_user_id=current_user.id)
        _validate_forum_book_metadata(book)
    headline = " ".join(body.headline.split()).strip()
    description = body.body.strip()
    if not headline or not description:
        raise HTTPException(400, "Forum headline and body are required.")
    next_status = _normalize_forum_status(body.status)
    if thread_type == FORUM_THREAD_TYPE_NOVEL and not has_public_authoring_access(current_user):
        attempted_non_closing_change = (
            headline != post.headline
            or description != post.body
            or body.desired_beta_reader_count != post.desired_beta_reader_count
            or bool(body.allow_contact_requests) != bool(post.allow_contact_requests)
            or next_status != FORUM_POST_CLOSED
        )
        if attempted_non_closing_change:
            raise HTTPException(403, "Opening or editing a public discussion requires Trial, Author, or Architect access.")
    if thread_type == FORUM_THREAD_TYPE_NOVEL and next_status == FORUM_POST_OPEN and book is not None:
        existing_open_post = (
            await db.execute(
                select(BookForumPost).where(
                    BookForumPost.book_id == book.id,
                    BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
                    BookForumPost.status == FORUM_POST_OPEN,
                    BookForumPost.id != post.id,
                )
            )
        ).scalar_one_or_none()
        if existing_open_post is not None:
            raise HTTPException(409, "This manuscript already has another open beta forum post.")
    post.headline = headline
    post.body = description
    post.desired_beta_reader_count = body.desired_beta_reader_count if thread_type == FORUM_THREAD_TYPE_NOVEL else None
    post.allow_contact_requests = bool(body.allow_contact_requests) if thread_type == FORUM_THREAD_TYPE_NOVEL else False
    post.status = next_status
    await db.commit()
    await db.refresh(post)
    await _invalidate_public_forum_cache()
    await _invalidate_public_profile_cache_for_users(current_user.id)
    return await get_public_forum_post_detail(db, post_id=post.id, current_user=current_user)


async def list_public_forum_posts(
    db: AsyncSession,
    *,
    q: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
    current_user: User | None = None,
) -> PublicForumPostListOut:
    normalized_page, normalized_page_size = _normalize_public_forum_pagination(page, page_size)
    total_statement = (
        select(func.count(BookForumPost.id))
        .outerjoin(Book, Book.id == BookForumPost.book_id)
        .join(User, User.id == BookForumPost.author_user_id)
        .where(*_public_forum_visibility_filters())
    )
    search_clause = _public_forum_search_clause(q)
    if search_clause is not None:
        total_statement = total_statement.where(search_clause)
    total = int((await db.execute(total_statement)).scalar_one() or 0)

    statement = _public_forum_post_select_statement(
        q=q,
        viewer_user_id=current_user.id if current_user is not None else None,
    ).order_by(
        literal_column("discoverability_score").desc(),
        User.reputation_score.desc(),
        literal_column("average_rating").desc(),
        literal_column("rating_count").desc(),
        literal_column("comment_count").desc(),
        BookForumPost.created_at.desc(),
    )
    rows = (
        await db.execute(
            statement.offset((normalized_page - 1) * normalized_page_size).limit(normalized_page_size)
        )
    ).all()
    items = [
        build_public_forum_post_out(
            post=post,
            book=book,
            author_user=author_user,
            rating_summary=PublicForumRatingSummaryOut(
                average_rating=float(average_rating) if average_rating is not None else None,
                rating_count=int(rating_count or 0),
                positive_rating_count=int(positive_rating_count or 0),
                neutral_rating_count=int(neutral_rating_count or 0),
                negative_rating_count=int(negative_rating_count or 0),
            ),
            interest_count=int(interest_count or 0),
            comment_count=int(comment_count or 0),
            viewer_interest_status=viewer_interest_status,
            viewer_reaction=viewer_reaction,
            discoverability_score=float(discoverability_score or 0.0),
        )
        for (
            post,
            book,
            author_user,
            comment_count,
            interest_count,
            average_rating,
            rating_count,
            positive_rating_count,
            neutral_rating_count,
            negative_rating_count,
            viewer_interest_status,
            viewer_reaction,
            discoverability_score,
        ) in rows
    ]
    return PublicForumPostListOut(
        items=items,
        total=total,
        page=normalized_page,
        page_size=normalized_page_size,
        has_more=(normalized_page * normalized_page_size) < total,
    )


async def get_public_forum_post_detail(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    current_user: User | None = None,
) -> PublicForumPostOut:
    row = (
        await db.execute(
            _public_forum_post_select_statement(
                viewer_user_id=current_user.id if current_user is not None else None,
                post_id=post_id,
            )
        )
    ).first()
    if row is None:
        if current_user is None:
            raise HTTPException(404, "Forum post not found.")
        row = (
            await db.execute(
                _author_forum_post_select_statement(
                    author_user_id=current_user.id,
                    post_id=post_id,
                )
            )
        ).first()
        if row is None:
            raise HTTPException(404, "Forum post not found.")
    (
        post,
        book,
        author_user,
        comment_count,
        interest_count,
        average_rating,
        rating_count,
        positive_rating_count,
        neutral_rating_count,
        negative_rating_count,
        viewer_interest_status,
        viewer_reaction,
        discoverability_score,
    ) = row
    return build_public_forum_post_out(
        post=post,
        book=book,
        author_user=author_user,
        rating_summary=PublicForumRatingSummaryOut(
            average_rating=float(average_rating) if average_rating is not None else None,
            rating_count=int(rating_count or 0),
            positive_rating_count=int(positive_rating_count or 0),
            neutral_rating_count=int(neutral_rating_count or 0),
            negative_rating_count=int(negative_rating_count or 0),
        ),
        interest_count=int(interest_count or 0),
        comment_count=int(comment_count or 0),
        viewer_interest_status=viewer_interest_status,
        viewer_reaction=viewer_reaction,
        discoverability_score=float(discoverability_score or 0.0),
    )


async def build_public_forum_interest_out(
    db: AsyncSession,
    *,
    interest: BookForumInterest,
) -> PublicForumInterestOut:
    interested_user = await db.get(User, interest.interested_user_id)
    if interested_user is None:
        raise HTTPException(404, "Interested user not found.")
    return PublicForumInterestOut(
        id=str(interest.id),
        post_id=str(interest.post_id),
        book_id=str(interest.book_id),
        author_user_id=str(interest.author_user_id),
        interested_user_id=str(interest.interested_user_id),
        interested_username=interested_user.username,
        interested_email=interested_user.email,
        message=interest.message,
        status=interest.status,
        created_at=interest.created_at,
        updated_at=interest.updated_at,
    )


async def create_public_forum_interest(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    current_user: User,
    body: PublicForumInterestCreateBody,
) -> PublicForumInterestOut:
    post, _book = await _get_visible_forum_post(db, post_id=post_id)
    if _is_general_forum_post(post):
        raise HTTPException(409, "General discussions do not accept collaborator requests.")
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "A contact message is required.")
    if post.author_user_id == current_user.id:
        raise HTTPException(409, "You cannot contact yourself through your own beta forum post.")
    if not post.allow_contact_requests:
        raise HTTPException(409, "This beta forum post is not accepting contact requests.")
    existing = (
        await db.execute(
            select(BookForumInterest).where(
                BookForumInterest.post_id == post.id,
                BookForumInterest.interested_user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, "You already contacted this author through the beta forum.")

    interest = BookForumInterest(
        post_id=post.id,
        book_id=post.book_id,
        author_user_id=post.author_user_id,
        interested_user_id=current_user.id,
        message=message,
    )
    post.last_activity_at = func.now()
    db.add(interest)
    db.add(
        Notification(
            user_id=post.author_user_id,
            book_id=post.book_id,
            kind="beta_forum_interest_received",
            title="A reader is interested in your manuscript",
            body="Someone approached you through your public beta forum post.",
            data={
                "post_id": str(post.id),
                "book_id": str(post.book_id),
                "interested_user_id": str(current_user.id),
            },
        )
    )
    await db.commit()
    await db.refresh(interest)
    await _invalidate_public_forum_cache()
    await _invalidate_public_profile_cache_for_users(post.author_user_id, current_user.id)
    return await build_public_forum_interest_out(db, interest=interest)


async def list_public_forum_interests_for_author(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    author_user_id: uuid.UUID,
) -> list[PublicForumInterestOut]:
    post = await _get_forum_post(db, post_id=post_id)
    if post.author_user_id != author_user_id:
        raise HTTPException(404, "Forum post not found.")
    if _is_general_forum_post(post):
        return []
    interests = (
        await db.execute(
            select(BookForumInterest)
            .where(BookForumInterest.post_id == post.id)
            .order_by(BookForumInterest.created_at.desc())
        )
    ).scalars().all()
    return [await build_public_forum_interest_out(db, interest=interest) for interest in interests]


async def build_public_forum_comment_out(
    db: AsyncSession,
    *,
    comment: BookForumComment,
    author_user: User | None = None,
    current_user: User | None = None,
    reaction_map: dict[uuid.UUID, str] | None = None,
) -> PublicForumCommentOut:
    resolved_author = author_user or await db.get(User, comment.author_user_id)
    if resolved_author is None:
        raise HTTPException(404, "Comment author not found.")
    current_reaction = (reaction_map or {}).get(comment.id)
    return PublicForumCommentOut(
        id=str(comment.id),
        post_id=str(comment.post_id),
        book_id=str(comment.book_id) if comment.book_id is not None else None,
        parent_comment_id=str(comment.parent_comment_id) if comment.parent_comment_id is not None else None,
        author_user_id=str(comment.author_user_id),
        author_username=resolved_author.username,
        author_reputation_score=int(resolved_author.reputation_score or 0),
        author_trust_level=reputation_trust_level(resolved_author.reputation_score),
        body=comment.body,
        like_count=int(comment.like_count or 0),
        dislike_count=int(comment.dislike_count or 0),
        reaction=current_reaction,
        can_edit=current_user is not None and comment.author_user_id == current_user.id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def _nest_public_forum_comments(comments: list[PublicForumCommentOut]) -> list[PublicForumCommentOut]:
    comment_map = {
        comment.id: comment.model_copy(update={"replies": []})
        for comment in comments
    }
    roots: list[PublicForumCommentOut] = []
    for comment in comments:
        current = comment_map[comment.id]
        if current.parent_comment_id and current.parent_comment_id in comment_map:
            parent = comment_map[current.parent_comment_id]
            parent.replies.append(current)
            continue
        roots.append(current)
    return roots


async def list_public_forum_comments(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    current_user: User | None = None,
) -> list[PublicForumCommentOut]:
    if current_user is not None:
        try:
            post, _book = await _get_author_accessible_forum_post(
                db,
                post_id=post_id,
                author_user_id=current_user.id,
            )
        except HTTPException:
            post, _book = await _get_visible_forum_post(db, post_id=post_id)
    else:
        post, _book = await _get_visible_forum_post(db, post_id=post_id)
    rows = (
        await db.execute(
            select(BookForumComment, User)
            .join(User, User.id == BookForumComment.author_user_id)
            .where(BookForumComment.post_id == post.id)
            .order_by(BookForumComment.created_at.asc(), BookForumComment.id.asc())
        )
    ).all()
    reaction_map = await _comment_reaction_map(
        db,
        post_id=post.id,
        user_id=current_user.id if current_user is not None else None,
    )
    comment_payloads = [
        await build_public_forum_comment_out(
            db,
            comment=comment,
            author_user=author_user,
            current_user=current_user,
            reaction_map=reaction_map,
        )
        for comment, author_user in rows
    ]
    return _nest_public_forum_comments(comment_payloads)


async def create_public_forum_comment(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    current_user: User,
    body: PublicForumCommentCreateBody,
) -> PublicForumCommentOut:
    post, _book = await _get_visible_forum_post(db, post_id=post_id)
    comment_body = body.body.strip()
    if not comment_body:
        raise HTTPException(400, "A comment is required.")
    parent_comment = None
    if body.parent_comment_id is not None:
        parent_comment = await db.get(BookForumComment, body.parent_comment_id)
        if parent_comment is None or parent_comment.post_id != post.id:
            raise HTTPException(404, "Parent forum comment not found.")
    comment = BookForumComment(
        post_id=post.id,
        book_id=post.book_id,
        parent_comment_id=parent_comment.id if parent_comment is not None else None,
        author_user_id=current_user.id,
        body=comment_body,
    )
    post.last_activity_at = func.now()
    db.add(comment)
    await db.flush()
    notified_user_ids: set[uuid.UUID] = set()
    if post.author_user_id != current_user.id:
        notified_user_ids.add(post.author_user_id)
        notification_title = "New beta forum comment" if _forum_post_thread_type(post) == FORUM_THREAD_TYPE_NOVEL else "New forum comment"
        notification_body = (
            "Someone replied to your public beta forum post."
            if _forum_post_thread_type(post) == FORUM_THREAD_TYPE_NOVEL
            else "Someone replied to your public discussion."
        )
        db.add(
            Notification(
                user_id=post.author_user_id,
                book_id=post.book_id,
                kind="beta_forum_comment_received",
                title=notification_title,
                body=notification_body,
                data={
                    "post_id": str(post.id),
                    "book_id": str(post.book_id),
                    "comment_author_user_id": str(current_user.id),
                },
            )
        )
    if (
        parent_comment is not None
        and parent_comment.author_user_id != current_user.id
        and parent_comment.author_user_id not in notified_user_ids
    ):
        db.add(
            Notification(
                user_id=parent_comment.author_user_id,
                book_id=post.book_id,
                kind="beta_forum_comment_reply_received",
                title="New forum reply",
                body="Someone replied to your public forum comment.",
                data={
                    "post_id": str(post.id),
                    "book_id": str(post.book_id),
                    "comment_id": str(parent_comment.id),
                    "reply_comment_id": str(comment.id),
                    "comment_author_user_id": str(current_user.id),
                },
            )
        )
    await db.commit()
    await db.refresh(comment)
    await _invalidate_public_forum_cache()
    await _invalidate_public_profile_cache_for_users(post.author_user_id, current_user.id)
    return await build_public_forum_comment_out(db, comment=comment, author_user=current_user, current_user=current_user)


def forum_post_is_publicly_interactive(post: BookForumPost | PublicForumPostOut | None) -> bool:
    return str(getattr(post, "status", "") or "").strip().lower() == FORUM_POST_OPEN


async def react_to_public_forum_comment(
    db: AsyncSession,
    *,
    comment_id: uuid.UUID,
    current_user: User,
    reaction: str,
) -> PublicForumCommentOut:
    normalized_reaction = _normalize_forum_comment_reaction(reaction)
    comment = await db.get(BookForumComment, comment_id)
    if comment is None:
        raise HTTPException(404, "Forum comment not found.")
    await _get_visible_forum_post(db, post_id=comment.post_id)
    if comment.author_user_id == current_user.id:
        raise HTTPException(409, "You cannot react to your own comment.")
    author_user = await db.get(User, comment.author_user_id)
    if author_user is None:
        raise HTTPException(404, "Comment author not found.")

    existing = (
        await db.execute(
            select(BookForumCommentReaction).where(
                BookForumCommentReaction.comment_id == comment.id,
                BookForumCommentReaction.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    previous_reaction = existing.reaction if existing is not None else None
    next_reaction = None if normalized_reaction == FORUM_COMMENT_REACTION_CLEAR else normalized_reaction
    if previous_reaction == next_reaction:
        return await build_public_forum_comment_out(
            db,
            comment=comment,
            author_user=author_user,
            current_user=current_user,
            reaction_map={comment.id: previous_reaction} if previous_reaction else {},
        )

    like_delta, dislike_delta, reputation_delta = _reaction_delta(previous_reaction, next_reaction)
    comment.like_count = max(int(comment.like_count or 0) + like_delta, 0)
    comment.dislike_count = max(int(comment.dislike_count or 0) + dislike_delta, 0)
    author_user.reputation_likes_received = max(int(author_user.reputation_likes_received or 0) + like_delta, 0)
    author_user.reputation_dislikes_received = max(int(author_user.reputation_dislikes_received or 0) + dislike_delta, 0)
    author_user.reputation_score = int(author_user.reputation_score or 0) + reputation_delta

    if next_reaction is None:
        if existing is not None:
            await db.delete(existing)
    elif existing is None:
        db.add(
            BookForumCommentReaction(
                comment_id=comment.id,
                post_id=comment.post_id,
                user_id=current_user.id,
                reaction=next_reaction,
            )
        )
    else:
        existing.reaction = next_reaction

    await db.commit()
    await db.refresh(comment)
    await db.refresh(author_user)
    await _invalidate_public_forum_cache()
    await _invalidate_public_profile_cache_for_users(comment.author_user_id, current_user.id)
    reaction_map = {comment.id: next_reaction} if next_reaction else {}
    return await build_public_forum_comment_out(
        db,
        comment=comment,
        author_user=author_user,
        current_user=current_user,
        reaction_map=reaction_map,
    )


async def react_to_public_forum_post(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    current_user: User,
    reaction: str,
) -> PublicForumPostOut:
    normalized_reaction = _normalize_forum_comment_reaction(reaction)
    post, _book = await _get_visible_forum_post(db, post_id=post_id)
    if post.author_user_id == current_user.id:
        raise HTTPException(409, "You cannot react to your own forum post.")
    author_user = await db.get(User, post.author_user_id)
    if author_user is None:
        raise HTTPException(404, "Forum post author not found.")

    existing = (
        await db.execute(
            select(BookForumPostReaction).where(
                BookForumPostReaction.post_id == post.id,
                BookForumPostReaction.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    previous_reaction = existing.reaction if existing is not None else None
    next_reaction = None if normalized_reaction == FORUM_COMMENT_REACTION_CLEAR else normalized_reaction
    if previous_reaction == next_reaction:
        return await get_public_forum_post_detail(db, post_id=post.id, current_user=current_user)

    like_delta, dislike_delta, reputation_delta = _reaction_delta(previous_reaction, next_reaction)
    post.like_count = max(int(post.like_count or 0) + like_delta, 0)
    post.dislike_count = max(int(post.dislike_count or 0) + dislike_delta, 0)
    author_user.reputation_likes_received = max(int(author_user.reputation_likes_received or 0) + like_delta, 0)
    author_user.reputation_dislikes_received = max(int(author_user.reputation_dislikes_received or 0) + dislike_delta, 0)
    author_user.reputation_score = int(author_user.reputation_score or 0) + reputation_delta

    if next_reaction is None:
        if existing is not None:
            await db.delete(existing)
    elif existing is None:
        db.add(
            BookForumPostReaction(
                post_id=post.id,
                user_id=current_user.id,
                reaction=next_reaction,
            )
        )
    else:
        existing.reaction = next_reaction

    await db.commit()
    await db.refresh(post)
    await db.refresh(author_user)
    await _invalidate_public_forum_cache()
    await _invalidate_public_profile_cache_for_users(post.author_user_id, current_user.id)
    return await get_public_forum_post_detail(db, post_id=post.id, current_user=current_user)


async def get_public_user_profile(
    db: AsyncSession,
    *,
    username: str,
) -> PublicUserProfileOut:
    normalized_username = (username or "").strip().lower()
    if not normalized_username:
        raise HTTPException(404, "Public profile not found.")
    user = (
        await db.execute(select(User).where(func.lower(User.username) == normalized_username))
    ).scalar_one_or_none()
    if user is None or not user.username:
        raise HTTPException(404, "Public profile not found.")
    if not await _user_has_public_profile_presence(db, user_id=user.id):
        raise HTTPException(404, "Public profile not found.")
    cache_version = await get_public_profile_cache_version(str(user.id))
    cached = await get_public_user_profile_cache(str(user.id), user.username.lower(), cache_version)
    if cached is not None:
        return PublicUserProfileOut(**cached)
    payload = await build_public_user_profile_out(db, user=user)
    await set_public_user_profile_cache(
        str(user.id),
        user.username.lower(),
        cache_version,
        payload.model_dump(mode="json"),
    )
    return payload
