import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import REDIS_OPERATION_EXCEPTIONS, get_redis, key_ratelimit
from app.models.user import User
from app.utils.billing_utils import (
    DAILY_LIMIT_MESSAGE,
    advisor_daily_limit_message,
    continuity_daily_limit_message,
    continuity_limit_per_day,
    free_advisor_limit_per_week,
    free_search_limit_per_day,
    prediction_limit_per_day,
    protected_authoring_limit_per_day,
    recall_limit_per_day,
)
from app.utils.client_identity import trusted_client_identifier
from app.utils.email_utils import track_usage_limit_friction_and_maybe_send
from app.utils.rate_limit_utils import limit_for_user

log = logging.getLogger("lorevia.rate_limit")


async def _window(key: str, limit: int, window: int = 60, *, fail_open: bool = False) -> bool:
    try:
        r = await get_redis()
        now = time.time()
        member = f"{int(now * 1000)}:{uuid.uuid4().hex}"
        if hasattr(r, "pipeline"):
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {member: now})
            pipe.zcard(key)
            pipe.expire(key, window)
            results = await pipe.execute()
            return results[2] <= limit

        # Some lightweight test doubles only implement simple counter primitives.
        # Fall back to a coarse per-window counter so routes remain testable without
        # requiring full sorted-set pipeline semantics.
        await r.set(key, "0", ex=window, nx=True)
        count = int(await r.incr(key))
        return count <= limit
    except REDIS_OPERATION_EXCEPTIONS as exc:
        if fail_open:
            log.warning("rate_limit_redis_unavailable_fail_open", extra={"rate_limit_key": key})
            return True
        raise HTTPException(
            503,
            "This action is temporarily unavailable. Please try again shortly.",
        ) from exc


async def _require_window(key: str, limit: int, window: int, message: str) -> None:
    ok = await _window(key, limit, window)
    if not ok:
        raise HTTPException(429, message)


def _current_utc(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current if current.tzinfo else current.replace(tzinfo=UTC)


def _utc_day_bucket(action: str, now: datetime | None = None) -> tuple[str, int]:
    current = _current_utc(now)
    tomorrow = current.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + 86400
    ttl_seconds = max(int(tomorrow - current.timestamp()), 1)
    return current.strftime(f"{action}:%Y%m%d"), ttl_seconds


def _utc_week_bucket(action: str, now: datetime | None = None) -> tuple[str, int]:
    current = _current_utc(now)
    week_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    next_week = week_start + timedelta(days=7 - current.weekday())
    ttl_seconds = max(int(next_week.timestamp() - current.timestamp()), 1)
    iso_year, iso_week, _ = current.isocalendar()
    return f"{action}:{iso_year}w{iso_week:02d}", ttl_seconds


async def _bump_daily_bucket(
    db: AsyncSession,
    user: User | object,
    action: str,
    limit: int,
    *,
    message: str | None = None,
) -> None:
    if limit <= 0:
        raise HTTPException(403, DAILY_LIMIT_MESSAGE)

    bucket, ttl_seconds = _utc_day_bucket(action)
    user_id = getattr(user, "id", user)
    key = key_ratelimit(str(user_id), bucket)
    r = await get_redis()
    await r.set(key, "0", ex=ttl_seconds, nx=True)
    count = int(await r.incr(key))
    if count > limit:
        if isinstance(user, User) or getattr(user, "email", None):
            await track_usage_limit_friction_and_maybe_send(user, action=action)
        raise HTTPException(429, message or DAILY_LIMIT_MESSAGE)


async def _bump_weekly_bucket(
    db: AsyncSession,
    user: User | object,
    action: str,
    limit: int,
) -> None:
    if limit <= 0:
        raise HTTPException(403, DAILY_LIMIT_MESSAGE)

    bucket, ttl_seconds = _utc_week_bucket(action)
    user_id = getattr(user, "id", user)
    key = key_ratelimit(str(user_id), bucket)
    r = await get_redis()
    await r.set(key, "0", ex=ttl_seconds, nx=True)
    count = int(await r.incr(key))
    if count > limit:
        if isinstance(user, User) or getattr(user, "email", None):
            await track_usage_limit_friction_and_maybe_send(user, action=action)
        raise HTTPException(
            429, "Your free Story Advisor turn refreshes next week. Upgrade for more capacity."
        )


async def rate_limit_search(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    limit = free_search_limit_per_day(current_user)
    if limit is None:
        return
    limit = await _limit_for_user(db, current_user.id, "search_per_hour", limit)
    await _bump_daily_bucket(db, current_user, "search", limit)


async def rate_limit_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_window_limit(
        db,
        current_user.id,
        "summary",
        field="summary_per_hour",
        default=settings.FREE_SUMMARY_PER_HOUR,
        window=3600,
        message=DAILY_LIMIT_MESSAGE,
    )


async def rate_limit_chat(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    daily_limit = prediction_limit_per_day(current_user)
    daily_limit = await _limit_for_user(db, current_user.id, "chat_per_day", daily_limit)
    await _bump_daily_bucket(db, current_user, "prediction", daily_limit)


async def rate_limit_advisor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    weekly_limit = free_advisor_limit_per_week(current_user)
    if weekly_limit is not None:
        weekly_limit = await _limit_for_user(db, current_user.id, "advisor_per_week", weekly_limit)
        await _bump_weekly_bucket(db, current_user, "advisor", weekly_limit)
        return

    daily_limit = protected_authoring_limit_per_day(current_user)
    if daily_limit <= 0:
        raise HTTPException(
            403, "Story Advisor requires an active trial, Author, or Architect plan."
        )
    daily_limit = await _limit_for_user(db, current_user.id, "advisor_per_day", daily_limit)
    await _bump_daily_bucket(
        db,
        current_user,
        "high_cost_authoring",
        daily_limit,
        message=advisor_daily_limit_message(daily_limit),
    )


async def rate_limit_recall(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    daily_limit = recall_limit_per_day(current_user)
    if daily_limit is None:
        return
    await _bump_daily_bucket(db, current_user, "recall", daily_limit)


async def rate_limit_continuity_checker(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce_continuity_rate_limit(db, current_user)


async def enforce_continuity_rate_limit(db: AsyncSession, billing_user: User) -> None:
    daily_limit = continuity_limit_per_day(billing_user)
    if daily_limit <= 0:
        raise HTTPException(
            403, "Continuity checks are authoring features. Upgrade to Author for access."
        )
    await _bump_daily_bucket(
        db,
        billing_user,
        "continuity",
        daily_limit,
        message=continuity_daily_limit_message(daily_limit),
    )


async def rate_limit_api(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    limit = await _limit_for_user(db, current_user.id, "api_per_minute", 300)
    ok = await _window(
        key_ratelimit(str(current_user.id), "api"),
        limit,
        60,
        fail_open=True,
    )
    if not ok:
        raise HTTPException(429, "Rate limit exceeded")


async def rate_limit_support(
    current_user: User = Depends(get_current_user),
):
    """Short abuse throttle; AI support replies are still charged to LLM usage."""

    ok = await _window(key_ratelimit(str(current_user.id), "support"), 30, 600)
    if not ok:
        raise HTTPException(
            429, "Too many support requests. Please wait a few minutes and try again."
        )


def _client_identifier(request: Request) -> str:
    return trusted_client_identifier(request)


async def _auth_window(request: Request, bucket: str, limit: int, window: int) -> None:
    identifier = _client_identifier(request)
    ok = await _window(key_ratelimit(f"auth:{identifier}", bucket), limit, window)
    if not ok:
        raise HTTPException(429, "Too many authentication attempts. Please wait and try again.")


async def rate_limit_auth_register(request: Request):
    await _auth_window(request, "register", 8, 3600)


async def rate_limit_auth_login(request: Request):
    await _auth_window(request, "login", 20, 900)


async def rate_limit_auth_password(request: Request):
    await _auth_window(request, "password", 8, 3600)


async def rate_limit_auth_refresh(request: Request):
    await _auth_window(request, "refresh", 30, 300)


async def rate_limit_public(request: Request):
    identifier = _client_identifier(request)
    ok = await _window(
        key_ratelimit(f"public:{identifier}", "api"),
        120,
        60,
        fail_open=True,
    )
    if not ok:
        raise HTTPException(429, "Public rate limit exceeded")


async def rate_limit_public_asset(request: Request):
    identifier = _client_identifier(request)
    ok = await _window(
        key_ratelimit(f"public:{identifier}", "asset"),
        240,
        60,
        fail_open=True,
    )
    if not ok:
        raise HTTPException(429, "Asset rate limit exceeded")


async def _user_window_limit(
    db: AsyncSession,
    user_id: object,
    action: str,
    *,
    field: str,
    default: int,
    window: int,
    message: str,
) -> None:
    limit = await _limit_for_user(db, user_id, field, default)
    await _require_window(key_ratelimit(str(user_id), action), limit, window, message)


async def rate_limit_upload(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_window_limit(
        db,
        current_user.id,
        "upload",
        field="uploads_per_hour",
        default=6,
        window=3600,
        message="Upload rate limit exceeded. Please wait before uploading more files.",
    )


async def rate_limit_public_publish(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_window_limit(
        db,
        current_user.id,
        "public_publish",
        field="public_publish_per_hour",
        default=6,
        window=3600,
        message="Public publishing rate limit exceeded. Please wait before trying again.",
    )


async def rate_limit_public_unpublish(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_window_limit(
        db,
        current_user.id,
        "public_unpublish",
        field="public_unpublish_per_hour",
        default=12,
        window=3600,
        message="Public unpublish rate limit exceeded. Please wait before trying again.",
    )


async def rate_limit_public_report(request: Request):
    identifier = _client_identifier(request)
    ok = await _window(key_ratelimit(f"public-report:{identifier}", "report"), 8, 3600)
    if not ok:
        raise HTTPException(
            429, "Report rate limit exceeded. Please wait before sending another report."
        )


async def rate_limit_manuscript_import(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_window_limit(
        db,
        current_user.id,
        "manuscript_import",
        field="manuscript_imports_per_hour",
        default=12,
        window=3600,
        message="Manuscript import rate limit exceeded. Please wait before importing more files.",
    )


async def enforce_manuscript_import_rate_limit(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> None:
    await _user_window_limit(
        db,
        user_id,
        "manuscript_import",
        field="manuscript_imports_per_hour",
        default=12,
        window=3600,
        message="Manuscript import rate limit exceeded. Please wait before importing more files.",
    )


async def rate_limit_world_building_upload(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_window_limit(
        db,
        current_user.id,
        "world_building_upload",
        field="world_building_uploads_per_hour",
        default=10,
        window=3600,
        message="World-building upload rate limit exceeded. Please wait before uploading more documents.",
    )


async def enforce_world_building_upload_rate_limit(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> None:
    await _user_window_limit(
        db,
        user_id,
        "world_building_upload",
        field="world_building_uploads_per_hour",
        default=10,
        window=3600,
        message="World-building upload rate limit exceeded. Please wait before uploading more documents.",
    )


async def rate_limit_world_building_ai(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _user_window_limit(
        db,
        current_user.id,
        "world_building_ai",
        field="world_building_ai_per_hour",
        default=30,
        window=3600,
        message="World-building analysis rate limit exceeded. Please wait before running more AI requests.",
    )


async def rate_limit_internal_job(
    request: Request,
):
    identifier = _client_identifier(request)
    ok = await _window(key_ratelimit(f"internal_job:{identifier}", "job"), 10, 60)
    if not ok:
        raise HTTPException(429, "Internal job rate limit exceeded. Please wait and try again.")


async def rate_limit_verified_internal_scheduler():
    ok = await _window(key_ratelimit("internal_job:scheduler", "job"), 60, 60)
    if not ok:
        raise HTTPException(429, "Internal job rate limit exceeded. Please wait and try again.")


async def _limit_for_user(
    db: AsyncSession,
    user_id: object,
    field: str,
    default: int,
) -> int:
    return await limit_for_user(db, user_id, field, default)
