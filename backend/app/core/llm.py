from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any, cast

import httpx
from openai import AsyncOpenAI, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.utils.llm_usage_utils import (
    create_tracked_chat_completion,
    is_retryable_llm_call_error,
)
from app.utils.retry_utils import LLM_MAX_RETRIES

_openai_client: AsyncOpenAI | None = None
_gemini_client: object | None = None
LLM_PROVIDER_EXCEPTIONS = (OpenAIError, httpx.HTTPError, TimeoutError, RuntimeError, ValueError)


def _get_openai_client(external: AsyncOpenAI | None = None) -> AsyncOpenAI:
    global _openai_client
    if external is not None:
        return external
    if _openai_client is None:
        # Tenacity below is the single retry owner. Leaving the SDK's default
        # retries enabled would multiply every configured attempt.
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
    return _openai_client


def _get_gemini_client() -> object:
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    from google import generativeai as genai

    _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


def _is_transient_openai_error(exc: BaseException) -> bool:
    return is_retryable_llm_call_error(exc)


@retry(
    stop=stop_after_attempt(LLM_MAX_RETRIES + 1),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(_is_transient_openai_error),
    reraise=True,
)
async def _call_openai_completion(
    *,
    client: AsyncOpenAI,
    feature: str,
    model: str,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
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
    usage_user_id: uuid.UUID | None = None,
    usage_book_id: uuid.UUID | None = None,
    usage_metadata: dict[str, Any] | None = None,
    usage_db: AsyncSession | None = None,
    language: str | None = None,
) -> str:
    from app.utils.advisor_utils import language_context_hint

    if language:
        system = language_context_hint(language) + system
    openai_error: Exception | None = None

    if settings.OPENAI_API_KEY:
        client = _get_openai_client(openai_client)
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
                **request_kwargs,
            )
            content = response.choices[0].message.content or ""
            if content.strip():
                return content.strip()
        except LLM_PROVIDER_EXCEPTIONS as exc:  # pragma: no cover - network/provider path
            openai_error = exc

    if settings.GEMINI_API_KEY and gemini_model:
        try:
            return await _complete_with_gemini(
                system=system,
                user=user,
                model=gemini_model,
                temperature=temperature,
                max_tokens=max_tokens,
                want_json=response_format == {"type": "json_object"},
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
) -> str:
    try:
        from google.generativeai import types
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

    response = await _run_blocking(
        lambda: client.models.generate_content(
            model=model,
            contents=user,
            config=config,
        )
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


async def _run_blocking(fn: Callable[[], Any]) -> Any:
    import asyncio

    return await asyncio.to_thread(fn)
