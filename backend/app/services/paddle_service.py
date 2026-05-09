import hashlib
import hmac
import time
from typing import Any

import httpx

from app.core.config import settings
from app.utils.billing_utils import (
    any_paddle_plan_is_configured,
    normalize_plan_code,
    paddle_plan_is_configured,
    price_id_for_plan,
)

PADDLE_API_BASE = "https://api.paddle.com"


def paddle_is_configured() -> bool:
    return any_paddle_plan_is_configured()


def paddle_webhooks_configured() -> bool:
    return bool(settings.PADDLE_WEBHOOK_SECRET)


def _headers() -> dict[str, str]:
    if not settings.PADDLE_API_KEY:
        raise RuntimeError("Paddle API key is not configured")
    return {
        "Authorization": f"Bearer {settings.PADDLE_API_KEY}",
        "Content-Type": "application/json",
        "Paddle-Version": "1",
    }


async def get_or_create_customer(email: str, existing_customer_id: str | None = None) -> str:
    if existing_customer_id:
        return existing_customer_id

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{PADDLE_API_BASE}/customers",
            headers=_headers(),
            json={"email": email},
        )
        response.raise_for_status()
        return response.json()["data"]["id"]


async def create_checkout_url(
    user_id: str,
    email: str,
    plan: str,
    existing_customer_id: str | None = None,
) -> tuple[str, str]:
    normalized_plan = normalize_plan_code(plan)
    if not paddle_plan_is_configured(normalized_plan):
        raise RuntimeError(f"Paddle is not configured for plan: {normalized_plan}")

    customer_id = await get_or_create_customer(email, existing_customer_id)
    payload: dict[str, Any] = {
        "items": [{"price_id": price_id_for_plan(normalized_plan), "quantity": 1}],
        "customer_id": customer_id,
        "collection_mode": "automatic",
        "custom_data": {
            "user_id": user_id,
            "plan": normalized_plan,
        },
    }
    if settings.PADDLE_DEFAULT_CHECKOUT_URL:
        payload["checkout"] = {
            # Let Paddle generate the payment link against your approved/default domain.
            "url": settings.PADDLE_DEFAULT_CHECKOUT_URL,
        }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{PADDLE_API_BASE}/transactions",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()["data"]
        checkout_url = (data.get("checkout") or {}).get("url")
        if not checkout_url:
            raise RuntimeError("Paddle did not return a checkout URL")
        return checkout_url, customer_id


async def create_portal_url(customer_id: str, subscription_ids: list[str] | None = None) -> str:
    body: dict[str, Any] = {}
    if subscription_ids:
        body["subscription_ids"] = subscription_ids

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{PADDLE_API_BASE}/customers/{customer_id}/portal-sessions",
            headers=_headers(),
            json=body,
        )
        response.raise_for_status()
        data = response.json()["data"]
        return data["urls"]["general"]["overview"]


def verify_webhook_signature(raw_body: bytes, paddle_signature: str | None) -> bool:
    secret = settings.PADDLE_WEBHOOK_SECRET
    if not secret or not paddle_signature:
        return False

    timestamp: str | None = None
    signatures: list[str] = []
    for part in paddle_signature.split(";"):
        key, _, value = part.strip().partition("=")
        if key == "ts":
            timestamp = value
        elif key == "h1" and value:
            signatures.append(value)

    if not timestamp or not signatures:
        return False

    try:
        timestamp_value = int(timestamp)
    except ValueError:
        return False

    tolerance_seconds = max(settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS, 0)
    if tolerance_seconds and abs(int(time.time()) - timestamp_value) > tolerance_seconds:
        return False

    signed_payload = f"{timestamp}:{raw_body.decode('utf-8')}"
    computed = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return any(hmac.compare_digest(computed, candidate) for candidate in signatures)
