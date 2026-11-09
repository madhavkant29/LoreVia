"""Bounded provider and response retries for evidence-backed Advisor scans."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from fastapi import HTTPException
from openai import OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.advisor_result_utils import normalize_proactive_scan_result
from app.utils.advisor_suggestions_utils import advisor_scan_output_token_budget
from app.utils.llm_usage_utils import (
    create_tracked_chat_completion,
    is_transient_llm_provider_error,
    require_complete_llm_response,
    short_llm_coordination_retry_delay,
)


async def run_bounded_scan_groups(
    groups: Sequence[tuple[int, Any]],
    *,
    scan_one: Callable[[int, Any], Awaitable[Any]],
    on_complete: Callable[[int, Any], Awaitable[None]],
    concurrency: int = 2,
) -> list[tuple[int, Any]]:
    """Run independent evidence groups without saturating the user's AI slots."""
    if concurrency < 1:
        raise ValueError("invalid_advisor_scan_concurrency")
    semaphore = asyncio.Semaphore(concurrency)

    async def run(index: int, group: Any) -> tuple[int, Any]:
        async with semaphore:
            return index, await scan_one(index, group)

    tasks = [asyncio.create_task(run(index, group)) for index, group in groups]
    completed: list[tuple[int, Any]] = []
    try:
        for task in asyncio.as_completed(tasks):
            index, result = await task
            completed.append((index, result))
            await on_complete(index, result)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return sorted(completed, key=lambda item: item[0])


async def request_proactive_scan_result(
    *,
    client: Any,
    db: AsyncSession,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    model: str,
    messages: list[dict[str, str]],
    source_blocks: Sequence[str],
) -> dict[str, Any]:
    """Retry one transient or malformed result, never treating failure as an empty audit."""
    for attempt in range(2):
        try:
            response = await create_tracked_chat_completion(
                client=client,
                feature="advisor_proactive_scan",
                model=model,
                db=db,
                user_id=user_id,
                book_id=book_id,
                temperature=0.2,
                max_tokens=advisor_scan_output_token_budget(len(source_blocks)),
                response_format={"type": "json_object"},
                messages=messages,
            )
            require_complete_llm_response(response)
            return normalize_proactive_scan_result(
                response.choices[0].message.content or "{}",
                strict=True,
                source_blocks=list(source_blocks),
                allow_partial=attempt > 0,
            )
        except HTTPException as exc:
            delay = short_llm_coordination_retry_delay(exc)
            if attempt or delay is None:
                raise
            await asyncio.sleep(delay)
        except (OpenAIError, TimeoutError, ValueError, TypeError, KeyError, IndexError) as exc:
            malformed = isinstance(exc, (ValueError, TypeError, KeyError, IndexError))
            if attempt or not (malformed or is_transient_llm_provider_error(exc)):
                raise
            await asyncio.sleep(0.5)

    raise RuntimeError("proactive_scan_retry_exhausted")
