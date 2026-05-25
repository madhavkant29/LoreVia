from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.utils.user_utils import (
    add_daily_word_progress,
    build_writing_activity_entry,
    build_writing_dashboard_stats,
    current_daily_word_count,
    current_daily_word_goal,
    login_activity_dates,
    normalize_writing_entry_title,
    record_login_activity,
)


def _user_stub(**overrides):
    payload = {
        "daily_word_goal": 1000,
        "today_word_count": 0,
        "today_word_count_date": None,
        "last_login_at": None,
        "last_login_date": None,
        "login_streak_days": 0,
        "longest_login_streak_days": 0,
        "login_activity_dates": [],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


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


def test_normalize_writing_entry_title_prefers_explicit_title():
    assert normalize_writing_entry_title("  Epilogue  ", chapter_number=4, fallback="Atlas") == "Epilogue"


def test_normalize_writing_entry_title_falls_back_to_chapter_number():
    assert normalize_writing_entry_title("", chapter_number=8, fallback="Atlas") == "Chapter 8"


def test_build_writing_activity_entry_ignores_non_positive_word_counts():
    user = _user_stub(id="user-1")
    book = SimpleNamespace(id="book-1", title="Atlas")

    assert build_writing_activity_entry(user, book, 0, chapter_number=2, title="Storm") is None


def test_build_writing_activity_entry_sets_date_and_title():
    user = _user_stub(id="user-1")
    book = SimpleNamespace(id="book-1", title="Atlas")

    entry = build_writing_activity_entry(
        user,
        book,
        315,
        chapter_number=6,
        title="  The Crossing  ",
        now=datetime(2026, 5, 7, 9, 15, tzinfo=UTC),
    )

    assert entry is not None
    assert entry.entry_title == "The Crossing"
    assert entry.chapter_number == 6
    assert entry.words_added == 315
    assert entry.activity_date == date(2026, 5, 7)


class _ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarList(self._items)


class _FakeDB:
    def __init__(self, items):
        self._items = items

    async def execute(self, *_args, **_kwargs):
        return _Result(self._items)


@pytest.mark.asyncio
async def test_build_writing_dashboard_stats_rolls_up_periods_and_entries(monkeypatch):
    user = _user_stub(id="user-1", daily_word_goal=1000)
    now = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    activities = [
        SimpleNamespace(
            book_id="book-1",
            chapter_number=36,
            entry_title="Chapter XXXVI",
            words_added=763,
            activity_date=date(2026, 5, 14),
            created_at=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
        ),
        SimpleNamespace(
            book_id="book-1",
            chapter_number=None,
            entry_title="Epilogue",
            words_added=439,
            activity_date=date(2026, 5, 14),
            created_at=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
        ),
        SimpleNamespace(
            book_id="book-1",
            chapter_number=35,
            entry_title="Chapter XXXV",
            words_added=1363,
            activity_date=date(2026, 5, 12),
            created_at=datetime(2026, 5, 12, 18, 0, tzinfo=UTC),
        ),
        SimpleNamespace(
            book_id="book-1",
            chapter_number=20,
            entry_title="Chapter XX",
            words_added=9600,
            activity_date=date(2026, 5, 2),
            created_at=datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
        ),
        SimpleNamespace(
            book_id="book-1",
            chapter_number=4,
            entry_title="Chapter IV",
            words_added=47806,
            activity_date=date(2026, 2, 14),
            created_at=datetime(2026, 2, 14, 8, 0, tzinfo=UTC),
        ),
    ]

    cache_store = {}

    async def _fake_get_version(_user_id):
        return 0

    async def _fake_get_cache(_user_id, _version, _day_marker):
        return cache_store.get("payload")

    async def _fake_set_cache(_user_id, _version, _day_marker, payload):
        cache_store["payload"] = payload

    import app.utils.user_utils as user_utils_module

    monkeypatch.setattr(user_utils_module, "get_user_dashboard_cache_version", _fake_get_version)
    monkeypatch.setattr(user_utils_module, "get_writing_dashboard_cache", _fake_get_cache)
    monkeypatch.setattr(user_utils_module, "set_writing_dashboard_cache", _fake_set_cache)

    stats = await build_writing_dashboard_stats(_FakeDB(activities), user, now=now)

    assert stats["today"]["words"] == 1202
    assert stats["today"]["target_words"] == 1000
    assert stats["today"]["progress_pct"] == 100
    assert stats["this_week"]["words"] == 2565
    assert stats["this_week"]["target_words"] == 7000
    assert stats["this_month"]["words"] == 12165
    assert stats["this_year"]["words"] == 59971
    assert stats["last_24_hours"]["words"] == 1202
    assert stats["last_7_days"]["words"] == 2565
    assert stats["last_30_days"]["words"] == 12165
    assert stats["last_year"]["words"] == 59971
    assert stats["entries_today"][0]["title"] == "Epilogue"
    assert stats["entries_today"][0]["words"] == 439
    assert stats["entries_today"][1]["title"] == "Chapter XXXVI"
    assert stats["entries_today"][1]["words"] == 763
    assert len(stats["heatmap"]) == 140


@pytest.mark.asyncio
async def test_build_writing_dashboard_stats_returns_cached_payload(monkeypatch):
    user = _user_stub(id="user-1", daily_word_goal=1000)
    cached_payload = {"today": {"words": 42, "target_words": 1000, "progress_pct": 4}}

    async def _fake_get_version(_user_id):
        return 0

    async def _fake_get_cache(_user_id, _version, _day_marker):
        return cached_payload

    async def _fake_set_cache(*_args, **_kwargs):
        raise AssertionError("cache set should not run on a cache hit")

    import app.utils.user_utils as user_utils_module

    monkeypatch.setattr(user_utils_module, "get_user_dashboard_cache_version", _fake_get_version)
    monkeypatch.setattr(user_utils_module, "get_writing_dashboard_cache", _fake_get_cache)
    monkeypatch.setattr(user_utils_module, "set_writing_dashboard_cache", _fake_set_cache)

    stats = await build_writing_dashboard_stats(_FakeDB([]), user, now=datetime(2026, 5, 14, 12, 0, tzinfo=UTC))

    assert stats == cached_payload
