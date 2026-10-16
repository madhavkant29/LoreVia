"""Notification mutations must stay bounded and preserve tenant/read state."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.intelligence import Notification
from app.models.user import User
from app.services import notification_service


@pytest.mark.asyncio
@pytest.mark.parametrize("unread_total", [0, 1, 65])
async def test_read_all_is_one_scoped_update_with_bounded_page(
    client, db, monkeypatch, unread_total
):
    owner = User(email=f"{uuid.uuid4()}@test.local", password_hash="hashed", tier="author")
    other = User(email=f"{uuid.uuid4()}@test.local", password_hash="hashed", tier="author")
    db.add_all([owner, other])
    await db.flush()
    original_read = datetime(2026, 1, 1, tzinfo=UTC)
    already_read = Notification(
        user_id=owner.id, kind="test", title="Read", body="", read_at=original_read
    )
    other_unread = Notification(user_id=other.id, kind="test", title="Private", body="")
    db.add_all([already_read, other_unread])
    db.add_all(
        Notification(user_id=owner.id, kind="test", title=f"Item {i}", body="")
        for i in range(unread_total)
    )
    await db.commit()
    sync = AsyncMock(side_effect=AssertionError("Read-all must not rebuild intelligence"))
    monkeypatch.setattr(
        notification_service, "sync_revision_digest_notifications", sync, raising=False
    )
    updates = []

    def capture_update(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE NOTIFICATIONS"):
            updates.append((statement, executemany))

    event.listen(db.bind.sync_engine, "before_cursor_execute", capture_update)
    try:
        response = await client.put(
            "/api/v1/notifications/read-all",
            headers={"Authorization": f"Bearer {create_access_token(str(owner.id))}"},
        )
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", capture_update)
    assert response.status_code == 200, response.text
    assert len(updates) == 1
    assert updates[0][1] is False
    payload = response.json()
    assert payload["unread_count"] == 0
    assert len(payload["items"]) == min(unread_total + 1, 40)
    assert all(item["read_at"] is not None for item in payload["items"])
    assert all(item["title"] != "Private" for item in payload["items"])
    await db.refresh(other_unread)
    await db.refresh(already_read)
    assert other_unread.read_at is None
    assert already_read.read_at == original_read
    sync.assert_not_awaited()

    repeat = await client.put(
        "/api/v1/notifications/read-all",
        headers={"Authorization": f"Bearer {create_access_token(str(owner.id))}"},
    )
    assert repeat.json() == payload


@pytest.mark.asyncio
async def test_read_all_reports_notification_arriving_after_update(client, db, monkeypatch):
    owner = User(email=f"{uuid.uuid4()}@test.local", password_hash="hashed", tier="author")
    db.add(owner)
    await db.commit()
    owner_id = owner.id
    original_commit = db.commit

    async def commit_then_deliver():
        await original_commit()
        async with AsyncSession(db.bind) as delivery:
            delivery.add(Notification(user_id=owner_id, kind="test", title="Just arrived", body=""))
            await delivery.commit()

    monkeypatch.setattr(db, "commit", commit_then_deliver)
    response = await client.put(
        "/api/v1/notifications/read-all",
        headers={"Authorization": f"Bearer {create_access_token(str(owner_id))}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["unread_count"] == 1
    assert response.json()["items"][0]["read_at"] is None


@pytest.mark.asyncio
async def test_single_read_preserves_timestamp_and_rejects_other_users(client, db):
    owner = User(email=f"{uuid.uuid4()}@test.local", password_hash="hashed", tier="author")
    other = User(email=f"{uuid.uuid4()}@test.local", password_hash="hashed", tier="author")
    db.add_all([owner, other])
    await db.flush()
    notification = Notification(user_id=owner.id, kind="test", title="Private", body="")
    db.add(notification)
    await db.commit()
    path = f"/api/v1/notifications/{notification.id}/read"
    other_headers = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}
    denied = await client.put(path, headers=other_headers)
    assert denied.status_code == 404
    missing = await client.put(f"/api/v1/notifications/{uuid.uuid4()}/read", headers=other_headers)
    assert missing.status_code == 404
    owner_headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    first = await client.put(path, headers=owner_headers)
    second = await client.put(path, headers=owner_headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["read_at"] is not None
    assert first.json() == second.json()


@pytest.mark.asyncio
async def test_notification_list_has_stable_tie_order_and_validates_limit(client, db):
    owner = User(email=f"{uuid.uuid4()}@test.local", password_hash="hashed", tier="author")
    db.add(owner)
    await db.flush()
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    items = [
        Notification(user_id=owner.id, kind="test", title=str(i), body="", created_at=created_at)
        for i in range(3)
    ]
    db.add_all(items)
    await db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    response = await client.get(
        "/api/v1/notifications?limit=2&sync_revision_digests=false", headers=headers
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == sorted(
        [str(item.id) for item in items], reverse=True
    )[:2]
    assert response.json()["unread_count"] == 3
    assert response.json()["has_more"] is True
    assert response.json()["next_cursor"]
    for limit in [0, 101, "invalid"]:
        invalid = await client.get(f"/api/v1/notifications?limit={limit}", headers=headers)
        assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_notification_cursor_has_no_gaps_or_duplicates_across_ties(client, db):
    owner = User(email=f"{uuid.uuid4()}@test.local", password_hash="hashed", tier="author")
    db.add(owner)
    await db.flush()
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    notifications = [
        Notification(
            user_id=owner.id, kind="test", title=str(index), body="", created_at=created_at
        )
        for index in range(5)
    ]
    db.add_all(notifications)
    await db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}

    first = await client.get("/api/v1/notifications?limit=2", headers=headers)
    assert first.status_code == 200
    first_payload = first.json()
    second = await client.get(
        f"/api/v1/notifications?limit=2&cursor={first_payload['next_cursor']}",
        headers=headers,
    )
    third = await client.get(
        f"/api/v1/notifications?limit=2&cursor={second.json()['next_cursor']}",
        headers=headers,
    )

    seen = [
        *(item["id"] for item in first_payload["items"]),
        *(item["id"] for item in second.json()["items"]),
        *(item["id"] for item in third.json()["items"]),
    ]
    assert len(seen) == len(set(seen)) == len(notifications)
    assert third.json()["has_more"] is False
