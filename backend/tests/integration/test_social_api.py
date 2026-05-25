from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token
from app.models.user import User


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Cookie": f"lorevia_access_token={create_access_token(str(user_id))}"}


async def _create_user(db, *, email: str, username: str, messaging_permission: str = "anyone") -> User:
    user = User(
        email=email,
        username=username,
        password_hash="hashed",
        tier="author",
        messaging_permission=messaging_permission,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_anyone_permission_allows_direct_messages_without_friendship(client, db):
    sender = await _create_user(db, email="sender@lorevia.test", username="sender")
    recipient = await _create_user(db, email="recipient@lorevia.test", username="recipient", messaging_permission="anyone")

    search_response = await client.get(
        "/api/v1/social/users/search",
        headers=_auth_headers(sender.id),
        params={"q": "recipient"},
    )
    assert search_response.status_code == 200
    assert search_response.json()["items"][0]["can_message"] is True

    conversation_response = await client.post(
        "/api/v1/social/conversations/direct",
        headers=_auth_headers(sender.id),
        json={"target_user_id": str(recipient.id)},
    )
    assert conversation_response.status_code == 200
    conversation_id = conversation_response.json()["items"][0]["id"]

    message_response = await client.post(
        f"/api/v1/social/conversations/{conversation_id}/messages",
        headers=_auth_headers(sender.id),
        json={"body": "Hey there, I would love to talk about your manuscript."},
    )
    assert message_response.status_code == 201

    recipient_conversations = await client.get(
        "/api/v1/social/conversations",
        headers=_auth_headers(recipient.id),
    )
    assert recipient_conversations.status_code == 200
    assert recipient_conversations.json()["unread_count"] == 1

    recipient_unread = await client.get(
        "/api/v1/social/conversations/unread-count",
        headers=_auth_headers(recipient.id),
    )
    assert recipient_unread.status_code == 200
    assert recipient_unread.json()["unread_count"] == 1

    recipient_messages = await client.get(
        f"/api/v1/social/conversations/{conversation_id}/messages",
        headers=_auth_headers(recipient.id),
    )
    assert recipient_messages.status_code == 200
    assert recipient_messages.json()["items"][0]["body"] == "Hey there, I would love to talk about your manuscript."

    mark_read_response = await client.post(
        f"/api/v1/social/conversations/{conversation_id}/read",
        headers=_auth_headers(recipient.id),
    )
    assert mark_read_response.status_code == 200

    recipient_conversations_after = await client.get(
        "/api/v1/social/conversations",
        headers=_auth_headers(recipient.id),
    )
    assert recipient_conversations_after.status_code == 200
    assert recipient_conversations_after.json()["unread_count"] == 0

    recipient_unread_after = await client.get(
        "/api/v1/social/conversations/unread-count",
        headers=_auth_headers(recipient.id),
    )
    assert recipient_unread_after.status_code == 200
    assert recipient_unread_after.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_friends_only_requires_request_acceptance_before_dm(client, db):
    sender = await _create_user(db, email="gated-sender@lorevia.test", username="gatedsender")
    recipient = await _create_user(db, email="gated-recipient@lorevia.test", username="gatedrecipient", messaging_permission="friends_only")

    blocked_response = await client.post(
        "/api/v1/social/conversations/direct",
        headers=_auth_headers(sender.id),
        json={"target_user_id": str(recipient.id)},
    )
    assert blocked_response.status_code == 403

    friend_request_response = await client.post(
        "/api/v1/social/friend-requests",
        headers=_auth_headers(sender.id),
        json={"target_user_id": str(recipient.id)},
    )
    assert friend_request_response.status_code == 201
    request_id = friend_request_response.json()["id"]

    recipient_notifications = await client.get(
        "/api/v1/notifications",
        headers=_auth_headers(recipient.id),
    )
    assert recipient_notifications.status_code == 200
    assert recipient_notifications.json()["items"][0]["kind"] == "friend_request"

    accept_response = await client.post(
        f"/api/v1/social/friend-requests/{request_id}/accept",
        headers=_auth_headers(recipient.id),
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    sender_notifications = await client.get(
        "/api/v1/notifications",
        headers=_auth_headers(sender.id),
    )
    assert sender_notifications.status_code == 200
    assert any(item["kind"] == "friend_request_accepted" for item in sender_notifications.json()["items"])

    search_response = await client.get(
        "/api/v1/social/users/search",
        headers=_auth_headers(sender.id),
        params={"q": "gatedrecipient"},
    )
    assert search_response.status_code == 200
    assert search_response.json()["items"][0]["friend_state"] == "accepted"
    assert search_response.json()["items"][0]["can_message"] is True

    conversation_response = await client.post(
        "/api/v1/social/conversations/direct",
        headers=_auth_headers(sender.id),
        json={"target_user_id": str(recipient.id)},
    )
    assert conversation_response.status_code == 200
    assert conversation_response.json()["items"][0]["other_user"]["username"] == "gatedrecipient"
