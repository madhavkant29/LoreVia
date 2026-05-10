from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.api.deps.rate_limit import (
    _bump_daily_bucket,
    _client_identifier,
    rate_limit_advisor,
    rate_limit_manuscript_import,
    rate_limit_upload,
    rate_limit_world_building_ai,
    rate_limit_world_building_upload,
)


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

    async def _fake_overflow_units(user_id, action, now=None):
        return 0

    monkeypatch.setattr("app.api.deps.rate_limit.get_redis", _fake_get_redis)
    monkeypatch.setattr(
        "app.api.deps.rate_limit.purchased_overflow_units_for_action_via_session",
        _fake_overflow_units,
    )
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
async def test_daily_bucket_allows_purchased_overflow_units(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    async def _fake_overflow_units(user_id, action, now=None):
        assert user_id == "user-overflow"
        assert action == "prediction"
        return 1

    monkeypatch.setattr("app.api.deps.rate_limit.get_redis", _fake_get_redis)
    monkeypatch.setattr(
        "app.api.deps.rate_limit.purchased_overflow_units_for_action_via_session",
        _fake_overflow_units,
    )
    monkeypatch.setattr(
        "app.api.deps.rate_limit._current_utc",
        lambda now=None: datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    )

    await _bump_daily_bucket("user-overflow", "prediction", 2)
    await _bump_daily_bucket("user-overflow", "prediction", 2)
    await _bump_daily_bucket("user-overflow", "prediction", 2)

    with pytest.raises(Exception) as exc_info:
        await _bump_daily_bucket("user-overflow", "prediction", 2)

    assert getattr(exc_info.value, "status_code", None) == 429


@pytest.mark.asyncio
async def test_trial_authoring_surfaces_share_one_daily_bucket(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    async def _fake_limit_for_user(user_id, field, default):
        return default

    async def _fake_overflow_units(user_id, action, now=None):
        return 0

    monkeypatch.setattr("app.api.deps.rate_limit.get_redis", _fake_get_redis)
    monkeypatch.setattr("app.api.deps.rate_limit._limit_for_user", _fake_limit_for_user)
    monkeypatch.setattr(
        "app.api.deps.rate_limit.purchased_overflow_units_for_action_via_session",
        _fake_overflow_units,
    )
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limiter", "field", "expected_message"),
    [
        (rate_limit_upload, "uploads_per_hour", "Upload rate limit exceeded"),
        (rate_limit_manuscript_import, "manuscript_imports_per_hour", "Manuscript import rate limit exceeded"),
        (rate_limit_world_building_upload, "world_building_uploads_per_hour", "World-building upload rate limit exceeded"),
        (rate_limit_world_building_ai, "world_building_ai_per_hour", "World-building analysis rate limit exceeded"),
    ],
)
async def test_window_rate_limits_block_after_threshold(monkeypatch, limiter, field, expected_message):
    class _FakePipeline:
        def __init__(self, redis):
            self.redis = redis
            self.ops: list[tuple[str, tuple]] = []

        def zremrangebyscore(self, key, minimum, maximum):
            self.ops.append(("zremrangebyscore", (key, minimum, maximum)))
            return self

        def zadd(self, key, mapping):
            self.ops.append(("zadd", (key, mapping)))
            return self

        def zcard(self, key):
            self.ops.append(("zcard", (key,)))
            return self

        def expire(self, key, ttl):
            self.ops.append(("expire", (key, ttl)))
            return self

        async def execute(self):
            results = []
            for op_name, args in self.ops:
                if op_name == "zremrangebyscore":
                    key, _minimum, maximum = args
                    members = self.redis.zsets.setdefault(key, [])
                    original_size = len(members)
                    self.redis.zsets[key] = [(member, score) for member, score in members if score > maximum]
                    results.append(original_size - len(self.redis.zsets[key]))
                elif op_name == "zadd":
                    key, mapping = args
                    members = self.redis.zsets.setdefault(key, [])
                    for member, score in mapping.items():
                        members.append((member, score))
                    results.append(len(mapping))
                elif op_name == "zcard":
                    key = args[0]
                    results.append(len(self.redis.zsets.get(key, [])))
                elif op_name == "expire":
                    results.append(True)
            return results

    class _FakeWindowRedis:
        def __init__(self) -> None:
            self.zsets: dict[str, list[tuple[str, float]]] = {}

        def pipeline(self):
            return _FakePipeline(self)

    fake_redis = _FakeWindowRedis()

    async def _fake_get_redis():
        return fake_redis

    async def _fake_limit_for_user(user_id, field_name, default):
        assert user_id == "user-3"
        assert field_name == field
        return 2

    monkeypatch.setattr("app.api.deps.rate_limit.get_redis", _fake_get_redis)
    monkeypatch.setattr("app.api.deps.rate_limit._limit_for_user", _fake_limit_for_user)

    user = SimpleNamespace(id="user-3")

    await limiter(user)
    await limiter(user)

    with pytest.raises(Exception) as exc_info:
        await limiter(user)

    assert getattr(exc_info.value, "status_code", None) == 429
    assert expected_message in str(exc_info.value.detail)
