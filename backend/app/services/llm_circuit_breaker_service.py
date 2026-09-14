from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis

log = logging.getLogger("lorevia.llm_circuit_breaker")


@dataclass(frozen=True)
class ProviderCircuitPermit:
    provider: str
    model: str
    probe_token: str | None = None
    previous_cooldown_seconds: int = 0

    @property
    def is_probe(self) -> bool:
        return self.probe_token is not None


def _scope(provider: str, model: str) -> str:
    return f"{provider}:{model}".replace(" ", "_")


def _state_key(provider: str, model: str) -> str:
    return f"llm:provider_breaker:{_scope(provider, model)}:state"


def _failure_key(provider: str, model: str) -> str:
    return f"llm:provider_breaker:{_scope(provider, model)}:failures"


def _probe_key(provider: str, model: str) -> str:
    return f"llm:provider_breaker:{_scope(provider, model)}:probe"


def _decode_json(value: object) -> dict:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _capacity_error(retry_after: int) -> HTTPException:
    return HTTPException(
        503,
        "LLM provider capacity is temporarily unavailable. Retry shortly.",
        headers={"Retry-After": str(max(retry_after, 1))},
    )


async def acquire_provider_circuit_permit(
    *,
    provider: str,
    model: str,
) -> ProviderCircuitPermit:
    try:
        redis = await get_redis()
        state = _decode_json(await redis.get(_state_key(provider, model)))
        if not state:
            return ProviderCircuitPermit(provider, model)
        now = int(time.time())
        open_until = int(state.get("open_until") or 0)
        cooldown = int(
            state.get("cooldown_seconds") or settings.LLM_PROVIDER_BREAKER_INITIAL_COOLDOWN_SECONDS
        )
        if open_until > now:
            raise _capacity_error(open_until - now)
        probe_token = str(uuid.uuid4())
        acquired = await redis.set(
            _probe_key(provider, model),
            probe_token,
            nx=True,
            ex=max(cooldown, 30),
        )
        if not acquired:
            raise _capacity_error(5)
        log.warning(
            "llm_provider_circuit_half_open provider=%s model=%s cooldown_seconds=%s",
            provider,
            model,
            cooldown,
        )
        return ProviderCircuitPermit(provider, model, probe_token, cooldown)
    except HTTPException:
        raise
    except RedisError as exc:
        raise HTTPException(
            503,
            "LLM coordination is temporarily unavailable.",
            headers={"Retry-After": "2"},
        ) from exc


async def record_provider_success(permit: ProviderCircuitPermit) -> None:
    try:
        redis = await get_redis()
        if permit.is_probe:
            await redis.delete(
                _state_key(permit.provider, permit.model),
                _probe_key(permit.provider, permit.model),
                _failure_key(permit.provider, permit.model),
            )
        else:
            await redis.delete(_failure_key(permit.provider, permit.model))
    except RedisError:
        return


async def release_provider_circuit_permit(permit: ProviderCircuitPermit) -> None:
    """Release an unused half-open probe without changing breaker state."""

    if not permit.is_probe:
        return
    try:
        redis = await get_redis()
        await redis.delete(_probe_key(permit.provider, permit.model))
    except RedisError:
        return


async def record_provider_failure(
    permit: ProviderCircuitPermit,
    *,
    transient: bool,
) -> None:
    try:
        redis = await get_redis()
        if not transient:
            if permit.is_probe:
                await redis.delete(
                    _state_key(permit.provider, permit.model),
                    _probe_key(permit.provider, permit.model),
                )
            return
        now = int(time.time())
        initial = settings.LLM_PROVIDER_BREAKER_INITIAL_COOLDOWN_SECONDS
        maximum = settings.LLM_PROVIDER_BREAKER_MAX_COOLDOWN_SECONDS
        if permit.is_probe:
            cooldown = min(max(permit.previous_cooldown_seconds * 2, initial), maximum)
            await redis.set(
                _state_key(permit.provider, permit.model),
                json.dumps({"open_until": now + cooldown, "cooldown_seconds": cooldown}),
            )
            await redis.delete(_probe_key(permit.provider, permit.model))
            log.warning(
                "llm_provider_circuit_reopened provider=%s model=%s cooldown_seconds=%s",
                permit.provider,
                permit.model,
                cooldown,
            )
            return
        failure_key = _failure_key(permit.provider, permit.model)
        member = f"{now}:{uuid.uuid4()}"
        window = settings.LLM_PROVIDER_BREAKER_WINDOW_SECONDS
        await redis.zadd(failure_key, {member: now})
        await redis.zremrangebyscore(failure_key, "-inf", now - window)
        await redis.expire(failure_key, window + 5)
        failures = int(await redis.zcard(failure_key))
        if failures >= settings.LLM_PROVIDER_BREAKER_FAILURES:
            await redis.set(
                _state_key(permit.provider, permit.model),
                json.dumps({"open_until": now + initial, "cooldown_seconds": initial}),
            )
            await redis.delete(failure_key)
            log.warning(
                "llm_provider_circuit_opened provider=%s model=%s failures=%s cooldown_seconds=%s",
                permit.provider,
                permit.model,
                failures,
                initial,
            )
    except RedisError:
        return


async def provider_circuit_is_open(*, provider: str, model: str) -> bool:
    try:
        redis = await get_redis()
        state = _decode_json(await redis.get(_state_key(provider, model)))
        return int(state.get("open_until") or 0) > int(time.time())
    except RedisError:
        return True
