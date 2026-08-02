import uuid

import pytest
from redis.exceptions import RedisError

from app.models.user import UserRateLimitOverride
from app.utils import rate_limit_utils


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _Db:
    def __init__(self, value):
        self.value = value
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        return _Result(self.value)


@pytest.mark.asyncio
async def test_limit_for_user_uses_cached_positive_override(monkeypatch):
    user_id = uuid.uuid4()

    async def fake_cache_get(key):
        assert key == rate_limit_utils.rate_limit_override_cache_key(user_id)
        return {"api_per_minute": 42}

    monkeypatch.setattr(rate_limit_utils, "cache_get", fake_cache_get)
    db = _Db(None)

    assert await rate_limit_utils.limit_for_user(db, user_id, "api_per_minute", 300) == 42
    assert db.execute_count == 0


@pytest.mark.asyncio
async def test_limit_for_user_uses_negative_cache_without_db(monkeypatch):
    user_id = uuid.uuid4()

    async def fake_cache_get(_key):
        return rate_limit_utils._NO_OVERRIDE

    monkeypatch.setattr(rate_limit_utils, "cache_get", fake_cache_get)
    db = _Db(None)

    assert await rate_limit_utils.limit_for_user(db, user_id, "api_per_minute", 300) == 300
    assert db.execute_count == 0


@pytest.mark.asyncio
async def test_limit_for_user_caches_database_override(monkeypatch):
    user_id = uuid.uuid4()
    stored = {}
    override = UserRateLimitOverride(user_id=user_id, api_per_minute=75)

    async def fake_cache_get(_key):
        return None

    async def fake_cache_set(key, value, ttl):
        stored["key"] = key
        stored["value"] = value
        stored["ttl"] = ttl

    monkeypatch.setattr(rate_limit_utils, "cache_get", fake_cache_get)
    monkeypatch.setattr(rate_limit_utils, "cache_set", fake_cache_set)
    db = _Db(override)

    assert await rate_limit_utils.limit_for_user(db, user_id, "api_per_minute", 300) == 75
    assert db.execute_count == 1
    assert stored == {
        "key": rate_limit_utils.rate_limit_override_cache_key(user_id),
        "value": {
            "api_per_minute": 75,
            **{
                field: None
                for field in rate_limit_utils._OVERRIDE_FIELDS
                if field != "api_per_minute"
            },
        },
        "ttl": rate_limit_utils.RATE_LIMIT_OVERRIDE_CACHE_TTL_SECONDS,
    }


@pytest.mark.asyncio
async def test_limit_for_user_treats_redis_cache_get_failure_as_miss(monkeypatch):
    user_id = uuid.uuid4()
    override = UserRateLimitOverride(user_id=user_id, api_per_minute=81)

    async def fail_cache_get(_key):
        raise RedisError("redis unavailable")

    async def fake_cache_set(_key, _value, _ttl):
        return None

    monkeypatch.setattr(rate_limit_utils, "cache_get", fail_cache_get)
    monkeypatch.setattr(rate_limit_utils, "cache_set", fake_cache_set)
    db = _Db(override)

    assert await rate_limit_utils.limit_for_user(db, user_id, "api_per_minute", 300) == 81
    assert db.execute_count == 1


@pytest.mark.asyncio
async def test_limit_for_user_propagates_unexpected_cache_get_failure(monkeypatch):
    user_id = uuid.uuid4()

    async def fail_cache_get(_key):
        raise RuntimeError("bug in cache client")

    monkeypatch.setattr(rate_limit_utils, "cache_get", fail_cache_get)
    db = _Db(None)

    with pytest.raises(RuntimeError, match="bug in cache client"):
        await rate_limit_utils.limit_for_user(db, user_id, "api_per_minute", 300)


@pytest.mark.asyncio
async def test_limit_for_user_propagates_unexpected_cache_set_failure(monkeypatch):
    user_id = uuid.uuid4()
    override = UserRateLimitOverride(user_id=user_id, api_per_minute=91)

    async def fake_cache_get(_key):
        return None

    async def fail_cache_set(_key, _value, _ttl):
        raise RuntimeError("serialization regression")

    monkeypatch.setattr(rate_limit_utils, "cache_get", fake_cache_get)
    monkeypatch.setattr(rate_limit_utils, "cache_set", fail_cache_set)
    db = _Db(override)

    with pytest.raises(RuntimeError, match="serialization regression"):
        await rate_limit_utils.limit_for_user(db, user_id, "api_per_minute", 300)
