from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Subscription
from app.services.paddle_service import get_subscription
from app.services.paddle_webhook_service import (
    deliver_subscription_email_job,
    sync_subscription_from_paddle,
)

logger = logging.getLogger(__name__)

RECONCILABLE_STATUSES = ("active", "trialing", "past_due", "paused")
RECONCILIATION_STALE_AFTER = timedelta(hours=24)
PADDLE_RECONCILIATION_EXCEPTIONS = (RuntimeError, httpx.HTTPError, KeyError, ValueError)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def reconcile_stale_subscriptions(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 25,
) -> dict[str, int]:
    """Refresh local state from Paddle for subscriptions that look stale.

    A missed webhook should not permanently corrupt entitlement state. This job
    only asks Paddle about paid subscriptions whose local row has not changed
    for a day, so it stays cheap and does not hammer the provider.
    """

    current = _as_utc(now)
    cutoff = current - RECONCILIATION_STALE_AFTER
    subscriptions = (
        (
            await db.execute(
                select(Subscription)
                .where(
                    Subscription.paddle_sub_id.is_not(None),
                    Subscription.status.in_(RECONCILABLE_STATUSES),
                    Subscription.updated_at < cutoff,
                )
                .order_by(Subscription.updated_at.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    synced = 0
    missing = 0
    failed = 0
    for subscription in subscriptions:
        try:
            data = await get_subscription(str(subscription.paddle_sub_id))
        except PADDLE_RECONCILIATION_EXCEPTIONS:
            failed += 1
            logger.exception(
                "Paddle subscription reconciliation fetch failed for %s",
                subscription.paddle_sub_id,
            )
            continue

        if not data:
            missing += 1
            continue

        try:
            email_jobs = await sync_subscription_from_paddle(
                db,
                subscription=subscription,
                data=data,
                event_type="subscription.updated",
                occurred_at=current,
            )
            await db.commit()
        except PADDLE_RECONCILIATION_EXCEPTIONS:
            await db.rollback()
            failed += 1
            logger.exception(
                "Paddle subscription reconciliation sync failed for %s",
                subscription.paddle_sub_id,
            )
            continue

        for email_job in email_jobs:
            await deliver_subscription_email_job(
                email_job,
                event_id=f"reconcile:{subscription.paddle_sub_id}",
            )
        synced += 1

    return {
        "checked": len(subscriptions),
        "synced": synced,
        "missing": missing,
        "failed": failed,
    }
