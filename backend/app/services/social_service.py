"""Bounded direct-message read paths and read-state mutations."""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.social import DirectConversation, DirectMessage, FriendRequest
from app.models.user import User
from app.schemas.social import (
    DirectConversationPageOut,
    DirectConversationSummary,
    DirectMessageOut,
    DirectMessagePageOut,
    SocialUserSummary,
)
from app.utils.social_utils import (
    can_message_target,
    derive_friend_state,
    ensure_conversation_access,
)

DEFAULT_CONVERSATION_PAGE_LIMIT = 30
DEFAULT_MESSAGE_PAGE_LIMIT = 50
MAX_CONVERSATION_PAGE_LIMIT = 100
MAX_MESSAGE_PAGE_LIMIT = 200


def _encode_cursor(payload: dict[str, str]) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")


def _decode_cursor(cursor: str, *, error_detail: str) -> dict[str, object]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if not isinstance(payload, dict):
            raise ValueError("Cursor must be an object")
        return payload
    except (TypeError, ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise HTTPException(400, error_detail) from exc


def _decode_timestamp(value: object, *, error_detail: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(str(value))
        if timestamp.tzinfo is None:
            raise ValueError("Cursor timestamp must include a timezone")
        return timestamp
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, error_detail) from exc


def encode_conversation_page_cursor(activity_at: datetime, conversation_id: uuid.UUID) -> str:
    """Encode the full conversation ordering tuple into an opaque cursor."""
    return _encode_cursor({"activity_at": activity_at.isoformat(), "id": str(conversation_id)})


def decode_conversation_page_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode a conversation cursor, rejecting malformed values."""
    error_detail = "Invalid conversation page cursor"
    payload = _decode_cursor(cursor, error_detail=error_detail)
    try:
        activity_at = _decode_timestamp(payload["activity_at"], error_detail=error_detail)
        return activity_at, uuid.UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, error_detail) from exc


def encode_message_page_cursor(created_at: datetime, message_id: uuid.UUID) -> str:
    """Encode the full reverse-chronological message ordering tuple."""
    return _encode_cursor({"created_at": created_at.isoformat(), "id": str(message_id)})


def decode_message_page_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode a message cursor, rejecting malformed values."""
    error_detail = "Invalid message page cursor"
    payload = _decode_cursor(cursor, error_detail=error_detail)
    try:
        created_at = _decode_timestamp(payload["created_at"], error_detail=error_detail)
        return created_at, uuid.UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, error_detail) from exc


def _bounded_limit(limit: int, *, maximum: int) -> int:
    return max(1, min(int(limit), maximum))


def _conversation_activity_expression():
    return func.coalesce(DirectConversation.last_message_at, DirectConversation.created_at)


async def _relationships_by_other_user_id(
    db: AsyncSession,
    *,
    current_user_id: uuid.UUID,
    other_user_ids: set[uuid.UUID],
) -> dict[uuid.UUID, FriendRequest]:
    if not other_user_ids:
        return {}
    rows = list(
        (
            await db.execute(
                select(FriendRequest).where(
                    or_(
                        and_(
                            FriendRequest.requester_user_id == current_user_id,
                            FriendRequest.addressee_user_id.in_(other_user_ids),
                        ),
                        and_(
                            FriendRequest.addressee_user_id == current_user_id,
                            FriendRequest.requester_user_id.in_(other_user_ids),
                        ),
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    relationships: dict[uuid.UUID, FriendRequest] = {}
    for relationship in rows:
        other_user_id = (
            relationship.addressee_user_id
            if relationship.requester_user_id == current_user_id
            else relationship.requester_user_id
        )
        relationships[other_user_id] = relationship
    return relationships


def _direct_message_out(message: DirectMessage) -> DirectMessageOut:
    return DirectMessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_user_id=message.sender_user_id,
        recipient_user_id=message.recipient_user_id,
        body=message.body,
        recipient_read_at=message.recipient_read_at,
        created_at=message.created_at,
    )


def _conversation_summary(
    *,
    current_user_id: uuid.UUID,
    conversation: DirectConversation,
    other_user: User,
    last_message: DirectMessage | None,
    unread_count: int,
    relationship: FriendRequest | None,
) -> DirectConversationSummary:
    return DirectConversationSummary(
        id=conversation.id,
        other_user=SocialUserSummary(
            id=other_user.id,
            username=other_user.username or "member",
            messaging_permission=(
                "friends_only"
                if other_user.messaging_permission == "friends_only"
                else "anyone"
            ),
            friend_state=derive_friend_state(current_user_id, relationship),
            can_message=can_message_target(current_user_id, other_user, relationship),
        ),
        last_message_preview=last_message.body[:120] if last_message is not None else None,
        last_message_at=(
            last_message.created_at if last_message is not None else conversation.last_message_at
        ),
        unread_count=unread_count,
    )


async def list_direct_conversation_page(
    db: AsyncSession,
    *,
    current_user: User,
    limit: int = DEFAULT_CONVERSATION_PAGE_LIMIT,
    cursor: str | None = None,
) -> DirectConversationPageOut:
    """Load one stable page of a user's conversation summaries without N+1 reads."""
    bounded_limit = _bounded_limit(limit, maximum=MAX_CONVERSATION_PAGE_LIMIT)
    other_user = aliased(User)
    last_message = aliased(DirectMessage)
    activity_at = _conversation_activity_expression()
    other_user_id = case(
        (
            DirectConversation.participant_a_user_id == current_user.id,
            DirectConversation.participant_b_user_id,
        ),
        else_=DirectConversation.participant_a_user_id,
    )
    latest_message_id = (
        select(DirectMessage.id)
        .where(DirectMessage.conversation_id == DirectConversation.id)
        .order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc())
        .limit(1)
        .correlate(DirectConversation)
        .scalar_subquery()
    )
    unread_counts = (
        select(
            DirectMessage.conversation_id.label("conversation_id"),
            func.count(DirectMessage.id).label("unread_count"),
        )
        .where(
            DirectMessage.recipient_user_id == current_user.id,
            DirectMessage.recipient_read_at.is_(None),
        )
        .group_by(DirectMessage.conversation_id)
        .subquery()
    )
    statement = (
        select(
            DirectConversation,
            other_user,
            last_message,
            func.coalesce(unread_counts.c.unread_count, 0).label("unread_count"),
            activity_at.label("activity_at"),
        )
        .join(other_user, other_user.id == other_user_id)
        .outerjoin(last_message, last_message.id == latest_message_id)
        .outerjoin(unread_counts, unread_counts.c.conversation_id == DirectConversation.id)
        .where(
            or_(
                DirectConversation.participant_a_user_id == current_user.id,
                DirectConversation.participant_b_user_id == current_user.id,
            )
        )
        .order_by(activity_at.desc(), DirectConversation.id.desc())
        .limit(bounded_limit + 1)
    )
    if cursor:
        cursor_activity_at, cursor_id = decode_conversation_page_cursor(cursor)
        statement = statement.where(
            or_(
                activity_at < cursor_activity_at,
                and_(activity_at == cursor_activity_at, DirectConversation.id < cursor_id),
            )
        )

    rows = list((await db.execute(statement)).all())
    has_more = len(rows) > bounded_limit
    page_rows = rows[:bounded_limit]
    relationships = await _relationships_by_other_user_id(
        db,
        current_user_id=current_user.id,
        other_user_ids={row[1].id for row in page_rows},
    )
    items = [
        _conversation_summary(
            current_user_id=current_user.id,
            conversation=conversation,
            other_user=other_user_row,
            last_message=last_message_row,
            unread_count=int(unread_count),
            relationship=relationships.get(other_user_row.id),
        )
        for conversation, other_user_row, last_message_row, unread_count, _activity_at in page_rows
    ]
    return DirectConversationPageOut(
        items=items,
        next_cursor=(
            encode_conversation_page_cursor(page_rows[-1][4], page_rows[-1][0].id)
            if has_more and page_rows
            else None
        ),
        has_more=has_more,
    )


async def list_direct_message_page(
    db: AsyncSession,
    *,
    current_user: User,
    conversation_id: uuid.UUID,
    limit: int = DEFAULT_MESSAGE_PAGE_LIMIT,
    cursor: str | None = None,
) -> DirectMessagePageOut:
    """Load older messages with a newest-first query and chronological response."""
    conversation = await ensure_conversation_access(
        db, current_user=current_user, conversation_id=conversation_id
    )
    bounded_limit = _bounded_limit(limit, maximum=MAX_MESSAGE_PAGE_LIMIT)
    statement = (
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conversation.id)
        .order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc())
        .limit(bounded_limit + 1)
    )
    if cursor:
        cursor_created_at, cursor_id = decode_message_page_cursor(cursor)
        statement = statement.where(
            or_(
                DirectMessage.created_at < cursor_created_at,
                and_(
                    DirectMessage.created_at == cursor_created_at,
                    DirectMessage.id < cursor_id,
                ),
            )
        )

    rows = list((await db.execute(statement)).scalars().all())
    has_more = len(rows) > bounded_limit
    page_rows = rows[:bounded_limit]
    return DirectMessagePageOut(
        items=[_direct_message_out(message) for message in reversed(page_rows)],
        next_cursor=(
            encode_message_page_cursor(page_rows[-1].created_at, page_rows[-1].id)
            if has_more and page_rows
            else None
        ),
        has_more=has_more,
    )


async def mark_direct_conversation_read(
    db: AsyncSession, *, current_user: User, conversation_id: uuid.UUID
) -> None:
    """Mark unread incoming messages with one scoped update statement."""
    await ensure_conversation_access(db, current_user=current_user, conversation_id=conversation_id)
    result = await db.execute(
        update(DirectMessage)
        .where(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.recipient_user_id == current_user.id,
            DirectMessage.recipient_read_at.is_(None),
        )
        .values(recipient_read_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    if result.rowcount:
        await db.commit()
