import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.user import AdminPrincipal, Subscription, User
from app.utils.billing_utils import create_billing_confirmation_token


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
    monkeypatch.setattr("app.utils.billing_utils.settings.JWT_SECRET", "jwt-secret", raising=False)
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
    monkeypatch.setattr(
        "app.api.v1.routes.billing.create_billing_confirmation_token",
        lambda transaction_id: f"confirm-{transaction_id}",
    )

    async def create_checkout(user_id_value, email, plan, *, existing_customer_id=None):
        assert user_id_value == str(user_id)
        assert plan == "author_monthly"
        assert existing_customer_id is None
        return "https://checkout.example/session", "ctm_123", "txn_123"

    monkeypatch.setattr("app.api.v1.routes.billing.create_checkout_url", create_checkout)
    checkout = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={"plan": "author_monthly"},
    )
    assert checkout.status_code == 200
    assert checkout.json()["billing_enabled"] is True
    assert "confirm-txn_123" in checkout.json()["checkout_url"]

    subscription = await db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    assert subscription is not None
    assert subscription.status == "pending"
    assert subscription.paddle_customer_id == "ctm_123"

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
async def test_checkout_and_portal_cover_disabled_invalid_and_provider_failures(
    client, auth_headers, monkeypatch
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

    async def fail_checkout(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.api.v1.routes.billing.create_checkout_url", fail_checkout)
    failed = await client.post(
        "/api/v1/billing/checkout",
        headers=auth_headers,
        json={"plan": "architect_monthly"},
    )
    assert failed.status_code == 502
