import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import create_access_token
from app.models.user import AdminPrincipal, Subscription, User
from app.services.billing_checkout_service import (
    build_checkout_disclosure,
    create_checkout_session,
)
from app.services.paddle_service import (
    PaddlePriceChangedError,
    PaddlePriceQuote,
    PaddleTransactionState,
)
from app.utils.billing_utils import create_billing_confirmation_token


def _paddle_quote(plan: str) -> PaddlePriceQuote:
    amounts = {
        "author_monthly": ("1900", "$19.00 USD"),
        "author_annual": ("19000", "$190.00 USD"),
        "architect_monthly": ("3900", "$39.00 USD"),
        "architect_annual": ("39000", "$390.00 USD"),
    }
    amount_minor, formatted_total = amounts[plan]
    return PaddlePriceQuote(
        plan=plan,
        price_id=f"pri_{plan}",
        amount_minor=amount_minor,
        currency_code="USD",
        formatted_total=formatted_total,
        country_code="US",
    )


def _mock_paddle_quote(monkeypatch) -> None:
    async def get_quote(
        plan,
        *,
        customer_ip_address=None,
        existing_customer_id=None,
    ):
        return _paddle_quote(plan)

    monkeypatch.setattr(
        "app.services.billing_checkout_service.get_paddle_price_quote",
        get_quote,
    )


def _pending_transaction_state(
    *,
    user_id: uuid.UUID,
    plan: str = "author_monthly",
    customer_id: str = "ctm_123",
    transaction_id: str = "txn_123",
    checkout_intent_id: str = "",
) -> PaddleTransactionState:
    return PaddleTransactionState(
        transaction_id=transaction_id,
        status="draft",
        total_minor=_paddle_quote(plan).amount_minor,
        currency_code="USD",
        customer_id=customer_id,
        price_ids=(f"pri_{plan}",),
        quantities=(1,),
        custom_user_id=str(user_id),
        custom_plan=plan,
        custom_checkout_intent_id=checkout_intent_id,
        collection_mode="automatic",
        discount_id="",
        checkout_url=f"https://getlorevia.com/checkout?_ptxn={transaction_id}",
    )


async def _admin_headers(client, db) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"billing-admin-{uuid.uuid4().hex[:8]}@lorevia.app",
            "username": f"billingadmin{uuid.uuid4().hex[:8]}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert response.status_code == 201
    user = await db.get(User, uuid.UUID(response.json()["id"]))
    assert user is not None
    db.add(
        AdminPrincipal(
            user_id=user.id,
            status="active",
            is_owner=False,
            scopes=["billing_admin"],
            grant_reason="Test billing admin grant.",
        )
    )
    await db.commit()
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_billing_status_requires_admin(auth_headers, client):
    response = await client.get("/api/v1/admin/billing/status", headers=auth_headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin only"}


@pytest.mark.asyncio
async def test_billing_status_reports_missing_configuration(client, db, monkeypatch):
    headers = await _admin_headers(client, db)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_API_KEY", None, raising=False)
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_WEBHOOK_SECRET", None, raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_DEFAULT_CHECKOUT_URL", None, raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID", None, raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID", None, raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID", None, raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID", None, raising=False
    )
    monkeypatch.setattr("app.utils.billing_utils.settings.RESEND_API_KEY", "", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.INTERNAL_JOB_SECRET", None, raising=False)

    response = await client.get("/api/v1/admin/billing/status", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["billing_enabled"] is False
    assert payload["payments_ready"] is False
    assert payload["paddle_api_key_present"] is False
    assert payload["webhook_secret_present"] is False
    assert payload["recommended_default_checkout_url"] == "https://getlorevia.com/checkout"
    assert payload["resend_api_key_present"] is False
    assert payload["internal_job_secret_present"] is False
    assert "PADDLE_API_KEY" in payload["missing_configuration"]
    assert "PADDLE_WEBHOOK_SECRET" in payload["missing_configuration"]
    assert "PADDLE_DEFAULT_CHECKOUT_URL" in payload["missing_configuration"]
    assert "RESEND_API_KEY" in payload["missing_configuration"]
    assert "INTERNAL_JOB_SECRET" in payload["missing_configuration"]
    assert len(payload["plans"]) == 4
    assert payload["trial_email_automation_code_ready"] is True
    assert payload["priority_processing_code_ready"] is True
    assert payload["webhook_endpoint_path"] == "/api/v1/webhooks/paddle"
    assert payload["trial_email_job_endpoint_path"] == "/api/v1/internal/jobs/send-due-trial-emails"
    assert "transaction.completed" in payload["supported_webhook_events"]
    assert "transaction.payment_failed" in payload["supported_webhook_events"]
    assert "subscription.activated" in payload["supported_webhook_events"]
    assert "subscription.resumed" in payload["supported_webhook_events"]
    assert "subscription.trialing" in payload["supported_webhook_events"]
    author_monthly = next(plan for plan in payload["plans"] if plan["code"] == "author_monthly")
    author_annual = next(plan for plan in payload["plans"] if plan["code"] == "author_annual")
    architect_monthly = next(
        plan for plan in payload["plans"] if plan["code"] == "architect_monthly"
    )
    architect_annual = next(plan for plan in payload["plans"] if plan["code"] == "architect_annual")
    assert author_monthly["display_name"] == "Author"
    assert author_monthly["billing_interval"] == "monthly"
    assert author_monthly["price_usd"] == 19
    assert author_annual["display_name"] == "Author"
    assert author_annual["billing_interval"] == "annual"
    assert author_annual["price_usd"] == 190
    assert architect_monthly["display_name"] == "Architect"
    assert architect_monthly["billing_interval"] == "monthly"
    assert architect_monthly["price_usd"] == 39
    assert architect_annual["display_name"] == "Architect"
    assert architect_annual["billing_interval"] == "annual"
    assert architect_annual["price_usd"] == 390


@pytest.mark.asyncio
async def test_billing_status_reports_fully_configured_catalog(client, db, monkeypatch):
    headers = await _admin_headers(client, db)
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_WEBHOOK_SECRET", "whsec_test", raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_DEFAULT_CHECKOUT_URL",
        "https://getlorevia.com/checkout",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID",
        "pri_author_monthly",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID",
        "pri_author_annual",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID",
        "pri_architect_monthly",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID",
        "pri_architect_annual",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.RESEND_API_KEY", "re_live_test", raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.INTERNAL_JOB_SECRET",
        "internal_job_secret_value",
        raising=False,
    )

    response = await client.get("/api/v1/admin/billing/status", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["billing_enabled"] is True
    assert payload["payments_ready"] is True
    assert payload["recommended_default_checkout_url"] == "https://getlorevia.com/checkout"
    assert payload["resend_api_key_present"] is True
    assert payload["internal_job_secret_present"] is True
    assert payload["fully_configured_plan_count"] == 4
    assert payload["missing_configuration"] == []
    assert all(plan["configured"] for plan in payload["plans"])


@pytest.mark.asyncio
async def test_billing_status_requires_backend_checkout_url_for_payments_ready(
    client, db, monkeypatch
):
    headers = await _admin_headers(client, db)
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_API_KEY", "pdl_test_key", raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_WEBHOOK_SECRET", "whsec_test", raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_DEFAULT_CHECKOUT_URL", None, raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID",
        "pri_author_monthly",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID",
        "pri_author_annual",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID",
        "pri_architect_monthly",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID",
        "pri_architect_annual",
        raising=False,
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.RESEND_API_KEY", "re_live_test", raising=False
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.INTERNAL_JOB_SECRET",
        "internal_job_secret_value",
        raising=False,
    )

    response = await client.get("/api/v1/admin/billing/status", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["billing_enabled"] is True
    assert payload["payments_ready"] is False
    assert payload["default_checkout_url_present"] is False
    assert "PADDLE_DEFAULT_CHECKOUT_URL" in payload["missing_configuration"]


@pytest.mark.asyncio
async def test_legacy_billing_status_route_is_not_exposed(client, db):
    headers = await _admin_headers(client, db)

    response = await client.get("/api/v1/billing/status", headers=headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_billing_confirmation_returns_transaction_summary(client, db, monkeypatch):
    from app.core.security import create_access_token

    me_request = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"billing-txn-{uuid.uuid4().hex[:8]}@lorevia.app",
            "username": f"billing-txn-{uuid.uuid4().hex[:8]}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert me_request.status_code == 201
    user_id = uuid.UUID(me_request.json()["id"])
    token = create_access_token(str(user_id))
    cookie_headers = {"Cookie": f"lorevia_access_token={token}"}
    me = await client.get("/api/v1/auth/me", headers=cookie_headers)
    assert me.status_code == 200

    db.add(
        Subscription(
            user_id=user_id,
            plan="author_annual",
            status="active",
            paddle_transaction_id="txn_123",
            paddle_sub_id="sub_123",
        )
    )
    await db.commit()

    class Summary:
        transaction_id = "txn_123"
        status = "completed"
        plan = "author_annual"
        billing_interval = "annual"
        display_name = "Author"
        currency_code = "USD"
        total = "USD 249.00"
        invoice_number = "INV-123"
        invoice_pdf_url = "https://files.paddle.com/invoice.pdf"
        subscription_id = "sub_123"
        customer_email = "billing@getlorevia.com"

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_123"
        return Summary()

    monkeypatch.setattr(
        "app.api.v1.routes.billing.get_transaction_summary", fake_get_transaction_summary
    )

    response = await client.get(
        "/api/v1/billing/confirmation?transaction_id=txn_123", headers=cookie_headers
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transaction_id"] == "txn_123"
    assert payload["status"] == "completed"
    assert payload["plan"] == "author_annual"
    assert payload["billing_interval"] == "annual"
    assert payload["invoice_number"] == "INV-123"
    assert payload["invoice_pdf_url"] == "https://files.paddle.com/invoice.pdf"


@pytest.mark.asyncio
async def test_billing_confirmation_allows_public_success_page_lookup(client, db, monkeypatch):
    me = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"billing-public-{uuid.uuid4().hex[:8]}@lorevia.app",
            "username": f"billing-public-{uuid.uuid4().hex[:8]}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert me.status_code == 201
    user_id = uuid.UUID(me.json()["id"])

    db.add(
        Subscription(
            user_id=user_id,
            plan="author_annual",
            status="active",
            paddle_transaction_id="txn_public_123",
            paddle_sub_id="sub_public_123",
        )
    )
    await db.commit()

    class Summary:
        transaction_id = "txn_public_123"
        status = "completed"
        plan = "author_annual"
        billing_interval = "annual"
        display_name = "Author"
        currency_code = "USD"
        total = "USD 249.00"
        invoice_number = "INV-PUBLIC-123"
        invoice_pdf_url = "https://files.paddle.com/public-invoice.pdf"
        subscription_id = "sub_public_123"
        customer_email = "billing@getlorevia.com"

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_public_123"
        return Summary()

    monkeypatch.setattr(
        "app.api.v1.routes.billing.get_transaction_summary", fake_get_transaction_summary
    )
    monkeypatch.setattr(
        "app.utils.billing_utils.settings.JWT_SECRET",
        "test-billing-jwt-secret-with-at-least-32-characters",
        raising=False,
    )
    monkeypatch.setattr("app.utils.billing_utils.settings.JWT_ALGORITHM", "HS256", raising=False)
    confirmation_token = create_billing_confirmation_token("txn_public_123")

    response = await client.get(
        f"/api/v1/billing/confirmation?transaction_id=txn_public_123&confirmation_token={confirmation_token}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transaction_id"] == "txn_public_123"
    assert payload["invoice_number"] == "INV-PUBLIC-123"
    assert payload["invoice_pdf_url"] == "https://files.paddle.com/public-invoice.pdf"
    assert payload["customer_email"] == "billing@getlorevia.com"

    replay = await client.get(
        f"/api/v1/billing/confirmation?transaction_id=txn_public_123&confirmation_token={confirmation_token}"
    )
    assert replay.status_code == 401


@pytest.mark.asyncio
async def test_billing_confirmation_rejects_public_lookup_without_token(client, db):
    me = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"billing-public-blocked-{uuid.uuid4().hex[:8]}@lorevia.app",
            "username": f"billing-public-blocked-{uuid.uuid4().hex[:8]}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert me.status_code == 201
    user_id = uuid.UUID(me.json()["id"])

    db.add(
        Subscription(
            user_id=user_id,
            plan="author_monthly",
            status="active",
            paddle_transaction_id="txn_blocked_123",
            paddle_sub_id="sub_blocked_123",
        )
    )
    await db.commit()

    response = await client.get("/api/v1/billing/confirmation?transaction_id=txn_blocked_123")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_checkout_creates_pending_subscription_and_portal_session(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])

    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_plan_is_configured", lambda _plan: True)
    _mock_paddle_quote(monkeypatch)
    monkeypatch.setattr(
        "app.api.v1.routes.billing.create_billing_confirmation_token",
        lambda transaction_id: f"confirm-{transaction_id}",
    )

    provider_call_count = 0

    async def create_checkout(
        user_id_value,
        email,
        plan,
        *,
        existing_customer_id=None,
        checkout_intent_id,
        expected_total_minor,
        currency_code,
    ):
        nonlocal provider_call_count
        provider_call_count += 1
        assert user_id_value == str(user_id)
        assert plan == "author_monthly"
        assert existing_customer_id is None
        assert checkout_intent_id
        assert expected_total_minor == "1900"
        assert currency_code == "USD"
        return "https://checkout.example/session", "ctm_123", "txn_123"

    async def get_transaction_state(transaction_id):
        assert transaction_id == "txn_123"
        return _pending_transaction_state(
            user_id=user_id,
            transaction_id=transaction_id,
        )

    monkeypatch.setattr(
        "app.services.billing_checkout_service.create_checkout_url", create_checkout
    )
    monkeypatch.setattr(
        "app.services.billing_checkout_service.get_paddle_transaction_state",
        get_transaction_state,
    )
    preview = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "author_monthly"},
    )
    assert preview.status_code == 200
    quote_token = preview.json()["quote_token"]
    checkout = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={
            "plan": "author_monthly",
            "confirmed_immediate_charge": True,
            "quote_token": quote_token,
        },
    )
    assert checkout.status_code == 200
    assert checkout.json()["billing_enabled"] is True
    assert "confirm-txn_123" in checkout.json()["checkout_url"]

    subscription = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    assert subscription is not None
    assert subscription.status == "pending"
    assert subscription.paddle_customer_id == "ctm_123"

    repeated_checkout = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={
            "plan": "author_monthly",
            "confirmed_immediate_charge": True,
            "quote_token": quote_token,
        },
    )
    conflicting_preview = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "architect_monthly"},
    )
    assert repeated_checkout.status_code == 200
    assert "txn_123" in repeated_checkout.json()["checkout_url"]
    assert provider_call_count == 1
    assert conflicting_preview.status_code == 409
    assert "checkout is already pending" in conflicting_preview.json()["detail"]

    async def create_portal(customer_id, subscription_ids):
        assert customer_id == "ctm_123"
        assert subscription_ids is None
        return "https://portal.example/customer"

    monkeypatch.setattr("app.api.v1.routes.billing.create_portal_url", create_portal)
    portal = await client.post("/api/v1/billing/portal", headers=auth_headers)
    assert portal.status_code == 200
    assert portal.json() == {
        "portal_url": "https://portal.example/customer",
        "billing_enabled": True,
    }


@pytest.mark.asyncio
async def test_checkout_recovers_provider_transaction_from_durable_intent(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user = await db.get(User, uuid.UUID(me.json()["id"]))
    assert user is not None
    intent = Subscription(
        user_id=user.id,
        plan="author_monthly",
        status="creating",
    )
    db.add(intent)
    await db.commit()
    await db.refresh(intent)
    quote = _paddle_quote("author_monthly")
    quote_token = build_checkout_disclosure(
        user,
        "author_monthly",
        price_quote=quote,
    ).quote_token
    recovered_state = _pending_transaction_state(
        user_id=user.id,
        transaction_id="txn_recovered",
        checkout_intent_id=str(intent.id),
    )

    async def find_transaction(checkout_intent_id, *, customer_id, created_after):
        assert checkout_intent_id == str(intent.id)
        assert customer_id is None
        assert created_after < intent.created_at
        return recovered_state

    async def should_not_create_checkout(*_args, **_kwargs):
        raise AssertionError("recovered checkout must be reused")

    _mock_paddle_quote(monkeypatch)
    monkeypatch.setattr(
        "app.services.billing_checkout_service.find_paddle_transaction_by_checkout_intent",
        find_transaction,
    )
    monkeypatch.setattr(
        "app.services.billing_checkout_service.create_checkout_url",
        should_not_create_checkout,
    )

    checkout = await create_checkout_session(
        db,
        user,
        "author_monthly",
        confirmed_immediate_charge=True,
        quote_token=quote_token,
        client_ip="203.0.113.10",
    )

    assert checkout.transaction_id == "txn_recovered"
    await db.refresh(intent)
    assert intent.status == "pending"
    assert intent.paddle_customer_id == "ctm_123"
    assert intent.paddle_transaction_id == "txn_recovered"


@pytest.mark.asyncio
async def test_checkout_rejects_a_changed_signed_paddle_quote(client, auth_headers, monkeypatch):
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_plan_is_configured", lambda _plan: True)
    current_quote = _paddle_quote("author_monthly")

    async def get_quote(
        plan,
        *,
        customer_ip_address=None,
        existing_customer_id=None,
    ):
        return current_quote

    monkeypatch.setattr(
        "app.services.billing_checkout_service.get_paddle_price_quote",
        get_quote,
    )
    preview = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "author_monthly"},
    )
    assert preview.status_code == 200
    current_quote = PaddlePriceQuote(
        plan="author_monthly",
        price_id="pri_author_monthly",
        amount_minor="2000",
        currency_code="USD",
        formatted_total="$20.00 USD",
        country_code="US",
    )

    checkout = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={
            "plan": "author_monthly",
            "confirmed_immediate_charge": True,
            "quote_token": preview.json()["quote_token"],
        },
    )

    assert checkout.status_code == 409
    assert "changed or expired" in checkout.json()["detail"]


@pytest.mark.asyncio
async def test_checkout_cancels_provider_transaction_when_local_persistence_fails(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user = await db.get(User, uuid.UUID(me.json()["id"]))
    assert user is not None
    quote = _paddle_quote("author_monthly")
    quote_token = build_checkout_disclosure(
        user,
        "author_monthly",
        price_quote=quote,
    ).quote_token
    canceled: list[str] = []

    async def get_quote(*_args, **_kwargs):
        return quote

    async def create_checkout(*_args, **_kwargs):
        return (
            "https://getlorevia.com/checkout?_ptxn=txn_orphan",
            "ctm_orphan",
            "txn_orphan",
        )

    real_commit = db.commit
    commit_calls = 0

    async def fail_second_commit():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 2:
            raise SQLAlchemyError("forced local persistence failure")
        await real_commit()

    async def cancel_transaction(transaction_id):
        canceled.append(transaction_id)
        return "canceled"

    monkeypatch.setattr(
        "app.services.billing_checkout_service.get_paddle_price_quote",
        get_quote,
    )
    monkeypatch.setattr(
        "app.services.billing_checkout_service.create_checkout_url",
        create_checkout,
    )
    monkeypatch.setattr(
        "app.services.billing_checkout_service.cancel_paddle_transaction",
        cancel_transaction,
    )
    monkeypatch.setattr(db, "commit", fail_second_commit)

    with pytest.raises(SQLAlchemyError, match="forced local persistence"):
        await create_checkout_session(
            db,
            user,
            "author_monthly",
            confirmed_immediate_charge=True,
            quote_token=quote_token,
            client_ip="203.0.113.10",
        )

    assert canceled == ["txn_orphan"]
    assert commit_calls == 2


@pytest.mark.asyncio
async def test_checkout_does_not_replace_pending_transaction_with_unknown_provider_state(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    db.add(
        Subscription(
            user_id=user_id,
            plan="author_monthly",
            status="pending",
            paddle_customer_id="ctm_unknown",
            paddle_transaction_id="txn_unknown",
        )
    )
    await db.commit()
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr(
        "app.api.v1.routes.billing.paddle_plan_is_configured",
        lambda _plan: True,
    )
    _mock_paddle_quote(monkeypatch)

    async def get_transaction_state(_transaction_id):
        state = _pending_transaction_state(
            user_id=user_id,
            customer_id="ctm_unknown",
            transaction_id="txn_unknown",
        )
        return PaddleTransactionState(**{**state.__dict__, "status": "unknown"})

    async def should_not_create(*_args, **_kwargs):
        raise AssertionError("An unknown provider transaction must not be replaced")

    monkeypatch.setattr(
        "app.services.billing_checkout_service.get_paddle_transaction_state",
        get_transaction_state,
    )
    monkeypatch.setattr(
        "app.services.billing_checkout_service.create_checkout_url",
        should_not_create,
    )
    preview = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "author_monthly"},
    )
    assert preview.status_code == 200

    checkout = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={
            "plan": "author_monthly",
            "confirmed_immediate_charge": True,
            "quote_token": preview.json()["quote_token"],
        },
    )

    assert checkout.status_code == 409
    assert "cannot be safely replaced" in checkout.json()["detail"]


@pytest.mark.asyncio
async def test_checkout_close_cancels_only_the_users_pending_transaction(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    pending = Subscription(
        user_id=user_id,
        plan="author_monthly",
        status="pending",
        paddle_customer_id="ctm_pending",
        paddle_transaction_id="txn_pending",
    )
    db.add(pending)
    await db.commit()

    async def get_transaction_state(transaction_id):
        assert transaction_id == "txn_pending"
        return PaddleTransactionState("draft", "1900", "USD")

    async def cancel_transaction(transaction_id):
        assert transaction_id == "txn_pending"
        return "canceled"

    monkeypatch.setattr(
        "app.services.billing_checkout_service.get_paddle_transaction_state",
        get_transaction_state,
    )
    monkeypatch.setattr(
        "app.services.billing_checkout_service.cancel_paddle_transaction",
        cancel_transaction,
    )

    response = await client.post(
        "/api/v1/billing/checkout/abandon",
        headers=auth_headers,
        json={"transaction_id": "txn_pending"},
    )

    assert response.status_code == 200
    assert response.json()["abandoned"] is True
    await db.refresh(pending)
    assert pending.status == "canceled"


@pytest.mark.asyncio
async def test_checkout_close_never_cancels_a_completed_transaction(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    pending = Subscription(
        user_id=user_id,
        plan="author_monthly",
        status="pending",
        paddle_customer_id="ctm_paid",
        paddle_transaction_id="txn_paid",
    )
    db.add(pending)
    await db.commit()

    async def get_transaction_state(transaction_id):
        assert transaction_id == "txn_paid"
        return PaddleTransactionState("completed", "1900", "USD")

    async def cancel_transaction(_transaction_id):
        raise AssertionError("A completed transaction must never be canceled")

    monkeypatch.setattr(
        "app.services.billing_checkout_service.get_paddle_transaction_state",
        get_transaction_state,
    )
    monkeypatch.setattr(
        "app.services.billing_checkout_service.cancel_paddle_transaction",
        cancel_transaction,
    )

    response = await client.post(
        "/api/v1/billing/checkout/abandon",
        headers=auth_headers,
        json={"transaction_id": "txn_paid"},
    )

    assert response.status_code == 200
    assert response.json()["abandoned"] is False
    await db.refresh(pending)
    assert pending.status == "active"


@pytest.mark.asyncio
async def test_stale_pending_checkout_is_canceled_before_plan_switch(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    pending = Subscription(
        user_id=user_id,
        plan="author_monthly",
        status="pending",
        paddle_customer_id="ctm_stale",
        paddle_transaction_id="txn_stale",
        created_at=datetime.now(UTC) - timedelta(minutes=31),
    )
    db.add(pending)
    await db.commit()
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_plan_is_configured", lambda _plan: True)
    _mock_paddle_quote(monkeypatch)

    async def get_transaction_state(transaction_id):
        assert transaction_id == "txn_stale"
        return PaddleTransactionState("ready", "1900", "USD")

    async def cancel_transaction(transaction_id):
        assert transaction_id == "txn_stale"
        return "canceled"

    monkeypatch.setattr(
        "app.services.billing_checkout_service.get_paddle_transaction_state",
        get_transaction_state,
    )
    monkeypatch.setattr(
        "app.services.billing_checkout_service.cancel_paddle_transaction",
        cancel_transaction,
    )

    response = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "architect_monthly"},
    )

    assert response.status_code == 200
    await db.refresh(pending)
    assert pending.status == "canceled"


@pytest.mark.asyncio
async def test_checkout_and_portal_cover_disabled_invalid_and_provider_failures(
    client, db, auth_headers, monkeypatch
):
    invalid = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={"plan": "free"},
    )
    assert invalid.status_code == 422

    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: False)
    disabled = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={"plan": "author_annual"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["billing_enabled"] is False
    portal_disabled = await client.post("/api/v1/billing/portal", headers=auth_headers)
    assert portal_disabled.status_code == 200
    assert portal_disabled.json()["billing_enabled"] is False

    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_plan_is_configured", lambda _plan: True)

    _mock_paddle_quote(monkeypatch)

    async def fail_checkout(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.services.billing_checkout_service.create_checkout_url", fail_checkout)
    preview = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "architect_monthly"},
    )
    assert preview.status_code == 200
    failed = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={
            "plan": "architect_monthly",
            "confirmed_immediate_charge": True,
            "quote_token": preview.json()["quote_token"],
        },
    )
    assert failed.status_code == 502
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    durable_intent = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    assert durable_intent is not None
    assert durable_intent.status == "creating"
    assert durable_intent.paddle_transaction_id is None


@pytest.mark.asyncio
async def test_checkout_requires_fresh_review_when_paddle_transaction_details_change(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr(
        "app.api.v1.routes.billing.paddle_plan_is_configured",
        lambda _plan: True,
    )
    _mock_paddle_quote(monkeypatch)

    async def changed_checkout(*_args, **_kwargs):
        raise PaddlePriceChangedError("provider details changed")

    monkeypatch.setattr(
        "app.services.billing_checkout_service.create_checkout_url",
        changed_checkout,
    )
    preview = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "author_monthly"},
    )
    checkout = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={
            "plan": "author_monthly",
            "confirmed_immediate_charge": True,
            "quote_token": preview.json()["quote_token"],
        },
    )

    assert checkout.status_code == 409
    assert checkout.json()["detail"] == (
        "Paddle checkout details changed. Close this dialog and review the current "
        "payment details again."
    )


@pytest.mark.asyncio
async def test_checkout_preview_discloses_active_trial_and_immediate_charge(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_plan_is_configured", lambda _plan: True)
    _mock_paddle_quote(monkeypatch)

    response = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "author_monthly"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trial_status"] == "active"
    assert payload["trial_active"] is True
    assert payload["trial_ends_at"] is not None
    assert payload["charge_today"] == "$19.00 USD"
    assert payload["recurring_price"] == "$19.00 USD every month"
    assert payload["confirmation_required"] is True
    assert payload["confirmation_text"] == (
        "I understand my trial is already active and I will be charged $19.00 USD now."
    )
    assert payload["checkout_button_label"] == "Pay $19.00 USD now"
    assert payload["default_action_label"] == "Continue free trial"
    assert payload["quote_token"]


@pytest.mark.asyncio
async def test_checkout_preview_discloses_expired_trial(client, db, auth_headers, monkeypatch):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user = await db.get(User, uuid.UUID(me.json()["id"]))
    assert user is not None
    user.created_at = datetime.now(UTC) - timedelta(days=11)
    await db.commit()
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_plan_is_configured", lambda _plan: True)
    _mock_paddle_quote(monkeypatch)

    response = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "architect_annual"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trial_status"] == "expired"
    assert payload["trial_active"] is False
    assert payload["trial_ends_at"] is not None
    assert payload["charge_today"] == "$390.00 USD"
    assert payload["recurring_price"] == "$390.00 USD every year"
    assert payload["confirmation_required"] is False
    assert payload["confirmation_text"] is None
    assert payload["default_action_label"] is None


@pytest.mark.asyncio
async def test_active_trial_checkout_requires_explicit_immediate_charge_confirmation(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_plan_is_configured", lambda _plan: True)
    _mock_paddle_quote(monkeypatch)
    provider_call_count = 0

    async def should_not_create_checkout(*_args, **_kwargs):
        nonlocal provider_call_count
        provider_call_count += 1
        raise AssertionError("Paddle must not be called without confirmation")

    monkeypatch.setattr(
        "app.services.billing_checkout_service.create_checkout_url",
        should_not_create_checkout,
    )

    response = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={"plan": "author_monthly", "confirmed_immediate_charge": False},
    )

    assert response.status_code == 409
    assert "I understand my trial is already active" in response.json()["detail"]
    assert provider_call_count == 0


@pytest.mark.asyncio
async def test_checkout_rejects_duplicate_paddle_subscription(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    db.add(
        Subscription(
            user_id=user_id,
            plan="author_monthly",
            status="active",
            paddle_customer_id="ctm_existing",
            paddle_sub_id="sub_existing",
            paddle_transaction_id="txn_existing",
        )
    )
    await db.commit()
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_is_configured", lambda: True)
    monkeypatch.setattr("app.api.v1.routes.billing.paddle_plan_is_configured", lambda _plan: True)

    preview = await client.post(
        "/api/v1/billing/checkout/preview",
        headers=auth_headers,
        json={"plan": "architect_monthly"},
    )
    checkout = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={"plan": "architect_monthly", "confirmed_immediate_charge": True},
    )

    assert preview.status_code == 409
    assert checkout.status_code == 409
    assert "already has a Paddle subscription" in checkout.json()["detail"]


async def _create_billing_subscription(
    client,
    db,
    auth_headers,
    *,
    status: str,
    cancel_at_period_end: bool = False,
    last_payment_status: str | None = None,
) -> tuple[uuid.UUID, datetime]:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    user = await db.get(User, user_id)
    user.tier = "author" if status in {"active", "past_due"} else "free"
    period_start = datetime(2026, 9, 19, tzinfo=UTC)
    period_end = datetime(2026, 10, 19, tzinfo=UTC)
    db.add(
        Subscription(
            user_id=user_id,
            plan="author_monthly",
            status=status,
            paddle_customer_id=f"ctm_status_{status}_{uuid.uuid4().hex[:8]}",
            paddle_sub_id=f"sub_status_{uuid.uuid4().hex[:8]}",
            current_period_start=period_start,
            current_period_end=period_end,
            cancel_at_period_end=cancel_at_period_end,
            cancellation_scheduled_at=period_end if cancel_at_period_end else None,
            last_payment_status=last_payment_status,
        )
    )
    await db.commit()
    return user_id, period_end


@pytest.mark.asyncio
async def test_billing_subscription_endpoint_reports_active_renewal(client, db, auth_headers):
    await _create_billing_subscription(client, db, auth_headers, status="active")

    response = await client.get("/api/v1/billing/subscription", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"] == "author_monthly"
    assert payload["plan_tier"] == "author"
    assert payload["display_state"] == "active"
    assert payload["price"] == {"amount": 19, "currency": "USD", "interval": "month"}
    assert payload["cancel_at_period_end"] is False
    assert payload["auto_renew"] is True
    assert payload["next_charge_at"] is not None
    assert payload["has_paddle_subscription"] is True


@pytest.mark.asyncio
async def test_billing_subscription_endpoint_reports_cancellation_scheduled(
    client, db, auth_headers
):
    _user_id, period_end = await _create_billing_subscription(
        client,
        db,
        auth_headers,
        status="active",
        cancel_at_period_end=True,
    )

    response = await client.get("/api/v1/billing/subscription", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_state"] == "cancellation_scheduled"
    assert payload["cancel_at_period_end"] is True
    assert payload["auto_renew"] is False
    assert payload["next_charge_at"] is None
    assert payload["current_period_end"] == period_end.isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_billing_subscription_endpoint_reports_past_due(client, db, auth_headers):
    await _create_billing_subscription(
        client,
        db,
        auth_headers,
        status="past_due",
        last_payment_status="failed",
    )

    response = await client.get("/api/v1/billing/subscription", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_state"] == "past_due"
    assert payload["auto_renew"] is False
    assert payload["next_charge_at"] is None
    assert payload["last_payment_status"] == "failed"


@pytest.mark.asyncio
async def test_billing_subscription_endpoint_reports_free_without_paddle_subscription(
    client, db, auth_headers
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user = await db.get(User, uuid.UUID(me.json()["id"]))
    user.tier = "free"
    user.created_at = datetime.now(UTC) - timedelta(days=60)
    await db.commit()

    response = await client.get("/api/v1/billing/subscription", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"] == "free"
    assert payload["display_state"] == "free"
    assert payload["price"] == {"amount": 0, "currency": "USD", "interval": "month"}
    assert payload["auto_renew"] is False
    assert payload["has_paddle_subscription"] is False
