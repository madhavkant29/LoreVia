import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.intelligence import Notification
from app.services.notification_service import (
    decode_notification_cursor,
    encode_notification_cursor,
    mark_user_notifications_read,
)
from app.utils.notification_utils import notification_out


def test_notification_out_serializes_nullable_fields_and_uuid_identities():
    notification = Notification(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        kind="test",
        title="Hello",
        body="",
        created_at=datetime.now(UTC),
        data=None,
        read_at=None,
    )
    result = notification_out(notification)
    assert result.id == str(notification.id)
    assert result.book_id == str(notification.book_id)
    assert result.data is result.read_at is None
    notification.book_id = None
    assert notification_out(notification).book_id is None


def test_notification_cursor_round_trip_and_invalid_payload():
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    notification_id = uuid.uuid4()

    cursor = encode_notification_cursor(created_at, notification_id)

    assert decode_notification_cursor(cursor) == (created_at, notification_id)
    with pytest.raises(HTTPException, match="Invalid notification cursor"):
        decode_notification_cursor("not-a-notification-cursor")


@pytest.mark.asyncio
async def test_failed_read_all_update_does_not_commit_or_return_success():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        await mark_user_notifications_read(db, uuid.uuid4())
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_read_all_commit_does_not_load_success_response():
    db = AsyncMock()
    db.commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError, match="commit failed"):
        await mark_user_notifications_read(db, uuid.uuid4())
    assert db.execute.await_count == 1
