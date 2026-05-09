from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User


DEFAULT_DAILY_WORD_GOAL = 1000
MAX_LOGIN_ACTIVITY_DAYS = 35


def utc_today(now: datetime | None = None) -> date:
    current = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    return current.date()


def current_daily_word_count(user: User, *, today: date | None = None) -> int:
    active_day = today or utc_today()
    if user.today_word_count_date != active_day:
        return 0
    return max(int(user.today_word_count or 0), 0)


def current_daily_word_goal(user: User) -> int:
    return max(int(user.daily_word_goal or DEFAULT_DAILY_WORD_GOAL), 1)


def login_activity_dates(user: User) -> list[date]:
    values = sorted({item for item in (user.login_activity_dates or []) if isinstance(item, date)})
    if len(values) <= MAX_LOGIN_ACTIVITY_DAYS:
        return values
    return values[-MAX_LOGIN_ACTIVITY_DAYS:]


def record_login_activity(user: User, *, now: datetime | None = None) -> None:
    current = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    today = current.date()
    previous_day = user.last_login_date

    user.last_login_at = current
    user.last_login_date = today

    if previous_day == today:
        user.login_activity_dates = _append_login_day(user.login_activity_dates, today)
        return

    if previous_day == today - timedelta(days=1):
        user.login_streak_days = max(int(user.login_streak_days or 0) + 1, 1)
    else:
        user.login_streak_days = 1

    user.longest_login_streak_days = max(int(user.longest_login_streak_days or 0), int(user.login_streak_days or 0))
    user.login_activity_dates = _append_login_day(user.login_activity_dates, today)


def add_daily_word_progress(user: User, words_added: int, *, now: datetime | None = None) -> int:
    current = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    today = current.date()
    current_words = current_daily_word_count(user, today=today)

    user.today_word_count_date = today
    user.today_word_count = current_words + max(int(words_added or 0), 0)
    return int(user.today_word_count or 0)


def _append_login_day(existing_days: list[date] | None, day: date) -> list[date]:
    days = sorted({item for item in (existing_days or []) if isinstance(item, date)} | {day})
    if len(days) > MAX_LOGIN_ACTIVITY_DAYS:
        days = days[-MAX_LOGIN_ACTIVITY_DAYS:]
    return days
