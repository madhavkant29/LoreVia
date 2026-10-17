from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.feature_flags import require_cursor_page_apis_enabled
from app.core.database import get_db
from app.models.user import User
from app.schemas.social import (
    DirectConversationCreateBody,
    DirectConversationListOut,
    DirectConversationPageOut,
    DirectMessageCreateBody,
    DirectMessageListOut,
    DirectMessageOut,
    DirectMessagePageOut,
    FriendRequestCreateBody,
    FriendRequestOut,
    SocialRelationshipListOut,
    UnreadCountOut,
    UserSearchResponse,
)
from app.services.social_service import (
    DEFAULT_CONVERSATION_PAGE_LIMIT,
    DEFAULT_MESSAGE_PAGE_LIMIT,
    MAX_CONVERSATION_PAGE_LIMIT,
    MAX_MESSAGE_PAGE_LIMIT,
    list_direct_conversation_page,
    list_direct_message_page,
    mark_direct_conversation_read,
)
from app.utils.social_utils import (
    build_conversation_summary,
    cancel_outgoing_friend_request,
    count_unread_direct_messages,
    create_friend_request,
    get_or_create_direct_conversation,
    list_conversation_messages,
    list_conversation_summaries,
    list_relationships,
    respond_to_friend_request,
    search_users_for_social,
    send_direct_message,
)

router = APIRouter()


@router.get("/users/search", response_model=UserSearchResponse)
async def search_users(
    q: str = Query("", min_length=0, max_length=64),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return UserSearchResponse(
        items=await search_users_for_social(db, current_user_id=current_user.id, query=q)
    )


@router.get("/relationships", response_model=SocialRelationshipListOut)
async def get_relationships(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_relationships(db, current_user=current_user)


@router.post("/friend-requests", response_model=FriendRequestOut, status_code=201)
async def send_friend_request(
    body: FriendRequestCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = await create_friend_request(
        db, current_user=current_user, target_user_id=body.target_user_id
    )
    return FriendRequestOut(
        id=request.id,
        requester_user_id=request.requester_user_id,
        addressee_user_id=request.addressee_user_id,
        requester_username=current_user.username,
        addressee_username=None,
        status=request.status,
        created_at=request.created_at,
        responded_at=request.responded_at,
    )


@router.post("/friend-requests/{request_id}/accept", response_model=FriendRequestOut)
async def accept_friend_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = await respond_to_friend_request(
        db, request_id=request_id, current_user=current_user, action="accept"
    )
    return FriendRequestOut(
        id=request.id,
        requester_user_id=request.requester_user_id,
        addressee_user_id=request.addressee_user_id,
        requester_username=None,
        addressee_username=current_user.username,
        status=request.status,
        created_at=request.created_at,
        responded_at=request.responded_at,
    )


@router.post("/friend-requests/{request_id}/decline", response_model=FriendRequestOut)
async def decline_friend_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = await respond_to_friend_request(
        db, request_id=request_id, current_user=current_user, action="decline"
    )
    return FriendRequestOut(
        id=request.id,
        requester_user_id=request.requester_user_id,
        addressee_user_id=request.addressee_user_id,
        requester_username=None,
        addressee_username=current_user.username,
        status=request.status,
        created_at=request.created_at,
        responded_at=request.responded_at,
    )


@router.post("/friend-requests/{request_id}/cancel", response_model=FriendRequestOut)
async def cancel_friend_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request = await cancel_outgoing_friend_request(
        db, request_id=request_id, current_user=current_user
    )
    return FriendRequestOut(
        id=request.id,
        requester_user_id=request.requester_user_id,
        addressee_user_id=request.addressee_user_id,
        requester_username=current_user.username,
        addressee_username=None,
        status=request.status,
        created_at=request.created_at,
        responded_at=request.responded_at,
    )


@router.get("/conversations", response_model=DirectConversationListOut)
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = await list_conversation_summaries(db, current_user=current_user)
    return DirectConversationListOut(
        items=items, unread_count=sum(item.unread_count for item in items)
    )


@router.get(
    "/conversations/page",
    response_model=DirectConversationPageOut,
    dependencies=[Depends(require_cursor_page_apis_enabled)],
)
async def list_conversations_page(
    limit: int = Query(
        DEFAULT_CONVERSATION_PAGE_LIMIT,
        ge=1,
        le=MAX_CONVERSATION_PAGE_LIMIT,
    ),
    cursor: str | None = Query(None, max_length=512),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_direct_conversation_page(
        db,
        current_user=current_user,
        limit=limit,
        cursor=cursor,
    )


@router.get("/conversations/unread-count", response_model=UnreadCountOut)
async def get_unread_conversation_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return UnreadCountOut(
        unread_count=await count_unread_direct_messages(db, current_user=current_user)
    )


@router.post("/conversations/direct", response_model=DirectConversationListOut)
async def create_or_get_direct_conversation(
    body: DirectConversationCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = await get_or_create_direct_conversation(
        db, current_user=current_user, target_user_id=body.target_user_id
    )
    summary = await build_conversation_summary(
        db, current_user=current_user, conversation=conversation
    )
    return DirectConversationListOut(items=[summary], unread_count=summary.unread_count)


@router.get("/conversations/{conversation_id}/messages", response_model=DirectMessageListOut)
async def get_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = await list_conversation_messages(
        db, current_user=current_user, conversation_id=conversation_id, limit=limit
    )
    return DirectMessageListOut(
        items=[
            DirectMessageOut(
                id=item.id,
                conversation_id=item.conversation_id,
                sender_user_id=item.sender_user_id,
                recipient_user_id=item.recipient_user_id,
                body=item.body,
                recipient_read_at=item.recipient_read_at,
                created_at=item.created_at,
            )
            for item in items
        ]
    )


@router.get(
    "/conversations/{conversation_id}/messages/page",
    response_model=DirectMessagePageOut,
    dependencies=[Depends(require_cursor_page_apis_enabled)],
)
async def get_messages_page(
    conversation_id: uuid.UUID,
    limit: int = Query(DEFAULT_MESSAGE_PAGE_LIMIT, ge=1, le=MAX_MESSAGE_PAGE_LIMIT),
    cursor: str | None = Query(None, max_length=512),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_direct_message_page(
        db,
        current_user=current_user,
        conversation_id=conversation_id,
        limit=limit,
        cursor=cursor,
    )


@router.post(
    "/conversations/{conversation_id}/messages", response_model=DirectMessageOut, status_code=201
)
async def post_message(
    conversation_id: uuid.UUID,
    body: DirectMessageCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await send_direct_message(
        db, current_user=current_user, conversation_id=conversation_id, body=body.body
    )
    return DirectMessageOut(
        id=item.id,
        conversation_id=item.conversation_id,
        sender_user_id=item.sender_user_id,
        recipient_user_id=item.recipient_user_id,
        body=item.body,
        recipient_read_at=item.recipient_read_at,
        created_at=item.created_at,
    )


@router.post("/conversations/{conversation_id}/read")
async def read_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await mark_direct_conversation_read(
        db, current_user=current_user, conversation_id=conversation_id
    )
    return {"ok": True}
