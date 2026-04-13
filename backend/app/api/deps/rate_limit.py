from fastapi import Depends, HTTPException, Request
from app.core.redis import get_redis, key_ratelimit
from app.core.config import effective_tier, settings
from app.api.deps.auth import get_current_user
from app.models.user import User, UserRateLimitOverride
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
import time


async def _window(key: str, limit: int, window: int = 60) -> bool:
    r = await get_redis()
    now = int(time.time())
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    return results[2] <= limit


async def rate_limit_search(current_user: User = Depends(get_current_user)):
    if effective_tier(current_user.tier) == "free":
        limit = await _limit_for_user(current_user.id, "search_per_hour", settings.FREE_SEARCH_PER_HOUR)
        ok = await _window(key_ratelimit(str(current_user.id), "search"), limit, 3600)
        if not ok:
            raise HTTPException(429, "Search limit reached. Upgrade to Pro for unlimited search.")


async def rate_limit_summary(current_user: User = Depends(get_current_user)):
    if effective_tier(current_user.tier) == "free":
        limit = await _limit_for_user(current_user.id, "summary_per_hour", settings.FREE_SUMMARY_PER_HOUR)
        ok = await _window(key_ratelimit(str(current_user.id), "summary"), limit, 3600)
        if not ok:
            raise HTTPException(429, "Summary limit reached. Upgrade to Pro.")


async def rate_limit_chat(current_user: User = Depends(get_current_user)):
    tier = effective_tier(current_user.tier)
    daily_limit = {
        "free": settings.FREE_CHAT_PER_DAY,
        "pro": settings.PRO_CHAT_PER_DAY,
        "power": 999999,
    }.get(tier, settings.FREE_CHAT_PER_DAY)
    daily_limit = await _limit_for_user(current_user.id, "chat_per_day", daily_limit)
    ok = await _window(key_ratelimit(str(current_user.id), "chat"), daily_limit, 86400)
    if not ok:
        raise HTTPException(429, "Chat turn limit reached for today.")


async def rate_limit_api(request: Request, current_user: User = Depends(get_current_user)):
    limit = await _limit_for_user(current_user.id, "api_per_minute", 300)
    ok = await _window(key_ratelimit(str(current_user.id), "api"), limit, 60)
    if not ok:
        raise HTTPException(429, "Rate limit exceeded")


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


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


async def _limit_for_user(user_id, field: str, default: int) -> int:
    async with AsyncSessionLocal() as db:
        override = (
            await db.execute(
                select(UserRateLimitOverride).where(UserRateLimitOverride.user_id == user_id)
            )
        ).scalar()
        if not override:
            return default
        value = getattr(override, field, None)
        return int(value) if isinstance(value, int) and value > 0 else default
