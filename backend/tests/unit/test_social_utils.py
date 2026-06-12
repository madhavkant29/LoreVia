from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.utils.social_utils import (
    build_social_user_summary,
    can_message_target,
    canonical_user_pair,
    derive_friend_state,
    normalize_messaging_permission,
)


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
