from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.utils.monetization_utils import (
    TRIAL_EMAIL_ENDED,
    TRIAL_EMAIL_ENDING,
    TRIAL_EMAIL_NUDGE,
    TRIAL_EMAIL_STARTED,
    build_trial_email_schedule,
    generate_referral_code,
    normalize_referral_code,
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
