import pytest


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
    author_monthly = next(plan for plan in payload["plans"] if plan["code"] == "author_monthly")
    architect_monthly = next(plan for plan in payload["plans"] if plan["code"] == "architect_monthly")
    assert author_monthly["display_name"] == "Author"
    assert author_monthly["billing_interval"] == "monthly"
    assert author_monthly["price_usd"] == 29
    assert architect_monthly["display_name"] == "Lore Architect"
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
    assert payload["resend_api_key_present"] is True
    assert payload["internal_job_secret_present"] is True
    assert payload["fully_configured_plan_count"] == 4
    assert payload["missing_configuration"] == []
    assert all(plan["configured"] for plan in payload["plans"])
