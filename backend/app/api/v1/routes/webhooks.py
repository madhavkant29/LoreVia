from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import or_, select, update

from app.core.database import AsyncSessionLocal
from app.core.redis import remember_webhook_event
from app.models.user import Subscription, User
from app.services.paddle_service import paddle_webhooks_configured, verify_webhook_signature
from app.utils.billing_utils import (
    coerce_user_id,
    event_id_from_paddle_payload,
    paddle_plan_from_event_data,
    paddle_price_id_from_event_data,
    tier_from_plan_code,
)

router = APIRouter()


def _service_is_active(event_type: str, status: str | None) -> bool:
    normalized_status = (status or "").strip().lower()
    if event_type == "transaction.completed":
        return True
    return normalized_status in {"active", "trialing"}


@router.post("/paddle")
async def paddle_webhook(request: Request, paddle_signature: str | None = Header(default=None, alias="Paddle-Signature")):
    if not paddle_webhooks_configured():
        raise HTTPException(503, "Paddle webhooks are not configured")

    payload = await request.body()
    if not verify_webhook_signature(payload, paddle_signature):
        raise HTTPException(400, "Invalid request.")

    event = await request.json()
    event_id = event_id_from_paddle_payload(event)
    if not event_id:
        raise HTTPException(400, "Missing Paddle event ID")

    if not await remember_webhook_event(event_id):
        return {"received": True, "duplicate": True}

    event_type = event.get("event_type", "")
    data = event.get("data") or {}

    async with AsyncSessionLocal() as db:
        if event_type in {"transaction.completed", "subscription.created", "subscription.updated"}:
            custom_data = data.get("custom_data") or {}
            user_id = coerce_user_id(custom_data.get("user_id"))
            customer_id = data.get("customer_id")
            subscription_id = data.get("subscription_id") or data.get("id")
            transaction_id = data.get("id") if event_type.startswith("transaction.") else data.get("transaction_id")
            plan = paddle_plan_from_event_data(data)
            status = str(data.get("status") or ("active" if event_type == "transaction.completed" else "pending")).lower()

            existing = None
            if subscription_id:
                existing = (
                    await db.execute(
                        select(Subscription)
                        .where(Subscription.paddle_sub_id == subscription_id)
                        .order_by(Subscription.created_at.desc())
                    )
                ).scalars().first()
            if user_id:
                existing = existing or (
                    await db.execute(
                        select(Subscription)
                        .where(Subscription.user_id == user_id)
                        .order_by(Subscription.created_at.desc())
                    )
                ).scalars().first()
            elif customer_id:
                existing = existing or (
                    await db.execute(
                        select(Subscription)
                        .where(Subscription.paddle_customer_id == customer_id)
                        .order_by(Subscription.created_at.desc())
                    )
                ).scalars().first()

            if existing is None and user_id is not None:
                existing = Subscription(
                    user_id=user_id,
                    plan=plan or "free",
                    status=status,
                    paddle_customer_id=customer_id,
                    paddle_sub_id=subscription_id,
                    paddle_transaction_id=transaction_id,
                )
                db.add(existing)

            if existing is not None:
                existing.plan = plan or existing.plan
                existing.status = status
                existing.paddle_customer_id = customer_id or existing.paddle_customer_id
                existing.paddle_sub_id = subscription_id or existing.paddle_sub_id
                existing.paddle_transaction_id = transaction_id or existing.paddle_transaction_id
                effective_plan = plan or existing.plan
                next_tier = (
                    tier_from_plan_code(effective_plan, paddle_price_id_from_event_data(data))
                    if _service_is_active(event_type, status)
                    else "free"
                )
                await db.execute(
                    update(User)
                    .where(User.id == existing.user_id)
                    .values(tier=next_tier)
                )
                await db.commit()

        elif event_type in {"subscription.canceled", "subscription.past_due", "subscription.paused"}:
            subscription_id = data.get("id")
            customer_id = data.get("customer_id")
            conditions = []
            if subscription_id:
                conditions.append(Subscription.paddle_sub_id == subscription_id)
            if customer_id:
                conditions.append(Subscription.paddle_customer_id == customer_id)
            existing = None
            if conditions:
                existing = (
                    await db.execute(
                        select(Subscription)
                        .where(or_(*conditions))
                        .order_by(Subscription.created_at.desc())
                    )
                ).scalars().first()
            if existing:
                existing.status = data.get("status", "cancelled" if event_type == "subscription.canceled" else "past_due")
                await db.execute(update(User).where(User.id == existing.user_id).values(tier="free"))
                await db.commit()

    return {"received": True}
