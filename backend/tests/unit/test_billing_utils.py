from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.utils.billing_utils import (
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
