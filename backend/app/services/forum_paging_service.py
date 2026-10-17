"""Bounded cursor pages for secondary public-forum collections."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import BookForumComment, BookForumInterest, BookForumPost
from app.models.user import User
from app.schemas.public import (
    PublicForumCommentCursorPageOut,
    PublicForumInterestCursorPageOut,
    PublicForumPostCursorPageOut,
    PublicForumRatingSummaryOut,
)
from app.utils.pagination_utils import (
    decode_datetime_uuid_cursor,
    encode_datetime_uuid_cursor,
)
from app.utils.public.forum_engagement import (
    build_public_forum_comment_out,
    build_public_forum_interest_out,
)
from app.utils.public.forum_foundation import (
    _author_forum_post_select_statement,
    _get_author_accessible_forum_post,
    _get_forum_post,
    _get_visible_forum_post,
    _is_general_forum_post,
)
from app.utils.public.forum_posts import _comment_reaction_map, build_public_forum_post_out


def _decode_cursor(cursor: str | None) -> tuple | None:
    if not cursor:
        return None
    try:
        return decode_datetime_uuid_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(400, "Invalid forum page cursor") from exc


async def list_author_forum_posts_page(
    db: AsyncSession,
    *,
    author_user_id: uuid.UUID,
    limit: int,
    cursor: str | None,
) -> PublicForumPostCursorPageOut:
    statement = _author_forum_post_select_statement(author_user_id=author_user_id)
    decoded = _decode_cursor(cursor)
    if decoded is not None:
        cursor_updated_at, cursor_id = decoded
        statement = statement.where(
            or_(
                BookForumPost.updated_at < cursor_updated_at,
                and_(
                    BookForumPost.updated_at == cursor_updated_at,
                    BookForumPost.id < cursor_id,
                ),
            )
        )
    rows = (
        await db.execute(
            statement.order_by(BookForumPost.updated_at.desc(), BookForumPost.id.desc()).limit(
                limit + 1
            )
        )
    ).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
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
        ) in page_rows
    ]
    return PublicForumPostCursorPageOut(
        items=items,
        has_more=has_more,
        next_cursor=(
            encode_datetime_uuid_cursor(page_rows[-1][0].updated_at, page_rows[-1][0].id)
            if has_more and page_rows
            else None
        ),
    )


async def list_forum_interests_page(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    author_user_id: uuid.UUID,
    limit: int,
    cursor: str | None,
) -> PublicForumInterestCursorPageOut:
    post = await _get_forum_post(db, post_id=post_id)
    if post.author_user_id != author_user_id:
        raise HTTPException(404, "Forum post not found.")
    if _is_general_forum_post(post):
        return PublicForumInterestCursorPageOut(items=[])

    statement = (
        select(BookForumInterest, User)
        .join(User, User.id == BookForumInterest.interested_user_id)
        .where(BookForumInterest.post_id == post.id)
    )
    decoded = _decode_cursor(cursor)
    if decoded is not None:
        cursor_created_at, cursor_id = decoded
        statement = statement.where(
            or_(
                BookForumInterest.created_at < cursor_created_at,
                and_(
                    BookForumInterest.created_at == cursor_created_at,
                    BookForumInterest.id < cursor_id,
                ),
            )
        )
    rows = (
        await db.execute(
            statement.order_by(
                BookForumInterest.created_at.desc(), BookForumInterest.id.desc()
            ).limit(limit + 1)
        )
    ).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [
        await build_public_forum_interest_out(
            db,
            interest=interest,
            interested_user=interested_user,
        )
        for interest, interested_user in page_rows
    ]
    return PublicForumInterestCursorPageOut(
        items=items,
        has_more=has_more,
        next_cursor=(
            encode_datetime_uuid_cursor(page_rows[-1][0].created_at, page_rows[-1][0].id)
            if has_more and page_rows
            else None
        ),
    )


async def list_forum_comments_page(
    db: AsyncSession,
    *,
    post_id: uuid.UUID,
    current_user: User | None,
    limit: int,
    cursor: str | None,
) -> PublicForumCommentCursorPageOut:
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

    statement = (
        select(BookForumComment, User)
        .join(User, User.id == BookForumComment.author_user_id)
        .where(BookForumComment.post_id == post.id)
    )
    decoded = _decode_cursor(cursor)
    if decoded is not None:
        cursor_created_at, cursor_id = decoded
        statement = statement.where(
            or_(
                BookForumComment.created_at > cursor_created_at,
                and_(
                    BookForumComment.created_at == cursor_created_at,
                    BookForumComment.id > cursor_id,
                ),
            )
        )
    rows = (
        await db.execute(
            statement.order_by(BookForumComment.created_at.asc(), BookForumComment.id.asc()).limit(
                limit + 1
            )
        )
    ).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    comment_ids = [comment.id for comment, _author in page_rows]
    reaction_map = await _comment_reaction_map(
        db,
        post_id=post.id,
        user_id=current_user.id if current_user is not None else None,
        comment_ids=comment_ids,
    )
    items = [
        await build_public_forum_comment_out(
            db,
            comment=comment,
            author_user=author,
            current_user=current_user,
            reaction_map=reaction_map,
        )
        for comment, author in page_rows
    ]
    return PublicForumCommentCursorPageOut(
        items=items,
        has_more=has_more,
        next_cursor=(
            encode_datetime_uuid_cursor(page_rows[-1][0].created_at, page_rows[-1][0].id)
            if has_more and page_rows
            else None
        ),
    )
