from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.utils.monetization_utils import (
    POINT_ACTION_PREDICTION,
    POINT_OFFER_PREDICTION_OVERFLOW,
    REWARDED_AD_STATUS_ERROR,
    REWARDED_AD_STATUS_REWARDED,
    REWARDED_AD_STATUS_UNSUPPORTED,
    TRIAL_EMAIL_ENDED,
    TRIAL_EMAIL_ENDING,
    TRIAL_EMAIL_NUDGE,
    TRIAL_EMAIL_STARTED,
    build_trial_email_schedule,
    generate_referral_code,
    normalize_referral_code,
    normalize_rewarded_ad_outcome,
    point_spend_offer_by_code,
    point_spend_offer_for_action,
    points_balance_from_deltas,
)


def test_normalize_referral_code_removes_separators_and_uppercases():
    assert normalize_referral_code(" lore-via 123 ") == "LOREVIA123"


def test_generate_referral_code_uses_username_prefix_when_available():
    user = SimpleNamespace(username="reader-one")

    code = generate_referral_code(user)

    assert code.startswith("READERON")
    assert len(code) > len("READERON")


def test_trial_email_schedule_covers_all_required_trial_touchpoints():
    started_at = datetime(2026, 5, 1, 12, tzinfo=UTC)

    schedule = build_trial_email_schedule(started_at)

    assert schedule[TRIAL_EMAIL_STARTED] == started_at
    assert schedule[TRIAL_EMAIL_NUDGE] == started_at + timedelta(days=3)
    assert schedule[TRIAL_EMAIL_ENDING] == started_at + timedelta(days=9)
    assert schedule[TRIAL_EMAIL_ENDED] == started_at + timedelta(days=10)


def test_points_balance_never_returns_negative_public_balance():
    assert points_balance_from_deltas([100, -150]) == 0


def test_point_spend_offer_lookup_by_code_returns_matching_offer():
    offer = point_spend_offer_by_code(POINT_OFFER_PREDICTION_OVERFLOW)

    assert offer is not None
    assert offer.action == POINT_ACTION_PREDICTION
    assert offer.points_cost == 6


def test_point_spend_offer_lookup_by_action_returns_matching_offer():
    offer = point_spend_offer_for_action(POINT_ACTION_PREDICTION)

    assert offer is not None
    assert offer.code == POINT_OFFER_PREDICTION_OVERFLOW


def test_normalize_rewarded_ad_outcome_defaults_unknown_values_to_error():
    assert normalize_rewarded_ad_outcome("rewarded") == REWARDED_AD_STATUS_REWARDED
    assert normalize_rewarded_ad_outcome("unsupported") == REWARDED_AD_STATUS_UNSUPPORTED
    assert normalize_rewarded_ad_outcome("unexpected") == REWARDED_AD_STATUS_ERROR
