from __future__ import annotations

import logging
import math
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.models.user import LlmUsageEvent, ProcessingUsageEvent, User
from app.utils.billing_utils import ARCHITECT_TIER, AUTHOR_TIER, billing_access_tier
from app.utils.llm_pricing import (
    UnsupportedLlmPricingError,
    calculate_llm_cost,
    calculate_llm_reservation_cost,
)
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
_SYSTEM_RATE_ACQUIRE_SCRIPT = """
local rate_key = KEYS[1]
local now = tonumber(ARGV[1])
local cutoff = now - 60000
local request_id = ARGV[2]
local tokens = tonumber(ARGV[3])
local rpm = tonumber(ARGV[4])
local tpm = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', rate_key, '-inf', cutoff)
local entries = redis.call('ZRANGEBYSCORE', rate_key, cutoff, '+inf')
local used_tokens = 0
for _, member in ipairs(entries) do
  local token_text = string.match(member, '|(%d+)$')
  if token_text then used_tokens = used_tokens + tonumber(token_text) end
end
if #entries >= rpm or used_tokens + tokens > tpm then return {0, 60} end
redis.call('ZADD', rate_key, now, request_id .. '|' .. tokens)
redis.call('PEXPIRE', rate_key, 61000)
return {1, 0}
"""
_COORDINATION_READY_KEY = "llm:coordination:ready"
_COORDINATION_REHYDRATE_LOCK_KEY = "llm:coordination:rehydrate_lock"
_CONCURRENCY_TTL_SECONDS = 30 * 60
PROCESSING_BUDGET_CLASS = "processing"
INTERACTIVE_BUDGET_CLASS = "interactive"
VALID_BUDGET_CLASSES = {PROCESSING_BUDGET_CLASS, INTERACTIVE_BUDGET_CLASS}
AUTHOR_ALLOWED_MODELS_BY_OPERATION = {
    "chat": {"gpt-4o-mini"},
    "embedding": {"text-embedding-3-small"},
}

log = logging.getLogger("lorevia.llm_control")


@dataclass(frozen=True)
class LlmReservation:
    id: str
    operation: str
    user_id: uuid.UUID
    provider: str = "openai"
    model: str = ""
    estimated_cost_usd: Decimal = Decimal("0")


@dataclass(frozen=True)
class LlmCostCapacitySummary:
    committed_cost_usd: Decimal
    reservation_ceiling_usd: Decimal | None
    provider_cost_limit_usd: Decimal | None
    protected_processing_cost_usd: Decimal
    available_cost_usd: Decimal | None
    usage_fraction: float
    available: bool
    resets_at: datetime


@dataclass(frozen=True)
class ProcessingCostEfficiencySummary:
    p95_cost_per_100k_words_usd: float
    total_processing_cost_usd: float
    total_processed_words: int
    sampled_users: int
    exceeds_acceptance_threshold: bool
    resets_at: datetime


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    start = current.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return start, end


def _decimal_setting(name: str) -> Decimal:
    return Decimal(str(getattr(settings, name)))


async def _committed_cost_usd(
    db: Any,
    *,
    user_id: uuid.UUID,
    month_start: datetime,
    month_end: datetime | None = None,
) -> Decimal:
    conditions = [
        LlmUsageEvent.user_id == user_id,
        LlmUsageEvent.created_at >= month_start,
    ]
    if month_end is not None:
        conditions.append(LlmUsageEvent.created_at < month_end)
    value = await db.scalar(
        select(func.coalesce(func.sum(LlmUsageEvent.total_cost_usd), 0)).where(*conditions)
    )
    return Decimal(str(value or 0))


async def _protected_processing_cost_usd(
    db: Any,
    user: User,
    *,
    reserve_setting: str,
    now: datetime | None = None,
) -> Decimal:
    from app.services.processing_allowance_service import summarize_processing_allowances

    allowance = await summarize_processing_allowances(db, user)
    if allowance.monthly_processed_word_limit <= 0:
        return Decimal("0")
    month_start, month_end = _month_bounds(now or datetime.now(UTC))
    completed_words = int(
        await db.scalar(
            select(func.coalesce(func.sum(ProcessingUsageEvent.word_count), 0)).where(
                ProcessingUsageEvent.user_id == user.id,
                ProcessingUsageEvent.status == "consumed",
                ProcessingUsageEvent.reserved_at >= month_start,
                ProcessingUsageEvent.reserved_at < month_end,
            )
        )
        or 0
    )
    remaining_words = max(allowance.monthly_processed_word_limit - completed_words, 0)
    remaining_ratio = Decimal(remaining_words) / Decimal(allowance.monthly_processed_word_limit)
    return _decimal_setting(reserve_setting) * remaining_ratio


def _paid_tier_cost_settings(tier: str) -> tuple[str, str, str] | None:
    if tier == AUTHOR_TIER:
        return (
            "AUTHOR_LLM_PROVIDER_COST_LIMIT_USD",
            "AUTHOR_LLM_RESERVATION_CEILING_USD",
            "AUTHOR_LLM_PROCESSING_RESERVE_USD",
        )
    if tier == ARCHITECT_TIER:
        return (
            "ARCHITECT_LLM_PROVIDER_COST_LIMIT_USD",
            "ARCHITECT_LLM_RESERVATION_CEILING_USD",
            "ARCHITECT_LLM_PROCESSING_RESERVE_USD",
        )
    return None


async def summarize_llm_cost_capacity(
    db: Any,
    *,
    user: User,
    budget_class: str = INTERACTIVE_BUDGET_CLASS,
    now: datetime | None = None,
) -> LlmCostCapacitySummary:
    if budget_class not in VALID_BUDGET_CLASSES:
        raise ValueError(f"Unsupported LLM budget class: {budget_class}")
    current = now or datetime.now(UTC)
    month_start, resets_at = _month_bounds(current)
    committed = await _committed_cost_usd(
        db,
        user_id=user.id,
        month_start=month_start,
        month_end=resets_at,
    )
    tier_settings = _paid_tier_cost_settings(billing_access_tier(user, current))
    if tier_settings is None:
        return LlmCostCapacitySummary(
            committed_cost_usd=committed,
            reservation_ceiling_usd=None,
            provider_cost_limit_usd=None,
            protected_processing_cost_usd=Decimal("0"),
            available_cost_usd=None,
            usage_fraction=0.0,
            available=True,
            resets_at=resets_at,
        )
    provider_limit_setting, ceiling_setting, reserve_setting = tier_settings
    provider_limit = _decimal_setting(provider_limit_setting)
    ceiling = min(
        _decimal_setting(ceiling_setting),
        provider_limit,
    )
    protected = (
        await _protected_processing_cost_usd(
            db,
            user,
            reserve_setting=reserve_setting,
            now=current,
        )
        if budget_class == INTERACTIVE_BUDGET_CLASS
        else Decimal("0")
    )
    effective_ceiling = max(ceiling - protected, Decimal("0"))
    available_cost = max(effective_ceiling - committed, Decimal("0"))
    usage_fraction = float(min(committed / ceiling, Decimal("1"))) if ceiling > 0 else 1.0
    return LlmCostCapacitySummary(
        committed_cost_usd=committed,
        reservation_ceiling_usd=ceiling,
        provider_cost_limit_usd=provider_limit,
        protected_processing_cost_usd=protected,
        available_cost_usd=available_cost,
        usage_fraction=usage_fraction,
        available=available_cost > 0,
        resets_at=resets_at,
    )


async def summarize_monthly_processing_cost_efficiency(
    db: Any,
    *,
    now: datetime | None = None,
) -> ProcessingCostEfficiencySummary:
    """Measure processing cost per 100K completed words for operational alerting."""

    current = now or datetime.now(UTC)
    month_start, resets_at = _month_bounds(current)
    cost_rows = (
        await db.execute(
            select(
                LlmUsageEvent.user_id,
                func.coalesce(func.sum(LlmUsageEvent.total_cost_usd), 0),
            )
            .where(
                LlmUsageEvent.status.in_(("succeeded", "failed")),
                LlmUsageEvent.created_at >= month_start,
                LlmUsageEvent.created_at < resets_at,
                LlmUsageEvent.metadata_json["budget_class"].as_string() == "processing",
            )
            .group_by(LlmUsageEvent.user_id)
        )
    ).all()
    word_rows = (
        await db.execute(
            select(
                ProcessingUsageEvent.user_id,
                func.coalesce(func.sum(ProcessingUsageEvent.word_count), 0),
            )
            .where(
                ProcessingUsageEvent.status == "consumed",
                ProcessingUsageEvent.reserved_at >= month_start,
                ProcessingUsageEvent.reserved_at < resets_at,
            )
            .group_by(ProcessingUsageEvent.user_id)
        )
    ).all()
    costs_by_user = {user_id: float(cost or 0) for user_id, cost in cost_rows}
    words_by_user = {user_id: int(words or 0) for user_id, words in word_rows}
    sampled_user_ids = {
        user_id
        for user_id, words in words_by_user.items()
        if words > 0 and user_id in costs_by_user
    }
    per_100k = sorted(
        costs_by_user[user_id] * 100_000 / words_by_user[user_id] for user_id in sampled_user_ids
    )
    p95 = per_100k[max(math.ceil(len(per_100k) * 0.95) - 1, 0)] if per_100k else 0.0
    threshold = 0.25
    exceeds_threshold = p95 > threshold
    if exceeds_threshold:
        log.warning(
            "llm_processing_cost_p95_exceeded p95_cost_per_100k_usd=%.6f threshold_usd=%.2f sampled_users=%s",
            p95,
            threshold,
            len(per_100k),
        )
    return ProcessingCostEfficiencySummary(
        p95_cost_per_100k_words_usd=round(p95, 6),
        total_processing_cost_usd=round(
            sum(costs_by_user[user_id] for user_id in sampled_user_ids),
            6,
        ),
        total_processed_words=sum(words_by_user[user_id] for user_id in sampled_user_ids),
        sampled_users=len(per_100k),
        exceeds_acceptance_threshold=exceeds_threshold,
        resets_at=resets_at,
    )


def _limits(operation: str) -> tuple[int, int]:
    if operation == "embedding":
        return settings.LLM_EMBEDDING_RPM_LIMIT, settings.LLM_EMBEDDING_TPM_LIMIT
    return settings.LLM_CHAT_RPM_LIMIT, settings.LLM_CHAT_TPM_LIMIT


async def enforce_system_llm_rate_limit(
    *,
    provider: str,
    model: str,
    operation: str,
    estimated_tokens: int,
) -> None:
    """Apply the shared provider budget to unattributed system-funded work."""

    rpm, tpm = _limits(operation)
    request_id = str(uuid.uuid4())
    safe_scope = f"{provider}:{operation}:{model}".replace(" ", "_")
    try:
        redis = await get_redis()
        allowed, retry_after = await redis.eval(
            _SYSTEM_RATE_ACQUIRE_SCRIPT,
            1,
            f"llm:system-rate:{safe_scope}",
            int(time.time() * 1000),
            request_id,
            max(int(estimated_tokens or 0), 1),
            rpm,
            tpm,
        )
    except RedisError as exc:
        raise HTTPException(
            503,
            "LLM coordination is temporarily unavailable.",
            headers={"Retry-After": "2"},
        ) from exc
    if not int(allowed):
        raise HTTPException(
            429,
            "System AI capacity is temporarily busy. Retry shortly.",
            headers={"Retry-After": str(max(int(retry_after), 1))},
        )


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
                (await db.execute(select(LlmUsageEvent).where(LlmUsageEvent.status == "reserved")))
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
                    event.total_tokens = max(
                        int(event.total_tokens or 0),
                        int(event.estimated_tokens or 0),
                    )
                    metadata = dict(event.metadata_json or {})
                    metadata["cost_disposition"] = "uncertain_provider_attempt"
                    metadata["stale_reservation"] = True
                    event.metadata_json = metadata
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
            await redis.expire(f"llm:concurrency:{event.user_id}", _CONCURRENCY_TTL_SECONDS)
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


async def settle_stale_llm_reservations(
    *,
    limit: int = 500,
    now: datetime | None = None,
) -> int:
    """Conservatively settle crashed provider calls and release stale concurrency slots."""

    current = now or datetime.now(UTC)
    cutoff = current - timedelta(seconds=_CONCURRENCY_TTL_SECONDS)
    stale_reservations: list[tuple[uuid.UUID, str]] = []
    async with AsyncSessionLocal() as db:
        events = list(
            (
                await db.execute(
                    select(LlmUsageEvent)
                    .where(
                        LlmUsageEvent.status == "reserved",
                        LlmUsageEvent.created_at < cutoff,
                    )
                    .order_by(LlmUsageEvent.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(max(1, int(limit or 500)))
                )
            )
            .scalars()
            .all()
        )
        for event in events:
            event.status = "failed"
            event.total_tokens = max(
                int(event.total_tokens or 0),
                int(event.estimated_tokens or 0),
            )
            event.metadata_json = {
                **dict(event.metadata_json or {}),
                "cost_disposition": "uncertain_provider_attempt",
                "stale_reservation": True,
            }
            stale_reservations.append((event.user_id, str(event.reservation_id or event.id)))
        if events:
            await db.commit()

    if stale_reservations:
        try:
            redis = await get_redis()
            for user_id, reservation_id in stale_reservations:
                await redis.srem(f"llm:concurrency:{user_id}", reservation_id)
        except RedisError:
            log.warning(
                "llm_stale_concurrency_cleanup_failed reservations=%s",
                len(stale_reservations),
                exc_info=True,
            )
        log.warning(
            "llm_stale_reservations_settled reservations=%s",
            len(stale_reservations),
        )
    return len(stale_reservations)


async def reserve_llm_call(
    *,
    user_id: uuid.UUID,
    estimated_prompt_tokens: int | None = None,
    estimated_completion_tokens: int = 0,
    estimated_tokens: int | None = None,
    feature: str,
    operation: str,
    model: str,
    book_id: uuid.UUID | None,
    provider: str = "openai",
    budget_class: str = INTERACTIVE_BUDGET_CLASS,
    metadata: dict[str, Any] | None = None,
) -> LlmReservation:
    if budget_class not in VALID_BUDGET_CLASSES:
        raise ValueError(f"Unsupported LLM budget class: {budget_class}")
    prompt_estimate = max(
        int(
            estimated_prompt_tokens
            if estimated_prompt_tokens is not None
            else estimated_tokens or 0
        ),
        0,
    )
    completion_estimate = max(int(estimated_completion_tokens or 0), 0)
    total_estimate = max(prompt_estimate + completion_estimate, 1)
    try:
        input_cost, output_cost, reserved_cost, pricing_version = calculate_llm_reservation_cost(
            model,
            estimated_prompt_tokens=prompt_estimate,
            estimated_completion_tokens=completion_estimate,
            provider=provider,
        )
    except UnsupportedLlmPricingError as exc:
        log.error(
            "llm_pricing_missing provider=%s model=%s feature=%s",
            provider,
            model,
            feature,
        )
        raise HTTPException(
            503,
            {
                "kind": "llm_configuration",
                "message": "AI processing is temporarily unavailable because its pricing configuration is incomplete.",
            },
        ) from exc
    try:
        await rehydrate_llm_coordination_state()
    except HTTPException:
        raise
    except (RedisError, SQLAlchemyError) as exc:
        raise HTTPException(
            503,
            "LLM coordination is temporarily unavailable.",
            headers={"Retry-After": "2"},
        ) from exc
    reservation_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(user_id)))))
        user = await db.get(User, user_id)
        if user is None:
            raise HTTPException(403, "User is required for LLM usage.")
        author_models = AUTHOR_ALLOWED_MODELS_BY_OPERATION.get(operation, set())
        if billing_access_tier(user) == AUTHOR_TIER and model not in author_models:
            log.error(
                "author_llm_model_rejected user_id=%s provider=%s model=%s feature=%s",
                user_id,
                provider,
                model,
                feature,
            )
            raise HTTPException(
                503,
                {
                    "kind": "llm_configuration",
                    "message": "AI processing is temporarily unavailable because the configured model is not enabled for this plan.",
                },
            )
        await assert_llm_token_capacity(
            db, user=user, estimated_tokens=total_estimate, limit_subject="LLM usage"
        )
        cost_capacity = await summarize_llm_cost_capacity(
            db,
            user=user,
            budget_class=budget_class,
        )
        if (
            cost_capacity.available_cost_usd is not None
            and reserved_cost > cost_capacity.available_cost_usd
        ):
            log.warning(
                "llm_budget_blocked user_id=%s feature=%s budget_class=%s committed_usd=%s reserved_usd=%s reset_at=%s",
                user_id,
                feature,
                budget_class,
                cost_capacity.committed_cost_usd,
                reserved_cost,
                cost_capacity.resets_at.isoformat(),
            )
            raise HTTPException(
                429,
                {
                    "kind": "llm_budget",
                    "message": "Monthly AI capacity has been reached. AI work will resume at the monthly reset.",
                    "detail": "Monthly AI capacity has been reached. AI work will resume at the monthly reset.",
                    "next_resume_at": cost_capacity.resets_at.isoformat(),
                    "auto_resume": True,
                },
            )
        projected_cost = cost_capacity.committed_cost_usd + reserved_cost
        for threshold in (Decimal("3.00"), Decimal("3.50")):
            if cost_capacity.committed_cost_usd < threshold <= projected_cost:
                log.warning(
                    "llm_cost_threshold_crossed user_id=%s threshold_usd=%s projected_usd=%s feature=%s",
                    user_id,
                    threshold,
                    projected_cost,
                    feature,
                )
        event_metadata = dict(metadata or {})
        event_metadata.update(
            {
                "budget_class": budget_class,
                "cost_disposition": "reserved",
                "estimated_prompt_tokens": prompt_estimate,
                "estimated_completion_tokens": completion_estimate,
                "protected_processing_cost_usd": str(cost_capacity.protected_processing_cost_usd),
            }
        )
        db.add(
            LlmUsageEvent(
                reservation_id=reservation_id,
                status="reserved",
                user_id=user_id,
                book_id=book_id,
                provider=provider,
                model=model,
                operation=operation,
                feature=feature[:120],
                estimated_tokens=total_estimate,
                total_tokens=total_estimate,
                input_cost_usd=input_cost,
                output_cost_usd=output_cost,
                total_cost_usd=reserved_cost,
                pricing_version=pricing_version,
                metadata_json=event_metadata,
            )
        )
        await db.commit()
    rpm, tpm = _limits(operation)
    try:
        redis = await get_redis()
        allowed, retry_after = await redis.eval(
            _ACQUIRE_SCRIPT,
            2,
            f"llm:rate:{operation}",
            f"llm:concurrency:{user_id}",
            int(time.time() * 1000),
            reservation_id,
            total_estimate,
            rpm,
            tpm,
            settings.LLM_MAX_CONCURRENT_CALLS_PER_USER,
        )
    except RedisError as exc:
        async with AsyncSessionLocal() as db:
            event = await db.scalar(
                select(LlmUsageEvent).where(LlmUsageEvent.reservation_id == reservation_id)
            )
            if event is not None:
                event.status = "failed"
                event.total_tokens = 0
                event.input_cost_usd = Decimal("0")
                event.output_cost_usd = Decimal("0")
                event.total_cost_usd = Decimal("0")
                event.metadata_json = {
                    **dict(event.metadata_json or {}),
                    "cost_disposition": "released_before_provider",
                }
                await db.commit()
        raise HTTPException(503, "LLM coordination is temporarily unavailable.") from exc
    if not int(allowed):
        await fail_llm_reservation(
            LlmReservation(
                reservation_id,
                operation,
                user_id,
                provider,
                model,
                reserved_cost,
            ),
            provider_attempted=False,
        )
        raise HTTPException(
            429,
            "LLM capacity is temporarily busy. Retry shortly.",
            headers={"Retry-After": str(int(retry_after))},
        )
    return LlmReservation(
        reservation_id,
        operation,
        user_id,
        provider,
        model,
        reserved_cost,
    )


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
            input_cost, output_cost, total_cost, version = (
                calculate_llm_cost(
                    event.model,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    cached_prompt_tokens=cached,
                )
                if usage is not None
                else (
                    event.input_cost_usd,
                    event.output_cost_usd,
                    event.total_cost_usd,
                    event.pricing_version,
                )
            )
            event.status = "succeeded"
            if usage is not None:
                event.prompt_tokens = prompt
                event.completion_tokens = completion
                event.total_tokens = total
            else:
                event.total_tokens = max(
                    int(event.total_tokens or 0),
                    int(event.estimated_tokens or 0),
                )
            event.cached_prompt_tokens = cached
            event.cached = cached > 0
            event.input_cost_usd = input_cost
            event.output_cost_usd = output_cost
            event.total_cost_usd = total_cost
            event.pricing_version = version
            event.metadata_json = {
                **dict(event.metadata_json or {}),
                "cost_disposition": "actual" if usage is not None else "usage_missing_upper_bound",
            }
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
            event.metadata_json = {
                **dict(event.metadata_json or {}),
                "cost_disposition": "actual",
            }
            await db.commit()
    await _release_redis_concurrency(reservation)


async def fail_llm_reservation(
    reservation: LlmReservation,
    *,
    provider_attempted: bool = True,
) -> None:
    async with AsyncSessionLocal() as db:
        event = (
            await db.execute(
                select(LlmUsageEvent).where(LlmUsageEvent.reservation_id == reservation.id)
            )
        ).scalar_one_or_none()
        if event is not None:
            event.status = "failed"
            if provider_attempted:
                event.total_tokens = max(
                    int(event.total_tokens or 0),
                    int(event.estimated_tokens or 0),
                )
                event.metadata_json = {
                    **dict(event.metadata_json or {}),
                    "cost_disposition": "uncertain_provider_attempt",
                }
            else:
                event.total_tokens = 0
                event.input_cost_usd = Decimal("0")
                event.output_cost_usd = Decimal("0")
                event.total_cost_usd = Decimal("0")
                event.metadata_json = {
                    **dict(event.metadata_json or {}),
                    "cost_disposition": "released_before_provider",
                }
            await db.commit()
    await _release_redis_concurrency(reservation)


async def _release_redis_concurrency(reservation: LlmReservation) -> None:
    try:
        redis = await get_redis()
        await redis.srem(f"llm:concurrency:{reservation.user_id}", reservation.id)
    except RedisError:
        # PostgreSQL is authoritative. A Redis restart rehydrates only still-reserved calls.
        log.warning(
            "llm_concurrency_release_failed reservation_id=%s",
            reservation.id,
            exc_info=True,
        )
