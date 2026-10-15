from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Subscription, SubscriptionEmailEvent, User
from app.services.email_service import (
    send_subscription_payment_failed,
    send_subscription_renewal_reminder,
)
from app.utils.billing_utils import (
    RENEWAL_REMINDER_DAYS_BEFORE,
    SUBSCRIPTION_EMAIL_PAYMENT_FAILED,
    SUBSCRIPTION_EMAIL_RENEWAL_REMINDER,
    VALID_PAID_PLAN_CODES,
    format_minor_amount,
    normalize_plan_code,
    plan_price_payload,
)
from app.utils.privacy_utils import user_is_deleted

logger = logging.getLogger(__name__)

EMAIL_EVENT_STATUS_PENDING = "pending"
EMAIL_EVENT_STATUS_SENDING = "sending"
EMAIL_EVENT_STATUS_SENT = "sent"
EMAIL_EVENT_STATUS_FAILED = "failed"
EMAIL_EVENT_STALE_SENDING = timedelta(minutes=30)
MAX_PAYMENT_FAILURE_ATTEMPTS = 2


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def claim_subscription_email_event(
    db: AsyncSession,
    *,
    subscription: Subscription,
    email_type: str,
    billing_period_end: datetime,
    scheduled_for: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> SubscriptionEmailEvent | None:
    """Insert a lifecycle-email claim, or return None when one already exists.

    The unique constraint on (subscription_id, email_type, billing_period_end)
    is the idempotency guard: the second event for the same period loses.
    """

    if subscription.id is None:
        await db.flush()
    event = SubscriptionEmailEvent(
        user_id=subscription.user_id,
        subscription_id=subscription.id,
        email_type=email_type,
        billing_period_end=billing_period_end,
        scheduled_for=scheduled_for or billing_period_end,
        status=EMAIL_EVENT_STATUS_PENDING,
        metadata_json=metadata or {},
    )
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except IntegrityError:
        return None
    return event


async def mark_subscription_email_event(
    db: AsyncSession,
    *,
    event_id: uuid.UUID | None,
    delivered: bool,
    error: str | None = None,
) -> None:
    if event_id is None:
        return
    event = await db.get(SubscriptionEmailEvent, event_id)
    if event is None:
        return
    if delivered:
        event.status = EMAIL_EVENT_STATUS_SENT
        event.sent_at = datetime.now(UTC)
        event.last_error = None
    else:
        event.status = EMAIL_EVENT_STATUS_FAILED
        event.sent_at = None
        event.last_error = error or "Email delivery failed."


def payment_failure_period_end(
    subscription: Subscription,
    *,
    event_period_end: datetime | None = None,
    fallback: datetime | None = None,
) -> datetime | None:
    return (
        _as_utc(event_period_end) or _as_utc(subscription.current_period_end) or _as_utc(fallback)
    )


def transaction_amount(data: dict[str, Any]) -> str | None:
    totals = (data.get("details") or {}).get("totals") or {}
    return format_minor_amount(totals.get("total"), data.get("currency_code"))


async def _mark_stale_sending_events(db: AsyncSession, current: datetime) -> None:
    stale_rows = (
        (
            await db.execute(
                select(SubscriptionEmailEvent).where(
                    SubscriptionEmailEvent.status == EMAIL_EVENT_STATUS_SENDING,
                    SubscriptionEmailEvent.updated_at < current - EMAIL_EVENT_STALE_SENDING,
                )
            )
        )
        .scalars()
        .all()
    )
    for event in stale_rows:
        event.status = EMAIL_EVENT_STATUS_FAILED
        event.last_error = (
            "Previous send attempt did not finalize. Review delivery logs before retrying."
        )


async def send_due_renewal_reminders(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    current = _as_utc(now) or datetime.now(UTC)
    window_end = current + timedelta(days=RENEWAL_REMINDER_DAYS_BEFORE)

    await _mark_stale_sending_events(db, current)

    due_rows = (
        await db.execute(
            select(Subscription, User)
            .join(User, User.id == Subscription.user_id)
            .where(
                Subscription.status == "active",
                Subscription.cancel_at_period_end.is_(False),
                Subscription.plan.in_(tuple(sorted(VALID_PAID_PLAN_CODES))),
                Subscription.current_period_end.is_not(None),
                Subscription.current_period_end > current,
                Subscription.current_period_end <= window_end,
                User.email_verified_at.is_not(None),
            )
            .order_by(Subscription.current_period_end.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()

    claimed: list[tuple[uuid.UUID, str, str, datetime]] = []
    for subscription, user in due_rows:
        if user_is_deleted(user):
            continue
        period_end = _as_utc(subscription.current_period_end)
        if period_end is None:
            continue
        plan = normalize_plan_code(subscription.plan)
        event = await claim_subscription_email_event(
            db,
            subscription=subscription,
            email_type=SUBSCRIPTION_EMAIL_RENEWAL_REMINDER,
            billing_period_end=period_end,
            scheduled_for=current,
            metadata={"source": "renewal_reminder_scheduler", "plan": plan},
        )
        if event is None:
            continue
        event.status = EMAIL_EVENT_STATUS_SENDING
        claimed.append((event.id, user.email, plan, period_end))

    await db.commit()

    sent_count = 0
    for event_id, email, plan, period_end in claimed:
        delivered = await send_subscription_renewal_reminder(
            email,
            plan,
            renewal_at=period_end,
            amount_usd=plan_price_payload(plan)["amount"],
        )
        await mark_subscription_email_event(db, event_id=event_id, delivered=delivered)
        if delivered:
            sent_count += 1
        await db.commit()

    return {"sent": sent_count, "checked": len(due_rows)}


async def send_due_payment_failure_notices(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 25,
) -> dict[str, int]:
    """Retry payment-failure notices that were claimed but not delivered.

    Webhook processing claims one row per subscription billing period and
    attempts delivery immediately. If delivery failed (or the process stopped
    between the claim and the send), this job retries the same row, so the
    unique constraint still guarantees at most one notice per period.
    """

    current = _as_utc(now) or datetime.now(UTC)
    retry_cutoff = current - EMAIL_EVENT_STALE_SENDING
    due_rows = (
        await db.execute(
            select(SubscriptionEmailEvent, User)
            .join(User, User.id == SubscriptionEmailEvent.user_id)
            .where(
                SubscriptionEmailEvent.email_type == SUBSCRIPTION_EMAIL_PAYMENT_FAILED,
                SubscriptionEmailEvent.status.in_(
                    (
                        EMAIL_EVENT_STATUS_PENDING,
                        EMAIL_EVENT_STATUS_SENDING,
                        EMAIL_EVENT_STATUS_FAILED,
                    )
                ),
                SubscriptionEmailEvent.updated_at <= retry_cutoff,
            )
            .order_by(SubscriptionEmailEvent.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()

    sent_count = 0
    for event, user in due_rows:
        if user_is_deleted(user):
            continue
        metadata = dict(event.metadata_json or {})
        attempts = int(metadata.get("attempts") or 0)
        if attempts >= MAX_PAYMENT_FAILURE_ATTEMPTS:
            continue
        metadata["attempts"] = attempts + 1
        event.metadata_json = metadata
        event.status = EMAIL_EVENT_STATUS_SENDING
        await db.commit()

        plan = normalize_plan_code(metadata.get("plan") or user.tier)
        amount = metadata.get("amount")
        delivered = await send_subscription_payment_failed(user.email, plan, amount=amount)
        await mark_subscription_email_event(db, event_id=event.id, delivered=delivered)
        if delivered:
            sent_count += 1
        await db.commit()

    return {"sent": sent_count, "checked": len(due_rows)}


async def send_due_subscription_emails(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    renewal = await send_due_renewal_reminders(db, now=now, limit=limit)
    payment = await send_due_payment_failure_notices(db, now=now, limit=min(max(limit, 1), 25))
    return {
        "renewal_sent": renewal["sent"],
        "renewal_checked": renewal["checked"],
        "payment_failure_sent": payment["sent"],
        "payment_failure_checked": payment["checked"],
    }
