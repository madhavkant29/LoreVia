from __future__ import annotations

import re

from fastapi import HTTPException

from app.core.config import settings
from app.models.book import (
    Book,
)
from app.models.user import User
from app.schemas.public import (
    PublicBookAnalyticsOut,
    PublicBookOut,
)
from app.utils.billing_utils import has_authoring_access

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


def is_admin_user(user: User | None) -> bool:
    return False


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
    if (
        book is None
        or getattr(book, "hidden_at", None) is not None
        or getattr(book, "archived_at", None) is not None
    ):
        return False
    if not bool(getattr(book, "is_public", False)):
        return False

    public_status = str(getattr(book, "public_status", "") or "").strip().lower()
    moderation_status = str(getattr(book, "moderation_status", "") or "").strip().lower()
    if public_status or moderation_status:
        return public_status == PUBLIC_STATUS_PUBLISHED and (
            not moderation_status
            or moderation_status in {MODERATION_STATUS_CLEAN, MODERATION_STATUS_REPORTED}
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
    }:
        return "This book is currently hidden from public view due to a policy or copyright report."
    if public_status == PUBLIC_STATUS_PENDING_REVIEW:
        return "This book is waiting for review before it can appear publicly."
    return None


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
    if (
        bool(getattr(book, "is_public", False))
        and str(getattr(book, "source_kind", "") or "").strip().lower()
        == USER_PUBLIC_SHARE_SOURCE_KIND
    ):
        return PUBLIC_SHARE_STATUS_APPROVED
    return PUBLIC_SHARE_STATUS_NOT_REQUESTED


def is_approved_user_public_share_book(book: Book | None) -> bool:
    return (
        bool(getattr(book, "is_public", False))
        and str(getattr(book, "source_kind", "") or "").strip().lower()
        == USER_PUBLIC_SHARE_SOURCE_KIND
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
    creator_display_name = author_username or (
        book.author.strip() if isinstance(book.author, str) and book.author.strip() else None
    )
    return PublicBookOut(
        id=str(book.id),
        public_kind=PUBLIC_DEMO_SOURCE_KIND
        if is_public_demo_book(book)
        else USER_PUBLIC_SHARE_SOURCE_KIND,
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
        public_updated_at=getattr(book, "public_updated_at", None),
    )
