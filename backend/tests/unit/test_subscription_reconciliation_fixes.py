"""Regression tests for the confirmed Paddle reconciliation defects.

Covers:
- D1: a second reconciliation sync of the same subscription must not raise
  IntegrityError from the unique SubscriptionEvent.source_event_id.
- D2: provider-side paused/canceled statuses must downgrade entitlements
  instead of keeping the paid tier.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Subscription, SubscriptionEvent, User
from app.services.paddle_webhook_service import sync_subscription_from_paddle


async def _create_subscription(
    db: AsyncSession, *, status: str = "active"
) -> tuple[User, Subscription]:
    user = User(
        email=f"reconcile-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"reconcile{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    subscription = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status=status,
        paddle_sub_id=f"sub_{uuid.uuid4().hex[:12]}",
        paddle_customer_id=f"ctm_{uuid.uuid4().hex[:12]}",
    )
    db.add(subscription)
    await db.flush()
    return user, subscription


def _provider_payload(subscription: Subscription, status: str) -> dict:
    return {
        "id": subscription.paddle_sub_id,
        "status": status,
        "customer_id": subscription.paddle_customer_id,
    }


@pytest.mark.asyncio
async def test_reconciliation_sync_is_repeatable_without_integrity_error(db: AsyncSession):
    user, subscription = await _create_subscription(db)
    await db.commit()

    now = datetime.now(UTC)
    await sync_subscription_from_paddle(
        db,
        subscription=subscription,
        data=_provider_payload(subscription, "active"),
        event_type="subscription.updated",
        occurred_at=now,
    )
    await db.commit()

    # Second sync of unchanged provider state must not collide on the
    # unique SubscriptionEvent.source_event_id.
    await sync_subscription_from_paddle(
        db,
        subscription=subscription,
        data=_provider_payload(subscription, "active"),
        event_type="subscription.updated",
        occurred_at=datetime.now(UTC),
    )
    await db.commit()

    watermarks = (
        (
            await db.execute(
                select(SubscriptionEvent).where(
                    SubscriptionEvent.user_id == user.id,
                    SubscriptionEvent.paddle_sub_id == subscription.paddle_sub_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(watermarks) >= 2


@pytest.mark.asyncio
async def test_reconciliation_paused_status_downgrades_tier(db: AsyncSession):
    user, subscription = await _create_subscription(db)
    await db.commit()

    email_jobs = await sync_subscription_from_paddle(
        db,
        subscription=subscription,
        data=_provider_payload(subscription, "paused"),
        event_type="subscription.updated",
        occurred_at=datetime.now(UTC),
    )
    await db.commit()
    await db.refresh(subscription)

    await db.refresh(user)
    assert subscription.status == "paused"
    assert user.tier == "free"
    assert email_jobs is not None


@pytest.mark.asyncio
async def test_reconciliation_canceled_status_cancels_and_downgrades(db: AsyncSession):
    user, subscription = await _create_subscription(db)
    await db.commit()

    await sync_subscription_from_paddle(
        db,
        subscription=subscription,
        data=_provider_payload(subscription, "canceled"),
        event_type="subscription.updated",
        occurred_at=datetime.now(UTC),
    )
    await db.commit()
    await db.refresh(subscription)
    await db.refresh(user)

    assert subscription.status == "canceled"
    assert subscription.plan == "free"
    assert user.tier == "free"
