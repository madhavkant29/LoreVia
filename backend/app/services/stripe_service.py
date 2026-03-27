import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

PRICE_IDS = {
    "pro_monthly":    "price_pro_monthly_id",
    "pro_annual":     "price_pro_annual_id",
    "power_monthly":  "price_power_monthly_id",
}


def create_checkout_session(user_id: str, email: str, plan: str) -> str:
    session = stripe.checkout.Session.create(
        customer_email=email,
        payment_method_types=["card"],
        line_items=[{"price": PRICE_IDS[plan], "quantity": 1}],
        mode="subscription",
        success_url="https://lorevia.app/library?upgraded=true",
        cancel_url="https://lorevia.app/settings",
        metadata={"user_id": user_id, "plan": plan},
    )
    return session.url


def create_portal_session(customer_id: str) -> str:
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url="https://lorevia.app/settings",
    )
    return session.url
