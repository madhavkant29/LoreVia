from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.models.user import Subscription, SubscriptionEmailEvent, User
from app.services.subscription_email_service import (
    EMAIL_EVENT_STATUS_PENDING,
    EMAIL_EVENT_STATUS_SENT,
    send_due_payment_failure_notices,
    send_due_renewal_reminders,
)
from app.utils.billing_utils import (
    SUBSCRIPTION_EMAIL_PAYMENT_FAILED,
    SUBSCRIPTION_EMAIL_RENEWAL_REMINDER,
)


@pytest.fixture(autouse=True)
async def _clean_subscription_state(db):
    await db.execute(delete(SubscriptionEmailEvent))
    await db.execute(delete(Subscription))
    await db.commit()
    yield


async def _create_paid_user(db, *, suffix: str) -> User:
    user = User(
        email=f"subscription-email-{suffix}@lorevia.test",
        username=f"subscription-email-{suffix}",
        password_hash="hashed",
        tier="author",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_subscription(
    db,
    *,
    user: User,
    plan: str = "author_monthly",
    status: str = "active",
    current_period_end: datetime,
    cancel_at_period_end: bool = False,
) -> Subscription:
    subscription = Subscription(
        user_id=user.id,
        paddle_customer_id=f"ctm_{user.username}",
        paddle_sub_id=f"sub_{user.username}",
        plan=plan,
        status=status,
        current_period_start=current_period_end - timedelta(days=30),
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


@pytest.mark.asyncio
async def test_renewal_reminder_sends_once_three_days_before_period_end(db, monkeypatch):
    now = datetime.now(UTC)
    user = await _create_paid_user(db, suffix="renew")
    subscription = await _create_subscription(
        db,
        user=user,
        current_period_end=now + timedelta(days=3) - timedelta(hours=1),
    )

    deliveries: list[tuple[str, str, datetime, int]] = []

    async def fake_send(email: str, plan: str, *, renewal_at: datetime, amount_usd: int) -> bool:
        deliveries.append((email, plan, renewal_at, amount_usd))
        return True

    monkeypatch.setattr(
        "app.services.subscription_email_service.send_subscription_renewal_reminder",
        fake_send,
    )

    first = await send_due_renewal_reminders(db, now=now, limit=10)
    second = await send_due_renewal_reminders(db, now=now, limit=10)

    assert first == {"sent": 1, "checked": 1}
    assert second["sent"] == 0
    assert deliveries == [(user.email, "author_monthly", subscription.current_period_end, 19)]

    events = (
        (
            await db.execute(
                select(SubscriptionEmailEvent).where(
                    SubscriptionEmailEvent.subscription_id == subscription.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].email_type == SUBSCRIPTION_EMAIL_RENEWAL_REMINDER
    assert events[0].status == EMAIL_EVENT_STATUS_SENT


@pytest.mark.asyncio
async def test_renewal_reminder_skips_scheduled_cancellations(db, monkeypatch):
    now = datetime.now(UTC)
    user = await _create_paid_user(db, suffix="cancel")
    await _create_subscription(
        db,
        user=user,
        current_period_end=now + timedelta(days=3) - timedelta(hours=1),
        cancel_at_period_end=True,
    )

    deliveries: list[str] = []

    async def fake_send(email: str, plan: str, *, renewal_at: datetime, amount_usd: int) -> bool:
        deliveries.append(email)
        return True

    monkeypatch.setattr(
        "app.services.subscription_email_service.send_subscription_renewal_reminder",
        fake_send,
    )

    result = await send_due_renewal_reminders(db, now=now, limit=10)

    assert result == {"sent": 0, "checked": 0}
    assert deliveries == []


@pytest.mark.asyncio
async def test_renewal_reminder_waits_until_within_three_days(db, monkeypatch):
    now = datetime.now(UTC)
    user = await _create_paid_user(db, suffix="early")
    await _create_subscription(
        db,
        user=user,
        current_period_end=now + timedelta(days=10),
    )

    deliveries: list[str] = []

    async def fake_send(email: str, plan: str, *, renewal_at: datetime, amount_usd: int) -> bool:
        deliveries.append(email)
        return True

    monkeypatch.setattr(
        "app.services.subscription_email_service.send_subscription_renewal_reminder",
        fake_send,
    )

    result = await send_due_renewal_reminders(db, now=now, limit=10)

    assert result == {"sent": 0, "checked": 0}
    assert deliveries == []


@pytest.mark.asyncio
async def test_payment_failure_notice_retries_a_failed_delivery_once(db, monkeypatch):
    now = datetime.now(UTC)
    user = await _create_paid_user(db, suffix="payment")
    subscription = await _create_subscription(
        db,
        user=user,
        status="past_due",
        current_period_end=now + timedelta(days=20),
    )
    event = SubscriptionEmailEvent(
        user_id=user.id,
        subscription_id=subscription.id,
        email_type=SUBSCRIPTION_EMAIL_PAYMENT_FAILED,
        billing_period_end=subscription.current_period_end,
        scheduled_for=now - timedelta(hours=1),
        status=EMAIL_EVENT_STATUS_PENDING,
        metadata_json={"plan": "author_monthly", "amount": "USD 19.00"},
    )
    db.add(event)
    await db.commit()
    event.updated_at = now - timedelta(hours=1)
    await db.commit()

    attempts: list[str] = []

    async def fake_send(email: str, plan: str, *, amount: str | None = None) -> bool:
        attempts.append(plan)
        return len(attempts) > 1

    monkeypatch.setattr(
        "app.services.subscription_email_service.send_subscription_payment_failed",
        fake_send,
    )

    first = await send_due_payment_failure_notices(db, now=now, limit=10)
    await db.refresh(event)
    assert first == {"sent": 0, "checked": 1}
    assert event.status == "failed"

    later = now + timedelta(hours=1)
    second = await send_due_payment_failure_notices(db, now=later, limit=10)
    await db.refresh(event)
    assert second == {"sent": 1, "checked": 1}
    assert event.status == EMAIL_EVENT_STATUS_SENT
    assert attempts == ["author_monthly", "author_monthly"]
