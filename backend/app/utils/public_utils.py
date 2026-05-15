from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book, BookForumComment, BookForumCommentReaction, BookForumInterest, BookForumPost, Chapter
from app.models.intelligence import Notification
from app.models.user import User
from app.schemas.public import (
    PublicForumCommentCreateBody,
    PublicForumCommentOut,
    PublicForumInterestCreateBody,
    PublicForumInterestOut,
    PublicForumPostCreateBody,
    PublicForumPostOut,
    PublicForumPostUpdateBody,
    PublicForumRatingSummaryOut,
    PublicUserProfileOut,
    PublicUserProjectOut,
)
from app.utils.beta_read_utils import book_beta_rating_summary

FORUM_POST_OPEN = "open"
FORUM_POST_CLOSED = "closed"
VALID_FORUM_POST_STATUSES = {FORUM_POST_OPEN, FORUM_POST_CLOSED}
FORUM_COMMENT_REACTION_LIKE = "like"
FORUM_COMMENT_REACTION_DISLIKE = "dislike"
FORUM_COMMENT_REACTION_CLEAR = "clear"
VALID_FORUM_COMMENT_REACTIONS = {
    FORUM_COMMENT_REACTION_LIKE,
    FORUM_COMMENT_REACTION_DISLIKE,
    FORUM_COMMENT_REACTION_CLEAR,
}


def ensure_public_mode_enabled() -> None:
    if not settings.PUBLIC_MODE_ENABLED:
        raise HTTPException(503, "Public mode is temporarily disabled")


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


async def _get_private_owned_book(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    author_user_id: uuid.UUID,
) -> Book:
    book = await db.get(Book, book_id)
    if book is None or book.user_id != author_user_id:
        raise HTTPException(404, "Book not found.")
    if bool(book.is_public):
        raise HTTPException(409, "Only private manuscripts can be posted in the public beta forum.")
    if book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(409, "This manuscript is not available for public beta discovery.")
    return book


async def _get_forum_post(db: AsyncSession, *, post_id: uuid.UUID) -> BookForumPost:
    post = await db.get(BookForumPost, post_id)
    if post is None:
        raise HTTPException(404, "Forum post not found.")
    return post


async def _get_visible_forum_post(db: AsyncSession, *, post_id: uuid.UUID) -> tuple[BookForumPost, Book]:
    post = await _get_forum_post(db, post_id=post_id)
    if post.status != FORUM_POST_OPEN:
        raise HTTPException(404, "Forum post not found.")
    book = await db.get(Book, post.book_id)
    if book is None or book.hidden_at is not None or book.archived_at is not None or bool(book.is_public):
        raise HTTPException(404, "Forum post not found.")
    return post, book


async def _count_forum_interests(db: AsyncSession, *, post_id: uuid.UUID) -> int:
    count = (
        await db.execute(select(func.count(BookForumInterest.id)).where(BookForumInterest.post_id == post_id))
    ).scalar_one()
    return int(count or 0)


async def _count_forum_comments(db: AsyncSession, *, post_id: uuid.UUID) -> int:
    count = (
        await db.execute(select(func.count(BookForumComment.id)).where(BookForumComment.post_id == post_id))
    ).scalar_one()
    return int(count or 0)


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
                BookForumPost.status == FORUM_POST_OPEN,
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
                Book.is_public.is_(False),
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

    latest_book = (
        await db.execute(
            select(Book)
            .where(
                Book.user_id == user_id,
                Book.is_public.is_(True),
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
            )
            .order_by(Book.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
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
            .join(Book, Book.id == BookForumPost.book_id)
            .where(
                BookForumPost.author_user_id == user_id,
                BookForumPost.status == FORUM_POST_OPEN,
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
                Book.is_public.is_(False),
            )
        )
    ).scalar_one()
    public_forum_comment_count = (
        await db.execute(
            select(func.count(BookForumComment.id))
            .join(BookForumPost, BookForumPost.id == BookForumComment.post_id)
            .join(Book, Book.id == BookForumComment.book_id)
            .where(
                BookForumComment.author_user_id == user_id,
                BookForumPost.status == FORUM_POST_OPEN,
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
                Book.is_public.is_(False),
            )
        )
    ).scalar_one()
    public_book_count = (
        await db.execute(
            select(func.count(Book.id)).where(
                Book.user_id == user_id,
                Book.is_public.is_(True),
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
            )
        )
    ).scalar_one()
    return (
        int(public_forum_post_count or 0),
        int(public_forum_comment_count or 0),
        int(public_book_count or 0),
    )


async def _user_has_public_profile_presence(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    return any(await public_profile_activity_counts(db, user_id=user_id))


async def build_public_user_profile_out(
    db: AsyncSession,
    *,
    user: User,
) -> PublicUserProfileOut:
    forum_post_count, forum_comment_count, _public_book_count = await public_profile_activity_counts(db, user_id=user.id)
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
        created_at=user.created_at,
    )


async def build_public_forum_post_out(
    db: AsyncSession,
    *,
    post: BookForumPost,
    book: Book | None = None,
    author_user: User | None = None,
    interest_count: int | None = None,
    comment_count: int | None = None,
) -> PublicForumPostOut:
    resolved_book = book or await db.get(Book, post.book_id)
    if resolved_book is None:
        raise HTTPException(404, "Book not found.")
    resolved_author = author_user or await db.get(User, post.author_user_id)
    if resolved_author is None:
        raise HTTPException(404, "Author not found.")
    rating_summary = await book_beta_rating_summary(db, book_id=post.book_id)
    resolved_interest_count = interest_count if interest_count is not None else await _count_forum_interests(db, post_id=post.id)
    resolved_comment_count = comment_count if comment_count is not None else await _count_forum_comments(db, post_id=post.id)
    rating_payload = PublicForumRatingSummaryOut(**rating_summary)
    discoverability_score = public_forum_discoverability_score(
        average_rating=rating_payload.average_rating,
        rating_count=rating_payload.rating_count,
        positive_rating_count=rating_payload.positive_rating_count,
        negative_rating_count=rating_payload.negative_rating_count,
        interest_count=resolved_interest_count,
    )
    return PublicForumPostOut(
        id=str(post.id),
        book_id=str(post.book_id),
        author_user_id=str(post.author_user_id),
        author_username=resolved_author.username,
        author_reputation_score=int(resolved_author.reputation_score or 0),
        author_trust_level=reputation_trust_level(resolved_author.reputation_score),
        title=resolved_book.title,
        author=resolved_book.author,
        genre=resolved_book.genre,
        work_type=resolved_book.work_type,
        headline=post.headline,
        body=post.body,
        desired_beta_reader_count=post.desired_beta_reader_count,
        allow_contact_requests=bool(post.allow_contact_requests),
        status=post.status,
        interest_count=resolved_interest_count,
        comment_count=resolved_comment_count,
        rating_summary=rating_payload,
        discoverability_score=discoverability_score,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


async def create_public_forum_post(
    db: AsyncSession,
    *,
    current_user: User,
    body: PublicForumPostCreateBody,
) -> PublicForumPostOut:
    book = await _get_private_owned_book(db, book_id=body.book_id, author_user_id=current_user.id)
    headline = " ".join(body.headline.split()).strip()
    description = body.body.strip()
    if not headline or not description:
        raise HTTPException(400, "Forum headline and body are required.")
    existing = (
        await db.execute(select(BookForumPost).where(BookForumPost.book_id == book.id))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, "This manuscript already has a beta forum post. Update it instead.")

    post = BookForumPost(
        book_id=book.id,
        author_user_id=current_user.id,
        headline=headline,
        body=description,
        desired_beta_reader_count=body.desired_beta_reader_count,
        allow_contact_requests=bool(body.allow_contact_requests),
        status=FORUM_POST_OPEN,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return await build_public_forum_post_out(db, post=post, book=book, author_user=current_user, interest_count=0, comment_count=0)


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
    book = await _get_private_owned_book(db, book_id=post.book_id, author_user_id=current_user.id)
    headline = " ".join(body.headline.split()).strip()
    description = body.body.strip()
    if not headline or not description:
        raise HTTPException(400, "Forum headline and body are required.")
    post.headline = headline
    post.body = description
    post.desired_beta_reader_count = body.desired_beta_reader_count
    post.allow_contact_requests = bool(body.allow_contact_requests)
    post.status = _normalize_forum_status(body.status)
    await db.commit()
    await db.refresh(post)
    return await build_public_forum_post_out(db, post=post, book=book, author_user=current_user)


async def list_public_forum_posts(
    db: AsyncSession,
    *,
    q: str | None = None,
) -> list[PublicForumPostOut]:
    statement = (
        select(BookForumPost, Book, User)
        .join(Book, Book.id == BookForumPost.book_id)
        .join(User, User.id == BookForumPost.author_user_id)
        .where(
            BookForumPost.status == FORUM_POST_OPEN,
            Book.hidden_at.is_(None),
            Book.archived_at.is_(None),
            Book.is_public.is_(False),
        )
    )
    query = " ".join((q or "").split()).strip()
    if query:
        like = f"%{query}%"
        statement = statement.where(
            or_(
                Book.title.ilike(like),
                Book.author.ilike(like),
                Book.genre.ilike(like),
                BookForumPost.headline.ilike(like),
                BookForumPost.body.ilike(like),
                User.username.ilike(like),
            )
        )
    rows = (await db.execute(statement)).all()
    items = [await build_public_forum_post_out(db, post=post, book=book, author_user=author_user) for post, book, author_user in rows]
    return sorted(
        items,
        key=lambda item: (
            item.discoverability_score,
            item.author_reputation_score,
            item.rating_summary.average_rating or 0.0,
            item.rating_summary.rating_count,
            item.comment_count,
            item.created_at,
        ),
        reverse=True,
    )


async def get_public_forum_post_detail(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
) -> PublicForumPostOut:
    post, book = await _get_visible_forum_post(db, post_id=post_id)
    author_user = await db.get(User, post.author_user_id)
    return await build_public_forum_post_out(db, post=post, book=book, author_user=author_user)


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
        book_id=str(comment.book_id),
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


async def list_public_forum_comments(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    current_user: User | None = None,
) -> list[PublicForumCommentOut]:
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
    return [
        await build_public_forum_comment_out(
            db,
            comment=comment,
            author_user=author_user,
            current_user=current_user,
            reaction_map=reaction_map,
        )
        for comment, author_user in rows
    ]


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
    comment = BookForumComment(
        post_id=post.id,
        book_id=post.book_id,
        author_user_id=current_user.id,
        body=comment_body,
    )
    post.last_activity_at = func.now()
    db.add(comment)
    if post.author_user_id != current_user.id:
        db.add(
            Notification(
                user_id=post.author_user_id,
                book_id=post.book_id,
                kind="beta_forum_comment_received",
                title="New beta forum comment",
                body="Someone replied to your public beta forum post.",
                data={
                    "post_id": str(post.id),
                    "book_id": str(post.book_id),
                    "comment_author_user_id": str(current_user.id),
                },
            )
        )
    await db.commit()
    await db.refresh(comment)
    return await build_public_forum_comment_out(db, comment=comment, author_user=current_user, current_user=current_user)


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
    reaction_map = {comment.id: next_reaction} if next_reaction else {}
    return await build_public_forum_comment_out(
        db,
        comment=comment,
        author_user=author_user,
        current_user=current_user,
        reaction_map=reaction_map,
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
    return await build_public_user_profile_out(db, user=user)
