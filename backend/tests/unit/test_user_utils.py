from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.utils.user_utils import (
    add_daily_word_progress,
    current_daily_word_count,
    current_daily_word_goal,
    login_activity_dates,
    record_login_activity,
)


def _user_stub(**overrides):
    return SimpleNamespace(
        daily_word_goal=1000,
        today_word_count=0,
        today_word_count_date=None,
        last_login_at=None,
        last_login_date=None,
        login_streak_days=0,
        longest_login_streak_days=0,
        login_activity_dates=[],
        **overrides,
    )


def test_current_daily_word_goal_falls_back_to_default():
    assert current_daily_word_goal(_user_stub(daily_word_goal=0)) == 1000


def test_add_daily_word_progress_resets_for_new_day():
    user = _user_stub(today_word_count=275, today_word_count_date=date(2026, 5, 6))

    add_daily_word_progress(user, 125, now=datetime(2026, 5, 7, 9, 0, tzinfo=UTC))

    assert user.today_word_count == 125
    assert user.today_word_count_date == date(2026, 5, 7)


def test_current_daily_word_count_ignores_stale_values():
    user = _user_stub(today_word_count=900, today_word_count_date=date(2026, 5, 6))

    assert current_daily_word_count(user, today=date(2026, 5, 7)) == 0


def test_record_login_activity_increments_streak_on_consecutive_days():
    user = _user_stub(
        last_login_date=date(2026, 5, 6),
        login_streak_days=3,
        longest_login_streak_days=4,
        login_activity_dates=[date(2026, 5, 5), date(2026, 5, 6)],
    )

    record_login_activity(user, now=datetime(2026, 5, 7, 8, 30, tzinfo=UTC))

    assert user.last_login_date == date(2026, 5, 7)
    assert user.login_streak_days == 4
    assert user.longest_login_streak_days == 4
    assert login_activity_dates(user)[-1] == date(2026, 5, 7)


def test_record_login_activity_does_not_double_count_same_day():
    user = _user_stub(
        last_login_date=date(2026, 5, 7),
        login_streak_days=2,
        longest_login_streak_days=2,
        login_activity_dates=[date(2026, 5, 6), date(2026, 5, 7)],
    )

    record_login_activity(user, now=datetime(2026, 5, 7, 17, 45, tzinfo=UTC))

    assert user.login_streak_days == 2
    assert user.longest_login_streak_days == 2
    assert login_activity_dates(user) == [date(2026, 5, 6), date(2026, 5, 7)]
