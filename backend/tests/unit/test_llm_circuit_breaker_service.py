from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from app.services import llm_circuit_breaker_service as breaker


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.sorted_sets.pop(key, None)

    async def zadd(self, key, mapping):
        self.sorted_sets.setdefault(key, {}).update(
            {str(member): float(score) for member, score in mapping.items()}
        )

    async def zremrangebyscore(self, key, minimum, maximum):
        lower = float("-inf") if minimum == "-inf" else float(minimum)
        upper = float("inf") if maximum == "+inf" else float(maximum)
        entries = self.sorted_sets.setdefault(key, {})
        removed = [member for member, score in entries.items() if lower <= score <= upper]
        for member in removed:
            del entries[member]
        return len(removed)

    async def expire(self, *_args):
        return True

    async def zcard(self, key):
        return len(self.sorted_sets.get(key, {}))


async def _async_value(value):
    return value


@pytest.fixture
def fake_breaker(monkeypatch):
    redis = _FakeRedis()
    now = [1_000]
    monkeypatch.setattr(breaker, "get_redis", lambda: _async_value(redis))
    monkeypatch.setattr(breaker.time, "time", lambda: now[0])
    monkeypatch.setattr(breaker.settings, "LLM_PROVIDER_BREAKER_FAILURES", 5)
    monkeypatch.setattr(breaker.settings, "LLM_PROVIDER_BREAKER_WINDOW_SECONDS", 30)
    monkeypatch.setattr(breaker.settings, "LLM_PROVIDER_BREAKER_INITIAL_COOLDOWN_SECONDS", 60)
    monkeypatch.setattr(breaker.settings, "LLM_PROVIDER_BREAKER_MAX_COOLDOWN_SECONDS", 900)
    return redis, now


@pytest.mark.asyncio
async def test_circuit_opens_after_five_transient_failures_and_allows_one_probe(fake_breaker):
    _redis, now = fake_breaker
    for _ in range(5):
        permit = await breaker.acquire_provider_circuit_permit(
            provider="openai", model="gpt-4o-mini"
        )
        await breaker.record_provider_failure(permit, transient=True)

    assert await breaker.provider_circuit_is_open(provider="openai", model="gpt-4o-mini")
    with pytest.raises(HTTPException) as open_error:
        await breaker.acquire_provider_circuit_permit(provider="openai", model="gpt-4o-mini")
    assert open_error.value.status_code == 503
    assert open_error.value.headers == {"Retry-After": "60"}

    now[0] += 60
    probe = await breaker.acquire_provider_circuit_permit(provider="openai", model="gpt-4o-mini")
    assert probe.is_probe
    with pytest.raises(HTTPException):
        await breaker.acquire_provider_circuit_permit(provider="openai", model="gpt-4o-mini")

    await breaker.record_provider_success(probe)
    assert not await breaker.provider_circuit_is_open(provider="openai", model="gpt-4o-mini")
    assert not (
        await breaker.acquire_provider_circuit_permit(provider="openai", model="gpt-4o-mini")
    ).is_probe


@pytest.mark.asyncio
async def test_failed_half_open_probe_doubles_cooldown_up_to_cap(fake_breaker):
    redis, now = fake_breaker
    state_key = breaker._state_key("openai", "gpt-4o-mini")
    redis.values[state_key] = json.dumps({"open_until": now[0], "cooldown_seconds": 60})

    probe = await breaker.acquire_provider_circuit_permit(provider="openai", model="gpt-4o-mini")
    await breaker.record_provider_failure(probe, transient=True)
    state = json.loads(redis.values[state_key])
    assert state == {"open_until": 1_120, "cooldown_seconds": 120}

    now[0] = state["open_until"]
    redis.values[state_key] = json.dumps({"open_until": now[0], "cooldown_seconds": 900})
    capped_probe = await breaker.acquire_provider_circuit_permit(
        provider="openai", model="gpt-4o-mini"
    )
    await breaker.record_provider_failure(capped_probe, transient=True)
    capped_state = json.loads(redis.values[state_key])
    assert capped_state["cooldown_seconds"] == 900
    assert capped_state["open_until"] == now[0] + 900


@pytest.mark.asyncio
async def test_non_transient_failure_does_not_open_circuit(fake_breaker):
    redis, _now = fake_breaker
    permit = await breaker.acquire_provider_circuit_permit(provider="openai", model="gpt-4o-mini")
    await breaker.record_provider_failure(permit, transient=False)

    assert redis.sorted_sets == {}
    assert not await breaker.provider_circuit_is_open(provider="openai", model="gpt-4o-mini")
