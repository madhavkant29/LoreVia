from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.user import Subscription, User
from app.schemas.billing import CheckoutBody
from app.services.paddle_service import create_checkout_url, create_portal_url, paddle_is_configured
from app.utils.billing_utils import VALID_PAID_PLAN_CODES, normalize_plan_code, paddle_plan_is_configured
from app.utils.logging import get_logger

router = APIRouter()
log = get_logger("lorevia.billing")


@router.post("/checkout")
async def start_checkout(
    body: CheckoutBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = normalize_plan_code(body.plan)
    if plan not in VALID_PAID_PLAN_CODES:
        raise HTTPException(400, "Invalid plan")

    if not paddle_is_configured() or not paddle_plan_is_configured(plan):
        return {
            "checkout_url": None,
            "billing_enabled": False,
            "message": f"Paddle is not configured for {plan.replace('_', ' ')} in this environment.",
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
            plan=plan,
            status="pending",
        )
        db.add(existing)
    else:
        existing.plan = plan
        existing.status = "pending"

    await db.commit()

    try:
        checkout_url, customer_id = await create_checkout_url(
            str(current_user.id),
            current_user.email,
            plan,
            existing_customer_id=existing.paddle_customer_id,
        )
    except Exception:
        log.exception("paddle_checkout_failed", extra={"user_id": str(current_user.id), "plan": plan})
        raise HTTPException(502, "Unable to start Paddle checkout.")

    existing.paddle_customer_id = customer_id
    await db.commit()
    return {"checkout_url": checkout_url, "billing_enabled": True}


@router.post("/portal")
async def open_portal(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not paddle_is_configured():
        return {
            "portal_url": None,
            "billing_enabled": False,
            "message": "Paddle is not configured in this environment.",
        }

    subscription = (
        await db.execute(
            select(Subscription)
            .where(Subscription.user_id == current_user.id, Subscription.paddle_customer_id.is_not(None))
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().first()

    if not subscription or not subscription.paddle_customer_id:
        raise HTTPException(404, "No billing account found")

    try:
        portal_url = await create_portal_url(
            subscription.paddle_customer_id,
            [subscription.paddle_sub_id] if subscription.paddle_sub_id else None,
        )
    except Exception:
        log.exception("paddle_portal_failed", extra={"user_id": str(current_user.id)})
        raise HTTPException(502, "Unable to open Paddle portal.")
    return {"portal_url": portal_url, "billing_enabled": True}
