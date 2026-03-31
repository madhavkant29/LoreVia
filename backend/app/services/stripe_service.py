import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def stripe_is_configured() -> bool:
    return bool(
        settings.STRIPE_SECRET_KEY
        and settings.STRIPE_WEBHOOK_SECRET
        and settings.STRIPE_PRO_MONTHLY_PRICE_ID
        and settings.STRIPE_POWER_MONTHLY_PRICE_ID
    )


def _price_ids() -> dict[str, str]:
    return {
        "pro_monthly": settings.STRIPE_PRO_MONTHLY_PRICE_ID or "",
        "pro_annual": settings.STRIPE_PRO_ANNUAL_PRICE_ID or settings.STRIPE_PRO_MONTHLY_PRICE_ID or "",
        "power_monthly": settings.STRIPE_POWER_MONTHLY_PRICE_ID or "",
    }


def create_checkout_session(user_id: str, email: str, plan: str, idempotency_key: str | None = None) -> str:
    price_id = _price_ids().get(plan)
    if not price_id:
        raise ValueError(f"No Stripe price configured for plan '{plan}'")

    session = stripe.checkout.Session.create(
        customer_email=email,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.APP_URL}/settings?upgraded=true",
        cancel_url=f"{settings.APP_URL}/settings?billing=cancelled",
        metadata={"user_id": user_id, "plan": plan},
        idempotency_key=idempotency_key,
    )
    return session.url


def create_portal_session(customer_id: str, idempotency_key: str | None = None) -> str:
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.APP_URL}/settings",
        idempotency_key=idempotency_key,
    )
    return session.url
