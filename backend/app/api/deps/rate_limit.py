from fastapi import Depends, HTTPException, Request
from app.core.redis import get_redis, key_ratelimit
from app.core.config import settings
from app.api.deps.auth import get_current_user
from app.models.user import User
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
    if current_user.tier == "free":
        ok = await _window(key_ratelimit(str(current_user.id), "search"), settings.FREE_SEARCH_PER_HOUR, 3600)
        if not ok:
            raise HTTPException(429, "Search limit reached. Upgrade to Pro for unlimited search.")


async def rate_limit_summary(current_user: User = Depends(get_current_user)):
    if current_user.tier == "free":
        ok = await _window(key_ratelimit(str(current_user.id), "summary"), settings.FREE_SUMMARY_PER_HOUR, 3600)
        if not ok:
            raise HTTPException(429, "Summary limit reached. Upgrade to Pro.")


async def rate_limit_chat(current_user: User = Depends(get_current_user)):
    daily_limit = {
        "free": settings.FREE_CHAT_PER_DAY,
        "pro": settings.PRO_CHAT_PER_DAY,
        "power": 999999,
    }.get(current_user.tier, settings.FREE_CHAT_PER_DAY)
    ok = await _window(key_ratelimit(str(current_user.id), "chat"), daily_limit, 86400)
    if not ok:
        raise HTTPException(429, "Chat turn limit reached for today.")


async def rate_limit_api(request: Request, current_user: User = Depends(get_current_user)):
    ok = await _window(key_ratelimit(str(current_user.id), "api"), 300, 60)
    if not ok:
        raise HTTPException(429, "Rate limit exceeded")
