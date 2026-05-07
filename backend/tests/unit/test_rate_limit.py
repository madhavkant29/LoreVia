from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.api.deps.rate_limit import _bump_daily_bucket, _client_identifier, rate_limit_advisor


def _request_with_headers(headers: dict[str, str], client_host: str = "127.0.0.1") -> Request:
    scope_headers = [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": scope_headers,
        "client": (client_host, 50000),
    }
    return Request(scope)


def test_client_identifier_prefers_cloudflare_header() -> None:
    request = _request_with_headers(
        {
            "x-forwarded-for": "198.51.100.7",
            "cf-connecting-ip": "203.0.113.11",
        }
    )

    assert _client_identifier(request) == "203.0.113.11"


def test_client_identifier_falls_back_to_socket_client() -> None:
    request = _request_with_headers({}, client_host="10.0.0.9")

    assert _client_identifier(request) == "10.0.0.9"


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = str(value)
        return True

    async def incr(self, key):
        next_value = int(self.store.get(key, "0")) + 1
        self.store[key] = str(next_value)
        return next_value


@pytest.mark.asyncio
async def test_daily_bucket_blocks_after_limit(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr("app.api.deps.rate_limit.get_redis", _fake_get_redis)
    monkeypatch.setattr(
        "app.api.deps.rate_limit._current_utc",
        lambda now=None: datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    await _bump_daily_bucket("user-1", "search", 2)
    await _bump_daily_bucket("user-1", "search", 2)

    with pytest.raises(Exception) as exc_info:
        await _bump_daily_bucket("user-1", "search", 2)

    assert getattr(exc_info.value, "status_code", None) == 429


@pytest.mark.asyncio
async def test_trial_authoring_surfaces_share_one_daily_bucket(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    async def _fake_limit_for_user(user_id, field, default):
        return default

    monkeypatch.setattr("app.api.deps.rate_limit.get_redis", _fake_get_redis)
    monkeypatch.setattr("app.api.deps.rate_limit._limit_for_user", _fake_limit_for_user)
    monkeypatch.setattr("app.api.deps.rate_limit.settings.TRIAL_HIGH_COST_TURNS_PER_DAY", 2, raising=False)
    monkeypatch.setattr("app.api.deps.rate_limit.settings.DEBUG", False, raising=False)
    user = SimpleNamespace(
        id="user-2",
        tier="free",
        created_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
    )

    await rate_limit_advisor(user)
    await rate_limit_advisor(user)

    with pytest.raises(Exception) as exc_info:
        await rate_limit_advisor(user)

    assert getattr(exc_info.value, "status_code", None) == 429
