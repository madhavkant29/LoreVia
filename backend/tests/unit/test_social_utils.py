from __future__ import annotations

import uuid

from app.utils.social_utils import canonical_user_pair, normalize_messaging_permission


def test_normalize_messaging_permission_defaults_to_anyone():
    assert normalize_messaging_permission(None) == "anyone"
    assert normalize_messaging_permission("unexpected") == "anyone"
    assert normalize_messaging_permission("friends_only") == "friends_only"


def test_canonical_user_pair_returns_stable_sorted_order():
    first = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
    second = uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert canonical_user_pair(first, second) == (second, first)
    assert canonical_user_pair(second, first) == (second, first)
