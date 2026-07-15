from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import delete

from app.models.user import LlmUsageEvent, User
from app.services import llm_control_service


class _SessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_args):
        return None


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.sorted_sets: dict[str, dict[str, int]] = {}

    async def exists(self, key):
        return key in self.values

    async def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True

    async def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(str(value))

    async def expire(self, *_args):
        return True

    async def zadd(self, key, values):
        self.sorted_sets.setdefault(key, {}).update(values)

    async def pexpire(self, *_args):
        return True

    async def eval(self, _script, _key_count, key, owner):
        if self.values.get(key) == owner:
            self.values.pop(key, None)
            return 1
        return 0


async def test_rehydrate_llm_coordination_rebuilds_active_and_releases_stale(
    db, monkeypatch
):
    await db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.status == "reserved"))
    await db.commit()

    user = User(
        email=f"rehydrate-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"rehydrate{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    now = datetime.now(UTC)
    active = LlmUsageEvent(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        operation="chat",
        feature="advisor",
        reservation_id=str(uuid.uuid4()),
        status="reserved",
        estimated_tokens=120,
        total_tokens=120,
        created_at=now - timedelta(seconds=20),
    )
    stale = LlmUsageEvent(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        operation="chat",
        feature="advisor",
        reservation_id=str(uuid.uuid4()),
        status="reserved",
        estimated_tokens=80,
        total_tokens=80,
        created_at=now - timedelta(hours=1),
    )
    db.add_all([active, stale])
    await db.commit()
    redis = _FakeRedis()
    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(redis))
    monkeypatch.setattr(llm_control_service, "AsyncSessionLocal", lambda: _SessionContext(db))

    result = await llm_control_service.rehydrate_llm_coordination_state(force=True)

    assert result == {"rehydrated": True, "active_reservations": 1, "stale_released": 1}
    assert active.reservation_id in redis.sets[f"llm:concurrency:{user.id}"]
    assert f"{active.reservation_id}|120" in redis.sorted_sets["llm:rate:chat"]
    await db.refresh(stale)
    assert stale.status == "failed"
    assert stale.total_tokens == 0


async def _async_value(value):
    return value


async def test_redis_cleanup_failure_does_not_fail_completed_call(monkeypatch):
    class BrokenRedis:
        async def srem(self, *_args):
            raise RedisError("redis unavailable")

    monkeypatch.setattr(
        llm_control_service, "get_redis", lambda: _async_value(BrokenRedis())
    )
    reservation = llm_control_service.LlmReservation(
        id=str(uuid.uuid4()), operation="chat", user_id=uuid.uuid4()
    )

    await llm_control_service._release_redis_concurrency(reservation)


async def test_redis_cleanup_unexpected_failure_propagates(monkeypatch):
    class BrokenRedis:
        async def srem(self, *_args):
            raise RuntimeError("programming error")

    monkeypatch.setattr(
        llm_control_service, "get_redis", lambda: _async_value(BrokenRedis())
    )
    reservation = llm_control_service.LlmReservation(
        id=str(uuid.uuid4()), operation="chat", user_id=uuid.uuid4()
    )

    with pytest.raises(RuntimeError, match="programming error"):
        await llm_control_service._release_redis_concurrency(reservation)


async def test_reservation_returns_retryable_503_when_redis_is_unavailable(monkeypatch):
    async def _fail_rehydrate(*, force=False):
        raise RedisError("redis unavailable")

    monkeypatch.setattr(
        llm_control_service, "rehydrate_llm_coordination_state", _fail_rehydrate
    )

    with pytest.raises(HTTPException) as exc_info:
        await llm_control_service.reserve_llm_call(
            user_id=uuid.uuid4(),
            estimated_tokens=100,
            feature="advisor",
            operation="chat",
            model="gpt-4o-mini",
            book_id=None,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.headers == {"Retry-After": "2"}


async def test_reservation_rehydrate_unexpected_failure_propagates(monkeypatch):
    async def _fail_rehydrate(*, force=False):
        raise RuntimeError("programming error")

    monkeypatch.setattr(
        llm_control_service, "rehydrate_llm_coordination_state", _fail_rehydrate
    )

    with pytest.raises(RuntimeError, match="programming error"):
        await llm_control_service.reserve_llm_call(
            user_id=uuid.uuid4(),
            estimated_tokens=100,
            feature="advisor",
            operation="chat",
            model="gpt-4o-mini",
            book_id=None,
        )
