from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.routes import notifications


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
async def test_list_notifications_skips_revision_digest_sync_when_disabled(monkeypatch):
    sync_calls: list[tuple[uuid.UUID, int]] = []

    async def _fake_sync(_db, user_id, *, limit):
        sync_calls.append((user_id, limit))

    monkeypatch.setattr(notifications, "sync_revision_digest_notifications", _fake_sync)

    user_id = uuid.uuid4()
    db = _FakeDB(
        execute_values=[
            _Result(scalars=[_notification(user_id=user_id)]),
            _Result(scalar_one=1),
        ]
    )

    payload = await notifications.list_notifications(
        limit=10,
        sync_revision_digests=False,
        db=db,
        current_user=SimpleNamespace(id=user_id),
    )

    assert sync_calls == []
    assert payload.unread_count == 1
    assert len(payload.items) == 1


@pytest.mark.asyncio
async def test_list_notifications_syncs_revision_digests_by_default(monkeypatch):
    sync_calls: list[tuple[uuid.UUID, int]] = []

    async def _fake_sync(_db, user_id, *, limit):
        sync_calls.append((user_id, limit))

    monkeypatch.setattr(notifications, "sync_revision_digest_notifications", _fake_sync)

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

    assert sync_calls == [(user_id, 6)]
