from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.routes import notifications
from app.services import notification_service


class _ScalarList:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)


class _Result:
    def __init__(self, *, scalar_one=None, scalars=None):
        self._scalar_one = scalar_one
        self._scalars = [] if scalars is None else scalars

    def scalar_one(self):
        return self._scalar_one

    def scalars(self):
        return _ScalarList(self._scalars)


class _FakeDB:
    def __init__(self, execute_values):
        self._execute_values = list(execute_values)

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)


def _notification(*, user_id):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        book_id=None,
        kind="friend_request",
        title="Request pending",
        body="Someone sent a friend request.",
        data={},
        read_at=None,
        created_at="2026-05-25T12:00:00Z",
    )


@pytest.mark.asyncio
async def test_list_notifications_never_syncs_revision_digests(monkeypatch):
    sync_calls: list[tuple[uuid.UUID, int]] = []

    async def _fake_sync(_db, user_id, *, limit):
        sync_calls.append((user_id, limit))

    monkeypatch.setattr(
        notification_service, "sync_revision_digest_notifications", _fake_sync, raising=False
    )

    user_id = uuid.uuid4()
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[_notification(user_id=user_id)]),
            _Result(scalar_one=1),
        ]
    )

    payload = await notifications.list_notifications(
        limit=10,
        sync_revision_digests=True,
        db=db,
        current_user=SimpleNamespace(id=user_id),
    )

    assert sync_calls == []
    assert payload.unread_count == 1
    assert len(payload.items) == 1


@pytest.mark.asyncio
async def test_list_notifications_uses_no_digest_sync_by_default(monkeypatch):
    sync_calls: list[tuple[uuid.UUID, int]] = []

    async def _fake_sync(_db, user_id, *, limit):
        sync_calls.append((user_id, limit))

    monkeypatch.setattr(
        notification_service, "sync_revision_digest_notifications", _fake_sync, raising=False
    )

    user_id = uuid.uuid4()
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[_notification(user_id=user_id)]),
            _Result(scalar_one=1),
        ]
    )

    await notifications.list_notifications(
        limit=10,
        db=db,
        current_user=SimpleNamespace(id=user_id),
    )

    assert sync_calls == []


@pytest.mark.asyncio
async def test_mark_all_notifications_read_never_rebuilds_revision_digests(monkeypatch):
    sync_calls: list[tuple[uuid.UUID, int]] = []

    async def _fake_sync(_db, user_id, *, limit):
        sync_calls.append((user_id, limit))

    monkeypatch.setattr(
        notification_service, "sync_revision_digest_notifications", _fake_sync, raising=False
    )

    user_id = uuid.uuid4()
    pending_notification = _notification(user_id=user_id)
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[pending_notification]),
            _Result(scalars=[pending_notification]),
            _Result(scalar_one=1),
        ]
    )
    db.commit = AsyncMock()

    payload = await notifications.mark_all_notifications_read(
        db=db,
        current_user=SimpleNamespace(id=user_id),
    )

    assert payload.unread_count == 1
    assert sync_calls == []
