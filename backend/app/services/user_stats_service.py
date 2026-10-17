"""Bounded, display-only assembly for the author statistics response."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    USER_STATS_CACHE_TTL_SECONDS,
    cache_get,
    cache_set,
    get_user_dashboard_cache_version,
    key_user_stats_cache,
)
from app.models.intelligence import QuoteEntry
from app.schemas.books import PrivateUserStats, PublicUserStats, UserStatsOut
from app.services.library_stats_service import load_library_aggregate_stats
from app.services.processing_allowance_service import summarize_processing_allowances
from app.utils.billing_utils import calculate_upload_usage_summary
from app.utils.llm_usage_utils import summarize_llm_usage_for_user
from app.utils.user_utils import build_writing_dashboard_stats


async def build_user_stats(db: AsyncSession, current_user: Any) -> UserStatsOut:
    """Build the authoritative user-facing statistics payload.

    This is deliberately separate from authorization and allowance-reservation
    paths. Consumers may cache this display snapshot briefly without changing
    plan enforcement or billing decisions.
    """

    library_stats = await load_library_aggregate_stats(db, current_user.id)
    saved_quotes = int(
        (
            await db.execute(
                select(func.count(QuoteEntry.id)).where(QuoteEntry.user_id == current_user.id)
            )
        ).scalar()
        or 0
    )
    writing_stats = await build_writing_dashboard_stats(db, current_user)
    upload_usage = await calculate_upload_usage_summary(db, current_user)
    processing_allowances = await summarize_processing_allowances(db, current_user)
    llm_usage = await summarize_llm_usage_for_user(db, current_user.id)

    return UserStatsOut(
        public=PublicUserStats(
            total_books_read=library_stats.total_books_read,
            total_words_read=library_stats.total_words_read,
        ),
        private=PrivateUserStats(
            total_uploads=upload_usage.total_uploads,
            manuscript_uploads=upload_usage.manuscript_uploads,
            worldbuilding_uploads=upload_usage.worldbuilding_uploads,
            upload_limit=upload_usage.upload_limit,
            uploads_remaining=upload_usage.uploads_remaining,
            upload_limit_unlimited=upload_usage.upload_limit_unlimited,
            active_analyzed_words=processing_allowances.active_analyzed_words,
            active_word_limit=processing_allowances.active_word_limit,
            active_words_remaining=processing_allowances.active_words_remaining,
            monthly_processed_words=processing_allowances.monthly_processed_words,
            monthly_processed_word_limit=processing_allowances.monthly_processed_word_limit,
            monthly_processed_words_remaining=processing_allowances.monthly_processed_words_remaining,
            source_storage_bytes=processing_allowances.source_storage_bytes,
            source_storage_limit_bytes=processing_allowances.source_storage_limit_bytes,
            source_storage_remaining_bytes=processing_allowances.source_storage_remaining_bytes,
            allowances_enforced=processing_allowances.allowances_enforced,
            total_token_consumption=library_stats.total_token_consumption,
            llm_request_count=llm_usage.request_count,
            llm_prompt_tokens=llm_usage.prompt_tokens,
            llm_completion_tokens=llm_usage.completion_tokens,
            llm_total_tokens=llm_usage.total_tokens,
            ai_interactive_available=llm_usage.ai_interactive_available,
            ai_processing_available=llm_usage.ai_processing_available,
            ai_capacity_usage_percent=llm_usage.ai_capacity_usage_percent,
            ai_capacity_resets_at=llm_usage.ai_capacity_resets_at,
            total_chapters_tracked=library_stats.total_chapters_tracked,
            saved_quotes=saved_quotes,
        ),
        writing=writing_stats,
    )


async def get_user_stats_cached(db: AsyncSession, current_user: Any) -> UserStatsOut:
    """Return a safe, short-lived display snapshot with versioned invalidation."""

    user_id = str(current_user.id)
    version = await get_user_dashboard_cache_version(user_id)
    cached = await cache_get(key_user_stats_cache(user_id, version))
    if isinstance(cached, dict):
        try:
            return UserStatsOut.model_validate(cached)
        except (TypeError, ValueError):
            # A malformed/old cache entry must never make the dashboard fail.
            pass

    payload = await build_user_stats(db, current_user)
    await cache_set(
        key_user_stats_cache(user_id, version),
        payload.model_dump(mode="json"),
        USER_STATS_CACHE_TTL_SECONDS,
    )
    return payload
