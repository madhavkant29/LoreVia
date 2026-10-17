from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.security import create_access_token
from app.models.social import DirectConversation, DirectMessage
from app.models.user import User


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Cookie": f"lorevia_access_token={create_access_token(str(user_id))}"}


async def _create_user(
    db, *, email: str, username: str, messaging_permission: str = "anyone"
) -> User:
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
    recipient = await _create_user(
        db, email="recipient@lorevia.test", username="recipient", messaging_permission="anyone"
    )

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
    assert (
        recipient_messages.json()["items"][0]["body"]
        == "Hey there, I would love to talk about your manuscript."
    )

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
    recipient = await _create_user(
        db,
        email="gated-recipient@lorevia.test",
        username="gatedrecipient",
        messaging_permission="friends_only",
    )

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
    assert any(
        item["kind"] == "friend_request_accepted" for item in sender_notifications.json()["items"]
    )

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


@pytest.mark.asyncio
async def test_conversation_page_cursor_has_no_gaps_or_duplicates_and_keeps_legacy_list(client, db):
    owner = await _create_user(db, email="page-owner@lorevia.test", username="pageowner")
    activity_at = datetime(2026, 9, 12, 9, 30, tzinfo=UTC)
    conversations = []
    for index in range(5):
        other_user = await _create_user(
            db,
            email=f"page-other-{index}@lorevia.test",
            username=f"pageother{index}",
        )
        conversation = DirectConversation(
            participant_a_user_id=owner.id,
            participant_b_user_id=other_user.id,
            created_at=activity_at,
        )
        db.add(conversation)
        conversations.append(conversation)
    await db.commit()

    headers = _auth_headers(owner.id)
    seen: list[str] = []
    cursor = None
    for _ in range(3):
        params = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        response = await client.get(
            "/api/v1/social/conversations/page",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200
        payload = response.json()
        seen.extend(item["id"] for item in payload["items"])
        cursor = payload["next_cursor"]
        if not payload["has_more"]:
            break

    assert len(seen) == len(set(seen)) == len(conversations)
    legacy_response = await client.get("/api/v1/social/conversations", headers=headers)
    assert legacy_response.status_code == 200
    assert len(legacy_response.json()["items"]) == len(conversations)
    invalid = await client.get(
        "/api/v1/social/conversations/page?cursor=invalid",
        headers=headers,
    )
    assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_message_page_cursor_returns_chronological_pages_without_gaps(client, db):
    sender = await _create_user(db, email="message-page-sender@lorevia.test", username="pagesender")
    recipient = await _create_user(
        db,
        email="message-page-recipient@lorevia.test",
        username="pagerecipient",
    )
    conversation = DirectConversation(
        participant_a_user_id=sender.id,
        participant_b_user_id=recipient.id,
        created_at=datetime(2026, 9, 12, 9, 30, tzinfo=UTC),
    )
    db.add(conversation)
    await db.flush()
    created_at = datetime(2026, 9, 12, 10, tzinfo=UTC)
    messages = [
        DirectMessage(
            conversation_id=conversation.id,
            sender_user_id=sender.id,
            recipient_user_id=recipient.id,
            body=f"Message {index}",
            created_at=created_at,
        )
        for index in range(5)
    ]
    db.add_all(messages)
    await db.commit()

    headers = _auth_headers(recipient.id)
    seen: list[str] = []
    cursor = None
    for _ in range(3):
        params = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        response = await client.get(
            f"/api/v1/social/conversations/{conversation.id}/messages/page",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200
        payload = response.json()
        item_ids = [item["id"] for item in payload["items"]]
        assert item_ids == sorted(item_ids)
        seen.extend(item_ids)
        cursor = payload["next_cursor"]
        if not payload["has_more"]:
            break

    assert len(seen) == len(set(seen)) == len(messages)
    invalid = await client.get(
        f"/api/v1/social/conversations/{conversation.id}/messages/page?cursor=invalid",
        headers=headers,
    )
    assert invalid.status_code == 400
