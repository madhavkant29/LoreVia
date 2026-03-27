from fastapi import APIRouter, Request, HTTPException, Header
from app.core.config import settings
import stripe

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "Invalid signature")

    from app.core.database import AsyncSessionLocal
    from app.models.user import User, Subscription
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as db:
        if event["type"] == "customer.subscription.created":
            sub = event["data"]["object"]
            existing = (await db.execute(
                select(Subscription).where(Subscription.stripe_customer_id == sub["customer"])
            )).scalar()
            if existing:
                existing.status = "active"
                existing.stripe_sub_id = sub["id"]
                # Determine tier from plan
                plan = sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
                tier = "power" if "power" in plan.lower() else "pro"
                await db.execute(update(User).where(User.id == existing.user_id).values(tier=tier))
                await db.commit()

        elif event["type"] == "customer.subscription.deleted":
            sub = event["data"]["object"]
            existing = (await db.execute(
                select(Subscription).where(Subscription.stripe_sub_id == sub["id"])
            )).scalar()
            if existing:
                existing.status = "cancelled"
                await db.execute(update(User).where(User.id == existing.user_id).values(tier="free"))
                await db.commit()

    return {"received": True}
