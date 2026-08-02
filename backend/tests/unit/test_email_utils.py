import uuid
from datetime import UTC, datetime

import pytest

from app.models.user import EmailPreference, User
from app.utils.email_utils import (
    EMAIL_CATEGORY_MARKETING,
    EMAIL_CATEGORY_PRODUCT_UPDATES,
    EMAIL_CATEGORY_TRANSACTIONAL,
    can_send_email,
    track_usage_limit_friction_and_maybe_send,
)


def test_can_send_email_allows_transactional_even_when_unsubscribed():
    pref = EmailPreference(
        email="reader@example.com",
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        product_updates=False,
        marketing=False,
        unsubscribed_all=True,
        unsubscribed_at=datetime.now(UTC),
    )

    assert can_send_email(pref, EMAIL_CATEGORY_TRANSACTIONAL) is True


def test_can_send_email_blocks_promotional_categories_when_unsubscribed_all():
    pref = EmailPreference(
        email="reader@example.com",
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        product_updates=True,
        marketing=True,
        unsubscribed_all=True,
        unsubscribed_at=datetime.now(UTC),
    )

    assert can_send_email(pref, EMAIL_CATEGORY_PRODUCT_UPDATES) is False
    assert can_send_email(pref, EMAIL_CATEGORY_MARKETING) is False


def test_can_send_email_respects_category_specific_toggles():
    pref = EmailPreference(
        email="reader@example.com",
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        product_updates=False,
        marketing=True,
        unsubscribed_all=False,
    )

    assert can_send_email(pref, EMAIL_CATEGORY_PRODUCT_UPDATES) is False
    assert can_send_email(pref, EMAIL_CATEGORY_MARKETING) is True


def test_can_send_email_returns_false_for_unknown_categories():
    pref = EmailPreference(
        email="reader@example.com",
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
    )

    assert can_send_email(pref, "unknown") is False


@pytest.mark.asyncio
async def test_track_usage_limit_friction_sends_upgrade_offer_after_repeated_hits(monkeypatch):
    user = User(
        id=uuid.uuid4(),
        email="reader@example.com",
        username="reader",
        password_hash="hashed",
        tier="free",
        created_at=datetime.now(UTC),
        email_verified_at=datetime.now(UTC),
    )
    deliveries: list[tuple[str, str]] = []

    async def _fake_send(email: str, *, focus_area: str) -> bool:
        deliveries.append((email, focus_area))
        return True

    monkeypatch.setattr(
        "app.services.email_service.send_usage_limit_upgrade_offer_email",
        _fake_send,
        raising=False,
    )

    for _ in range(3):
        await track_usage_limit_friction_and_maybe_send(user, action="search")

    assert deliveries == [("reader@example.com", "search")]
