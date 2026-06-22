from __future__ import annotations

import re
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    get_public_profile_cache_version,
    get_public_user_profile_cache,
    set_public_user_profile_cache,
)
from app.models.book import (
    Book,
    BookForumComment,
    BookForumPost,
    Chapter,
)
from app.models.user import User
from app.schemas.public import (
    PublicUserActivityCommentOut,
    PublicUserActivityPostOut,
    PublicUserProfileOut,
    PublicUserProjectOut,
)
from app.utils.public.analytics import build_public_author_analytics
from app.utils.public.forum_foundation import (
    _forum_book_visibility_expression,
    _forum_post_thread_type,
    _public_forum_comment_count_subquery,
    _public_forum_interest_count_subquery,
    _public_profile_forum_visibility_expression,
    reputation_trust_level,
)
from app.utils.public.requests import (
    public_forum_image_url,
)
from app.utils.public.serialization import (
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


async def _project_progress_words(db: AsyncSession, *, book_id: uuid.UUID) -> int:
    total_words = await db.scalar(
        select(func.coalesce(func.sum(Chapter.word_count), 0)).where(Chapter.book_id == book_id)
    )
    return int(total_words or 0)


async def _build_public_user_project_out(
    db: AsyncSession, *, user_id: uuid.UUID
) -> PublicUserProjectOut | None:
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
        (
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
        )
        .scalars()
        .all()
    )
    latest_book = next(
        (book for book in latest_public_books if is_approved_user_public_share_book(book)), None
    )
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


async def public_profile_activity_counts(
    db: AsyncSession, *, user_id: uuid.UUID
) -> tuple[int, int, int]:
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
        (
            await db.execute(
                select(Book).where(
                    Book.user_id == user_id,
                    Book.is_public.is_(True),
                    Book.hidden_at.is_(None),
                    Book.archived_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return (
        int(public_forum_post_count or 0),
        int(public_forum_comment_count or 0),
        sum(1 for book in public_books if is_approved_user_public_share_book(book)),
    )


async def _user_has_public_profile_presence(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    return any(await public_profile_activity_counts(db, user_id=user_id))


async def list_public_user_activity_posts(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[PublicUserActivityPostOut]:
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
            image_url=public_forum_image_url(
                storage_key=post.image_s3_key,
                owner_user_id=post.author_user_id,
                target_kind="post",
                target_id=post.id,
            ),
            image_filename=post.image_filename,
            image_content_type=post.image_content_type,
            title=getattr(book, "title", None),
            genre=getattr(book, "genre", None),
            work_type=getattr(book, "work_type", None),
            book_id=str(post.book_id) if post.book_id is not None else None,
            comment_count=int(comment_count or 0),
            interest_count=int(interest_count or 0)
            if _forum_post_thread_type(post) == FORUM_THREAD_TYPE_NOVEL
            else 0,
            like_count=int(like_count or 0),
            dislike_count=int(dislike_count or 0),
            created_at=post.created_at,
            updated_at=post.updated_at,
        )
        for post, book, comment_count, interest_count, like_count, dislike_count in rows
    ]


async def list_public_user_activity_comments(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[PublicUserActivityCommentOut]:
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
            image_url=public_forum_image_url(
                storage_key=comment.image_s3_key,
                owner_user_id=comment.author_user_id,
                target_kind="comment",
                target_id=comment.id,
            ),
            image_filename=comment.image_filename,
            image_content_type=comment.image_content_type,
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
    (
        forum_post_count,
        forum_comment_count,
        _public_book_count,
    ) = await public_profile_activity_counts(db, user_id=user.id)
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
