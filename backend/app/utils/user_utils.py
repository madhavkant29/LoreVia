from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    get_user_dashboard_cache_version,
    get_writing_dashboard_cache,
    set_writing_dashboard_cache,
)

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.user import User


DEFAULT_DAILY_WORD_GOAL = 1000
MAX_LOGIN_ACTIVITY_DAYS = 35
WRITING_HEATMAP_WEEKS = 20


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


def build_writing_activity_entry(
    user: User,
    book: Book,
    words_added: int,
    *,
    chapter_number: int | None = None,
    title: str | None = None,
    now: datetime | None = None,
):
    from app.models.user import UserWritingActivity

    normalized_words = max(int(words_added or 0), 0)
    if normalized_words <= 0:
        return None

    current = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    normalized_title = normalize_writing_entry_title(title, chapter_number=chapter_number, fallback=book.title)

    return UserWritingActivity(
        user_id=user.id,
        book_id=book.id,
        chapter_number=chapter_number,
        entry_title=normalized_title,
        words_added=normalized_words,
        activity_date=current.date(),
        created_at=current,
    )


def normalize_writing_entry_title(title: str | None, *, chapter_number: int | None = None, fallback: str | None = None) -> str:
    cleaned = (title or "").strip()
    if cleaned:
        return cleaned
    if chapter_number is not None:
        return f"Chapter {chapter_number}"
    if fallback and fallback.strip():
        return fallback.strip()
    return "Untitled draft"


async def build_writing_dashboard_stats(
    db: AsyncSession,
    user: User,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    from app.models.user import UserWritingActivity

    current = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    version = await get_user_dashboard_cache_version(str(user.id))
    day_marker = current.date().isoformat()
    cached = await get_writing_dashboard_cache(str(user.id), version, day_marker)
    if cached is not None:
        return cached
    today = current.date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_year = today.replace(month=1, day=1)
    rolling_last_24_hours = current - timedelta(hours=24)
    rolling_last_7_days = current - timedelta(days=7)
    rolling_last_30_days = current - timedelta(days=30)
    rolling_last_year = current - timedelta(days=365)
    heatmap_start = start_of_week - timedelta(weeks=WRITING_HEATMAP_WEEKS - 1)
    earliest_day = min(start_of_year, heatmap_start, rolling_last_year.date())
    earliest_timestamp = datetime.combine(earliest_day, time.min, tzinfo=UTC)

    result = await db.execute(
        select(UserWritingActivity)
        .where(
            UserWritingActivity.user_id == user.id,
            UserWritingActivity.created_at >= earliest_timestamp,
        )
        .order_by(UserWritingActivity.created_at.desc())
    )
    activities = list(result.scalars().all())

    daily_totals: dict[date, int] = defaultdict(int)
    today_entries: dict[tuple[str | None, int | None, str], dict[str, Any]] = {}
    last_24_hours_words = 0
    last_7_days_words = 0
    last_30_days_words = 0
    last_year_words = 0

    for activity in activities:
        words_added = max(int(activity.words_added or 0), 0)
        if words_added <= 0:
            continue

        activity_day = activity.activity_date if isinstance(activity.activity_date, date) else activity.created_at.date()
        daily_totals[activity_day] += words_added

        if activity.created_at >= rolling_last_24_hours:
            last_24_hours_words += words_added
        if activity.created_at >= rolling_last_7_days:
            last_7_days_words += words_added
        if activity.created_at >= rolling_last_30_days:
            last_30_days_words += words_added
        if activity.created_at >= rolling_last_year:
            last_year_words += words_added

        if activity_day != today:
            continue

        entry_key = (
            str(activity.book_id) if activity.book_id else None,
            activity.chapter_number,
            normalize_writing_entry_title(activity.entry_title, chapter_number=activity.chapter_number),
        )
        if entry_key not in today_entries:
            today_entries[entry_key] = {
                "book_id": str(activity.book_id) if activity.book_id else None,
                "chapter_number": activity.chapter_number,
                "title": entry_key[2],
                "words": 0,
                "created_at": activity.created_at,
            }
        today_entries[entry_key]["words"] += words_added
        if activity.created_at > today_entries[entry_key]["created_at"]:
            today_entries[entry_key]["created_at"] = activity.created_at

    this_week_words = _sum_daily_totals(daily_totals, start=start_of_week)
    this_month_words = _sum_daily_totals(
        daily_totals,
        predicate=lambda item_day: item_day.year == today.year and item_day.month == today.month,
    )
    this_year_words = _sum_daily_totals(
        daily_totals,
        predicate=lambda item_day: item_day.year == today.year,
    )
    today_words = daily_totals.get(today, 0)

    daily_goal = current_daily_word_goal(user)
    heatmap = [
        {
            "date": (heatmap_start + timedelta(days=offset)).isoformat(),
            "words": daily_totals.get(heatmap_start + timedelta(days=offset), 0),
        }
        for offset in range(WRITING_HEATMAP_WEEKS * 7)
    ]
    ordered_today_entries = sorted(
        today_entries.values(),
        key=lambda entry: (entry["created_at"], entry["words"]),
        reverse=True,
    )

    payload = {
        "today": _writing_period_payload(today_words, target_words=daily_goal),
        "this_week": _writing_period_payload(this_week_words, target_words=daily_goal * 7),
        "this_month": _writing_period_payload(this_month_words),
        "this_year": _writing_period_payload(this_year_words),
        "last_24_hours": _writing_period_payload(last_24_hours_words),
        "last_7_days": _writing_period_payload(last_7_days_words),
        "last_30_days": _writing_period_payload(last_30_days_words),
        "last_year": _writing_period_payload(last_year_words),
        "heatmap": heatmap,
        "entries_today": [
            {
                "book_id": entry["book_id"],
                "chapter_number": entry["chapter_number"],
                "title": entry["title"],
                "words": entry["words"],
            }
            for entry in ordered_today_entries[:8]
        ],
    }
    await set_writing_dashboard_cache(str(user.id), version, day_marker, payload)
    return payload


def _sum_daily_totals(
    daily_totals: dict[date, int],
    *,
    start: date | None = None,
    predicate: Callable[[date], bool] | None = None,
) -> int:
    total = 0
    for item_day, words in daily_totals.items():
        if start is not None and item_day < start:
            continue
        if predicate is not None and not predicate(item_day):
            continue
        total += words
    return total


def _writing_period_payload(words: int, *, target_words: int | None = None) -> dict[str, int | None]:
    progress_pct = None
    if target_words and target_words > 0:
        progress_pct = min(100, int(round((max(words, 0) / target_words) * 100)))

    return {
        "words": max(int(words or 0), 0),
        "target_words": target_words if target_words and target_words > 0 else None,
        "progress_pct": progress_pct,
    }
