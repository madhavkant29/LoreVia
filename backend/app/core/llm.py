from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

from openai import AsyncOpenAI

from app.core.config import settings


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
) -> str:
    openai_error: Exception | None = None

    if settings.OPENAI_API_KEY:
        client = openai_client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            request_kwargs = cast(
                dict[str, Any],
                {
                    "model": openai_model,
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
            response = await client.chat.completions.create(**request_kwargs)
            content = response.choices[0].message.content or ""
            if content.strip():
                return content.strip()
        except Exception as exc:  # pragma: no cover - network/provider path
            openai_error = exc
        finally:
            if openai_client is None:
                await client.close()

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
        except Exception:  # pragma: no cover - network/provider path
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
        from google import generativeai as genai
        from google.generativeai import types
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Gemini fallback requested but google-genai is not installed") from exc

    client = cast(Any, genai).Client(api_key=settings.GEMINI_API_KEY)
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
