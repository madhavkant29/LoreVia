import hashlib
import hmac
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.utils.billing_utils import (
    PLAN_INTERVALS,
    PLAN_PRICES_USD,
    any_paddle_plan_is_configured,
    normalize_plan_code,
    paddle_plan_is_configured,
    price_id_for_plan,
    recommended_paddle_default_checkout_url,
)

PADDLE_API_BASE = "https://api.paddle.com"
_PADDLE_CUSTOMER_ID_RE = re.compile(r"\b(ctm_[a-z\d]+)\b", re.IGNORECASE)
logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class PaddlePriceQuote:
    plan: str
    price_id: str
    amount_minor: str
    currency_code: str
    formatted_total: str
    country_code: str | None


@dataclass(frozen=True)
class PaddleTransactionState:
    status: str
    total_minor: str
    currency_code: str
    transaction_id: str = ""
    customer_id: str = ""
    price_ids: tuple[str, ...] = ()
    quantities: tuple[int, ...] = ()
    custom_user_id: str = ""
    custom_plan: str = ""
    custom_checkout_intent_id: str = ""
    collection_mode: str = ""
    discount_id: str = ""
    checkout_url: str = ""


class PaddlePriceConfigurationError(RuntimeError):
    pass


class PaddlePriceChangedError(RuntimeError):
    pass


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


def _extract_existing_customer_id(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    detail = str(((payload.get("error") or {}).get("detail")) or "").strip()
    match = _PADDLE_CUSTOMER_ID_RE.search(detail)
    return match.group(1) if match else None


async def _lookup_customer_id_by_email(client: httpx.AsyncClient, email: str) -> str | None:
    response = await client.get(
        f"{PADDLE_API_BASE}/customers",
        headers=_headers(),
        params={"email": email},
    )
    response.raise_for_status()
    data = response.json().get("data") or []
    if not data:
        return None
    customer_id = (data[0] or {}).get("id")
    return str(customer_id).strip() or None


async def get_or_create_customer(email: str, existing_customer_id: str | None = None) -> str:
    if existing_customer_id:
        return existing_customer_id

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{PADDLE_API_BASE}/customers",
            headers=_headers(),
            json={"email": email},
        )
        if response.status_code == 409:
            customer_id = _extract_existing_customer_id(response)
            if customer_id:
                return customer_id
            customer_id = await _lookup_customer_id_by_email(client, email)
            if customer_id:
                return customer_id
        response.raise_for_status()
        return response.json()["data"]["id"]


async def create_checkout_url(
    user_id: str,
    email: str,
    plan: str,
    existing_customer_id: str | None = None,
    *,
    checkout_intent_id: str,
    expected_total_minor: str,
    currency_code: str,
) -> tuple[str, str, str]:
    normalized_plan = normalize_plan_code(plan)
    if not paddle_plan_is_configured(normalized_plan):
        raise RuntimeError(f"Paddle is not configured for plan: {normalized_plan}")

    customer_id = await get_or_create_customer(email, existing_customer_id)
    payload: dict[str, Any] = {
        "items": [{"price_id": price_id_for_plan(normalized_plan), "quantity": 1}],
        "customer_id": customer_id,
        "collection_mode": "automatic",
        "currency_code": currency_code,
        "custom_data": {
            "user_id": user_id,
            "plan": normalized_plan,
            "checkout_intent_id": checkout_intent_id,
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
        state = _transaction_state_from_data(data)
        try:
            _validate_created_transaction(
                state,
                user_id=user_id,
                plan=normalized_plan,
                checkout_intent_id=checkout_intent_id,
                price_id=price_id_for_plan(normalized_plan),
                customer_id=customer_id,
                expected_total_minor=str(expected_total_minor),
                currency_code=currency_code,
            )
        except PaddlePriceChangedError:
            try:
                cancel_response = await client.patch(
                    f"{PADDLE_API_BASE}/transactions/{transaction_id}",
                    headers=_headers(),
                    json={"status": "canceled"},
                )
                cancel_response.raise_for_status()
            except httpx.HTTPError:
                logger.exception("Unable to cancel invalid Paddle transaction %s", transaction_id)
            raise
        return checkout_url, customer_id, transaction_id


async def get_paddle_price_quote(
    plan: str,
    *,
    customer_ip_address: str | None = None,
    existing_customer_id: str | None = None,
) -> PaddlePriceQuote:
    normalized_plan = normalize_plan_code(plan)
    if not paddle_plan_is_configured(normalized_plan):
        raise RuntimeError(f"Paddle is not configured for plan: {normalized_plan}")

    price_id = price_id_for_plan(normalized_plan)
    async with httpx.AsyncClient(timeout=20.0) as client:
        price_response = await client.get(
            f"{PADDLE_API_BASE}/prices/{price_id}",
            headers=_headers(),
        )
        price_response.raise_for_status()
        price = price_response.json()["data"]
        amount_minor, currency_code = _validate_checkout_price(normalized_plan, price)

        preview_payload: dict[str, Any] = {
            "items": [{"price_id": price_id, "quantity": 1}],
            "currency_code": currency_code,
        }
        if existing_customer_id:
            preview_payload["customer_id"] = existing_customer_id
        elif customer_ip_address:
            preview_payload["customer_ip_address"] = customer_ip_address

        preview_response = await client.post(
            f"{PADDLE_API_BASE}/pricing-preview",
            headers=_headers(),
            json=preview_payload,
        )
        preview_response.raise_for_status()
        preview = preview_response.json()["data"]

    line_items = (preview.get("details") or {}).get("line_items") or []
    line_item = next(
        (item for item in line_items if str((item.get("price") or {}).get("id") or "") == price_id),
        None,
    )
    if line_item is None:
        raise RuntimeError("Paddle pricing preview did not return the selected price")

    preview_price = line_item.get("price") or price
    _validate_checkout_price(normalized_plan, preview_price)
    total_minor = str(((line_item.get("totals") or {}).get("total")) or "")
    formatted_total = str(((line_item.get("formatted_totals") or {}).get("total")) or "").strip()
    preview_currency = str(preview.get("currency_code") or currency_code).upper()
    if not total_minor or not formatted_total or not preview_currency:
        raise RuntimeError("Paddle pricing preview did not return a complete total")
    if total_minor != amount_minor or preview_currency != currency_code:
        raise PaddlePriceConfigurationError(
            "Paddle price localization or tax settings changed the checkout total. "
            "Use a fixed, tax-inclusive price with no regional overrides."
        )

    country_code = str((preview.get("address") or {}).get("country_code") or "").strip()
    return PaddlePriceQuote(
        plan=normalized_plan,
        price_id=price_id,
        amount_minor=total_minor,
        currency_code=preview_currency,
        formatted_total=f"{formatted_total} {preview_currency}",
        country_code=country_code or None,
    )


async def get_paddle_transaction_state(
    transaction_id: str,
) -> PaddleTransactionState | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{PADDLE_API_BASE}/transactions/{transaction_id}",
            headers=_headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json().get("data") or {}
        return _transaction_state_from_data(data)


async def get_subscription(subscription_id: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{PADDLE_API_BASE}/subscriptions/{subscription_id}",
            headers=_headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json().get("data") or {}
        return data or None


async def find_paddle_transaction_by_checkout_intent(
    checkout_intent_id: str,
    *,
    customer_id: str | None,
    created_after: datetime,
) -> PaddleTransactionState | None:
    """Find a checkout after an ambiguous provider response or process crash.

    Paddle does not offer a custom-data filter for transaction listings. Limit
    the scan to the intent's creation window (and its customer when known), then
    require an exact, unguessable local intent ID match before returning it.
    """

    created_after_utc = (
        created_after.replace(tzinfo=UTC)
        if created_after.tzinfo is None
        else created_after.astimezone(UTC)
    )
    params: dict[str, str | int] = {
        "origin": "api",
        "created_at[GTE]": created_after_utc.isoformat(),
        "order_by": "created_at[DESC]",
        "per_page": 30,
    }
    if customer_id:
        params["customer_id"] = customer_id
    after: str | None = None
    seen_cursors: set[str] = set()

    async with httpx.AsyncClient(timeout=20.0) as client:
        while True:
            request_params = dict(params)
            if after:
                request_params["after"] = after
            response = await client.get(
                f"{PADDLE_API_BASE}/transactions",
                headers=_headers(),
                params=request_params,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") or []
            for transaction in data:
                state = _transaction_state_from_data(transaction or {})
                if state.custom_checkout_intent_id == checkout_intent_id:
                    return state

            pagination = (payload.get("meta") or {}).get("pagination") or {}
            if not pagination.get("has_more") or not data:
                return None
            after = str((data[-1] or {}).get("id") or "").strip()
            if not after or after in seen_cursors:
                return None
            seen_cursors.add(after)


async def cancel_paddle_transaction(transaction_id: str) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.patch(
            f"{PADDLE_API_BASE}/transactions/{transaction_id}",
            headers=_headers(),
            json={"status": "canceled"},
        )
        response.raise_for_status()
        return str((response.json().get("data") or {}).get("status") or "canceled").lower()


def _validate_checkout_price(plan: str, price: dict[str, Any]) -> tuple[str, str]:
    if str(price.get("status") or "").lower() != "active":
        raise PaddlePriceConfigurationError("The configured Paddle price is not active.")
    if price.get("trial_period") is not None:
        raise PaddlePriceConfigurationError(
            "The configured Paddle price has its own trial. LoreVia paid prices must not include a Paddle trial."
        )
    if str(price.get("tax_mode") or "").lower() != "internal":
        raise PaddlePriceConfigurationError(
            "The configured Paddle price must be explicitly tax-inclusive (tax mode: internal)."
        )
    if price.get("unit_price_overrides"):
        raise PaddlePriceConfigurationError(
            "The configured Paddle price must not use regional price overrides."
        )

    billing_cycle = price.get("billing_cycle") or {}
    expected_interval = "month" if PLAN_INTERVALS[plan] == "monthly" else "year"
    if (
        str(billing_cycle.get("interval") or "").lower() != expected_interval
        or int(billing_cycle.get("frequency") or 0) != 1
    ):
        raise PaddlePriceConfigurationError(
            f"The configured Paddle price does not match LoreVia's {PLAN_INTERVALS[plan]} billing interval."
        )

    unit_price = price.get("unit_price") or {}
    amount_minor = str(unit_price.get("amount") or "")
    currency_code = str(unit_price.get("currency_code") or "").upper()
    if not amount_minor.isdigit() or not currency_code:
        raise PaddlePriceConfigurationError(
            "The configured Paddle price is missing a valid unit price."
        )
    expected_amount_minor = str(PLAN_PRICES_USD[plan] * 100)
    if currency_code != "USD" or amount_minor != expected_amount_minor:
        raise PaddlePriceConfigurationError(
            "The configured Paddle price does not match LoreVia's advertised USD catalog amount."
        )
    return amount_minor, currency_code


def _transaction_state_from_data(data: dict[str, Any]) -> PaddleTransactionState:
    items = data.get("items") or []
    price_ids: list[str] = []
    quantities: list[int] = []
    for item in items:
        price = item.get("price") or {}
        price_id = str(item.get("price_id") or price.get("id") or "").strip()
        if price_id:
            price_ids.append(price_id)
        try:
            quantities.append(int(item.get("quantity")))
        except (TypeError, ValueError):
            quantities.append(0)

    custom_data = data.get("custom_data") or {}
    return PaddleTransactionState(
        transaction_id=str(data.get("id") or "").strip(),
        status=str(data.get("status") or "").strip().lower(),
        total_minor=str(((data.get("details") or {}).get("totals") or {}).get("total") or ""),
        currency_code=str(data.get("currency_code") or "").strip().upper(),
        customer_id=str(data.get("customer_id") or "").strip(),
        price_ids=tuple(price_ids),
        quantities=tuple(quantities),
        custom_user_id=str(custom_data.get("user_id") or "").strip(),
        custom_plan=normalize_plan_code(custom_data.get("plan")),
        custom_checkout_intent_id=str(custom_data.get("checkout_intent_id") or "").strip(),
        collection_mode=str(data.get("collection_mode") or "").strip().lower(),
        discount_id=str(data.get("discount_id") or "").strip(),
        checkout_url=str((data.get("checkout") or {}).get("url") or "").strip(),
    )


def _validate_created_transaction(
    state: PaddleTransactionState,
    *,
    user_id: str,
    plan: str,
    checkout_intent_id: str,
    price_id: str,
    customer_id: str,
    expected_total_minor: str,
    currency_code: str,
) -> None:
    valid = (
        state.status in {"draft", "ready"}
        and state.total_minor == expected_total_minor
        and state.currency_code == currency_code.upper()
        and state.customer_id == customer_id
        and state.price_ids == (price_id,)
        and state.quantities == (1,)
        and state.custom_user_id == user_id
        and state.custom_plan == plan
        and state.custom_checkout_intent_id == checkout_intent_id
        and state.collection_mode == "automatic"
        and not state.discount_id
        and bool(state.checkout_url)
    )
    if not valid:
        raise PaddlePriceChangedError(
            "Paddle returned checkout details that differ from the confirmed payment. "
            "Review updated payment details before continuing."
        )


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
    display_name = (
        "Architect"
        if plan.startswith("architect_")
        else "Author"
        if plan.startswith("author_")
        else plan.replace("_", " ").title()
    )

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
        customer_email=(
            (data.get("customer") or {}).get("email")
            if isinstance(data.get("customer"), dict)
            else None
        ),
        customer_id=(
            (data.get("customer") or {}).get("id")
            if isinstance(data.get("customer"), dict)
            else None
        )
        or data.get("customer_id"),
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


async def cancel_subscription_at_period_end(subscription_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{PADDLE_API_BASE}/subscriptions/{subscription_id}/cancel",
            headers=_headers(),
            json={"effective_from": "next_billing_period"},
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

    tolerance_seconds = settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS
    if tolerance_seconds <= 0:
        return False
    if abs(int(time.time()) - timestamp_value) > tolerance_seconds:
        return False

    try:
        decoded_body = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        return False
    signed_payload = f"{timestamp}:{decoded_body}"
    computed = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return any(hmac.compare_digest(computed, candidate) for candidate in signatures)
