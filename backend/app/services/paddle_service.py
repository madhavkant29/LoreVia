import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.utils.billing_utils import (
    any_paddle_plan_is_configured,
    normalize_plan_code,
    paddle_plan_is_configured,
    price_id_for_plan,
    recommended_paddle_default_checkout_url,
)

PADDLE_API_BASE = "https://api.paddle.com"


@dataclass(frozen=True)
class PaddleTransactionSummary:
    transaction_id: str
    status: str
    plan: str
    billing_interval: str
    display_name: str
    currency_code: str | None
    total: str | None
    invoice_number: str | None
    invoice_pdf_url: str | None
    subscription_id: str | None
    customer_email: str | None
    customer_id: str | None
    charge_at: datetime | None


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
) -> tuple[str, str, str]:
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
    payload["checkout"] = {
        # Keep all generated checkout payment links pinned to LoreVia's public
        # Paddle-enabled checkout page, while the Paddle dashboard default link
        # remains the required fallback for emails and payment method updates.
        "url": settings.PADDLE_DEFAULT_CHECKOUT_URL or recommended_paddle_default_checkout_url(),
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{PADDLE_API_BASE}/transactions",
            headers=_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()["data"]
        transaction_id = str(data.get("id") or "")
        checkout_url = (data.get("checkout") or {}).get("url")
        if not checkout_url or not transaction_id:
            raise RuntimeError("Paddle did not return a checkout URL")
        return checkout_url, customer_id, transaction_id


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


def _parse_paddle_datetime(value: object | None) -> datetime | None:
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    normalized = candidate.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_transaction_total(data: dict[str, Any]) -> str | None:
    totals = data.get("details", {}).get("totals") or {}
    total = totals.get("total")
    currency_code = data.get("currency_code")
    if total is None or not currency_code:
        return None
    try:
        amount = float(total) / 100
    except (TypeError, ValueError):
        return None
    return f"{currency_code} {amount:,.2f}"


async def _get_invoice_pdf_url(transaction_id: str) -> str | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{PADDLE_API_BASE}/transactions/{transaction_id}/invoice",
            headers=_headers(),
            params={"disposition": "inline"},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return (response.json().get("data") or {}).get("url")


async def get_transaction_summary(transaction_id: str) -> PaddleTransactionSummary:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{PADDLE_API_BASE}/transactions/{transaction_id}",
            headers=_headers(),
            params={"include": "customer"},
        )
        response.raise_for_status()
        data = response.json()["data"]

    invoice_pdf_url = None
    if str(data.get("status") or "").lower() == "completed":
        try:
            invoice_pdf_url = await _get_invoice_pdf_url(transaction_id)
        except httpx.HTTPStatusError:
            invoice_pdf_url = None

    plan = normalize_plan_code((data.get("custom_data") or {}).get("plan"))
    interval = _transaction_billing_interval(data, plan=plan)
    display_name = "Architect" if plan.startswith("architect_") else "Author" if plan.startswith("author_") else plan.replace("_", " ").title()

    return PaddleTransactionSummary(
        transaction_id=str(data.get("id") or transaction_id),
        status=str(data.get("status") or ""),
        plan=plan,
        billing_interval=interval,
        display_name=display_name,
        currency_code=data.get("currency_code"),
        total=_format_transaction_total(data),
        invoice_number=data.get("invoice_number"),
        invoice_pdf_url=invoice_pdf_url,
        subscription_id=data.get("subscription_id"),
        customer_email=((data.get("customer") or {}).get("email") if isinstance(data.get("customer"), dict) else None),
        customer_id=((data.get("customer") or {}).get("id") if isinstance(data.get("customer"), dict) else None) or data.get("customer_id"),
        charge_at=(
            _parse_paddle_datetime(data.get("billed_at"))
            or _parse_paddle_datetime(data.get("completed_at"))
            or _parse_paddle_datetime(data.get("created_at"))
        ),
    )


def _transaction_billing_interval(data: dict[str, Any], *, plan: str) -> str:
    items = data.get("items") or []
    for item in items:
        billing_cycle = (item.get("price") or {}).get("billing_cycle") or {}
        interval = str(billing_cycle.get("interval") or "").strip().lower()
        if interval == "month":
            return "monthly"
        if interval == "year":
            return "annual"

    if plan.endswith("_monthly"):
        return "monthly"
    if plan.endswith("_annual"):
        return "annual"
    return ""


async def create_refund_adjustment(transaction_id: str, reason: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{PADDLE_API_BASE}/adjustments",
            headers=_headers(),
            json={
                "action": "refund",
                "transaction_id": transaction_id,
                "type": "full",
                "reason": reason[:250],
            },
        )
        response.raise_for_status()
        return response.json()["data"]


async def cancel_subscription_immediately(subscription_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{PADDLE_API_BASE}/subscriptions/{subscription_id}/cancel",
            headers=_headers(),
            json={"effective_from": "immediately"},
        )
        response.raise_for_status()
        return response.json()["data"]


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
