from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    BookForumCommentReaction,
    BookForumPost,
)
from app.models.user import User
from app.schemas.public import (
    PublicForumPostCreateBody,
    PublicForumPostListOut,
    PublicForumPostOut,
    PublicForumPostUpdateBody,
    PublicForumRatingSummaryOut,
)
from app.utils.public.forum_foundation import (
    _author_forum_post_select_statement,
    _forum_post_thread_type,
    _get_forum_eligible_owned_book,
    _get_forum_post,
    _invalidate_public_forum_cache,
    _invalidate_public_profile_cache_for_users,
    _normalize_forum_status,
    _normalize_forum_thread_type,
    _normalize_public_forum_pagination,
    _public_forum_post_select_statement,
    _public_forum_search_clause,
    _public_forum_visibility_filters,
    _validate_forum_book_metadata,
    enforce_daily_general_forum_post_limit,
    public_forum_discoverability_score,
    reputation_trust_level,
)
from app.utils.public.requests import (
    public_forum_image_url,
    store_public_forum_image,
)
from app.utils.public.serialization import (
    ensure_public_authoring_access,
    has_public_authoring_access,
)
from app.utils.storage_utils import delete_storage_key_best_effort

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
            select(BookForumCommentReaction.comment_id, BookForumCommentReaction.reaction).where(
                BookForumCommentReaction.post_id == post_id,
                BookForumCommentReaction.user_id == user_id,
            )
        )
    ).all()
    return {comment_id: reaction for comment_id, reaction in rows}


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
        image_url=public_forum_image_url(
            storage_key=post.image_s3_key,
            owner_user_id=post.author_user_id,
            target_kind="post",
            target_id=post.id,
        ),
        image_filename=post.image_filename,
        image_content_type=post.image_content_type,
        desired_beta_reader_count=post.desired_beta_reader_count
        if thread_type == FORUM_THREAD_TYPE_NOVEL
        else None,
        allow_contact_requests=bool(post.allow_contact_requests)
        if thread_type == FORUM_THREAD_TYPE_NOVEL
        else False,
        status=post.status,
        viewer_interest_status=viewer_interest_status
        if thread_type == FORUM_THREAD_TYPE_NOVEL
        else None,
        reaction=viewer_reaction,
        interest_count=interest_count if thread_type == FORUM_THREAD_TYPE_NOVEL else 0,
        comment_count=comment_count,
        like_count=int(post.like_count or 0),
        dislike_count=int(post.dislike_count or 0),
        rating_summary=rating_payload
        if thread_type == FORUM_THREAD_TYPE_NOVEL
        else PublicForumRatingSummaryOut(),
        discoverability_score=float(resolved_discoverability_score),
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


async def create_public_forum_post(
    db: AsyncSession,
    *,
    current_user: User,
    body: PublicForumPostCreateBody,
    image_upload: UploadFile | None = None,
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
        book = await _get_forum_eligible_owned_book(
            db, book_id=body.book_id, author_user_id=current_user.id
        )
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
            raise HTTPException(
                409, "This manuscript already has a beta forum post. Update it instead."
            )
        desired_beta_reader_count = body.desired_beta_reader_count
        allow_contact_requests = bool(body.allow_contact_requests)
    else:
        if body.book_id is not None:
            raise HTTPException(400, "General discussions cannot be attached to a manuscript.")
        await enforce_daily_general_forum_post_limit(db, user_id=current_user.id)

    post_id = uuid.uuid4()
    image_s3_key = None
    image_content_type = None
    image_filename = None
    if image_upload is not None:
        image_s3_key, image_content_type, image_filename = await store_public_forum_image(
            image_upload,
            owner_user_id=current_user.id,
            target_kind="post",
            target_id=post_id,
        )

    post = BookForumPost(
        id=post_id,
        book_id=book.id if book is not None else None,
        author_user_id=current_user.id,
        thread_type=thread_type,
        headline=headline,
        body=description,
        image_s3_key=image_s3_key,
        image_content_type=image_content_type,
        image_filename=image_filename,
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
    image_upload: UploadFile | None = None,
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
        book = await _get_forum_eligible_owned_book(
            db, book_id=post.book_id, author_user_id=current_user.id
        )
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
            or body.remove_image
            or image_upload is not None
            or next_status != FORUM_POST_CLOSED
        )
        if attempted_non_closing_change:
            raise HTTPException(
                403,
                "Opening or editing a public discussion requires Trial, Author, or Architect access.",
            )
    if (
        thread_type == FORUM_THREAD_TYPE_NOVEL
        and next_status == FORUM_POST_OPEN
        and book is not None
    ):
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
    previous_image_s3_key = post.image_s3_key
    post.headline = headline
    post.body = description
    if image_upload is not None:
        (
            post.image_s3_key,
            post.image_content_type,
            post.image_filename,
        ) = await store_public_forum_image(
            image_upload,
            owner_user_id=current_user.id,
            target_kind="post",
            target_id=post.id,
        )
    elif body.remove_image:
        post.image_s3_key = None
        post.image_content_type = None
        post.image_filename = None
    post.desired_beta_reader_count = (
        body.desired_beta_reader_count if thread_type == FORUM_THREAD_TYPE_NOVEL else None
    )
    post.allow_contact_requests = (
        bool(body.allow_contact_requests) if thread_type == FORUM_THREAD_TYPE_NOVEL else False
    )
    post.status = next_status
    await db.commit()
    await db.refresh(post)
    if image_upload is not None or body.remove_image:
        if previous_image_s3_key and previous_image_s3_key != post.image_s3_key:
            await delete_storage_key_best_effort(
                previous_image_s3_key, context="public_forum_image"
            )
    await _invalidate_public_forum_cache()
    await _invalidate_public_profile_cache_for_users(current_user.id)
    return await get_public_forum_post_detail(db, post_id=post.id, current_user=current_user)


async def list_public_forum_posts(
    db: AsyncSession,
    *,
    q: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
    thread_type: str | None = None,
    current_user: User | None = None,
) -> PublicForumPostListOut:
    normalized_page, normalized_page_size = _normalize_public_forum_pagination(page, page_size)
    visibility_filters = list(_public_forum_visibility_filters())
    if thread_type and thread_type in VALID_FORUM_THREAD_TYPES:
        visibility_filters.append(BookForumPost.thread_type == thread_type)
    total_statement = (
        select(func.count(BookForumPost.id))
        .outerjoin(Book, Book.id == BookForumPost.book_id)
        .join(User, User.id == BookForumPost.author_user_id)
        .where(*visibility_filters)
    )
    search_clause = _public_forum_search_clause(q)
    if search_clause is not None:
        total_statement = total_statement.where(search_clause)
    total = int((await db.execute(total_statement)).scalar_one() or 0)

    statement = _public_forum_post_select_statement(
        q=q,
        viewer_user_id=current_user.id if current_user is not None else None,
        thread_type=thread_type,
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
            statement.offset((normalized_page - 1) * normalized_page_size).limit(
                normalized_page_size
            )
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
