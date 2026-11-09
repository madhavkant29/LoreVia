import asyncio
import logging
import os
import random
import uuid
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception, stop_after_attempt

from app.core.config import settings
from app.core.redis import get_embedding_cache, set_embedding_cache
from app.parsers.chunker import count_tokens
from app.utils.llm_usage_utils import (
    CUSTOMER_BILLING_SCOPE,
    create_tracked_embedding,
    is_retryable_llm_call_error,
    resolve_llm_usage_attribution,
)
from app.utils.retry_utils import LLM_MAX_RETRIES

log = logging.getLogger("lorevia.embedder")

_EMBEDDING_CLIENT: AsyncOpenAI | None = None
_EMBEDDING_CLIENT_CACHE_KEY: (
    tuple[int, asyncio.AbstractEventLoop | None, str | None, int] | None
) = None


def _embedding_retry_wait_seconds(retry_state: Any) -> float:
    attempt = max(int(getattr(retry_state, "attempt_number", 1) or 1), 1)
    outcome = getattr(retry_state, "outcome", None)
    exc = outcome.exception() if outcome is not None else None
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    retry_after = headers.get("retry-after") if headers is not None else None
    try:
        if retry_after is not None:
            return min(max(float(retry_after), 0.0), 60.0)
    except (TypeError, ValueError):
        pass
    return random.uniform(0.0, min(float(2**attempt), 60.0))


def get_client() -> AsyncOpenAI:
    global _EMBEDDING_CLIENT, _EMBEDDING_CLIENT_CACHE_KEY

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    cache_key = (os.getpid(), loop, settings.OPENAI_API_KEY, id(AsyncOpenAI))
    if (
        _EMBEDDING_CLIENT is not None
        and _EMBEDDING_CLIENT_CACHE_KEY == cache_key
        and getattr(_EMBEDDING_CLIENT, "is_closed", lambda: False)() is not True
    ):
        return _EMBEDDING_CLIENT

    # The explicit call-level retry below is the single retry owner.
    _EMBEDDING_CLIENT = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
    _EMBEDDING_CLIENT_CACHE_KEY = cache_key
    return _EMBEDDING_CLIENT


async def close_embedding_client() -> None:
    global _EMBEDDING_CLIENT, _EMBEDDING_CLIENT_CACHE_KEY

    client = _EMBEDDING_CLIENT
    _EMBEDDING_CLIENT = None
    _EMBEDDING_CLIENT_CACHE_KEY = None
    if client is not None:
        await client.close()


MAX_EMBED_BATCH_TOKENS = 250000


@retry(
    stop=stop_after_attempt(LLM_MAX_RETRIES + 1),
    wait=_embedding_retry_wait_seconds,
    retry=retry_if_exception(is_retryable_llm_call_error),
    reraise=True,
)
async def _create_embedding_with_retry(**kwargs: Any) -> Any:
    return await create_tracked_embedding(**kwargs)


async def embed_text(
    text: str,
    *,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None,
    book_id: uuid.UUID | None = None,
    feature: str = "embedding",
    budget_class: str | None = None,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
) -> list[float]:
    resolved_user_id = resolve_llm_usage_attribution(
        user_id,
        billing_scope=billing_scope,
    )
    normalized = (text or "")[:8000]

    cached = await get_embedding_cache(
        feature=feature,
        model=settings.OPENAI_EMBED_MODEL,
        text=normalized,
    )
    if cached is not None:
        return cached

    client = get_client()
    r = await _create_embedding_with_retry(
        client=client,
        feature=feature,
        model=settings.OPENAI_EMBED_MODEL,
        db=db,
        user_id=resolved_user_id,
        book_id=book_id,
        budget_class=budget_class,
        billing_scope=billing_scope,
        input=normalized,
    )
    result = r.data[0].embedding

    await set_embedding_cache(
        feature=feature,
        model=settings.OPENAI_EMBED_MODEL,
        text=normalized,
        vector=result,
    )
    return result


async def embed_batch(
    texts: list[str],
    *,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None,
    book_id: uuid.UUID | None = None,
    feature: str = "embedding_batch",
    budget_class: str | None = None,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
) -> list[list[float]]:
    """Embed multiple texts while staying under the provider token cap per request."""
    resolved_user_id = resolve_llm_usage_attribution(
        user_id,
        billing_scope=billing_scope,
    )
    cleaned = [t[:8000] for t in texts]
    if not cleaned:
        return []

    client = get_client()
    results: list[list[float]] = []
    batch: list[str] = []
    batch_tokens = 0

    for text in cleaned:
        token_count = count_tokens(text)
        if batch and batch_tokens + token_count > MAX_EMBED_BATCH_TOKENS:
            r = await _create_embedding_with_retry(
                client=client,
                feature=feature,
                model=settings.OPENAI_EMBED_MODEL,
                db=db,
                user_id=resolved_user_id,
                book_id=book_id,
                budget_class=budget_class,
                billing_scope=billing_scope,
                metadata={"batch_size": len(batch)},
                input=batch,
            )
            results.extend(item.embedding for item in sorted(r.data, key=lambda x: x.index))
            batch = []
            batch_tokens = 0

        batch.append(text)
        batch_tokens += token_count

    if batch:
        r = await _create_embedding_with_retry(
            client=client,
            feature=feature,
            model=settings.OPENAI_EMBED_MODEL,
            db=db,
            user_id=resolved_user_id,
            book_id=book_id,
            budget_class=budget_class,
            billing_scope=billing_scope,
            metadata={"batch_size": len(batch)},
            input=batch,
        )
        results.extend(item.embedding for item in sorted(r.data, key=lambda x: x.index))

    return results


async def embed_character(
    name: str,
    traits: dict,
    *,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | None,
    book_id: uuid.UUID | None = None,
    billing_scope: str = CUSTOMER_BILLING_SCOPE,
) -> list[float]:
    return await embed_text(
        build_character_embedding_text(name=name, traits=traits),
        db=db,
        user_id=user_id,
        book_id=book_id,
        feature="character_embedding",
        budget_class="processing",
        billing_scope=billing_scope,
    )


def build_chunk_embedding_text(
    *,
    chapter_number: int | None,
    chapter_title: str | None,
    text: str,
) -> str:
    title = (chapter_title or "Untitled").strip() or "Untitled"
    chapter_label = (
        f"Chapter {chapter_number}: {title}" if chapter_number is not None else f"Chapter: {title}"
    )
    body = (text or "").strip()
    return f"{chapter_label}\n\n{body}" if body else chapter_label


def build_character_embedding_text(
    *,
    name: str,
    traits: dict | None,
    aliases: list[str] | None = None,
    role: str | None = None,
    arc_summary: str | None = None,
    evidence_snippets: list[str] | None = None,
) -> str:
    parts = [f"Character: {name}"]
    cleaned_aliases = [str(alias).strip() for alias in aliases or [] if str(alias).strip()]
    if cleaned_aliases:
        parts.append(f"Aliases: {', '.join(cleaned_aliases[:6])}")
    if role:
        parts.append(f"Role: {role}")
    for key in ["hair", "eyes", "build", "age", "face", "distinguishing"]:
        t = (traits or {}).get(key, {})
        if isinstance(t, dict) and t.get("value"):
            parts.append(f"{key}: {t['value']}")
        elif isinstance(t, str) and t:
            parts.append(f"{key}: {t}")
    if arc_summary:
        parts.append(f"Arc: {arc_summary}")
    for snippet in [str(item).strip() for item in (evidence_snippets or []) if str(item).strip()][
        :3
    ]:
        parts.append(f"Evidence: {snippet[:220]}")
    return ". ".join(parts)
