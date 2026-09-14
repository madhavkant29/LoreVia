from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.social import DirectConversation, DirectMessage
from app.services import social_service


class _Result:
    def __init__(self, *, rows=None, rowcount: int | None = None):
        self._rows = list(rows or [])
        self.rowcount = rowcount

    def all(self):
        return self._rows

    def scalars(self):
        return self


class _FakeDb:
    def __init__(self, results):
        self._results = list(results)
        self.statements = []
        self.commits = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self._results.pop(0)

    async def commit(self):
        self.commits += 1


def _message(
    *, conversation_id: uuid.UUID, sender_user_id: uuid.UUID, created_at: datetime
) -> DirectMessage:
    return DirectMessage(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        sender_user_id=sender_user_id,
        recipient_user_id=uuid.uuid4(),
        body="Message",
        created_at=created_at,
    )


def test_social_page_cursors_round_trip_and_reject_invalid_values():
    timestamp = datetime(2026, 9, 12, 9, 30, tzinfo=UTC)
    item_id = uuid.uuid4()

    conversation_cursor = social_service.encode_conversation_page_cursor(timestamp, item_id)
    message_cursor = social_service.encode_message_page_cursor(timestamp, item_id)

    assert social_service.decode_conversation_page_cursor(conversation_cursor) == (
        timestamp,
        item_id,
    )
    assert social_service.decode_message_page_cursor(message_cursor) == (timestamp, item_id)
    with pytest.raises(HTTPException, match="Invalid conversation page cursor"):
        social_service.decode_conversation_page_cursor("not-a-cursor")
    with pytest.raises(HTTPException, match="Invalid message page cursor"):
        social_service.decode_message_page_cursor("not-a-cursor")


@pytest.mark.asyncio
async def test_message_page_queries_newest_first_but_returns_messages_chronologically(monkeypatch):
    current_user = SimpleNamespace(id=uuid.uuid4())
    conversation_id = uuid.uuid4()
    conversation = SimpleNamespace(id=conversation_id)
    now = datetime(2026, 9, 12, 9, 30, tzinfo=UTC)
    newest = _message(
        conversation_id=conversation_id,
        sender_user_id=current_user.id,
        created_at=now,
    )
    middle = _message(
        conversation_id=conversation_id,
        sender_user_id=current_user.id,
        created_at=now - timedelta(minutes=1),
    )
    oldest = _message(
        conversation_id=conversation_id,
        sender_user_id=current_user.id,
        created_at=now - timedelta(minutes=2),
    )

    async def _access(*_args, **_kwargs):
        return conversation

    monkeypatch.setattr(social_service, "ensure_conversation_access", _access)
    db = _FakeDb([_Result(rows=[newest, middle, oldest])])

    page = await social_service.list_direct_message_page(
        db,
        current_user=current_user,
        conversation_id=conversation_id,
        limit=2,
    )

    assert [item.id for item in page.items] == [middle.id, newest.id]
    assert page.has_more is True
    assert social_service.decode_message_page_cursor(page.next_cursor) == (
        middle.created_at,
        middle.id,
    )
    assert "ORDER BY direct_messages.created_at DESC" in str(db.statements[0])


@pytest.mark.asyncio
async def test_conversation_page_uses_activity_cursor_and_batch_relationship_lookup():
    current_user = SimpleNamespace(id=uuid.uuid4())
    now = datetime(2026, 9, 12, 9, 30, tzinfo=UTC)
    rows = []
    for offset in range(3):
        other_user = SimpleNamespace(
            id=uuid.uuid4(),
            username=f"writer-{offset}",
            messaging_permission="anyone",
        )
        conversation = DirectConversation(
            id=uuid.uuid4(),
            participant_a_user_id=current_user.id,
            participant_b_user_id=other_user.id,
            created_at=now - timedelta(minutes=offset),
        )
        rows.append((conversation, other_user, None, 0, conversation.created_at))
    db = _FakeDb([_Result(rows=rows), _Result(rows=[])])

    page = await social_service.list_direct_conversation_page(
        db,
        current_user=current_user,
        limit=2,
    )

    assert [item.id for item in page.items] == [rows[0][0].id, rows[1][0].id]
    assert page.has_more is True
    assert social_service.decode_conversation_page_cursor(page.next_cursor) == (
        rows[1][4],
        rows[1][0].id,
    )
    assert len(db.statements) == 2


@pytest.mark.asyncio
async def test_mark_conversation_read_uses_one_scoped_update(monkeypatch):
    current_user = SimpleNamespace(id=uuid.uuid4())
    conversation_id = uuid.uuid4()

    async def _access(*_args, **_kwargs):
        return SimpleNamespace(id=conversation_id)

    monkeypatch.setattr(social_service, "ensure_conversation_access", _access)
    db = _FakeDb([_Result(rowcount=3)])

    await social_service.mark_direct_conversation_read(
        db,
        current_user=current_user,
        conversation_id=conversation_id,
    )

    assert len(db.statements) == 1
    assert str(db.statements[0]).startswith("UPDATE direct_messages")
    assert db.commits == 1
