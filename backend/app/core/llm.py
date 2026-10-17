from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
import uuid
from typing import Any, cast

import httpx
from google.genai.errors import APIError as GeminiAPIError
from openai import AsyncOpenAI, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
)

from app.core.config import settings
from app.utils.llm_pricing import calculate_llm_cost
from app.utils.llm_usage_utils import (
    CUSTOMER_BILLING_SCOPE,
    SYSTEM_BILLING_SCOPE,
    create_tracked_chat_completion,
    estimate_chat_completion_token_parts,
    is_retryable_llm_call_error,
)
from app.utils.observability_metrics import record_llm_client_creation
from app.utils.request_context import get_request_id
from app.utils.retry_utils import LLM_MAX_RETRIES

_openai_client: AsyncOpenAI | None = None
_openai_clients: dict[tuple[int, int | None], AsyncOpenAI] = {}
_gemini_client: object | None = None
_gemini_client_cache_key: tuple[str | None, int] | None = None
LLM_PROVIDER_EXCEPTIONS = (
    OpenAIError,
    GeminiAPIError,
    httpx.HTTPError,
    TimeoutError,
    RuntimeError,
    ValueError,
)
logger = logging.getLogger("lorevia.llm")


def _openai_client_registry_key() -> tuple[int, int | None]:
    """Keep httpx-backed clients inside the process and event loop that own them."""
    try:
        return os.getpid(), id(asyncio.get_running_loop())
    except RuntimeError:
        return os.getpid(), None


def get_openai_client(external: AsyncOpenAI | None = None) -> AsyncOpenAI:
    global _openai_client
    if external is not None:
        return external
    registry_key = _openai_client_registry_key()
    client = _openai_clients.get(registry_key)
    if client is None:
        # Tenacity below is the single retry owner. Leaving the SDK's default
        # retries enabled would multiply every configured attempt.
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
        _openai_clients[registry_key] = client
        record_llm_client_creation()
        logger.info(
            "openai_client_created",
            extra={"process_id": registry_key[0], "event_loop_id": registry_key[1]},
        )
    # Kept as a compatibility reference for modules and diagnostics that used
    # the original singleton. New code must always resolve through the registry.
    _openai_client = client
    return client


async def close_openai_clients() -> None:
    """Close every registry-owned OpenAI client during API or worker shutdown."""
    global _openai_client
    clients = list(dict.fromkeys(_openai_clients.values()))
    _openai_clients.clear()
    _openai_client = None
    for client in clients:
        await client.close()


def _get_gemini_client() -> object:
    global _gemini_client, _gemini_client_cache_key
    cache_key = (settings.GEMINI_API_KEY, int(settings.GEMINI_REQUEST_TIMEOUT_SECONDS))
    if _gemini_client is not None and _gemini_client_cache_key == cache_key:
        return _gemini_client
    from google import genai
    from google.genai import types

    _gemini_client = genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=cache_key[1] * 1_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    _gemini_client_cache_key = cache_key
    return _gemini_client


def _is_transient_openai_error(exc: BaseException) -> bool:
    return is_retryable_llm_call_error(exc)


def _is_transient_gemini_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, TimeoutError)):
        return True
    if isinstance(exc, GeminiAPIError):
        code = int(getattr(exc, "code", 0) or 0)
        return code in {408, 409, 429} or code >= 500
    return False


def _retry_after_seconds(exc: BaseException | None) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    value = headers.get("retry-after") if headers is not None else None
    try:
        return max(float(value), 0.0) if value is not None else None
    except (TypeError, ValueError):
        return None


def _llm_retry_wait_seconds(retry_state: Any) -> float:
    attempt = max(int(getattr(retry_state, "attempt_number", 1) or 1), 1)
    outcome = getattr(retry_state, "outcome", None)
    exc = outcome.exception() if outcome is not None else None
    retry_after = _retry_after_seconds(exc)
    if retry_after is not None:
        return min(retry_after, 60.0)
    return random.uniform(0.0, min(float(2**attempt), 60.0))


@retry(
    stop=stop_after_attempt(LLM_MAX_RETRIES + 1),
    wait=_llm_retry_wait_seconds,
    retry=retry_if_exception(_is_transient_openai_error),
    reraise=True,
)
async def _call_openai_completion(
    *,
    client: AsyncOpenAI,
    feature: str,
    model: str,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None,
    book_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
    **kwargs: Any,
) -> Any:
    return await create_tracked_chat_completion(
        client=client,
        feature=feature,
        model=model,
        db=db,
        user_id=user_id,
        book_id=book_id,
        metadata=metadata,
        billing_scope=billing_scope,
        **kwargs,
    )


async def complete_with_fallback(
    *,
    system: str,
    user: str,
    openai_model: str,
    gemini_model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1200,
    response_format: dict[str, Any] | None = None,
    openai_client: AsyncOpenAI | None = None,
    usage_feature: str = "llm_completion",
    usage_user_id: uuid.UUID | None,
    usage_book_id: uuid.UUID | None = None,
    usage_metadata: dict[str, Any] | None = None,
    usage_db: AsyncSession | None = None,
    usage_billing_scope: str = CUSTOMER_BILLING_SCOPE,
    language: str | None = None,
) -> str:
    from app.utils.advisor_utils import language_context_hint

    if language:
        system = language_context_hint(language) + system
    openai_error: Exception | None = None

    if settings.OPENAI_API_KEY:
        client = get_openai_client(openai_client)
        try:
            request_kwargs = cast(
                dict[str, Any],
                {
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            if response_format is not None:
                request_kwargs["response_format"] = response_format
            response = await _call_openai_completion(
                client=client,
                feature=usage_feature,
                model=openai_model,
                db=usage_db,
                user_id=usage_user_id,
                book_id=usage_book_id,
                metadata=usage_metadata,
                billing_scope=usage_billing_scope,
                **request_kwargs,
            )
            content = response.choices[0].message.content or ""
            if content.strip():
                return content.strip()
        except LLM_PROVIDER_EXCEPTIONS as exc:  # pragma: no cover - network/provider path
            openai_error = exc

    if settings.GEMINI_API_KEY and gemini_model and usage_billing_scope == SYSTEM_BILLING_SCOPE:
        try:
            return await _complete_with_gemini(
                system=system,
                user=user,
                model=gemini_model,
                temperature=temperature,
                max_tokens=max_tokens,
                want_json=response_format == {"type": "json_object"},
                usage_feature=usage_feature,
                usage_book_id=usage_book_id,
            )
        except LLM_PROVIDER_EXCEPTIONS:  # pragma: no cover - network/provider path
            if openai_error:
                raise openai_error
            raise

    if openai_error:
        raise openai_error

    raise RuntimeError("No available LLM provider configured")


async def _complete_with_gemini(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_tokens: int,
    want_json: bool,
    usage_feature: str = "llm_completion",
    usage_book_id: uuid.UUID | None = None,
) -> str:
    try:
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Gemini fallback requested but google-genai is not installed") from exc

    client = cast(Any, _get_gemini_client())
    config = cast(Any, types).GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
        system_instruction=system,
    )
    if want_json:
        config.response_mime_type = "application/json"

    prompt_tokens, completion_tokens = estimate_chat_completion_token_parts(
        {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }
    )
    from app.services.llm_circuit_breaker_service import (
        acquire_provider_circuit_permit,
        record_provider_failure,
        record_provider_success,
    )
    from app.services.llm_control_service import enforce_system_llm_rate_limit

    await enforce_system_llm_rate_limit(
        provider="google",
        model=model,
        operation="chat",
        estimated_tokens=prompt_tokens + completion_tokens,
    )
    permit = await acquire_provider_circuit_permit(provider="google", model=model)
    started_at = time.perf_counter()
    try:
        response = await _call_gemini_generation(
            client=client,
            model=model,
            contents=user,
            config=config,
        )
    except Exception as exc:
        await record_provider_failure(permit, transient=_is_transient_gemini_error(exc))
        raise
    await record_provider_success(permit)
    actual_prompt_tokens, actual_completion_tokens, actual_total_tokens = _gemini_usage_counts(
        response
    )
    _, _, total_cost, pricing_version = calculate_llm_cost(
        model,
        prompt_tokens=actual_prompt_tokens,
        completion_tokens=actual_completion_tokens,
        provider="google",
    )
    logger.info(
        "system_llm_call_succeeded",
        extra={
            "provider": "google",
            "model": model,
            "feature": usage_feature[:120],
            "book_id": str(usage_book_id) if usage_book_id else None,
            "request_id": get_request_id(),
            "prompt_tokens": actual_prompt_tokens,
            "completion_tokens": actual_completion_tokens,
            "total_tokens": actual_total_tokens,
            "total_cost_usd": str(total_cost) if total_cost is not None else None,
            "pricing_version": pricing_version,
            "duration_ms": round((time.perf_counter() - started_at) * 1_000, 2),
        },
    )
    text = getattr(response, "text", "") or ""
    if text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        parts = getattr(getattr(candidate, "content", None), "parts", None) or []
        combined = "".join(getattr(part, "text", "") or "" for part in parts).strip()
        if combined:
            return combined

    if want_json:
        return json.dumps({})
    return ""


@retry(
    stop=stop_after_attempt(LLM_MAX_RETRIES + 1),
    wait=_llm_retry_wait_seconds,
    retry=retry_if_exception(_is_transient_gemini_error),
    reraise=True,
)
async def _call_gemini_generation(*, client: Any, **kwargs: Any) -> Any:
    return await client.aio.models.generate_content(**kwargs)


def _gemini_usage_counts(response: Any) -> tuple[int, int, int]:
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
    completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
    total_tokens = int(getattr(usage, "total_token_count", 0) or 0)
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    return prompt_tokens, completion_tokens, total_tokens
