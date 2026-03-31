from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.user import Subscription, User
from app.services.stripe_service import create_checkout_session, create_portal_session, stripe_is_configured

router = APIRouter()


class CheckoutBody(BaseModel):
    plan: str


@router.post("/checkout")
async def start_checkout(
    body: CheckoutBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.plan not in {"pro_monthly", "pro_annual", "power_monthly"}:
        raise HTTPException(400, "Invalid plan")

    if not stripe_is_configured():
        return {
            "checkout_url": None,
            "billing_enabled": False,
            "message": "Stripe is not configured in this environment.",
        }

    existing = (
        await db.execute(
            select(Subscription)
            .where(Subscription.user_id == current_user.id)
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().first()

    if not existing:
        existing = Subscription(
            user_id=current_user.id,
            plan=body.plan,
            status="pending",
        )
        db.add(existing)
    else:
        existing.plan = body.plan
        existing.status = "pending"

    await db.commit()

    checkout_url = create_checkout_session(
        str(current_user.id),
        current_user.email,
        body.plan,
        idempotency_key=f"checkout:{current_user.id}:{existing.id}:{body.plan}",
    )
    return {"checkout_url": checkout_url, "billing_enabled": True}


@router.post("/portal")
async def open_portal(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not stripe_is_configured():
        return {
            "portal_url": None,
            "billing_enabled": False,
            "message": "Stripe is not configured in this environment.",
        }

    subscription = (
        await db.execute(
            select(Subscription)
            .where(Subscription.user_id == current_user.id, Subscription.stripe_customer_id.is_not(None))
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().first()

    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(404, "No billing account found")

    portal_url = create_portal_session(
        subscription.stripe_customer_id,
        idempotency_key=f"portal:{current_user.id}:{subscription.id}",
    )
    return {"portal_url": portal_url, "billing_enabled": True}
