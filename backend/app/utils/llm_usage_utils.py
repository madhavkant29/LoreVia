from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from openai import OpenAIError
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
from app.utils.request_context import get_request_id, get_request_user_id

log = logging.getLogger("lorevia.llm_usage")
LLM_PROVIDER_CALL_EXCEPTIONS = (OpenAIError, httpx.HTTPError, TimeoutError, RuntimeError)


@dataclass(frozen=True)
class LlmUsageSummary:
    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


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


def _coerce_uuid(value: object | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _usage_counts(response: ChatCompletion | CreateEmbeddingResponse) -> tuple[int, int, int]:
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


def estimate_chat_completion_tokens(kwargs: dict[str, Any]) -> int:
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
    prompt_tokens = count_tokens("\n".join(prompt_parts))
    completion_tokens = int(kwargs.get("max_tokens") or kwargs.get("max_completion_tokens") or 1000)
    return max(prompt_tokens + completion_tokens, 1)


def estimate_embedding_tokens(kwargs: dict[str, Any]) -> int:
    input_value = kwargs.get("input")
    if isinstance(input_value, list):
        return max(sum(count_tokens(str(item or "")) for item in input_value), 1)
    return max(count_tokens(str(input_value or "")), 1)


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
        return LlmTokenCaps(five_hour=0, weekly=0, monthly=0)
    resolved_user = user
    if resolved_user is None:
        resolved_user = await db.get(User, resolved_user_id)
    if resolved_user is None:
        raise HTTPException(403, "User is required for LLM usage.")
    caps = llm_token_caps_for_user(resolved_user)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    windows = (
        ("5-hour", current - timedelta(hours=5), caps.five_hour),
        ("weekly", current - timedelta(days=7), caps.weekly),
        ("monthly", current - timedelta(days=30), caps.monthly),
    )
    for label, started_at, limit in windows:
        used = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0)).where(
                        LlmUsageEvent.user_id == resolved_user_id,
                        LlmUsageEvent.created_at >= started_at,
                    )
                )
            ).scalar()
            or 0
        )
        if used + max(int(estimated_tokens or 0), 0) > limit:
            raise HTTPException(
                429,
                f"{limit_subject} token limit exceeded for the {label} window.",
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
        return LlmTokenCaps(five_hour=0, weekly=0, monthly=0)
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
) -> None:
    resolved_user_id = user_id or get_request_user_id()
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
) -> None:
    resolved_user_id = user_id or get_request_user_id()
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
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> ChatCompletion:
    resolved_user_id = _coerce_uuid(user_id or get_request_user_id())
    if resolved_user_id is None:
        return await client.chat.completions.create(model=model, **kwargs)
    from app.services.llm_control_service import (
        fail_llm_reservation,
        finish_llm_reservation,
        reserve_llm_call,
    )

    reservation = await reserve_llm_call(
        user_id=resolved_user_id,
        estimated_tokens=estimate_chat_completion_tokens(kwargs),
        feature=feature,
        operation="chat",
        model=model,
        book_id=book_id,
    )
    try:
        response = await client.chat.completions.create(model=model, **kwargs)
    except LLM_PROVIDER_CALL_EXCEPTIONS:
        await _fail_llm_reservation_best_effort(fail_llm_reservation, reservation)
        raise
    await finish_llm_reservation(reservation, response)
    return response


async def create_tracked_embedding(
    *,
    client: Any,
    feature: str,
    model: str,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> CreateEmbeddingResponse:
    resolved_user_id = _coerce_uuid(user_id or get_request_user_id())
    if resolved_user_id is None:
        return await client.embeddings.create(model=model, **kwargs)
    from app.services.llm_control_service import (
        fail_llm_reservation,
        finish_llm_reservation,
        reserve_llm_call,
    )

    reservation = await reserve_llm_call(
        user_id=resolved_user_id,
        estimated_tokens=estimate_embedding_tokens(kwargs),
        feature=feature,
        operation="embedding",
        model=model,
        book_id=book_id,
    )
    try:
        response = await client.embeddings.create(model=model, **kwargs)
    except LLM_PROVIDER_CALL_EXCEPTIONS:
        await _fail_llm_reservation_best_effort(fail_llm_reservation, reservation)
        raise
    await finish_llm_reservation(reservation, response)
    return response


async def summarize_llm_usage_for_user(db: AsyncSession, user_id: object) -> LlmUsageSummary:
    resolved_user_id = _coerce_uuid(user_id)
    if resolved_user_id is None:
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

    return LlmUsageSummary(
        request_count=int(row[0] or 0),
        prompt_tokens=int(row[1] or 0),
        completion_tokens=int(row[2] or 0),
        total_tokens=int(row[3] or 0),
    )
