"""
Advisor utility compatibility surface.

Implementation-heavy advisor workflows live in focused modules. This module
keeps the legacy import paths stable for routes, services, workers, and tests
while the codebase finishes migrating direct imports to domain modules.
"""

from __future__ import annotations

import asyncio
import uuid

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    invalidate_advisor_cache_namespaces,
)
from app.models.book import SeriesBook
from app.utils.advisor_chat_utils import (
    build_advisor_reply_payload,
    build_series_advisor_reply_payload,
    classify_response_type,
    stream_advisor_reply_payload,
    stream_series_advisor_reply_payload,
)
from app.utils.advisor_classification_utils import classify_intent_fast
from app.utils.advisor_prompt_templates import (
    EDITORIAL_SYSTEM,
    EDITORIAL_USER,
    INTENT_CLASSIFIER_PROMPT,
    PROACTIVE_SCAN_SYSTEM,
    PROACTIVE_SCAN_USER,
    PROSE_TIGHTEN_SYSTEM,
    PROSE_TIGHTEN_USER,
    SERIES_CONTINUITY_SYSTEM,
    SYNOPSIS_SYSTEM,
    SYNOPSIS_USER,
    VOICE_CONSISTENCY_SYSTEM,
    VOICE_CONSISTENCY_USER,
)
from app.utils.advisor_prompt_utils import (
    compute_synopsis_content_fingerprint,
    language_context_hint,
    make_advisor_cache_key,
    make_advisor_suggestions_cache_key,
    make_editorial_cache_key,
    safe_prompt_str,
)
from app.utils.advisor_report_utils import (
    build_continuity_report_markdown,
    build_continuity_report_pdf,
)
from app.utils.advisor_result_utils import (
    build_character_voice_context,
    build_fallback_advisor_suggestions,
    identify_character_mentions,
    merge_editorial_review_results,
    normalize_editorial_review_result,
    normalize_proactive_scan_result,
    normalize_prose_tighten_result,
    normalize_series_continuity_result,
    normalize_synopsis_result,
    normalize_voice_consistency_result,
)
from app.utils.advisor_retrieval_utils import (
    advisor_retrieval_settings,
    build_advisor_world_analysis,
    detect_advisor_world_mode,
    retrieve_series_continuity_passages,
)
from app.utils.advisor_scan_utils import build_advisor_suggestions_payload
from app.utils.advisor_story_context_utils import (
    build_series_story_context,
    build_story_context,
)
from app.utils.advisor_word_finder_utils import (
    generate_whats_the_word_result,
    normalize_whats_the_word_result,
)
from app.utils.advisor_world_context_utils import build_advisor_world_context
from app.utils.llm_usage_utils import create_tracked_chat_completion
from app.utils.world_building_utils import classify_world_intent

ADVISOR_LLM_FALLBACK_ERRORS = (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAIError,
    asyncio.TimeoutError,
    AttributeError,
    IndexError,
    KeyError,
    TypeError,
    ValueError,
)


async def invalidate_advisor_caches(
    *,
    book_id: uuid.UUID | str | None = None,
    series_ids: list[uuid.UUID | str] | None = None,
) -> None:
    """Drop shared advisor/editorial cache namespaces after semantic content changes."""
    await invalidate_advisor_cache_namespaces(
        book_id=str(book_id) if book_id is not None else None,
        series_ids=[str(series_id) for series_id in (series_ids or [])],
    )


async def invalidate_advisor_caches_for_book(db: AsyncSession, *, book_id: uuid.UUID | str) -> None:
    series_rows = (
        await db.execute(
            select(SeriesBook.series_id).where(SeriesBook.book_id == uuid.UUID(str(book_id)))
        )
    ).all()
    await invalidate_advisor_caches(
        book_id=book_id,
        series_ids=[row.series_id for row in series_rows],
    )


async def classify_intent(
    client: AsyncOpenAI,
    message: str,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID | None = None,
) -> str:
    try:
        response = await create_tracked_chat_completion(
            client=client,
            feature="advisor_intent_classification",
            model=settings.OPENAI_INTEL_MODEL,
            user_id=user_id,
            book_id=book_id,
            max_tokens=10,
            temperature=0,
            messages=[
                {"role": "user", "content": INTENT_CLASSIFIER_PROMPT.format(message=message[:500])},
            ],
        )
        return (response.choices[0].message.content or "").strip().lower()
    except ADVISOR_LLM_FALLBACK_ERRORS:
        return "general"
