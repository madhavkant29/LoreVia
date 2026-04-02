from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.redis import remember_webhook_event
from app.models.user import Subscription, User
from app.services.paddle_service import paddle_webhooks_configured, verify_webhook_signature

router = APIRouter()


def _tier_from_plan(plan_name: str, price_id: str) -> str:
    normalized = f"{plan_name} {price_id}".lower()
    if "power" in normalized:
        return "power"
    return "pro"


def _event_id(payload: dict) -> str:
    return (
        payload.get("event_id")
        or payload.get("notification_id")
        or payload.get("id")
        or ""
    )


def _extract_plan(data: dict) -> str:
    custom_data = data.get("custom_data") or {}
    if isinstance(custom_data, dict) and custom_data.get("plan"):
        return str(custom_data["plan"])

    items = data.get("items") or []
    for item in items:
        price = item.get("price") or {}
        product = price.get("product") or {}
        candidate = f"{price.get('name', '')} {product.get('name', '')}".lower()
        if "power" in candidate:
            interval = ((price.get("billing_cycle") or {}).get("interval") or "").lower()
            return "power_annual" if interval == "year" else "power_monthly"
        if "pro" in candidate:
            interval = ((price.get("billing_cycle") or {}).get("interval") or "").lower()
            return "pro_annual" if interval == "year" else "pro_monthly"

    return "pro_monthly"


def _extract_price_id(data: dict) -> str:
    items = data.get("items") or []
    for item in items:
        price = item.get("price") or {}
        if price.get("id"):
            return str(price["id"])
    return ""


@router.post("/paddle")
async def paddle_webhook(request: Request, paddle_signature: str | None = Header(default=None, alias="Paddle-Signature")):
    if not paddle_webhooks_configured():
        raise HTTPException(503, "Paddle webhooks are not configured")

    payload = await request.body()
    if not verify_webhook_signature(payload, paddle_signature):
        raise HTTPException(400, "Invalid signature")

    event = await request.json()
    event_id = _event_id(event)
    if not event_id:
        raise HTTPException(400, "Missing Paddle event ID")

    if not await remember_webhook_event(event_id):
        return {"received": True, "duplicate": True}

    event_type = event.get("event_type", "")
    data = event.get("data") or {}

    async with AsyncSessionLocal() as db:
        if event_type in {"transaction.completed", "subscription.created", "subscription.updated"}:
            custom_data = data.get("custom_data") or {}
            user_id = custom_data.get("user_id")
            customer_id = data.get("customer_id")
            subscription_id = data.get("subscription_id") or data.get("id")
            transaction_id = data.get("id") if event_type.startswith("transaction.") else data.get("transaction_id")
            plan = _extract_plan(data)

            existing = None
            if user_id:
                existing = (
                    await db.execute(
                        select(Subscription)
                        .where(Subscription.user_id == user_id)
                        .order_by(Subscription.created_at.desc())
                    )
                ).scalars().first()
            elif customer_id:
                existing = (
                    await db.execute(
                        select(Subscription)
                        .where(Subscription.paddle_customer_id == customer_id)
                        .order_by(Subscription.created_at.desc())
                    )
                ).scalars().first()

            if existing:
                existing.plan = plan
                existing.status = data.get("status", "active")
                existing.paddle_customer_id = customer_id or existing.paddle_customer_id
                existing.paddle_sub_id = subscription_id or existing.paddle_sub_id
                existing.paddle_transaction_id = transaction_id or existing.paddle_transaction_id
                await db.execute(
                    update(User)
                    .where(User.id == existing.user_id)
                    .values(tier=_tier_from_plan(plan, _extract_price_id(data)))
                )
                await db.commit()

        elif event_type in {"subscription.canceled", "subscription.past_due"}:
            subscription_id = data.get("id")
            existing = (
                await db.execute(
                    select(Subscription).where(Subscription.paddle_sub_id == subscription_id)
                )
            ).scalars().first()
            if existing:
                existing.status = data.get("status", "cancelled")
                if event_type == "subscription.canceled":
                    await db.execute(update(User).where(User.id == existing.user_id).values(tier="free"))
                await db.commit()

    return {"received": True}
