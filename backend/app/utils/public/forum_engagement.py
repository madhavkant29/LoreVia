from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    BookForumComment,
    BookForumCommentReaction,
    BookForumInterest,
    BookForumPost,
    BookForumPostReaction,
)
from app.models.intelligence import Notification
from app.models.user import User
from app.schemas.public import (
    PublicForumCommentCreateBody,
    PublicForumCommentOut,
    PublicForumInterestCreateBody,
    PublicForumInterestOut,
    PublicForumPostOut,
)
from app.utils.public.forum_foundation import (
    _forum_post_thread_type,
    _get_author_accessible_forum_post,
    _get_forum_post,
    _get_visible_forum_post,
    _invalidate_public_forum_cache,
    _invalidate_public_profile_cache_for_users,
    _is_general_forum_post,
    _normalize_forum_comment_reaction,
    _reaction_delta,
    reputation_trust_level,
)
from app.utils.public.forum_posts import (
    _comment_reaction_map,
    get_public_forum_post_detail,
)
from app.utils.public.requests import (
    public_forum_image_url,
    store_public_forum_image,
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


async def build_public_forum_interest_out(
    db: AsyncSession,
    *,
    interest: BookForumInterest,
    interested_user: User | None = None,
) -> PublicForumInterestOut:
    resolved_user = interested_user or await db.get(User, interest.interested_user_id)
    if resolved_user is None:
        raise HTTPException(404, "Interested user not found.")
    return PublicForumInterestOut(
        id=str(interest.id),
        post_id=str(interest.post_id),
        book_id=str(interest.book_id),
        author_user_id=str(interest.author_user_id),
        interested_user_id=str(interest.interested_user_id),
        interested_username=resolved_user.username,
        interested_email=resolved_user.email,
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
            select(BookForumInterest, User)
            .join(User, User.id == BookForumInterest.interested_user_id)
            .where(BookForumInterest.post_id == post.id)
            .order_by(BookForumInterest.created_at.desc())
        )
    ).all()
    return [
        await build_public_forum_interest_out(
            db, interest=interest, interested_user=interested_user
        )
        for interest, interested_user in interests
    ]


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
        parent_comment_id=str(comment.parent_comment_id)
        if comment.parent_comment_id is not None
        else None,
        author_user_id=str(comment.author_user_id),
        author_username=resolved_author.username,
        author_reputation_score=int(resolved_author.reputation_score or 0),
        author_trust_level=reputation_trust_level(resolved_author.reputation_score),
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
        reaction=current_reaction,
        can_edit=current_user is not None and comment.author_user_id == current_user.id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def _nest_public_forum_comments(
    comments: list[PublicForumCommentOut],
) -> list[PublicForumCommentOut]:
    comment_map = {comment.id: comment.model_copy(update={"replies": []}) for comment in comments}
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
    image_upload: UploadFile | None = None,
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
    comment_id = uuid.uuid4()
    image_s3_key = None
    image_content_type = None
    image_filename = None
    if image_upload is not None:
        image_s3_key, image_content_type, image_filename = await store_public_forum_image(
            image_upload,
            owner_user_id=current_user.id,
            target_kind="comment",
            target_id=comment_id,
        )

    comment = BookForumComment(
        id=comment_id,
        post_id=post.id,
        book_id=post.book_id,
        parent_comment_id=parent_comment.id if parent_comment is not None else None,
        author_user_id=current_user.id,
        body=comment_body,
        image_s3_key=image_s3_key,
        image_content_type=image_content_type,
        image_filename=image_filename,
    )
    post.last_activity_at = func.now()
    db.add(comment)
    await db.flush()
    notified_user_ids: set[uuid.UUID] = set()
    if post.author_user_id != current_user.id:
        notified_user_ids.add(post.author_user_id)
        notification_title = (
            "New beta forum comment"
            if _forum_post_thread_type(post) == FORUM_THREAD_TYPE_NOVEL
            else "New forum comment"
        )
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
    return await build_public_forum_comment_out(
        db, comment=comment, author_user=current_user, current_user=current_user
    )


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
    next_reaction = (
        None if normalized_reaction == FORUM_COMMENT_REACTION_CLEAR else normalized_reaction
    )
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
    author_user.reputation_likes_received = max(
        int(author_user.reputation_likes_received or 0) + like_delta, 0
    )
    author_user.reputation_dislikes_received = max(
        int(author_user.reputation_dislikes_received or 0) + dislike_delta, 0
    )
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
    next_reaction = (
        None if normalized_reaction == FORUM_COMMENT_REACTION_CLEAR else normalized_reaction
    )
    if previous_reaction == next_reaction:
        return await get_public_forum_post_detail(db, post_id=post.id, current_user=current_user)

    like_delta, dislike_delta, reputation_delta = _reaction_delta(previous_reaction, next_reaction)
    post.like_count = max(int(post.like_count or 0) + like_delta, 0)
    post.dislike_count = max(int(post.dislike_count or 0) + dislike_delta, 0)
    author_user.reputation_likes_received = max(
        int(author_user.reputation_likes_received or 0) + like_delta, 0
    )
    author_user.reputation_dislikes_received = max(
        int(author_user.reputation_dislikes_received or 0) + dislike_delta, 0
    )
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
