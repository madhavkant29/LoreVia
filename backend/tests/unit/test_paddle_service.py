import hashlib
import hmac
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.services import paddle_service


def _sign_payload(payload: dict, timestamp: int, secret: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:{raw_body.decode('utf-8')}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return raw_body, f"ts={timestamp};h1={digest}"


@pytest.mark.asyncio
async def test_find_checkout_transaction_pages_until_exact_intent_match(monkeypatch):
    requested_params: list[dict] = []
    responses = [
        {
            "data": [
                {
                    "id": "txn_newer",
                    "custom_data": {"checkout_intent_id": "another-intent"},
                }
            ],
            "meta": {"pagination": {"has_more": True}},
        },
        {
            "data": [
                {
                    "id": "txn_recovered",
                    "status": "draft",
                    "customer_id": "ctm_123",
                    "custom_data": {"checkout_intent_id": "intent_123"},
                }
            ],
            "meta": {"pagination": {"has_more": False}},
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url, *, headers=None, params=None):
            requested_params.append(dict(params or {}))
            return FakeResponse(responses.pop(0))

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient",
        lambda timeout=20.0: FakeAsyncClient(),
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY",
        "pdl_test_key",
        raising=False,
    )

    state = await paddle_service.find_paddle_transaction_by_checkout_intent(
        "intent_123",
        customer_id="ctm_123",
        created_after=datetime(2026, 9, 6, 10, 0, tzinfo=UTC),
    )

    assert state is not None
    assert state.transaction_id == "txn_recovered"
    assert requested_params[0]["customer_id"] == "ctm_123"
    assert requested_params[0]["created_at[GTE]"] == "2026-09-06T10:00:00+00:00"
    assert requested_params[1]["after"] == "txn_newer"


def test_verify_webhook_signature_accepts_valid_recent_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 60)

    assert paddle_service.verify_webhook_signature(raw_body, signature) is True


def test_verify_webhook_signature_rejects_stale_timestamp(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp + 301)

    assert paddle_service.verify_webhook_signature(raw_body, signature) is False


def test_verify_webhook_signature_rejects_invalid_timestamp(monkeypatch):
    secret = "pdl_secret_test"

    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )

    assert paddle_service.verify_webhook_signature(b"{}", "ts=not-a-number;h1=abc123") is False


def test_verify_webhook_signature_rejects_mismatched_signature(monkeypatch):
    secret = "pdl_secret_test"
    timestamp = 1_700_000_000
    payload = {"event_id": "evt_123", "event_type": "subscription.updated", "data": {}}
    raw_body, _signature = _sign_payload(payload, timestamp, secret)

    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_SECRET", secret, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300, raising=False
    )
    monkeypatch.setattr("app.services.paddle_service.time.time", lambda: timestamp)

    assert paddle_service.verify_webhook_signature(raw_body, "ts=1700000000;h1=deadbeef") is False


@pytest.mark.asyncio
async def test_cancel_subscription_at_period_end_uses_next_billing_period(monkeypatch):
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
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient()
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )

    result = await paddle_service.cancel_subscription_at_period_end("sub_123")

    assert result["id"] == "sub_123"
    assert captured["url"] == "https://api.paddle.com/subscriptions/sub_123/cancel"
    assert captured["json"] == {"effective_from": "next_billing_period"}


@pytest.mark.asyncio
async def test_create_checkout_url_uses_recommended_checkout_page_when_override_missing(
    monkeypatch,
):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "id": "txn_123",
                    "status": "draft",
                    "customer_id": "ctm_123",
                    "currency_code": "USD",
                    "collection_mode": "automatic",
                    "discount_id": None,
                    "custom_data": {
                        "user_id": "user_123",
                        "plan": "author_monthly",
                        "checkout_intent_id": "intent_123",
                    },
                    "items": [
                        {
                            "price": {"id": "pri_author_monthly"},
                            "quantity": 1,
                        }
                    ],
                    "checkout": {"url": "https://getlorevia.com/checkout?_ptxn=txn_123"},
                    "details": {"totals": {"total": "1900"}},
                }
            }

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

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient()
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID",
        "pri_author_monthly",
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_DEFAULT_CHECKOUT_URL", None, raising=False
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.APP_URL", "https://getlorevia.com", raising=False
    )

    async def fake_get_or_create_customer(email, existing_customer_id=None):
        return "ctm_123"

    monkeypatch.setattr(
        "app.services.paddle_service.get_or_create_customer", fake_get_or_create_customer
    )

    checkout_url, customer_id, transaction_id = await paddle_service.create_checkout_url(
        user_id="user_123",
        email="author@getlorevia.com",
        plan="author_monthly",
        checkout_intent_id="intent_123",
        expected_total_minor="1900",
        currency_code="USD",
    )

    assert checkout_url == "https://getlorevia.com/checkout?_ptxn=txn_123"
    assert customer_id == "ctm_123"
    assert transaction_id == "txn_123"
    assert captured["url"] == "https://api.paddle.com/transactions"
    assert captured["json"]["checkout"]["url"] == "https://getlorevia.com/checkout"
    assert captured["json"]["currency_code"] == "USD"
    assert captured["json"]["custom_data"]["checkout_intent_id"] == "intent_123"


@pytest.mark.asyncio
async def test_create_checkout_url_cancels_transaction_when_total_changed(monkeypatch):
    canceled: list[tuple[str, dict]] = []

    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            return FakeResponse(
                {
                    "data": {
                        "id": "txn_changed",
                        "status": "draft",
                        "customer_id": "ctm_123",
                        "currency_code": "USD",
                        "collection_mode": "automatic",
                        "discount_id": None,
                        "custom_data": {
                            "user_id": "user_123",
                            "plan": "author_monthly",
                            "checkout_intent_id": "intent_123",
                        },
                        "items": [
                            {
                                "price": {"id": "pri_author_monthly"},
                                "quantity": 1,
                            }
                        ],
                        "checkout": {"url": "https://getlorevia.com/checkout?_ptxn=txn_changed"},
                        "details": {"totals": {"total": "2000"}},
                    }
                }
            )

        async def patch(self, url, headers=None, json=None):
            canceled.append((url, json))
            return FakeResponse({"data": {"id": "txn_changed", "status": "canceled"}})

    async def fake_get_or_create_customer(email, existing_customer_id=None):
        return "ctm_123"

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient",
        lambda timeout=20.0: FakeAsyncClient(),
    )
    monkeypatch.setattr(
        "app.services.paddle_service.get_or_create_customer",
        fake_get_or_create_customer,
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY",
        "pdl_test_key",
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID",
        "pri_author_monthly",
        raising=False,
    )

    with pytest.raises(paddle_service.PaddlePriceChangedError, match="differ from"):
        await paddle_service.create_checkout_url(
            user_id="user_123",
            email="author@getlorevia.com",
            plan="author_monthly",
            checkout_intent_id="intent_123",
            expected_total_minor="1900",
            currency_code="USD",
        )

    assert canceled == [
        (
            "https://api.paddle.com/transactions/txn_changed",
            {"status": "canceled"},
        )
    ]


@pytest.mark.asyncio
async def test_create_checkout_url_cancels_transaction_when_identity_does_not_match(
    monkeypatch,
):
    canceled: list[str] = []

    class FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            return FakeResponse(
                {
                    "data": {
                        "id": "txn_wrong_owner",
                        "status": "draft",
                        "customer_id": "ctm_123",
                        "currency_code": "USD",
                        "collection_mode": "automatic",
                        "discount_id": None,
                        "custom_data": {
                            "user_id": "another_user",
                            "plan": "author_monthly",
                            "checkout_intent_id": "intent_123",
                        },
                        "items": [
                            {
                                "price": {"id": "pri_author_monthly"},
                                "quantity": 1,
                            }
                        ],
                        "checkout": {
                            "url": "https://getlorevia.com/checkout?_ptxn=txn_wrong_owner"
                        },
                        "details": {"totals": {"total": "1900"}},
                    }
                }
            )

        async def patch(self, url, headers=None, json=None):
            canceled.append(url)
            return FakeResponse({"data": {"status": "canceled"}})

    async def fake_get_or_create_customer(email, existing_customer_id=None):
        return "ctm_123"

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient",
        lambda timeout=20.0: FakeAsyncClient(),
    )
    monkeypatch.setattr(
        "app.services.paddle_service.get_or_create_customer",
        fake_get_or_create_customer,
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY",
        "pdl_test_key",
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID",
        "pri_author_monthly",
        raising=False,
    )

    with pytest.raises(paddle_service.PaddlePriceChangedError, match="differ from"):
        await paddle_service.create_checkout_url(
            user_id="user_123",
            email="author@getlorevia.com",
            plan="author_monthly",
            checkout_intent_id="intent_123",
            expected_total_minor="1900",
            currency_code="USD",
        )

    assert canceled == ["https://api.paddle.com/transactions/txn_wrong_owner"]


@pytest.mark.asyncio
async def test_get_paddle_price_quote_uses_tax_inclusive_provider_total(monkeypatch):
    requests: list[tuple[str, dict | None]] = []
    price = {
        "id": "pri_author_monthly",
        "status": "active",
        "trial_period": None,
        "tax_mode": "internal",
        "unit_price_overrides": [],
        "billing_cycle": {"interval": "month", "frequency": 1},
        "unit_price": {"amount": "1900", "currency_code": "USD"},
    }

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            requests.append((url, None))
            return FakeResponse({"data": price})

        async def post(self, url, headers=None, json=None):
            requests.append((url, json))
            return FakeResponse(
                {
                    "data": {
                        "currency_code": "USD",
                        "address": {"country_code": "US"},
                        "details": {
                            "line_items": [
                                {
                                    "price": price,
                                    "totals": {"total": "1900"},
                                    "formatted_totals": {"total": "$19.00"},
                                }
                            ]
                        },
                    }
                }
            )

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient",
        lambda timeout=20.0: FakeAsyncClient(),
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY",
        "pdl_test_key",
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID",
        "pri_author_monthly",
        raising=False,
    )

    quote = await paddle_service.get_paddle_price_quote(
        "author_monthly",
        customer_ip_address="203.0.113.10",
    )

    assert quote.amount_minor == "1900"
    assert quote.currency_code == "USD"
    assert quote.formatted_total == "$19.00 USD"
    assert quote.country_code == "US"
    assert requests[1][1] == {
        "items": [{"price_id": "pri_author_monthly", "quantity": 1}],
        "currency_code": "USD",
        "customer_ip_address": "203.0.113.10",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("price_change", "expected_message"),
    [
        ({"trial_period": {"interval": "day", "frequency": 10}}, "own trial"),
        ({"tax_mode": "external"}, "tax-inclusive"),
        ({"unit_price_overrides": [{"country_codes": ["IN"]}]}, "regional"),
        ({"unit_price": {"amount": "2000", "currency_code": "USD"}}, "advertised USD"),
        ({"unit_price": {"amount": "1900", "currency_code": "EUR"}}, "advertised USD"),
    ],
)
async def test_get_paddle_price_quote_rejects_unsafe_price_configuration(
    monkeypatch,
    price_change,
    expected_message,
):
    price = {
        "id": "pri_author_monthly",
        "status": "active",
        "trial_period": None,
        "tax_mode": "internal",
        "unit_price_overrides": [],
        "billing_cycle": {"interval": "month", "frequency": 1},
        "unit_price": {"amount": "1900", "currency_code": "USD"},
        **price_change,
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": price}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient",
        lambda timeout=20.0: FakeAsyncClient(),
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY",
        "pdl_test_key",
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID",
        "pri_author_monthly",
        raising=False,
    )

    with pytest.raises(
        paddle_service.PaddlePriceConfigurationError,
        match=expected_message,
    ):
        await paddle_service.get_paddle_price_quote("author_monthly")


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
                        "details": {"totals": {"total": 1900}},
                        "customer": {"email": "author@getlorevia.com"},
                        "billed_at": "2026-05-24T12:00:00Z",
                    }
                }
            )

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient()
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )

    summary = await paddle_service.get_transaction_summary("txn_123")

    assert summary.transaction_id == "txn_123"
    assert summary.plan == "author_monthly"
    assert summary.total == "USD 19.00"
    assert summary.invoice_number == "INV-123"
    assert summary.invoice_pdf_url == "https://files.paddle.com/invoice.pdf"
    assert summary.customer_email == "author@getlorevia.com"
    assert summary.charge_at is not None
    assert requests == [
        "https://api.paddle.com/transactions/txn_123",
        "https://api.paddle.com/transactions/txn_123/invoice",
    ]


@pytest.mark.asyncio
async def test_get_transaction_summary_derives_annual_interval_from_billing_cycle_when_plan_is_missing(
    monkeypatch,
):
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

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient()
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )

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

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient()
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )

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

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient()
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )

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
            raise AssertionError(
                "email lookup should not run when conflict payload already includes the customer id"
            )

    monkeypatch.setattr(
        "app.services.paddle_service.httpx.AsyncClient", lambda timeout=20.0: FakeAsyncClient()
    )
    monkeypatch.setattr(
        "app.services.paddle_service.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )

    customer_id = await paddle_service.get_or_create_customer("author@getlorevia.com")

    assert customer_id == "ctm_01ghbk4xjn4qdsmstcwzgcgg35"
    assert requests == [
        ("https://api.paddle.com/customers", {"email": "author@getlorevia.com"}),
    ]
