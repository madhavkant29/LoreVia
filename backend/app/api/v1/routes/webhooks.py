from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select, update

import stripe

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import remember_webhook_event
from app.models.user import Subscription, User

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY


def _tier_from_plan(plan_name: str, price_id: str) -> str:
    normalized = f"{plan_name} {price_id}".lower()
    if "power" in normalized:
        return "power"
    return "pro"


@router.post("/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid signature")

    if not await remember_webhook_event(event["id"]):
        return {"received": True, "duplicate": True}

    async with AsyncSessionLocal() as db:
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            metadata = session.get("metadata", {}) or {}
            user_id = metadata.get("user_id")
            plan = metadata.get("plan", "pro_monthly")
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")
            if user_id:
                existing = (
                    await db.execute(
                        select(Subscription)
                        .where(Subscription.user_id == user_id)
                        .order_by(Subscription.created_at.desc())
                    )
                ).scalars().first()
                if not existing:
                    existing = Subscription(
                        user_id=user_id,
                        plan=plan,
                        status="active",
                        stripe_customer_id=customer_id,
                        stripe_sub_id=subscription_id,
                    )
                    db.add(existing)
                else:
                    existing.plan = plan
                    existing.status = "active"
                    existing.stripe_customer_id = customer_id
                    existing.stripe_sub_id = subscription_id

                tier = _tier_from_plan(plan, "")
                await db.execute(update(User).where(User.id == user_id).values(tier=tier))
                await db.commit()

        elif event["type"] in {"customer.subscription.created", "customer.subscription.updated"}:
            sub = event["data"]["object"]
            existing = (
                await db.execute(
                    select(Subscription).where(Subscription.stripe_customer_id == sub["customer"])
                )
            ).scalars().first()
            if existing:
                price_id = sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
                existing.status = sub.get("status", "active")
                existing.stripe_sub_id = sub["id"]
                tier = _tier_from_plan(existing.plan, price_id)
                await db.execute(update(User).where(User.id == existing.user_id).values(tier=tier))
                await db.commit()

        elif event["type"] == "customer.subscription.deleted":
            sub = event["data"]["object"]
            existing = (
                await db.execute(
                    select(Subscription).where(Subscription.stripe_sub_id == sub["id"])
                )
            ).scalars().first()
            if existing:
                existing.status = "cancelled"
                await db.execute(update(User).where(User.id == existing.user_id).values(tier="free"))
                await db.commit()

    return {"received": True}
