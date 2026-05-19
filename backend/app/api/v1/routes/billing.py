from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user, get_optional_current_user
from app.api.deps.rate_limit import rate_limit_api
from app.core.database import get_db
from app.models.user import Subscription, User
from app.schemas.billing import BillingConfirmationOut, BillingStatusOut, CheckoutBody
from app.services.paddle_service import (
    create_checkout_url,
    create_portal_url,
    get_transaction_summary,
    paddle_is_configured,
)
from app.utils.billing_utils import (
    BILLING_CONFIRMATION_QUERY_KEY,
    VALID_PAID_PLAN_CODES,
    append_billing_confirmation_token,
    billing_interval_for_plan,
    billing_configuration_status,
    create_billing_confirmation_token,
    normalize_plan_code,
    paddle_plan_is_configured,
    verify_billing_confirmation_token,
)
from app.utils.logging import get_logger

router = APIRouter()
log = get_logger("lorevia.billing")


@router.get("/status", response_model=BillingStatusOut, dependencies=[Depends(rate_limit_api)])
async def get_billing_status():
    return BillingStatusOut(**billing_configuration_status())


@router.post("/checkout", dependencies=[Depends(rate_limit_api)])
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
        checkout_url, customer_id, transaction_id = await create_checkout_url(
            str(current_user.id),
            current_user.email,
            plan,
            existing_customer_id=existing.paddle_customer_id,
        )
    except Exception:
        log.exception("paddle_checkout_failed", extra={"user_id": str(current_user.id), "plan": plan})
        raise HTTPException(502, "Unable to start Paddle checkout.")

    existing.paddle_customer_id = customer_id
    existing.paddle_transaction_id = transaction_id
    await db.commit()
    confirmation_token = create_billing_confirmation_token(transaction_id)
    return {
        "checkout_url": append_billing_confirmation_token(checkout_url, confirmation_token),
        "billing_enabled": True,
    }


@router.get("/confirmation", response_model=BillingConfirmationOut)
async def get_checkout_confirmation(
    request: Request,
    response: Response,
    transaction_id: str = Query(..., min_length=1),
    confirmation_token: str | None = Query(default=None, alias="confirmation_token"),
    checkout_token: str | None = Query(default=None, alias=BILLING_CONFIRMATION_QUERY_KEY),
    db: AsyncSession = Depends(get_db),
):
    normalized_transaction_id = transaction_id.strip()
    resolved_confirmation_token = confirmation_token or checkout_token
    token_is_valid = verify_billing_confirmation_token(
        resolved_confirmation_token,
        normalized_transaction_id,
    )
    current_user: User | None = None
    if not token_is_valid:
        try:
            current_user = await get_optional_current_user(
                request=request,
                response=response,
                credentials=None,
                db=db,
            )
        except Exception:
            current_user = None
    if current_user is None and not token_is_valid:
        raise HTTPException(401, "A valid confirmation token is required.")

    statement = (
        select(Subscription)
        .where(Subscription.paddle_transaction_id == normalized_transaction_id)
        .order_by(Subscription.created_at.desc())
    )
    if current_user is not None and not token_is_valid:
        statement = statement.where(Subscription.user_id == current_user.id)

    subscription = (await db.execute(statement)).scalars().first()

    if not subscription:
        raise HTTPException(404, "No completed billing record found for this account.")

    try:
        summary = await get_transaction_summary(normalized_transaction_id)
    except Exception:
        log.exception(
            "paddle_confirmation_failed",
            extra={
                "user_id": str(current_user.id) if current_user is not None else None,
                "transaction_id": normalized_transaction_id,
            },
        )
        raise HTTPException(502, "Unable to load Paddle transaction details.")

    plan = normalize_plan_code(summary.plan or subscription.plan)
    display_name = summary.display_name or plan.replace("_", " ").title()

    return BillingConfirmationOut(
        transaction_id=summary.transaction_id,
        status=summary.status or subscription.status,
        plan=plan,
        billing_interval=billing_interval_for_plan(plan),
        display_name=display_name,
        currency_code=summary.currency_code,
        total=summary.total,
        invoice_number=summary.invoice_number,
        invoice_pdf_url=summary.invoice_pdf_url,
        subscription_id=summary.subscription_id or subscription.paddle_sub_id,
        customer_email=summary.customer_email or (current_user.email if current_user is not None else None),
    )


@router.post("/portal", dependencies=[Depends(rate_limit_api)])
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
