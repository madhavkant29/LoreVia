from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MessagingPermission = Literal["anyone", "friends_only"]
FriendState = Literal["none", "outgoing_pending", "incoming_pending", "accepted"]


class SocialUserSummary(BaseModel):
    id: uuid.UUID
    username: str
    messaging_permission: MessagingPermission
    friend_state: FriendState
    can_message: bool


class UserSearchResponse(BaseModel):
    items: list[SocialUserSummary]


class FriendRequestCreateBody(BaseModel):
    target_user_id: uuid.UUID


class FriendRequestRespondBody(BaseModel):
    action: Literal["accept", "decline"]


class FriendRequestOut(BaseModel):
    id: uuid.UUID
    requester_user_id: uuid.UUID
    addressee_user_id: uuid.UUID
    requester_username: str | None = None
    addressee_username: str | None = None
    status: str
    created_at: datetime
    responded_at: datetime | None = None


class FriendSummary(BaseModel):
    user_id: uuid.UUID
    username: str
    since: datetime


class SocialRelationshipListOut(BaseModel):
    friends: list[FriendSummary]
    incoming_requests: list[FriendRequestOut]
    outgoing_requests: list[FriendRequestOut]


class DirectConversationCreateBody(BaseModel):
    target_user_id: uuid.UUID


class DirectMessageCreateBody(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class DirectMessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_user_id: uuid.UUID
    recipient_user_id: uuid.UUID
    body: str
    recipient_read_at: datetime | None = None
    created_at: datetime


class DirectConversationSummary(BaseModel):
    id: uuid.UUID
    other_user: SocialUserSummary
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    unread_count: int


class DirectConversationListOut(BaseModel):
    items: list[DirectConversationSummary]
    unread_count: int


class DirectMessageListOut(BaseModel):
    items: list[DirectMessageOut]

