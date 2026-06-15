from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_del, cache_get, cache_set
from app.models.user import UserRateLimitOverride

log = logging.getLogger("lorevia.rate_limit")

RATE_LIMIT_OVERRIDE_CACHE_TTL_SECONDS = 120
_NO_OVERRIDE = "__none__"
_OVERRIDE_FIELDS = (
    "search_per_hour",
    "summary_per_hour",
    "chat_per_day",
    "api_per_minute",
    "advisor_per_day",
    "uploads_per_hour",
    "public_publish_per_hour",
    "public_unpublish_per_hour",
    "manuscript_imports_per_hour",
    "world_building_uploads_per_hour",
    "world_building_ai_per_hour",
)


def rate_limit_override_cache_key(user_id: object) -> str:
    return f"rate_limit_override:{user_id}"


def _serialize_override(override: UserRateLimitOverride | None) -> dict[str, int | None] | str:
    if override is None:
        return _NO_OVERRIDE
    return {field: getattr(override, field, None) for field in _OVERRIDE_FIELDS}


async def get_cached_rate_limit_override(
    db: AsyncSession,
    user_id: uuid.UUID | str | object,
) -> dict[str, int | None] | None:
    key = rate_limit_override_cache_key(user_id)
    try:
        cached = await cache_get(key)
    except Exception:
        log.warning("rate_limit_override_cache_get_failed", extra={"user_id": str(user_id)}, exc_info=True)
        cached = None

    if cached == _NO_OVERRIDE:
        return None
    if isinstance(cached, dict):
        return {field: cached.get(field) for field in _OVERRIDE_FIELDS}

    override = (
        await db.execute(
            select(UserRateLimitOverride).where(UserRateLimitOverride.user_id == user_id)
        )
    ).scalar()
    payload = _serialize_override(override)
    try:
        await cache_set(key, payload, RATE_LIMIT_OVERRIDE_CACHE_TTL_SECONDS)
    except Exception:
        log.warning("rate_limit_override_cache_set_failed", extra={"user_id": str(user_id)}, exc_info=True)
    return None if payload == _NO_OVERRIDE else payload


async def limit_for_user(
    db: AsyncSession,
    user_id: uuid.UUID | str | object,
    field: str,
    default: int,
) -> int:
    override = await get_cached_rate_limit_override(db, user_id)
    if not override:
        return default
    value: Any = override.get(field)
    return int(value) if isinstance(value, int) and value > 0 else default


async def invalidate_rate_limit_override_cache(user_id: uuid.UUID | str | object) -> None:
    try:
        await cache_del(rate_limit_override_cache_key(user_id))
    except Exception:
        log.warning("rate_limit_override_cache_delete_failed", extra={"user_id": str(user_id)}, exc_info=True)
