from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from openai.types.chat import ChatCompletion
from openai.types.create_embedding_response import CreateEmbeddingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.user import LlmUsageEvent
from app.utils.request_context import get_request_id, get_request_user_id

log = logging.getLogger("lorevia.llm_usage")


@dataclass(frozen=True)
class LlmUsageSummary:
    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


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
    response = await client.chat.completions.create(model=model, **kwargs)
    try:
        await record_llm_usage_event(
            response=response,
            feature=feature,
            operation="chat_completion",
            model=model,
            db=db,
            user_id=user_id,
            book_id=book_id,
            metadata=metadata,
        )
    except Exception:
        log.warning("llm_usage_record_failed feature=%s operation=chat_completion", feature, exc_info=True)
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
    response = await client.embeddings.create(model=model, **kwargs)
    try:
        await record_llm_usage_event(
            response=response,
            feature=feature,
            operation="embedding",
            model=model,
            db=db,
            user_id=user_id,
            book_id=book_id,
            metadata=metadata,
        )
    except Exception:
        log.warning("llm_usage_record_failed feature=%s operation=embedding", feature, exc_info=True)
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
