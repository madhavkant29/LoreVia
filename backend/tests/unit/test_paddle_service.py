import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from app.services import paddle_service


def _sign_payload(payload: dict, timestamp: int, secret: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:{raw_body.decode('utf-8')}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return raw_body, f"ts={timestamp};h1={digest}"


def test_verify_webhook_signature_accepts_valid_recent_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    assert paddle_service.verify_webhook_signature(raw_body, signature) is True


def test_verify_webhook_signature_rejects_stale_timestamp(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 301)

    assert paddle_service.verify_webhook_signature(raw_body, signature) is False


def test_verify_webhook_signature_rejects_invalid_timestamp(monkeypatch):
    secret = "pdl_secret_test"

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)

    assert paddle_service.verify_webhook_signature(b"{}", "ts=not-a-number;h1=abc123") is False


def test_verify_webhook_signature_rejects_mismatched_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, _signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False)
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp)

    assert paddle_service.verify_webhook_signature(raw_body, "ts=1700000000;h1=deadbeef") is False


@pytest.mark.asyncio
async def test_create_checkout_url_uses_recommended_checkout_page_when_override_missing(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"id": "txn_123", "checkout": {"url": "https://getlorevia.com/checkout?_ptxn=txn_123"}}}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient())
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID", "pri_author_monthly", raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_DEFAULT_CHECKOUT_URL", None, raising=False)
    monkeypatch.setattr("app.services.paddle_service.settings.APP_URL", "https://getlorevia.com", raising=False)
    async def fake_get_or_create_customer(email, existing_customer_id=None):
        return "ctm_123"

    monkeypatch.setattr("app.services.paddle_service.get_or_create_customer", fake_get_or_create_customer)

    checkout_url, customer_id, transaction_id = await paddle_service.create_checkout_url(
        user_id="user_123",
        email="author@getlorevia.com",
        plan="author_monthly",
    )

    assert checkout_url == "https://getlorevia.com/checkout?_ptxn=txn_123"
    assert customer_id == "ctm_123"
    assert transaction_id == "txn_123"
    assert captured["url"] == "https://api.paddle.com/transactions"
    assert captured["json"]["checkout"]["url"] == "https://getlorevia.com/checkout"


@pytest.mark.asyncio
async def test_get_transaction_summary_returns_invoice_details(monkeypatch):
    requests: list[str] = []

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            requests.append(url)
            if url.endswith("/invoice"):
                return FakeResponse({"data": {"url": "https://files.paddle.com/invoice.pdf"}})
            return FakeResponse(
                {
                    "data": {
                        "id": "txn_123",
                        "status": "completed",
                        "currency_code": "USD",
                        "invoice_number": "INV-123",
                        "subscription_id": "sub_123",
                        "custom_data": {"plan": "author_monthly"},
                        "details": {"totals": {"total": 2900}},
                        "customer": {"email": "author@getlorevia.com"},
                        "billed_at": "2026-05-24T12:00:00Z",
                    }
                }
            )

    monkeypatch.setattr("app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient())
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False)

    summary = await paddle_service.get_transaction_summary("txn_123")

    assert summary.transaction_id == "txn_123"
    assert summary.plan == "author_monthly"
    assert summary.total == "USD 29.00"
    assert summary.invoice_number == "INV-123"
    assert summary.invoice_pdf_url == "https://files.paddle.com/invoice.pdf"
    assert summary.customer_email == "author@getlorevia.com"
    assert summary.charge_at is not None
    assert requests == [
        "https://api.paddle.com/transactions/txn_123",
        "https://api.paddle.com/transactions/txn_123/invoice",
    ]


@pytest.mark.asyncio
async def test_get_transaction_summary_derives_annual_interval_from_billing_cycle_when_plan_is_missing(monkeypatch):
    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            if url.endswith("/invoice"):
                return FakeResponse({"data": {"url": "https://files.paddle.com/invoice.pdf"}})
            return FakeResponse(
                {
                    "data": {
                        "id": "txn_annual_123",
                        "status": "completed",
                        "currency_code": "USD",
                        "invoice_number": "INV-ANNUAL-123",
                        "subscription_id": "sub_annual_123",
                        "custom_data": {},
                        "items": [
                            {
                                "price": {
                                    "name": "Author annual",
                                    "billing_cycle": {"interval": "year"},
                                }
                            }
                        ],
                        "details": {"totals": {"total": 24900}},
                        "customer": {"email": "author@getlorevia.com"},
                        "billed_at": "2026-05-24T12:00:00Z",
                    }
                }
            )

    monkeypatch.setattr("app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient())
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False)

    summary = await paddle_service.get_transaction_summary("txn_annual_123")

    assert summary.billing_interval == "annual"


@pytest.mark.asyncio
async def test_create_refund_adjustment_posts_full_refund_request(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"id": "adj_123", "status": "pending_approval"}}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient())
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False)

    payload = await paddle_service.create_refund_adjustment("txn_123", "Accidental monthly renewal")

    assert payload == {"id": "adj_123", "status": "pending_approval"}
    assert captured["url"] == "https://api.paddle.com/adjustments"
    assert captured["json"] == {
        "action": "refund",
        "transaction_id": "txn_123",
        "type": "full",
        "reason": "Accidental monthly renewal",
    }


@pytest.mark.asyncio
async def test_cancel_subscription_immediately_posts_immediate_effective_date(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"id": "sub_123", "status": "canceled"}}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient())
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False)

    payload = await paddle_service.cancel_subscription_immediately("sub_123")

    assert payload == {"id": "sub_123", "status": "canceled"}
    assert captured["url"] == "https://api.paddle.com/subscriptions/sub_123/cancel"
    assert captured["json"] == {"effective_from": "immediately"}


@pytest.mark.asyncio
async def test_get_or_create_customer_reuses_existing_customer_on_duplicate_email(monkeypatch):
    requests: list[tuple[str, dict | None]] = []

    class FakeResponse:
        def __init__(self, *, status_code=200, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise paddle_service.httpx.HTTPStatusError(
                    "duplicate customer",
                    request=SimpleNamespace(),
                    response=self,
                )

        def json(self):
            return self._payload

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            requests.append((url, json))
            return FakeResponse(
                status_code=409,
                payload={
                    "error": {
                        "code": "customer_already_exists",
                        "detail": "customer email conflicts with customer of id ctm_01ghbk4xjn4qdsmstcwzgcgg35",
                    }
                },
            )

        async def get(self, url, headers=None, params=None):
            requests.append((url, params))
            raise AssertionError("email lookup should not run when conflict payload already includes the customer id")

    monkeypatch.setattr("app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient())
    monkeypatch.setattr("app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False)

    customer_id = await paddle_service.get_or_create_customer("author@getlorevia.com")

    assert customer_id == "ctm_01ghbk4xjn4qdsmstcwzgcgg35"
    assert requests == [
        ("https://api.paddle.com/customers", {"email": "author@getlorevia.com"}),
    ]
