from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.social import DirectConversation, DirectMessage, FriendRequest
from app.models.user import User
from app.schemas.social import DirectConversationSummary, FriendRequestOut, FriendSummary, SocialRelationshipListOut, SocialUserSummary
from app.utils.notification_utils import create_notification_once, make_notification_idempotency_key


def normalize_messaging_permission(value: str | None) -> str:
    return "friends_only" if value == "friends_only" else "anyone"


def canonical_user_pair(first_user_id: uuid.UUID, second_user_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    if str(first_user_id) <= str(second_user_id):
        return first_user_id, second_user_id
    return second_user_id, first_user_id


async def get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


async def get_relationship_record(db: AsyncSession, first_user_id: uuid.UUID, second_user_id: uuid.UUID) -> FriendRequest | None:
    return (
        await db.execute(
            select(FriendRequest).where(
                or_(
                    and_(
                        FriendRequest.requester_user_id == first_user_id,
                        FriendRequest.addressee_user_id == second_user_id,
                    ),
                    and_(
                        FriendRequest.requester_user_id == second_user_id,
                        FriendRequest.addressee_user_id == first_user_id,
                    ),
                )
            )
        )
    ).scalar_one_or_none()


def derive_friend_state(current_user_id: uuid.UUID, relationship: FriendRequest | None) -> str:
    if relationship is None:
        return "none"
    if relationship.status == "accepted":
        return "accepted"
    if relationship.status != "pending":
        return "none"
    if relationship.requester_user_id == current_user_id:
        return "outgoing_pending"
    return "incoming_pending"


def can_message_target(current_user_id: uuid.UUID, target: User, relationship: FriendRequest | None) -> bool:
    if target.id == current_user_id:
        return False
    if normalize_messaging_permission(target.messaging_permission) == "anyone":
        return True
    return relationship is not None and relationship.status == "accepted"


async def build_social_user_summary(
    db: AsyncSession,
    *,
    current_user_id: uuid.UUID,
    target: User,
    relationship: FriendRequest | None = None,
) -> SocialUserSummary:
    relation = relationship or await get_relationship_record(db, current_user_id, target.id)
    friend_state = derive_friend_state(current_user_id, relation)
    return SocialUserSummary(
        id=target.id,
        username=target.username or "member",
        messaging_permission=normalize_messaging_permission(target.messaging_permission),
        friend_state=friend_state,
        can_message=can_message_target(current_user_id, target, relation),
    )


async def search_users_for_social(db: AsyncSession, *, current_user_id: uuid.UUID, query: str, limit: int = 10) -> list[SocialUserSummary]:
    normalized = (query or "").strip().lower()
    if len(normalized) < 2:
        return []
    rows = (
        await db.execute(
            select(User)
            .where(
                User.id != current_user_id,
                User.username.is_not(None),
                func.lower(User.username).like(f"%{normalized}%"),
            )
            .order_by(func.lower(User.username))
            .limit(limit)
        )
    ).scalars().all()
    items: list[SocialUserSummary] = []
    for user in rows:
        items.append(await build_social_user_summary(db, current_user_id=current_user_id, target=user))
    return items


async def create_friend_request(db: AsyncSession, *, current_user: User, target_user_id: uuid.UUID) -> FriendRequest:
    if current_user.id == target_user_id:
        raise HTTPException(400, "You cannot send a friend request to yourself.")
    target = await get_user_or_404(db, target_user_id)
    existing = await get_relationship_record(db, current_user.id, target_user_id)
    if existing is not None:
        if existing.status == "accepted":
            raise HTTPException(400, "You are already friends.")
        if existing.status == "pending":
            if existing.requester_user_id == current_user.id:
                raise HTTPException(400, "Friend request already sent.")
            raise HTTPException(409, "This user has already sent you a friend request.")
    request = FriendRequest(
        requester_user_id=current_user.id,
        addressee_user_id=target_user_id,
        status="pending",
    )
    db.add(request)
    await db.flush()
    await create_notification_once(
        db,
        user_id=target_user_id,
        kind="friend_request",
        title=f"@{current_user.username or 'member'} sent you a friend request",
        body="Accept to unlock direct messages if you keep messaging limited to friends.",
        idempotency_key=make_notification_idempotency_key("friend-request", str(request.id), str(target_user_id)),
        data={
            "friend_request_id": str(request.id),
            "requester_user_id": str(current_user.id),
            "requester_username": current_user.username,
        },
    )
    await db.commit()
    await db.refresh(request)
    return request


async def respond_to_friend_request(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    current_user: User,
    action: str,
) -> FriendRequest:
    request = await db.get(FriendRequest, request_id)
    if request is None or request.addressee_user_id != current_user.id:
        raise HTTPException(404, "Friend request not found.")
    if request.status != "pending":
        raise HTTPException(400, "This friend request has already been handled.")
    request.status = "accepted" if action == "accept" else "declined"
    request.responded_at = datetime.now(UTC)
    if action == "accept":
        await create_notification_once(
            db,
            user_id=request.requester_user_id,
            kind="friend_request_accepted",
            title=f"@{current_user.username or 'member'} accepted your friend request",
            body="You can now message each other directly.",
            idempotency_key=make_notification_idempotency_key("friend-request-accepted", str(request.id), str(request.requester_user_id)),
            data={
                "friend_request_id": str(request.id),
                "accepted_user_id": str(current_user.id),
                "accepted_username": current_user.username,
            },
        )
    await db.commit()
    await db.refresh(request)
    return request


async def cancel_outgoing_friend_request(db: AsyncSession, *, request_id: uuid.UUID, current_user: User) -> FriendRequest:
    request = await db.get(FriendRequest, request_id)
    if request is None or request.requester_user_id != current_user.id:
        raise HTTPException(404, "Friend request not found.")
    if request.status != "pending":
        raise HTTPException(400, "Only pending requests can be canceled.")
    request.status = "canceled"
    request.responded_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(request)
    return request


async def list_relationships(db: AsyncSession, *, current_user: User) -> SocialRelationshipListOut:
    requester_user = aliased(User)
    addressee_user = aliased(User)
    rows = (
        await db.execute(
            select(FriendRequest, requester_user, addressee_user)
            .join(requester_user, requester_user.id == FriendRequest.requester_user_id)
            .join(addressee_user, addressee_user.id == FriendRequest.addressee_user_id)
            .where(
                or_(
                    FriendRequest.requester_user_id == current_user.id,
                    FriendRequest.addressee_user_id == current_user.id,
                )
            )
            .order_by(FriendRequest.created_at.desc())
        )
    ).scalars().all()

    friends: list[FriendSummary] = []
    incoming_requests: list[FriendRequestOut] = []
    outgoing_requests: list[FriendRequestOut] = []
    for row, requester, addressee in rows:
        item = FriendRequestOut(
            id=row.id,
            requester_user_id=row.requester_user_id,
            addressee_user_id=row.addressee_user_id,
            requester_username=requester.username,
            addressee_username=addressee.username,
            status=row.status,
            created_at=row.created_at,
            responded_at=row.responded_at,
        )
        if row.status == "accepted":
            other = addressee if row.requester_user_id == current_user.id else requester
            since = row.responded_at or row.updated_at or row.created_at
            friends.append(FriendSummary(user_id=other.id, username=other.username or "member", since=since))
        elif row.status == "pending" and row.addressee_user_id == current_user.id:
            incoming_requests.append(item)
        elif row.status == "pending":
            outgoing_requests.append(item)

    return SocialRelationshipListOut(
        friends=friends,
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
    )


async def get_or_create_direct_conversation(db: AsyncSession, *, current_user: User, target_user_id: uuid.UUID) -> DirectConversation:
    if current_user.id == target_user_id:
        raise HTTPException(400, "You cannot message yourself.")
    target = await get_user_or_404(db, target_user_id)
    relationship = await get_relationship_record(db, current_user.id, target_user_id)
    if not can_message_target(current_user.id, target, relationship):
        raise HTTPException(403, "This user only accepts messages from friends.")
    participant_a_user_id, participant_b_user_id = canonical_user_pair(current_user.id, target_user_id)
    conversation = (
        await db.execute(
            select(DirectConversation).where(
                DirectConversation.participant_a_user_id == participant_a_user_id,
                DirectConversation.participant_b_user_id == participant_b_user_id,
            )
        )
    ).scalar_one_or_none()
    if conversation is not None:
        return conversation
    conversation = DirectConversation(
        participant_a_user_id=participant_a_user_id,
        participant_b_user_id=participant_b_user_id,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def ensure_conversation_access(db: AsyncSession, *, current_user: User, conversation_id: uuid.UUID) -> DirectConversation:
    conversation = await db.get(DirectConversation, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found.")
    if current_user.id not in {conversation.participant_a_user_id, conversation.participant_b_user_id}:
        raise HTTPException(404, "Conversation not found.")
    return conversation


async def build_conversation_summary(db: AsyncSession, *, current_user: User, conversation: DirectConversation) -> DirectConversationSummary:
    other_user_id = conversation.participant_b_user_id if conversation.participant_a_user_id == current_user.id else conversation.participant_a_user_id
    other_user = await get_user_or_404(db, other_user_id)
    relationship = await get_relationship_record(db, current_user.id, other_user_id)
    last_message = (
        await db.execute(
            select(DirectMessage)
            .where(DirectMessage.conversation_id == conversation.id)
            .order_by(DirectMessage.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    unread_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(DirectMessage)
                .where(
                    DirectMessage.conversation_id == conversation.id,
                    DirectMessage.recipient_user_id == current_user.id,
                    DirectMessage.recipient_read_at.is_(None),
                )
            )
        ).scalar_one()
    )
    return DirectConversationSummary(
        id=conversation.id,
        other_user=await build_social_user_summary(db, current_user_id=current_user.id, target=other_user, relationship=relationship),
        last_message_preview=(last_message.body[:120] if last_message is not None else None),
        last_message_at=last_message.created_at if last_message is not None else conversation.last_message_at,
        unread_count=unread_count,
    )


async def list_conversation_summaries(db: AsyncSession, *, current_user: User) -> list[DirectConversationSummary]:
    rows = (
        await db.execute(
            select(DirectConversation)
            .where(
                or_(
                    DirectConversation.participant_a_user_id == current_user.id,
                    DirectConversation.participant_b_user_id == current_user.id,
                )
            )
            .order_by(
                case((DirectConversation.last_message_at.is_(None), DirectConversation.created_at), else_=DirectConversation.last_message_at).desc()
            )
        )
    ).scalars().all()
    return [await build_conversation_summary(db, current_user=current_user, conversation=row) for row in rows]


async def count_unread_direct_messages(db: AsyncSession, *, current_user: User) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(DirectMessage)
                .where(
                    DirectMessage.recipient_user_id == current_user.id,
                    DirectMessage.recipient_read_at.is_(None),
                )
            )
        ).scalar_one()
    )


async def list_conversation_messages(
    db: AsyncSession,
    *,
    current_user: User,
    conversation_id: uuid.UUID,
    limit: int = 50,
) -> list[DirectMessage]:
    conversation = await ensure_conversation_access(db, current_user=current_user, conversation_id=conversation_id)
    rows = (
        await db.execute(
            select(DirectMessage)
            .where(DirectMessage.conversation_id == conversation.id)
            .order_by(DirectMessage.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    return rows


async def send_direct_message(
    db: AsyncSession,
    *,
    current_user: User,
    conversation_id: uuid.UUID,
    body: str,
) -> DirectMessage:
    conversation = await ensure_conversation_access(db, current_user=current_user, conversation_id=conversation_id)
    recipient_user_id = conversation.participant_b_user_id if conversation.participant_a_user_id == current_user.id else conversation.participant_a_user_id
    recipient = await get_user_or_404(db, recipient_user_id)
    relationship = await get_relationship_record(db, current_user.id, recipient_user_id)
    if not can_message_target(current_user.id, recipient, relationship):
        raise HTTPException(403, "This user only accepts messages from friends.")
    message = DirectMessage(
        conversation_id=conversation.id,
        sender_user_id=current_user.id,
        recipient_user_id=recipient_user_id,
        body=body.strip(),
    )
    conversation.last_message_at = datetime.now(UTC)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def mark_conversation_read(db: AsyncSession, *, current_user: User, conversation_id: uuid.UUID) -> None:
    await ensure_conversation_access(db, current_user=current_user, conversation_id=conversation_id)
    rows = (
        await db.execute(
            select(DirectMessage).where(
                DirectMessage.conversation_id == conversation_id,
                DirectMessage.recipient_user_id == current_user.id,
                DirectMessage.recipient_read_at.is_(None),
            )
        )
    ).scalars().all()
    if not rows:
        return
    now = datetime.now(UTC)
    for row in rows:
        row.recipient_read_at = now
    await db.commit()
