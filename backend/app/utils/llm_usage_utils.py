from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAIError
from openai.types.chat import ChatCompletion
from openai.types.create_embedding_response import CreateEmbeddingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import LlmUsageEvent, User
from app.parsers.chunker import count_tokens
from app.utils.billing_utils import ARCHITECT_TIER, AUTHOR_TIER, billing_access_tier
from app.utils.logging.errors import public_error_message
from app.utils.request_context import get_request_id, get_request_user_id

log = logging.getLogger("lorevia.llm_usage")
LLM_PROVIDER_CALL_EXCEPTIONS = (
    OpenAIError,
    httpx.HTTPError,
    TimeoutError,
    RuntimeError,
)
CUSTOMER_BILLING_SCOPE = "customer"
SYSTEM_BILLING_SCOPE = "system"


class LLMIncompleteResponseError(ValueError):
    """The provider stopped generation before completing the requested answer."""

    def __init__(self, message: str, *, finish_reason: str | None = None) -> None:
        super().__init__(message)
        self.finish_reason = finish_reason


def require_complete_llm_response(response: Any) -> None:
    """Reject missing or non-final chat choices before parsing structured output."""
    choices = getattr(response, "choices", None)
    finish_reason = getattr(choices[0], "finish_reason", None) if choices else None
    if finish_reason != "stop":
        raise LLMIncompleteResponseError("llm_response_incomplete", finish_reason=finish_reason)


PROCESSING_FEATURE_PREFIXES = (
    "chapter_",
    "character_",
    "extraction_",
    "initial_ingestion",
    "manual_reprocess",
    "plot_thread_",
    "reader_recall",
)


@dataclass(frozen=True)
class LlmUsageSummary:
    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    ai_interactive_available: bool = True
    ai_processing_available: bool = True
    ai_capacity_usage_percent: int = 0
    ai_capacity_resets_at: datetime | None = None


@dataclass(frozen=True)
class ManualReprocessTokenCaps:
    five_hour: int
    weekly: int
    monthly: int


LlmTokenCaps = ManualReprocessTokenCaps


async def _fail_llm_reservation_best_effort(
    fail_llm_reservation: Any,
    reservation: Any,
) -> None:
    try:
        await fail_llm_reservation(reservation)
    except SQLAlchemyError:
        log.warning(
            "llm_reservation_failure_recording_failed reservation_id=%s",
            getattr(reservation, "id", None),
            exc_info=True,
        )


def is_transient_llm_provider_error(exc: BaseException) -> bool:
    """Identify provider/network failures that are safe to retry."""
    if isinstance(
        exc,
        (
            APIConnectionError,
            APITimeoutError,
            httpx.TransportError,
            TimeoutError,
        ),
    ):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in {408, 409, 429} or exc.status_code >= 500
    return False


def is_llm_call_error(exc: BaseException) -> bool:
    """Identify failures raised at the provider/control boundary."""
    return isinstance(exc, (OpenAIError, httpx.HTTPError, HTTPException, TimeoutError))


def is_retryable_llm_call_error(exc: BaseException) -> bool:
    """Identify failures that should be retried at one provider call, not at task level."""
    return is_transient_llm_provider_error(exc)


def short_llm_coordination_retry_delay(exc: HTTPException) -> float | None:
    """Honor only short, explicit coordination backoffs; never retry plan denials."""
    if exc.status_code not in {429, 503} or isinstance(exc.detail, dict):
        return None
    retry_after = (exc.headers or {}).get("Retry-After")
    try:
        delay = float(retry_after)
    except (TypeError, ValueError):
        return None
    return delay if math.isfinite(delay) and 0 < delay <= 5 else None


def public_llm_http_error_message(exc: HTTPException) -> str:
    """Preserve safe AI allowance messages while hiding unrelated HTTP details."""

    detail = exc.detail
    if isinstance(detail, dict) and detail.get("kind") in {
        "llm_attribution",
        "llm_budget",
        "llm_configuration",
        "llm_provider",
        "llm_tokens",
        "manuscript_source",
    }:
        message = detail.get("message") or detail.get("detail")
        if message:
            return str(message)
    if isinstance(detail, str) and detail.lower().startswith("llm "):
        return detail
    return public_error_message(exc.status_code)


def _coerce_uuid(value: object | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _usage_counts(
    response: ChatCompletion | CreateEmbeddingResponse,
) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
    return prompt_tokens, completion_tokens, total_tokens


def _message_content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content") or item.get("input_text")
                if value:
                    parts.append(str(value))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def estimate_chat_completion_token_parts(kwargs: dict[str, Any]) -> tuple[int, int]:
    messages = kwargs.get("messages") or []
    prompt_parts: list[str] = []
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict):
                prompt_parts.append(str(message.get("role") or ""))
                prompt_parts.append(_message_content_text(message.get("content")))
            else:
                prompt_parts.append(str(message))
    else:
        prompt_parts.append(str(messages))
    raw_prompt_tokens = count_tokens("\n".join(prompt_parts))
    prompt_tokens = max(math.ceil(raw_prompt_tokens * 1.10) + 16, 1)
    completion_tokens = int(kwargs.get("max_tokens") or kwargs.get("max_completion_tokens") or 1000)
    return prompt_tokens, max(completion_tokens, 0)


def estimate_chat_completion_tokens(kwargs: dict[str, Any]) -> int:
    prompt_tokens, completion_tokens = estimate_chat_completion_token_parts(kwargs)
    return max(prompt_tokens + completion_tokens, 1)


def estimate_embedding_tokens(kwargs: dict[str, Any]) -> int:
    input_value = kwargs.get("input")
    if isinstance(input_value, list):
        return max(sum(count_tokens(str(item or "")) for item in input_value), 1)
    return max(count_tokens(str(input_value or "")), 1)


def llm_budget_class_for_feature(feature: str) -> str:
    normalized = str(feature or "").strip().lower()
    if normalized.startswith(PROCESSING_FEATURE_PREFIXES):
        return "processing"
    return "interactive"


def _resolved_usage_user_id(
    user_id: uuid.UUID | None,
    *,
    billing_scope: str,
) -> uuid.UUID | None:
    resolved = _coerce_uuid(user_id or get_request_user_id())
    if resolved is not None:
        return resolved
    if billing_scope == SYSTEM_BILLING_SCOPE:
        return None
    log.error("llm_usage_attribution_missing billing_scope=%s", billing_scope)
    raise HTTPException(
        503,
        {
            "kind": "llm_attribution",
            "message": "AI processing is temporarily unavailable because account attribution is missing.",
        },
    )


def resolve_llm_usage_attribution(
    user_id: uuid.UUID | None,
    *,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
) -> uuid.UUID | None:
    """Validate customer attribution even when a provider call is skipped or cached."""

    return _resolved_usage_user_id(user_id, billing_scope=billing_scope)


def llm_token_caps_for_user(user: Any) -> LlmTokenCaps:
    tier = billing_access_tier(user)
    if tier == ARCHITECT_TIER:
        return LlmTokenCaps(
            five_hour=settings.ARCHITECT_LLM_TOKENS_5H,
            weekly=settings.ARCHITECT_LLM_TOKENS_WEEK,
            monthly=settings.ARCHITECT_LLM_TOKENS_MONTH,
        )
    if tier == AUTHOR_TIER:
        return LlmTokenCaps(
            five_hour=settings.AUTHOR_LLM_TOKENS_5H,
            weekly=settings.AUTHOR_LLM_TOKENS_WEEK,
            monthly=settings.AUTHOR_LLM_TOKENS_MONTH,
        )
    return LlmTokenCaps(
        five_hour=settings.FREE_LLM_TOKENS_5H,
        weekly=settings.FREE_LLM_TOKENS_WEEK,
        monthly=settings.FREE_LLM_TOKENS_MONTH,
    )


def manual_reprocess_token_caps_for_user(user: Any) -> ManualReprocessTokenCaps:
    return llm_token_caps_for_user(user)


def estimate_manual_reprocess_tokens(chapter_text: str) -> int:
    source_tokens = count_tokens(chapter_text)
    return max(source_tokens * 6, source_tokens + 1000)


async def assert_manual_reprocess_token_capacity(
    db: AsyncSession,
    user: Any,
    *,
    estimated_tokens: int,
    now: datetime | None = None,
) -> ManualReprocessTokenCaps:
    return await assert_llm_token_capacity(
        db,
        user=user,
        estimated_tokens=estimated_tokens,
        now=now,
        limit_subject="Manual chapter reprocess",
    )


async def assert_llm_token_capacity(
    db: AsyncSession,
    user: Any | None = None,
    *,
    user_id: uuid.UUID | None = None,
    estimated_tokens: int,
    now: datetime | None = None,
    limit_subject: str = "LLM usage",
) -> LlmTokenCaps:
    resolved_user_id = _coerce_uuid(user_id or getattr(user, "id", None) or get_request_user_id())
    if resolved_user_id is None:
        raise HTTPException(
            503,
            {
                "kind": "llm_attribution",
                "message": "AI processing is temporarily unavailable because account attribution is missing.",
            },
        )
    resolved_user = user
    if resolved_user is None:
        resolved_user = await db.get(User, resolved_user_id)
    if resolved_user is None:
        raise HTTPException(403, "User is required for LLM usage.")
    caps = llm_token_caps_for_user(resolved_user)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    requested_tokens = max(int(estimated_tokens or 0), 0)
    windows = (
        ("5-hour", timedelta(hours=5), caps.five_hour),
        ("weekly", timedelta(days=7), caps.weekly),
        ("monthly", timedelta(days=30), caps.monthly),
    )
    oldest_window_start = current - timedelta(days=30)
    usage_rows = list(
        (
            await db.execute(
                select(LlmUsageEvent.created_at, LlmUsageEvent.total_tokens)
                .where(
                    LlmUsageEvent.user_id == resolved_user_id,
                    LlmUsageEvent.created_at >= oldest_window_start,
                )
                .order_by(LlmUsageEvent.created_at.asc())
            )
        ).all()
    )
    blocked_windows: list[dict[str, Any]] = []
    for label, duration, limit in windows:
        started_at = current - duration
        active_rows = [row for row in usage_rows if row.created_at >= started_at]
        used = sum(max(int(row.total_tokens or 0), 0) for row in active_rows)
        if used + requested_tokens <= limit:
            continue

        next_resume_at: datetime | None = None
        if requested_tokens <= limit:
            tokens_to_expire = used + requested_tokens - limit
            expired_tokens = 0
            for row in active_rows:
                expired_tokens += max(int(row.total_tokens or 0), 0)
                if expired_tokens >= tokens_to_expire:
                    created_at = row.created_at
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=UTC)
                    next_resume_at = created_at + duration + timedelta(seconds=1)
                    break
        blocked_windows.append(
            {
                "window": label,
                "used_tokens": used,
                "token_limit": limit,
                "next_resume_at": next_resume_at,
            }
        )

    if blocked_windows:
        resumable_at = [
            item["next_resume_at"]
            for item in blocked_windows
            if isinstance(item.get("next_resume_at"), datetime)
        ]
        auto_resume = len(resumable_at) == len(blocked_windows)
        next_resume_at = max(resumable_at) if auto_resume and resumable_at else None
        labels = [str(item["window"]) for item in blocked_windows]
        window_label = labels[0] if len(labels) == 1 else ", ".join(labels)
        message = f"{limit_subject} token limit exceeded for the {window_label} window."
        raise HTTPException(
            429,
            {
                "kind": "llm_tokens",
                "message": message,
                "detail": message,
                "window": window_label,
                "windows": labels,
                "next_resume_at": (next_resume_at.isoformat() if next_resume_at else None),
                "auto_resume": auto_resume,
                "permanent": not auto_resume,
            },
        )
    return caps


async def assert_llm_token_capacity_for_request(
    *,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    estimated_tokens: int,
    limit_subject: str = "LLM usage",
) -> LlmTokenCaps:
    resolved_user_id = _coerce_uuid(user_id or get_request_user_id())
    if resolved_user_id is None:
        raise HTTPException(
            503,
            {
                "kind": "llm_attribution",
                "message": "AI processing is temporarily unavailable because account attribution is missing.",
            },
        )
    if db is not None:
        return await assert_llm_token_capacity(
            db,
            user_id=resolved_user_id,
            estimated_tokens=estimated_tokens,
            limit_subject=limit_subject,
        )
    async with AsyncSessionLocal() as session:
        return await assert_llm_token_capacity(
            session,
            user_id=resolved_user_id,
            estimated_tokens=estimated_tokens,
            limit_subject=limit_subject,
        )


async def record_llm_usage_event(
    *,
    response: ChatCompletion | CreateEmbeddingResponse,
    feature: str,
    operation: str,
    model: str,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    provider: str = "openai",
    cached: bool = False,
    metadata: dict[str, Any] | None = None,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
) -> None:
    resolved_user_id = _resolved_usage_user_id(user_id, billing_scope=billing_scope)
    if resolved_user_id is None:
        return

    prompt_tokens, completion_tokens, total_tokens = _usage_counts(response)
    payload = LlmUsageEvent(
        user_id=resolved_user_id,
        book_id=book_id,
        provider=provider,
        model=model,
        operation=operation,
        feature=feature[:120],
        request_id=get_request_id(),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached=cached,
        metadata_json=metadata or {},
    )

    if db is not None:
        db.add(payload)
        return

    async with AsyncSessionLocal() as session:
        session.add(payload)
        await session.commit()


async def record_llm_usage_counts(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    feature: str,
    operation: str,
    model: str,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    provider: str = "openai",
    cached: bool = False,
    metadata: dict[str, Any] | None = None,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
) -> None:
    resolved_user_id = _resolved_usage_user_id(user_id, billing_scope=billing_scope)
    if resolved_user_id is None:
        return

    payload = LlmUsageEvent(
        user_id=resolved_user_id,
        book_id=book_id,
        provider=provider,
        model=model,
        operation=operation,
        feature=feature[:120],
        request_id=get_request_id(),
        prompt_tokens=max(int(prompt_tokens or 0), 0),
        completion_tokens=max(int(completion_tokens or 0), 0),
        total_tokens=max(int(total_tokens or 0), 0),
        cached=cached,
        metadata_json=metadata or {},
    )

    if db is not None:
        db.add(payload)
        return

    async with AsyncSessionLocal() as session:
        session.add(payload)
        await session.commit()


async def create_tracked_chat_completion(
    *,
    client: Any,
    feature: str,
    model: str,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None,
    book_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    budget_class: str | None = None,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
    **kwargs: Any,
) -> ChatCompletion:
    resolved_user_id = _resolved_usage_user_id(user_id, billing_scope=billing_scope)
    if resolved_user_id is None:
        return await client.chat.completions.create(model=model, **kwargs)
    from app.services.llm_circuit_breaker_service import (
        acquire_provider_circuit_permit,
        record_provider_failure,
        record_provider_success,
        release_provider_circuit_permit,
    )
    from app.services.llm_control_service import (
        fail_llm_reservation,
        finish_llm_reservation,
        reserve_llm_call,
    )

    prompt_tokens, completion_tokens = estimate_chat_completion_token_parts(kwargs)
    permit = await acquire_provider_circuit_permit(provider="openai", model=model)
    try:
        reservation = await reserve_llm_call(
            user_id=resolved_user_id,
            estimated_prompt_tokens=prompt_tokens,
            estimated_completion_tokens=completion_tokens,
            feature=feature,
            operation="chat",
            model=model,
            book_id=book_id,
            provider="openai",
            budget_class=budget_class or llm_budget_class_for_feature(feature),
            metadata=metadata,
        )
    except BaseException:
        await release_provider_circuit_permit(permit)
        raise
    try:
        response = await client.chat.completions.create(model=model, **kwargs)
    except BaseException as exc:
        await _fail_llm_reservation_best_effort(fail_llm_reservation, reservation)
        if isinstance(exc, LLM_PROVIDER_CALL_EXCEPTIONS):
            await record_provider_failure(
                permit,
                transient=is_transient_llm_provider_error(exc),
            )
        else:
            await release_provider_circuit_permit(permit)
        raise
    try:
        await finish_llm_reservation(reservation, response)
    except BaseException:
        await release_provider_circuit_permit(permit)
        raise
    await record_provider_success(permit)
    return response


async def create_tracked_embedding(
    *,
    client: Any,
    feature: str,
    model: str,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None,
    book_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    budget_class: str | None = None,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
    **kwargs: Any,
) -> CreateEmbeddingResponse:
    resolved_user_id = _resolved_usage_user_id(user_id, billing_scope=billing_scope)
    if resolved_user_id is None:
        return await client.embeddings.create(model=model, **kwargs)
    from app.services.llm_circuit_breaker_service import (
        acquire_provider_circuit_permit,
        record_provider_failure,
        record_provider_success,
        release_provider_circuit_permit,
    )
    from app.services.llm_control_service import (
        fail_llm_reservation,
        finish_llm_reservation,
        reserve_llm_call,
    )

    prompt_tokens = estimate_embedding_tokens(kwargs)
    permit = await acquire_provider_circuit_permit(provider="openai", model=model)
    try:
        reservation = await reserve_llm_call(
            user_id=resolved_user_id,
            estimated_prompt_tokens=prompt_tokens,
            estimated_completion_tokens=0,
            feature=feature,
            operation="embedding",
            model=model,
            book_id=book_id,
            provider="openai",
            budget_class=budget_class or llm_budget_class_for_feature(feature),
            metadata=metadata,
        )
    except BaseException:
        await release_provider_circuit_permit(permit)
        raise
    try:
        response = await client.embeddings.create(model=model, **kwargs)
    except BaseException as exc:
        await _fail_llm_reservation_best_effort(fail_llm_reservation, reservation)
        if isinstance(exc, LLM_PROVIDER_CALL_EXCEPTIONS):
            await record_provider_failure(
                permit,
                transient=is_transient_llm_provider_error(exc),
            )
        else:
            await release_provider_circuit_permit(permit)
        raise
    try:
        await finish_llm_reservation(reservation, response)
    except BaseException:
        await release_provider_circuit_permit(permit)
        raise
    await record_provider_success(permit)
    return response


async def summarize_llm_usage_for_user(db: AsyncSession, user_id: object) -> LlmUsageSummary:
    resolved_user_id = _coerce_uuid(user_id)
    if resolved_user_id is None:
        return LlmUsageSummary()

    user = await db.get(User, resolved_user_id)
    if user is None:
        return LlmUsageSummary()
    row = (
        await db.execute(
            select(
                func.count(LlmUsageEvent.id),
                func.coalesce(func.sum(LlmUsageEvent.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsageEvent.completion_tokens), 0),
                func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0),
            ).where(LlmUsageEvent.user_id == resolved_user_id)
        )
    ).one()

    from app.services.llm_control_service import summarize_llm_cost_capacity

    interactive_capacity = await summarize_llm_cost_capacity(
        db,
        user=user,
        budget_class="interactive",
    )
    processing_capacity = await summarize_llm_cost_capacity(
        db,
        user=user,
        budget_class="processing",
    )
    return LlmUsageSummary(
        request_count=int(row[0] or 0),
        prompt_tokens=int(row[1] or 0),
        completion_tokens=int(row[2] or 0),
        total_tokens=int(row[3] or 0),
        ai_interactive_available=interactive_capacity.available,
        ai_processing_available=processing_capacity.available,
        ai_capacity_usage_percent=round(interactive_capacity.usage_fraction * 100),
        ai_capacity_resets_at=interactive_capacity.resets_at,
    )
