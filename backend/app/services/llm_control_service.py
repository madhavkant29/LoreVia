from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.models.user import LlmUsageEvent, User
from app.utils.llm_pricing import calculate_llm_cost
from app.utils.llm_usage_utils import assert_llm_token_capacity

_ACQUIRE_SCRIPT = """
local rate_key = KEYS[1]
local concurrency_key = KEYS[2]
local now = tonumber(ARGV[1])
local cutoff = now - 60000
local reservation = ARGV[2]
local tokens = tonumber(ARGV[3])
local rpm = tonumber(ARGV[4])
local tpm = tonumber(ARGV[5])
local max_concurrency = tonumber(ARGV[6])
redis.call('ZREMRANGEBYSCORE', rate_key, '-inf', cutoff)
local entries = redis.call('ZRANGEBYSCORE', rate_key, cutoff, '+inf')
local used_tokens = 0
for _, member in ipairs(entries) do
  local token_text = string.match(member, '|(%d+)$')
  if token_text then used_tokens = used_tokens + tonumber(token_text) end
end
if #entries >= rpm or used_tokens + tokens > tpm then return {0, 60} end
if redis.call('SCARD', concurrency_key) >= max_concurrency then return {0, 5} end
redis.call('ZADD', rate_key, now, reservation .. '|' .. tokens)
redis.call('PEXPIRE', rate_key, 61000)
redis.call('SADD', concurrency_key, reservation)
redis.call('EXPIRE', concurrency_key, 1800)
return {1, 0}
"""
_COORDINATION_READY_KEY = "llm:coordination:ready"
_COORDINATION_REHYDRATE_LOCK_KEY = "llm:coordination:rehydrate_lock"
_CONCURRENCY_TTL_SECONDS = 30 * 60

log = logging.getLogger("lorevia.llm_control")


@dataclass(frozen=True)
class LlmReservation:
    id: str
    operation: str
    user_id: uuid.UUID


def _limits(operation: str) -> tuple[int, int]:
    if operation == "embedding":
        return settings.LLM_EMBEDDING_RPM_LIMIT, settings.LLM_EMBEDDING_TPM_LIMIT
    return settings.LLM_CHAT_RPM_LIMIT, settings.LLM_CHAT_TPM_LIMIT


async def rehydrate_llm_coordination_state(*, force: bool = False) -> dict[str, int | bool]:
    redis = await get_redis()
    if not force and await redis.exists(_COORDINATION_READY_KEY):
        return {"rehydrated": False, "active_reservations": 0, "stale_released": 0}
    owner = str(uuid.uuid4())
    acquired = await redis.set(
        _COORDINATION_REHYDRATE_LOCK_KEY,
        owner,
        nx=True,
        ex=30,
    )
    if not acquired:
        raise HTTPException(
            503,
            "LLM coordination is rebuilding. Retry shortly.",
            headers={"Retry-After": "2"},
        )
    try:
        now = datetime.now(UTC)
        active_cutoff = now - timedelta(seconds=_CONCURRENCY_TTL_SECONDS)
        rate_cutoff = now - timedelta(seconds=60)
        async with AsyncSessionLocal() as db:
            reserved = (
                (
                    await db.execute(
                        select(LlmUsageEvent).where(LlmUsageEvent.status == "reserved")
                    )
                )
                .scalars()
                .all()
            )
            active: list[LlmUsageEvent] = []
            stale_released = 0
            for event in reserved:
                created_at = event.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)
                if created_at < active_cutoff:
                    event.status = "failed"
                    event.total_tokens = 0
                    stale_released += 1
                else:
                    active.append(event)
            if stale_released:
                await db.commit()
        for event in active:
            created_at = event.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            reservation_id = str(event.reservation_id or event.id)
            await redis.sadd(f"llm:concurrency:{event.user_id}", reservation_id)
            await redis.expire(
                f"llm:concurrency:{event.user_id}", _CONCURRENCY_TTL_SECONDS
            )
            if created_at >= rate_cutoff:
                member = f"{reservation_id}|{max(int(event.estimated_tokens or 0), 1)}"
                rate_key = f"llm:rate:{event.operation}"
                await redis.zadd(rate_key, {member: int(created_at.timestamp() * 1000)})
                await redis.pexpire(rate_key, 61_000)
        await redis.set(_COORDINATION_READY_KEY, "1")
        return {
            "rehydrated": True,
            "active_reservations": len(active),
            "stale_released": stale_released,
        }
    finally:
        await redis.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end",
            1,
            _COORDINATION_REHYDRATE_LOCK_KEY,
            owner,
        )


async def reserve_llm_call(
    *,
    user_id: uuid.UUID,
    estimated_tokens: int,
    feature: str,
    operation: str,
    model: str,
    book_id: uuid.UUID | None,
) -> LlmReservation:
    try:
        await rehydrate_llm_coordination_state()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            503,
            "LLM coordination is temporarily unavailable.",
            headers={"Retry-After": "2"},
        ) from exc
    reservation_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(user_id)))))
        user = await db.get(User, user_id)
        await assert_llm_token_capacity(
            db, user=user, estimated_tokens=estimated_tokens, limit_subject="LLM usage"
        )
        db.add(
            LlmUsageEvent(
                reservation_id=reservation_id,
                status="reserved",
                user_id=user_id,
                book_id=book_id,
                provider="openai",
                model=model,
                operation=operation,
                feature=feature[:120],
                estimated_tokens=estimated_tokens,
                total_tokens=estimated_tokens,
            )
        )
        await db.commit()
    rpm, tpm = _limits(operation)
    redis = await get_redis()
    try:
        allowed, retry_after = await redis.eval(
            _ACQUIRE_SCRIPT,
            2,
            f"llm:rate:{operation}",
            f"llm:concurrency:{user_id}",
            int(time.time() * 1000),
            reservation_id,
            max(estimated_tokens, 1),
            rpm,
            tpm,
            settings.LLM_MAX_CONCURRENT_CALLS_PER_USER,
        )
    except Exception as exc:
        async with AsyncSessionLocal() as db:
            event = await db.scalar(
                select(LlmUsageEvent).where(LlmUsageEvent.reservation_id == reservation_id)
            )
            if event is not None:
                event.status = "failed"
                event.total_tokens = 0
                await db.commit()
        raise HTTPException(503, "LLM coordination is temporarily unavailable.") from exc
    if not int(allowed):
        await fail_llm_reservation(LlmReservation(reservation_id, operation, user_id))
        raise HTTPException(
            429,
            "LLM capacity is temporarily busy. Retry shortly.",
            headers={"Retry-After": str(int(retry_after))},
        )
    return LlmReservation(reservation_id, operation, user_id)


async def finish_llm_reservation(reservation: LlmReservation, response: Any) -> None:
    usage = getattr(response, "usage", None)
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or prompt + completion)
    details = getattr(usage, "prompt_tokens_details", None)
    cached = int(getattr(details, "cached_tokens", 0) or 0)
    async with AsyncSessionLocal() as db:
        event = (
            await db.execute(
                select(LlmUsageEvent).where(LlmUsageEvent.reservation_id == reservation.id)
            )
        ).scalar_one_or_none()
        if event is not None:
            input_cost, output_cost, total_cost, version = calculate_llm_cost(
                event.model,
                prompt_tokens=prompt,
                completion_tokens=completion,
                cached_prompt_tokens=cached,
            )
            event.status = "succeeded"
            event.prompt_tokens = prompt
            event.completion_tokens = completion
            event.total_tokens = total
            event.cached_prompt_tokens = cached
            event.cached = cached > 0
            event.input_cost_usd = input_cost
            event.output_cost_usd = output_cost
            event.total_cost_usd = total_cost
            event.pricing_version = version
            await db.commit()
    await _release_redis_concurrency(reservation)


async def finish_llm_reservation_counts(
    reservation: LlmReservation,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cached_prompt_tokens: int = 0,
) -> None:
    async with AsyncSessionLocal() as db:
        event = (
            await db.execute(
                select(LlmUsageEvent).where(LlmUsageEvent.reservation_id == reservation.id)
            )
        ).scalar_one_or_none()
        if event is not None:
            input_cost, output_cost, total_cost, version = calculate_llm_cost(
                event.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_prompt_tokens=cached_prompt_tokens,
            )
            event.status = "succeeded"
            event.prompt_tokens = max(prompt_tokens, 0)
            event.completion_tokens = max(completion_tokens, 0)
            event.total_tokens = max(total_tokens, 0)
            event.cached_prompt_tokens = max(cached_prompt_tokens, 0)
            event.cached = cached_prompt_tokens > 0
            event.input_cost_usd = input_cost
            event.output_cost_usd = output_cost
            event.total_cost_usd = total_cost
            event.pricing_version = version
            await db.commit()
    await _release_redis_concurrency(reservation)


async def fail_llm_reservation(reservation: LlmReservation) -> None:
    async with AsyncSessionLocal() as db:
        event = (
            await db.execute(
                select(LlmUsageEvent).where(LlmUsageEvent.reservation_id == reservation.id)
            )
        ).scalar_one_or_none()
        if event is not None:
            event.status = "failed"
            event.total_tokens = 0
            await db.commit()
    await _release_redis_concurrency(reservation)


async def _release_redis_concurrency(reservation: LlmReservation) -> None:
    try:
        redis = await get_redis()
        await redis.srem(f"llm:concurrency:{reservation.user_id}", reservation.id)
    except Exception:
        # PostgreSQL is authoritative. A Redis restart rehydrates only still-reserved calls.
        log.warning(
            "llm_concurrency_release_failed reservation_id=%s",
            reservation.id,
            exc_info=True,
        )
