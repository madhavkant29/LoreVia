from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.schemas.books import (
    PrivateUserStats,
    PublicUserStats,
    UserStatsOut,
    WritingDashboardStatsOut,
    WritingPeriodStatOut,
)
from app.services import user_stats_service


def _stats_payload() -> UserStatsOut:
    period = WritingPeriodStatOut(words=0)
    return UserStatsOut(
        public=PublicUserStats(total_books_read=2, total_words_read=345),
        private=PrivateUserStats(
            total_uploads=4,
            total_token_consumption=567,
            total_chapters_tracked=8,
            saved_quotes=1,
        ),
        writing=WritingDashboardStatsOut(
            today=period,
            this_week=period,
            this_month=period,
            this_year=period,
            last_24_hours=period,
            last_7_days=period,
            last_30_days=period,
            last_year=period,
        ),
    )


class _ScalarResult:
    def __init__(self, value: object):
        self.value = value

    def scalar(self) -> object:
        return self.value


class _StatsDB:
    async def execute(self, *_args, **_kwargs):
        return _ScalarResult(3)


@pytest.mark.asyncio
async def test_get_user_stats_cached_returns_valid_versioned_cache_without_rebuilding(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    expected = _stats_payload()
    observed: dict[str, str] = {}

    async def _version(user_id: str) -> int:
        observed["version_user_id"] = user_id
        return 9

    async def _cache_get(key: str):
        observed["key"] = key
        return expected.model_dump(mode="json")

    async def _unexpected_build(*_args, **_kwargs):
        raise AssertionError("a valid cache entry must not rebuild stats")

    monkeypatch.setattr(user_stats_service, "get_user_dashboard_cache_version", _version)
    monkeypatch.setattr(user_stats_service, "cache_get", _cache_get)
    monkeypatch.setattr(user_stats_service, "build_user_stats", _unexpected_build)

    result = await user_stats_service.get_user_stats_cached(SimpleNamespace(), user)

    assert result == expected
    assert observed["version_user_id"] == str(user.id)
    assert observed["key"].endswith(f"{user.id}:v9")


@pytest.mark.asyncio
async def test_get_user_stats_cached_rebuilds_and_writes_display_snapshot_on_miss(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    expected = _stats_payload()
    writes: list[tuple[str, object, int]] = []

    async def _cache_get(_key: str):
        return None

    async def _build(*_args, **_kwargs):
        return expected

    async def _cache_set(key: str, value: object, ttl: int):
        writes.append((key, value, ttl))

    async def _version(_user_id: str) -> int:
        return 3

    monkeypatch.setattr(user_stats_service, "get_user_dashboard_cache_version", _version)
    monkeypatch.setattr(user_stats_service, "cache_get", _cache_get)
    monkeypatch.setattr(user_stats_service, "build_user_stats", _build)
    monkeypatch.setattr(user_stats_service, "cache_set", _cache_set)

    result = await user_stats_service.get_user_stats_cached(SimpleNamespace(), user)

    assert result is expected
    assert writes == [
        (
            f"user_stats:{user.id}:v3",
            expected.model_dump(mode="json"),
            user_stats_service.USER_STATS_CACHE_TTL_SECONDS,
        )
    ]


@pytest.mark.asyncio
async def test_build_user_stats_assembles_display_aggregates_without_parallel_session_queries(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    writing = _stats_payload().writing

    async def _library_stats(*_args, **_kwargs):
        return SimpleNamespace(
            total_books_read=7,
            total_words_read=900,
            total_token_consumption=1200,
            total_chapters_tracked=11,
        )

    async def _writing_stats(*_args, **_kwargs):
        return writing

    async def _upload_usage(*_args, **_kwargs):
        return SimpleNamespace(
            total_uploads=5,
            manuscript_uploads=3,
            worldbuilding_uploads=2,
            upload_limit=15,
            uploads_remaining=10,
            upload_limit_unlimited=False,
        )

    async def _allowances(*_args, **_kwargs):
        return SimpleNamespace(
            active_analyzed_words=100,
            active_word_limit=1000,
            active_words_remaining=900,
            monthly_processed_words=200,
            monthly_processed_word_limit=2000,
            monthly_processed_words_remaining=1800,
            source_storage_bytes=300,
            source_storage_limit_bytes=3000,
            source_storage_remaining_bytes=2700,
            allowances_enforced=True,
        )

    async def _llm_usage(*_args, **_kwargs):
        return SimpleNamespace(
            request_count=4,
            prompt_tokens=50,
            completion_tokens=60,
            total_tokens=110,
            ai_interactive_available=True,
            ai_processing_available=False,
            ai_capacity_usage_percent=25,
            ai_capacity_resets_at=None,
        )

    monkeypatch.setattr(user_stats_service, "load_library_aggregate_stats", _library_stats)
    monkeypatch.setattr(user_stats_service, "build_writing_dashboard_stats", _writing_stats)
    monkeypatch.setattr(user_stats_service, "calculate_upload_usage_summary", _upload_usage)
    monkeypatch.setattr(user_stats_service, "summarize_processing_allowances", _allowances)
    monkeypatch.setattr(user_stats_service, "summarize_llm_usage_for_user", _llm_usage)

    result = await user_stats_service.build_user_stats(_StatsDB(), user)

    assert result.public.total_books_read == 7
    assert result.private.saved_quotes == 3
    assert result.private.total_uploads == 5
    assert result.private.llm_total_tokens == 110
    assert result.private.allowances_enforced is True
    assert result.writing == writing
