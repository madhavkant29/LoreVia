from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.models.social import DirectConversation, DirectMessage, FriendRequest
from app.utils import social_utils
from app.utils.social_utils import (
    build_social_user_summary,
    can_message_target,
    canonical_user_pair,
    derive_friend_state,
    normalize_messaging_permission,
)


class FakeScalarResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def first(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self


class FakeDb:
    def __init__(self, *, get_map=None, execute_results=None):
        self.get_map = get_map or {}
        self.execute_results = list(execute_results or [])
        self.added = []
        self.flushed = 0
        self.committed = 0
        self.refreshed = []

    async def get(self, model, item_id):
        return self.get_map.get((model, item_id), self.get_map.get(item_id))

    async def execute(self, statement):
        if self.execute_results:
            return self.execute_results.pop(0)
        return FakeScalarResult()

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushed += 1

    async def commit(self):
        self.committed += 1

    async def refresh(self, item):
        self.refreshed.append(item)


def test_normalize_messaging_permission_defaults_to_anyone():
    assert normalize_messaging_permission(None) == "anyone"
    assert normalize_messaging_permission("unexpected") == "anyone"
    assert normalize_messaging_permission("friends_only") == "friends_only"


def test_canonical_user_pair_returns_stable_sorted_order():
    first = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
    second = uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert canonical_user_pair(first, second) == (second, first)
    assert canonical_user_pair(second, first) == (second, first)


def test_derive_friend_state_distinguishes_none_accepted_and_pending_direction():
    current_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    assert derive_friend_state(current_user_id, None) == "none"
    assert derive_friend_state(
        current_user_id,
        SimpleNamespace(
            status="accepted",
            requester_user_id=other_user_id,
            addressee_user_id=current_user_id,
        ),
    ) == "accepted"
    assert derive_friend_state(
        current_user_id,
        SimpleNamespace(
            status="pending",
            requester_user_id=current_user_id,
            addressee_user_id=other_user_id,
        ),
    ) == "outgoing_pending"
    assert derive_friend_state(
        current_user_id,
        SimpleNamespace(
            status="pending",
            requester_user_id=other_user_id,
            addressee_user_id=current_user_id,
        ),
    ) == "incoming_pending"
    assert derive_friend_state(
        current_user_id,
        SimpleNamespace(
            status="declined",
            requester_user_id=other_user_id,
            addressee_user_id=current_user_id,
        ),
    ) == "none"


def test_can_message_target_blocks_self_and_honors_friend_only_setting():
    current_user_id = uuid.uuid4()
    friend_only_target = SimpleNamespace(id=uuid.uuid4(), messaging_permission="friends_only")
    anyone_target = SimpleNamespace(id=uuid.uuid4(), messaging_permission="anyone")
    self_target = SimpleNamespace(id=current_user_id, messaging_permission="anyone")

    assert can_message_target(current_user_id, self_target, None) is False
    assert can_message_target(current_user_id, anyone_target, None) is True
    assert can_message_target(current_user_id, friend_only_target, None) is False
    assert can_message_target(
        current_user_id,
        friend_only_target,
        SimpleNamespace(status="pending"),
    ) is False
    assert can_message_target(
        current_user_id,
        friend_only_target,
        SimpleNamespace(status="accepted"),
    ) is True


@pytest.mark.asyncio
async def test_build_social_user_summary_uses_supplied_relationship_without_querying_db():
    current_user_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    target = SimpleNamespace(
        id=target_user_id,
        username=None,
        messaging_permission="friends_only",
    )
    relationship = SimpleNamespace(
        status="pending",
        requester_user_id=target_user_id,
        addressee_user_id=current_user_id,
    )

    summary = await build_social_user_summary(
        SimpleNamespace(),
        current_user_id=current_user_id,
        target=target,
        relationship=relationship,
    )

    assert summary.id == target_user_id
    assert summary.username == "member"
    assert summary.messaging_permission == "friends_only"
    assert summary.friend_state == "incoming_pending"
    assert summary.can_message is False


@pytest.mark.asyncio
async def test_create_friend_request_rejects_invalid_existing_states_and_creates_notification(monkeypatch):
    current = SimpleNamespace(id=uuid.uuid4(), username="mira")
    target_id = uuid.uuid4()
    target = SimpleNamespace(id=target_id, username="joren", messaging_permission="anyone")
    notifications = []

    async def fake_get_user_or_404(db, user_id):
      assert user_id == target_id
      return target

    async def fake_notify(*args, **kwargs):
      notifications.append(kwargs)

    monkeypatch.setattr(social_utils, "get_user_or_404", fake_get_user_or_404)
    monkeypatch.setattr(social_utils, "create_notification_once", fake_notify)

    with pytest.raises(Exception) as self_error:
        await social_utils.create_friend_request(FakeDb(), current_user=current, target_user_id=current.id)
    assert self_error.value.status_code == 400

    async def accepted_relationship(db, first_user_id, second_user_id):
        return SimpleNamespace(status="accepted", requester_user_id=target_id)

    monkeypatch.setattr(social_utils, "get_relationship_record", accepted_relationship)
    with pytest.raises(Exception) as accepted_error:
        await social_utils.create_friend_request(FakeDb(), current_user=current, target_user_id=target_id)
    assert accepted_error.value.status_code == 400

    async def incoming_pending(db, first_user_id, second_user_id):
        return SimpleNamespace(status="pending", requester_user_id=target_id)

    monkeypatch.setattr(social_utils, "get_relationship_record", incoming_pending)
    with pytest.raises(Exception) as incoming_error:
        await social_utils.create_friend_request(FakeDb(), current_user=current, target_user_id=target_id)
    assert incoming_error.value.status_code == 409

    async def no_relationship(db, first_user_id, second_user_id):
        return None

    monkeypatch.setattr(social_utils, "get_relationship_record", no_relationship)
    db = FakeDb()
    request = await social_utils.create_friend_request(db, current_user=current, target_user_id=target_id)

    assert isinstance(request, FriendRequest)
    assert request.requester_user_id == current.id
    assert request.addressee_user_id == target_id
    assert request.status == "pending"
    assert db.added == [request]
    assert db.flushed == 1
    assert db.committed == 1
    assert db.refreshed == [request]
    assert notifications[0]["kind"] == "friend_request"


@pytest.mark.asyncio
async def test_friend_request_response_and_cancel_paths(monkeypatch):
    addressee = SimpleNamespace(id=uuid.uuid4(), username="mira")
    requester_id = uuid.uuid4()
    request_id = uuid.uuid4()
    request = SimpleNamespace(
        id=request_id,
        requester_user_id=requester_id,
        addressee_user_id=addressee.id,
        status="pending",
        responded_at=None,
    )
    notifications = []

    async def fake_notify(*args, **kwargs):
        notifications.append(kwargs)

    monkeypatch.setattr(social_utils, "create_notification_once", fake_notify)
    db = FakeDb(get_map={(FriendRequest, request_id): request})

    accepted = await social_utils.respond_to_friend_request(
        db,
        request_id=request_id,
        current_user=addressee,
        action="accept",
    )

    assert accepted.status == "accepted"
    assert accepted.responded_at is not None
    assert db.committed == 1
    assert notifications[0]["kind"] == "friend_request_accepted"

    with pytest.raises(Exception) as handled_error:
        await social_utils.respond_to_friend_request(db, request_id=request_id, current_user=addressee, action="decline")
    assert handled_error.value.status_code == 400

    outgoing = SimpleNamespace(
        id=uuid.uuid4(),
        requester_user_id=addressee.id,
        addressee_user_id=requester_id,
        status="pending",
        responded_at=None,
    )
    cancel_db = FakeDb(get_map={(FriendRequest, outgoing.id): outgoing})
    canceled = await social_utils.cancel_outgoing_friend_request(cancel_db, request_id=outgoing.id, current_user=addressee)
    assert canceled.status == "canceled"
    assert canceled.responded_at is not None
    assert cancel_db.committed == 1


@pytest.mark.asyncio
async def test_direct_conversation_creation_access_send_and_read(monkeypatch):
    current = SimpleNamespace(id=uuid.UUID("00000000-0000-0000-0000-000000000001"), username="mira")
    target = SimpleNamespace(id=uuid.UUID("00000000-0000-0000-0000-000000000002"), username="joren", messaging_permission="friends_only")
    relationship = SimpleNamespace(status="accepted")

    async def fake_get_user_or_404(db, user_id):
        assert user_id == target.id
        return target

    async def fake_relationship(db, first_user_id, second_user_id):
        return relationship

    monkeypatch.setattr(social_utils, "get_user_or_404", fake_get_user_or_404)
    monkeypatch.setattr(social_utils, "get_relationship_record", fake_relationship)

    existing = DirectConversation(
        participant_a_user_id=current.id,
        participant_b_user_id=target.id,
    )
    existing.id = uuid.uuid4()
    existing_db = FakeDb(execute_results=[FakeScalarResult(scalar=existing)])
    assert await social_utils.get_or_create_direct_conversation(existing_db, current_user=current, target_user_id=target.id) is existing

    create_db = FakeDb(execute_results=[FakeScalarResult(scalar=None)])
    created = await social_utils.get_or_create_direct_conversation(create_db, current_user=current, target_user_id=target.id)
    assert isinstance(created, DirectConversation)
    assert create_db.added == [created]
    assert create_db.committed == 1

    with pytest.raises(Exception) as self_error:
        await social_utils.get_or_create_direct_conversation(FakeDb(), current_user=current, target_user_id=current.id)
    assert self_error.value.status_code == 400

    missing_db = FakeDb(get_map={(DirectConversation, existing.id): None})
    with pytest.raises(Exception) as missing_error:
        await social_utils.ensure_conversation_access(missing_db, current_user=current, conversation_id=existing.id)
    assert missing_error.value.status_code == 404

    access_db = FakeDb(get_map={(DirectConversation, existing.id): existing})
    assert await social_utils.ensure_conversation_access(access_db, current_user=current, conversation_id=existing.id) is existing

    async def fake_access(db, *, current_user, conversation_id):
        return existing

    monkeypatch.setattr(social_utils, "ensure_conversation_access", fake_access)
    send_db = FakeDb()
    message = await social_utils.send_direct_message(send_db, current_user=current, conversation_id=existing.id, body="  hello  ")
    assert isinstance(message, DirectMessage)
    assert message.body == "hello"
    assert message.recipient_user_id == target.id
    assert existing.last_message_at is not None
    assert send_db.added == [message]
    assert send_db.committed == 1

    unread = SimpleNamespace(recipient_read_at=None)
    read_db = FakeDb(execute_results=[FakeScalarResult(rows=[unread])])
    await social_utils.mark_conversation_read(read_db, current_user=current, conversation_id=existing.id)
    assert unread.recipient_read_at is not None
    assert read_db.committed == 1
