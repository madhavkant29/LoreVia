from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.utils.billing_utils import (
    billing_configuration_status,
    build_tier_presentation,
    free_search_limit_per_day,
    normalize_plan_code,
    paddle_plan_from_event_data,
    prediction_limit_per_day,
    protected_authoring_limit_per_day,
    summary_mode_allowed,
    tier_from_plan_code,
    user_access_tier,
)


def test_trial_user_gets_author_access_and_trial_label(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    user = SimpleNamespace(tier="free", created_at=datetime.now(UTC) - timedelta(days=2))

    presentation = build_tier_presentation(user)

    assert presentation.plan_tier == "free"
    assert presentation.access_tier == "author"
    assert presentation.trial_active is True
    assert presentation.tier_label == "Author (free trial)"


def test_expired_trial_reverts_to_free(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    user = SimpleNamespace(tier="free", created_at=datetime.now(UTC) - timedelta(days=11))

    assert user_access_tier(user) == "free"


def test_local_debug_grants_architect_access(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", True, raising=False)
    user = SimpleNamespace(tier="free", created_at=datetime.now(UTC) - timedelta(days=11))

    assert user_access_tier(user) == "architect"


def test_plan_and_tier_mapping_supports_new_and_legacy_codes():
    assert normalize_plan_code("pro_monthly") == "reader_monthly"
    assert normalize_plan_code("power_annual") == "author_annual"
    assert tier_from_plan_code("reader_monthly") == "reader"
    assert tier_from_plan_code("author_annual") == "author"
    assert tier_from_plan_code("architect_monthly") == "architect"


def test_paddle_event_plan_falls_back_to_price_names():
    payload = {
        "items": [
            {
                "price": {
                    "name": "Lore Architect annual",
                    "billing_cycle": {"interval": "year"},
                    "product": {"name": "LoreVia"},
                }
            }
        ]
    }

    assert paddle_plan_from_event_data(payload) == "architect_annual"


def test_trial_users_get_trial_high_cost_limit(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.TRIAL_HIGH_COST_TURNS_PER_DAY", 20, raising=False)
    user = SimpleNamespace(tier="free", created_at=datetime.now(UTC) - timedelta(days=2))

    assert protected_authoring_limit_per_day(user) == 20


def test_paid_reader_keeps_reader_access_without_trial_overlay(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    user = SimpleNamespace(tier="reader", created_at=datetime.now(UTC) - timedelta(days=2))

    presentation = build_tier_presentation(user)

    assert presentation.access_tier == "reader"
    assert presentation.trial_active is False


def test_free_summary_mode_rules_follow_launch_plan(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    expired_free_user = SimpleNamespace(tier="free", created_at=datetime.now(UTC) - timedelta(days=20))
    reader_user = SimpleNamespace(tier="reader", created_at=datetime.now(UTC) - timedelta(days=1))

    assert summary_mode_allowed(expired_free_user, "short") is True
    assert summary_mode_allowed(expired_free_user, "detailed") is False
    assert summary_mode_allowed(reader_user, "detailed") is True


def test_daily_search_and_prediction_limits_match_launch_tiers(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.FREE_SEARCH_PER_DAY", 5, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.FREE_PREDICTION_PER_DAY", 3, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.READER_PREDICTION_PER_DAY", 10, raising=False)

    free_user = SimpleNamespace(tier="free", created_at=datetime.now(UTC) - timedelta(days=20))
    reader_user = SimpleNamespace(tier="reader", created_at=datetime.now(UTC) - timedelta(days=20))

    assert free_search_limit_per_day(free_user) == 5
    assert free_search_limit_per_day(reader_user) is None
    assert prediction_limit_per_day(free_user) == 3
    assert prediction_limit_per_day(reader_user) == 10


def test_billing_configuration_status_reports_missing_paddle_values(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_API_KEY", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_WEBHOOK_SECRET", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_READER_MONTHLY_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_READER_ANNUAL_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID", None, raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.RESEND_API_KEY", "", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.INTERNAL_JOB_SECRET", None, raising=False)

    status = billing_configuration_status()

    assert status["billing_enabled"] is False
    assert status["payments_ready"] is False
    assert status["paddle_api_key_present"] is False
    assert status["webhook_secret_present"] is False
    assert status["resend_api_key_present"] is False
    assert status["internal_job_secret_present"] is False
    assert status["fully_configured_plan_count"] == 0
    assert "PADDLE_API_KEY" in status["missing_configuration"]
    assert "PADDLE_WEBHOOK_SECRET" in status["missing_configuration"]
    assert "RESEND_API_KEY" in status["missing_configuration"]
    assert "INTERNAL_JOB_SECRET" in status["missing_configuration"]
    assert any(plan["code"] == "reader_monthly" and plan["configured"] is False for plan in status["plans"])
    assert status["trial_email_automation_code_ready"] is True
    assert status["priority_processing_code_ready"] is True
    assert status["points_wallet_ready"] is True
    assert status["points_spend_ready"] is True
    assert status["rewarded_ads_code_ready"] is True
    assert status["webhook_endpoint_path"] == "/api/v1/webhooks/paddle"
    assert "transaction.completed" in status["supported_webhook_events"]
    assert status["trial_email_job_endpoint_path"] == "/api/v1/internal/jobs/send-due-trial-emails"
    assert status["trial_email_runner_script"] == "backend/scripts/run_due_trial_emails.py"
    assert "Register `/api/v1/webhooks/paddle` in Paddle" in status["external_action_items"][0]
    assert any(
        plan["code"] == "author_monthly"
        and plan["display_name"] == "Author"
        and plan["billing_interval"] == "monthly"
        and plan["price_usd"] == 29
        for plan in status["plans"]
    )
    assert any(
        plan["code"] == "architect_monthly"
        and plan["display_name"] == "Lore Architect"
        and plan["billing_interval"] == "monthly"
        and plan["price_usd"] == 49
        for plan in status["plans"]
    )


def test_billing_configuration_status_reports_fully_configured_catalog(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_API_KEY", "pdl_test_key", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_WEBHOOK_SECRET", "whsec_test", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_READER_MONTHLY_PRICE_ID", "pri_reader_monthly", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_READER_ANNUAL_PRICE_ID", "pri_reader_annual", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID", "pri_author_monthly", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID", "pri_author_annual", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID", "pri_architect_monthly", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID", "pri_architect_annual", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.RESEND_API_KEY", "re_live_test", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.INTERNAL_JOB_SECRET", "internal_job_secret_value", raising=False)

    status = billing_configuration_status()

    assert status["billing_enabled"] is True
    assert status["payments_ready"] is True
    assert status["resend_api_key_present"] is True
    assert status["internal_job_secret_present"] is True
    assert status["fully_configured_plan_count"] == 6
    assert status["missing_configuration"] == []
    assert all(plan["configured"] is True for plan in status["plans"])


def test_billing_configuration_status_treats_placeholder_values_as_missing(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_API_KEY", "pdl_live_or_sandbox_key_here", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_WEBHOOK_SECRET", "pdl_webhook_secret_here", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_READER_MONTHLY_PRICE_ID", "pri_reader_monthly", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_READER_ANNUAL_PRICE_ID", "pri_reader_annual", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_MONTHLY_PRICE_ID", "pri_author_monthly", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_AUTHOR_ANNUAL_PRICE_ID", "pri_author_annual", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_MONTHLY_PRICE_ID", "pri_architect_monthly", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.PADDLE_ARCHITECT_ANNUAL_PRICE_ID", "pri_architect_annual", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.RESEND_API_KEY", "dummy", raising=False)
    monkeypatch.setattr("app.utils.billing_utils.settings.INTERNAL_JOB_SECRET", "replace_with_an_internal_job_secret", raising=False)

    status = billing_configuration_status()

    assert status["billing_enabled"] is False
    assert status["payments_ready"] is False
    assert status["paddle_api_key_present"] is False
    assert status["webhook_secret_present"] is False
    assert status["resend_api_key_present"] is False
    assert status["internal_job_secret_present"] is False
