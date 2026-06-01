from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models.user import PaddleWebhookEvent, RefundReview, Subscription, User
from app.services.email_service import (
    send_subscription_cancellation,
    send_subscription_confirmation,
)
from app.services.refund_service import (
    REFUND_STATUS_APPROVED,
    REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED,
    apply_adjustment_webhook,
)
from app.utils.billing_utils import (
    SUPPORTED_PADDLE_WEBHOOK_EVENTS,
    coerce_user_id,
    event_id_from_paddle_payload,
    paddle_plan_from_event_data,
    paddle_price_id_from_event_data,
    record_subscription_event,
    subscription_event_type_for_metrics,
    subscription_service_is_active,
    tier_from_plan_code,
)
from app.utils.logging.errors import public_error_message, redact_sensitive_text


logger = logging.getLogger(__name__)

WEBHOOK_STATUS_PROCESSING = "processing"
WEBHOOK_STATUS_PROCESSED = "processed"
WEBHOOK_STATUS_IGNORED = "ignored"
WEBHOOK_STATUS_FAILED = "failed"
SERVICE_ACTIVE_STATUSES = {"active", "trialing"}
CANCELED_STATUSES = {"canceled", "cancelled"}
SUBSCRIPTION_CONFIRMATION_EMAIL = "subscription_confirmation"
SUBSCRIPTION_CANCELLATION_EMAIL = "subscription_cancellation"


async def process_paddle_webhook(event: dict[str, Any]) -> dict[str, Any]:
    event_id = event_id_from_paddle_payload(event)
    if not event_id:
        raise ValueError("Missing Paddle event ID")

    event_type = str(event.get("event_type") or "").strip()
    notification_id = _string_or_none(event.get("notification_id"))
    claim = await _claim_webhook_event(
        event_id=event_id,
        event_type=event_type,
        notification_id=notification_id,
        payload=event,
    )
    if claim["duplicate"]:
        return {"received": True, "duplicate": True}

    try:
        return await _process_claimed_webhook(
            event_id=event_id,
            event_type=event_type,
            notification_id=notification_id,
            payload=event,
        )
    except Exception:
        await _mark_webhook_failed(event_id=event_id, error_message=public_error_message(500))
        raise


async def _claim_webhook_event(
    *,
    event_id: str,
    event_type: str,
    notification_id: str | None,
    payload: dict[str, Any],
) -> dict[str, bool]:
    async with AsyncSessionLocal() as db:
        existing = await _get_webhook_event(db, event_id)
        if existing is None:
            db.add(
                PaddleWebhookEvent(
                    event_id=event_id,
                    event_type=event_type,
                    notification_id=notification_id,
                    processing_status=WEBHOOK_STATUS_PROCESSING,
                    payload_json=payload,
                )
            )
            try:
                await db.commit()
                return {"duplicate": False}
            except IntegrityError:
                await db.rollback()

    async with AsyncSessionLocal() as db:
        existing = await _get_webhook_event(db, event_id)
        if existing is None:
            raise RuntimeError(f"Unable to claim Paddle webhook event {event_id}")

        if existing.processing_status in {
            WEBHOOK_STATUS_PROCESSING,
            WEBHOOK_STATUS_PROCESSED,
            WEBHOOK_STATUS_IGNORED,
        }:
            existing.event_type = event_type
            existing.notification_id = notification_id or existing.notification_id
            existing.payload_json = payload
            existing.duplicate_count = int(existing.duplicate_count or 0) + 1
            await db.commit()
            return {"duplicate": True}

        retry_claim = await db.execute(
            update(PaddleWebhookEvent)
            .where(
                PaddleWebhookEvent.event_id == event_id,
                PaddleWebhookEvent.processing_status == WEBHOOK_STATUS_FAILED,
            )
            .values(
                event_type=event_type,
                notification_id=notification_id,
                payload_json=payload,
                processing_status=WEBHOOK_STATUS_PROCESSING,
                processed_at=None,
                last_error=None,
                duplicate_count=func.coalesce(PaddleWebhookEvent.duplicate_count, 0) + 1,
            )
        )
        await db.commit()
        if retry_claim.rowcount == 1:
            return {"duplicate": False}
        return {"duplicate": True}


async def _process_claimed_webhook(
    *,
    event_id: str,
    event_type: str,
    notification_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        try:
            webhook_event = await _get_webhook_event(db, event_id)
            if webhook_event is None:
                raise RuntimeError(f"Paddle webhook event {event_id} disappeared during processing")

            webhook_event.event_type = event_type
            webhook_event.notification_id = notification_id or webhook_event.notification_id
            webhook_event.payload_json = payload

            if event_type not in SUPPORTED_PADDLE_WEBHOOK_EVENTS:
                webhook_event.processing_status = WEBHOOK_STATUS_IGNORED
                webhook_event.processed_at = datetime.now(UTC)
                webhook_event.last_error = None
                await db.commit()
                return {"received": True, "ignored": True}

            data = payload.get("data") or {}
            email_job: tuple[str, str, str] | None = None
            if event_type.startswith("adjustment."):
                await apply_adjustment_webhook(
                    db,
                    event_type=event_type,
                    data=data,
                )
            else:
                context = await _resolve_subscription_context(db, event_type=event_type, data=data)
                email_job = await _apply_subscription_change(
                    db,
                    event_id=event_id,
                    event_type=event_type,
                    data=data,
                    context=context,
                )

            webhook_event.processing_status = WEBHOOK_STATUS_PROCESSED
            webhook_event.processed_at = datetime.now(UTC)
            webhook_event.last_error = None
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    if email_job is not None:
        email_kind, email_address, plan_tier = email_job
        try:
            if email_kind == SUBSCRIPTION_CONFIRMATION_EMAIL:
                await send_subscription_confirmation(email_address, plan_tier)
            elif email_kind == SUBSCRIPTION_CANCELLATION_EMAIL:
                await send_subscription_cancellation(email_address, plan_tier)
        except Exception:
            logger.exception("Failed to send subscription lifecycle email for Paddle event %s", event_id)

    return {"received": True}


async def _apply_subscription_change(
    db,
    *,
    event_id: str,
    event_type: str,
    data: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, str] | None:
    subscription: Subscription | None = context["subscription"]
    customer_id = context["customer_id"]
    subscription_id = context["subscription_id"]
    transaction_id = context["transaction_id"]
    plan = context["plan"]
    plan_price_id = context["price_id"]

    if subscription is None:
        return None

    previous_status = _normalized_status(subscription.status)
    user = await db.get(User, subscription.user_id)
    previous_user_tier = _normalized_status(user.tier if user else None)

    next_status = _next_subscription_status(
        event_type=event_type,
        incoming_status=context["status"],
        current_status=previous_status,
    )
    plan_to_store = plan or subscription.plan or "free"

    subscription.plan = plan_to_store
    subscription.status = next_status
    subscription.paddle_customer_id = customer_id or subscription.paddle_customer_id
    subscription.paddle_sub_id = subscription_id or subscription.paddle_sub_id
    subscription.paddle_transaction_id = transaction_id or subscription.paddle_transaction_id

    next_tier = _tier_after_event(
        event_type=event_type,
        status=next_status,
        plan=plan_to_store,
        price_id=plan_price_id,
        current_tier=previous_user_tier or "free",
    )
    if next_tier is not None:
        await db.execute(
            update(User)
            .where(User.id == subscription.user_id)
            .values(tier=next_tier)
        )

    metrics_event_type = _metrics_event_type(
        event_type=event_type,
        previous_status=previous_status,
        status=next_status,
    )
    if metrics_event_type:
        await record_subscription_event(
            db,
            user_id=subscription.user_id,
            event_type=metrics_event_type,
            source_event_id=event_id,
            plan=plan_to_store,
            status=next_status,
            paddle_customer_id=subscription.paddle_customer_id,
            paddle_sub_id=subscription.paddle_sub_id,
            metadata={"webhook_event_type": event_type},
        )

    await _resolve_refund_follow_up_if_completed_cancellation(
        db,
        event_type=event_type,
        status=next_status,
        transaction_id=subscription.paddle_transaction_id,
    )

    if (
        event_type == "transaction.completed"
        and not _is_service_active(previous_status)
        and _is_service_active(next_status)
        and previous_user_tier == "free"
    ):
        if user and user.email:
            return (
                SUBSCRIPTION_CONFIRMATION_EMAIL,
                user.email,
                next_tier or previous_user_tier or "free",
            )

    if (
        event_type == "subscription.canceled"
        and previous_status not in CANCELED_STATUSES
        and next_status in CANCELED_STATUSES
        and user
        and user.email
    ):
        return (
            SUBSCRIPTION_CANCELLATION_EMAIL,
            user.email,
            tier_from_plan_code(plan_to_store, plan_price_id) or previous_user_tier or plan_to_store,
        )

    return None


async def _resolve_subscription_context(db, *, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    custom_data = data.get("custom_data") or {}
    user_id = coerce_user_id(custom_data.get("user_id"))
    customer_id = _customer_id_from_data(data)
    subscription_id = _subscription_id_from_data(event_type=event_type, data=data)
    transaction_id = _transaction_id_from_data(event_type=event_type, data=data)
    plan = paddle_plan_from_event_data(data)
    price_id = paddle_price_id_from_event_data(data)
    status = _normalized_status(data.get("status"))

    if user_id is None:
        raise RuntimeError(
            "Unable to associate Paddle webhook with a local subscription or user "
            f"(event_type={event_type}, subscription_id={subscription_id or 'missing'}, "
            f"customer_id={customer_id or 'missing'}, user_id=missing)."
        )

    subscription = await _find_subscription(
        db,
        user_id=user_id,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )
    if subscription is None and user_id is not None:
        subscription = Subscription(
            user_id=user_id,
            plan=plan or "free",
            status="pending",
            paddle_customer_id=customer_id,
            paddle_sub_id=subscription_id,
            paddle_transaction_id=transaction_id,
        )
        db.add(subscription)

    if subscription is None:
        raise RuntimeError(
            "Unable to associate Paddle webhook with a local subscription or user "
            f"(event_type={event_type}, subscription_id={subscription_id or 'missing'}, "
            f"customer_id={customer_id or 'missing'}, user_id={user_id or 'missing'})."
        )

    return {
        "subscription": subscription,
        "user_id": user_id,
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "transaction_id": transaction_id,
        "plan": plan,
        "price_id": price_id,
        "status": status,
    }


async def _find_subscription(
    db,
    *,
    user_id,
    customer_id: str | None,
    subscription_id: str | None,
) -> Subscription | None:
    if user_id is not None:
        if subscription_id:
            subscription = (
                await db.execute(
                    select(Subscription)
                    .where(
                        Subscription.user_id == user_id,
                        Subscription.paddle_sub_id == subscription_id,
                    )
                    .order_by(Subscription.created_at.desc())
                )
            ).scalars().first()
            if subscription is not None:
                return subscription

        if customer_id:
            subscription = (
                await db.execute(
                    select(Subscription)
                    .where(
                        Subscription.user_id == user_id,
                        Subscription.paddle_customer_id == customer_id,
                    )
                    .order_by(Subscription.created_at.desc())
                )
            ).scalars().first()
            if subscription is not None:
                return subscription

        subscription = (
            await db.execute(
                select(Subscription)
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
            )
        ).scalars().first()
        return subscription

    if subscription_id:
        subscription = (
            await db.execute(
                select(Subscription)
                .where(Subscription.paddle_sub_id == subscription_id)
                .order_by(Subscription.created_at.desc())
            )
        ).scalars().first()
        if subscription is not None:
            return subscription

    if customer_id:
        return (
            await db.execute(
                select(Subscription)
                .where(Subscription.paddle_customer_id == customer_id)
                .order_by(Subscription.created_at.desc())
            )
        ).scalars().first()

    return None


async def _mark_webhook_failed(*, event_id: str, error_message: str) -> None:
    async with AsyncSessionLocal() as db:
        webhook_event = await _get_webhook_event(db, event_id)
        if webhook_event is None:
            return
        webhook_event.processing_status = WEBHOOK_STATUS_FAILED
        webhook_event.processed_at = None
        webhook_event.last_error = redact_sensitive_text(error_message)
        await db.commit()


async def _get_webhook_event(db, event_id: str) -> PaddleWebhookEvent | None:
    return (
        await db.execute(
            select(PaddleWebhookEvent).where(PaddleWebhookEvent.event_id == event_id)
        )
    ).scalars().first()


def _subscription_id_from_data(*, event_type: str, data: dict[str, Any]) -> str | None:
    if event_type.startswith("subscription."):
        return _string_or_none(data.get("id") or data.get("subscription_id"))
    subscription = data.get("subscription") or {}
    return _string_or_none(data.get("subscription_id") or subscription.get("id"))


def _customer_id_from_data(data: dict[str, Any]) -> str | None:
    customer = data.get("customer") or {}
    return _string_or_none(data.get("customer_id") or customer.get("id"))


def _transaction_id_from_data(*, event_type: str, data: dict[str, Any]) -> str | None:
    if event_type.startswith("transaction."):
        return _string_or_none(data.get("id"))
    transaction = data.get("transaction") or {}
    return _string_or_none(data.get("transaction_id") or transaction.get("id"))


def _next_subscription_status(*, event_type: str, incoming_status: str, current_status: str) -> str:
    if event_type == "transaction.completed":
        if current_status in {"paused", "past_due", *CANCELED_STATUSES, "trialing", "active"}:
            return current_status
        return "active"
    if event_type == "transaction.past_due":
        return "past_due"
    if event_type == "transaction.payment_failed":
        return incoming_status or "past_due"
    if event_type == "subscription.activated":
        return "active"
    if event_type == "subscription.resumed":
        return "active"
    if event_type == "subscription.trialing":
        return "trialing"
    if event_type == "subscription.paused":
        return "paused"
    if event_type == "subscription.past_due":
        return "past_due"
    if event_type == "subscription.canceled":
        return incoming_status or "canceled"
    if event_type == "subscription.created":
        return incoming_status or "pending"
    if event_type == "subscription.updated":
        return incoming_status or current_status or "pending"
    if event_type == "transaction.updated":
        return incoming_status or current_status or "pending"
    return incoming_status or current_status or "pending"


def _tier_after_event(
    *,
    event_type: str,
    status: str,
    plan: str,
    price_id: str,
    current_tier: str,
) -> str | None:
    if event_type == "subscription.paused":
        return "free"
    if event_type == "subscription.canceled":
        return "free" if status in CANCELED_STATUSES else current_tier
    if event_type in {"subscription.past_due", "transaction.past_due", "transaction.payment_failed", "transaction.updated"}:
        return current_tier
    if subscription_service_is_active(event_type, status):
        return tier_from_plan_code(plan, price_id)
    return current_tier


def _metrics_event_type(*, event_type: str, previous_status: str, status: str) -> str | None:
    if event_type == "subscription.canceled" and status not in CANCELED_STATUSES:
        return None
    metrics_event_type = subscription_event_type_for_metrics(event_type, status)
    if metrics_event_type == "subscription_activated":
        if _is_service_active(previous_status):
            return None
        if not _is_service_active(status):
            return None
    return metrics_event_type


def _is_service_active(status: str | None) -> bool:
    return _normalized_status(status) in SERVICE_ACTIVE_STATUSES


def _normalized_status(value: str | None) -> str:
    return (value or "").strip().lower()


def _string_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


async def _resolve_refund_follow_up_if_completed_cancellation(
    db,
    *,
    event_type: str,
    status: str,
    transaction_id: str | None,
) -> None:
    if event_type != "subscription.canceled" or status not in CANCELED_STATUSES or not transaction_id:
        return

    review = (
        await db.execute(
            select(RefundReview)
            .where(RefundReview.paddle_transaction_id == transaction_id)
            .order_by(RefundReview.created_at.desc())
        )
    ).scalars().first()
    if review is None or review.status != REFUND_STATUS_PROVIDER_FOLLOWUP_REQUIRED:
        return
    if not review.paddle_adjustment_id or not _review_has_approved_adjustment(review):
        return

    review.status = REFUND_STATUS_APPROVED
    review.resolved_at = review.resolved_at or datetime.now(UTC)


def _review_has_approved_adjustment(review: RefundReview) -> bool:
    provider_response = dict(review.provider_response_json or {})
    adjustment_updated = provider_response.get("adjustment_updated")
    if not isinstance(adjustment_updated, dict):
        return False
    return _normalized_status(adjustment_updated.get("status")) == "approved"
