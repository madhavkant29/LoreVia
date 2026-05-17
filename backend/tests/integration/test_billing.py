import pytest
import uuid

from app.models.user import Subscription
from app.utils.billing_utils import create_billing_confirmation_token


@pytest.mark.asyncio
async def test_billing_status_reports_missing_configuration(auth_headers, client, monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_API_KEY", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_WEBHOOK_SECRET", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.RESEND_API_KEY", "", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.INTERNAL_JOB_SECRET", None, raising=False)

    response = await client.get("/api/v1/billing/status", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["billing_enabled"] is False
    assert payload["payments_ready"] is False
    assert payload["paddle_api_key_present"] is False
    assert payload["webhook_secret_present"] is False
    assert payload["recommended_default_checkout_url"] == "http://localhost:3000/checkout"
    assert payload["resend_api_key_present"] is False
    assert payload["internal_job_secret_present"] is False
    assert "PADDLE_API_KEY" in payload["missing_configuration"]
    assert "PADDLE_WEBHOOK_SECRET" in payload["missing_configuration"]
    assert "RESEND_API_KEY" in payload["missing_configuration"]
    assert "INTERNAL_JOB_SECRET" in payload["missing_configuration"]
    assert len(payload["plans"]) == 4
    assert payload["trial_email_automation_code_ready"] is True
    assert payload["priority_processing_code_ready"] is True
    assert payload["points_wallet_ready"] is True
    assert payload["points_spend_ready"] is True
    assert payload["rewarded_ads_code_ready"] is True
    assert payload["webhook_endpoint_path"] == "/api/v1/webhooks/paddle"
    assert payload["trial_email_job_endpoint_path"] == "/api/v1/internal/jobs/send-due-trial-emails"
    assert "transaction.completed" in payload["supported_webhook_events"]
    assert "transaction.payment_failed" in payload["supported_webhook_events"]
    assert "subscription.activated" in payload["supported_webhook_events"]
    assert "subscription.resumed" in payload["supported_webhook_events"]
    assert "subscription.trialing" in payload["supported_webhook_events"]
    author_monthly = next(plan for plan in payload["plans"] if plan["code"] == "author_monthly")
    architect_monthly = next(plan for plan in payload["plans"] if plan["code"] == "architect_monthly")
    assert author_monthly["display_name"] == "Author"
    assert author_monthly["billing_interval"] == "monthly"
    assert author_monthly["price_usd"] == 29
    assert architect_monthly["display_name"] == "Architect"
    assert architect_monthly["billing_interval"] == "monthly"
    assert architect_monthly["price_usd"] == 49


@pytest.mark.asyncio
async def test_billing_status_reports_fully_configured_catalog(auth_headers, client, monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_API_KEY", "pdl_test_key", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_WEBHOOK_SECRET", "whsec_test", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID", "pri_author_monthly", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID", "pri_author_annual", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID", "pri_architect_monthly", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID", "pri_architect_annual", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.RESEND_API_KEY", "re_live_test", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.INTERNAL_JOB_SECRET", "internal_job_secret_value", raising=False)

    response = await client.get("/api/v1/billing/status", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["billing_enabled"] is True
    assert payload["payments_ready"] is True
    assert payload["recommended_default_checkout_url"] == "http://localhost:3000/checkout"
    assert payload["resend_api_key_present"] is True
    assert payload["internal_job_secret_present"] is True
    assert payload["fully_configured_plan_count"] == 4
    assert payload["missing_configuration"] == []
    assert all(plan["configured"] for plan in payload["plans"])


@pytest.mark.asyncio
async def test_billing_confirmation_returns_transaction_summary(auth_headers, client, db, monkeypatch):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

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
        total = "USD 290.00"
        invoice_number = "INV-123"
        invoice_pdf_url = "https://files.paddle.com/invoice.pdf"
        subscription_id = "sub_123"
        customer_email = "billing@getlorevia.com"

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_123"
        return Summary()

    monkeypatch.setattr("app.api.v1.routes.billing.get_transaction_summary", fake_get_transaction_summary)

    response = await client.get("/api/v1/billing/confirmation?transaction_id=txn_123", headers=auth_headers)

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
        total = "USD 290.00"
        invoice_number = "INV-PUBLIC-123"
        invoice_pdf_url = "https://files.paddle.com/public-invoice.pdf"
        subscription_id = "sub_public_123"
        customer_email = "billing@getlorevia.com"

    async def fake_get_transaction_summary(transaction_id: str):
        assert transaction_id == "txn_public_123"
        return Summary()

    monkeypatch.setattr("app.api.v1.routes.billing.get_transaction_summary", fake_get_transaction_summary)
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
