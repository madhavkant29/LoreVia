import time
import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from app.api.deps.auth import get_current_user
from app.core.config import effective_tier, settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis, key_ratelimit
from app.models.user import User, UserRateLimitOverride


async def _window(key: str, limit: int, window: int = 60) -> bool:
    r = await get_redis()
    now = time.time()
    member = f"{int(now * 1000)}:{uuid.uuid4().hex}"
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    return results[2] <= limit


async def _require_window(key: str, limit: int, window: int, message: str) -> None:
    ok = await _window(key, limit, window)
    if not ok:
        raise HTTPException(429, message)


async def rate_limit_search(current_user: User = Depends(get_current_user)):
    if effective_tier(current_user.tier) == "free":
        limit = await _limit_for_user(current_user.id, "search_per_hour", settings.FREE_SEARCH_PER_HOUR)
        ok = await _window(key_ratelimit(str(current_user.id), "search"), limit, 3600)
        if not ok:
            raise HTTPException(429, "Too many search requests right now. Please try again later.")


async def rate_limit_summary(current_user: User = Depends(get_current_user)):
    if effective_tier(current_user.tier) == "free":
        limit = await _limit_for_user(current_user.id, "summary_per_hour", settings.FREE_SUMMARY_PER_HOUR)
        ok = await _window(key_ratelimit(str(current_user.id), "summary"), limit, 3600)
        if not ok:
            raise HTTPException(429, "Too many summary requests right now. Please try again later.")


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
        raise HTTPException(429, "Too many chat requests right now. Please try again later.")


async def rate_limit_advisor(current_user: User = Depends(get_current_user)):
    tier = effective_tier(current_user.tier)
    limits = {
        "free": (
            settings.FREE_ADVISOR_PER_DAY,
            settings.FREE_ADVISOR_PER_WEEK,
            settings.FREE_ADVISOR_PER_MONTH,
        ),
        "pro": (
            settings.PRO_ADVISOR_PER_DAY,
            settings.PRO_ADVISOR_PER_WEEK,
            settings.PRO_ADVISOR_PER_MONTH,
        ),
        "power": (
            settings.POWER_ADVISOR_PER_DAY,
            settings.POWER_ADVISOR_PER_WEEK,
            settings.POWER_ADVISOR_PER_MONTH,
        ),
    }
    daily_limit, weekly_limit, monthly_limit = limits.get(
        tier,
        (
            settings.FREE_ADVISOR_PER_DAY,
            settings.FREE_ADVISOR_PER_WEEK,
            settings.FREE_ADVISOR_PER_MONTH,
        ),
    )
    daily_limit = await _limit_for_user(current_user.id, "advisor_per_day", daily_limit)
    message = "Too many Story Advisor requests right now. Please try again later."
    await _require_window(key_ratelimit(str(current_user.id), "advisor:day"), daily_limit, 86400, message)
    await _require_window(key_ratelimit(str(current_user.id), "advisor:week"), weekly_limit, 604800, message)
    await _require_window(key_ratelimit(str(current_user.id), "advisor:month"), monthly_limit, 2592000, message)


async def rate_limit_continuity_checker(current_user: User = Depends(get_current_user)):
    tier = effective_tier(current_user.tier)
    per_minute = {
        "free": settings.FREE_CONTINUITY_PER_MINUTE,
        "pro": settings.PRO_CONTINUITY_PER_MINUTE,
        "power": settings.POWER_CONTINUITY_PER_MINUTE,
    }.get(tier, settings.FREE_CONTINUITY_PER_MINUTE)
    await _require_window(
        key_ratelimit(str(current_user.id), "continuity"),
        per_minute,
        60,
        "Too many continuity checks right now. Please try again in a minute.",
    )


async def rate_limit_api(request: Request, current_user: User = Depends(get_current_user)):
    limit = await _limit_for_user(current_user.id, "api_per_minute", 300)
    ok = await _window(key_ratelimit(str(current_user.id), "api"), limit, 60)
    if not ok:
        raise HTTPException(429, "Rate limit exceeded")


import ipaddress as _ipaddress

# RFC-1918 + loopback ranges that may legitimately act as reverse proxies.
# Forwarded-IP headers are only trusted when the *direct* TCP connection
# comes from one of these networks — preventing header-spoofing by external
# clients who otherwise control X-Forwarded-For / CF-Connecting-IP freely.
_TRUSTED_PROXY_NETS = [
    _ipaddress.ip_network("10.0.0.0/8"),
    _ipaddress.ip_network("172.16.0.0/12"),
    _ipaddress.ip_network("192.168.0.0/16"),
    _ipaddress.ip_network("127.0.0.0/8"),
    _ipaddress.ip_network("::1/128"),
]


def _is_trusted_proxy(host: str) -> bool:
    try:
        addr = _ipaddress.ip_address(host)
        return any(addr in net for net in _TRUSTED_PROXY_NETS)
    except ValueError:
        return False


def _client_identifier(request: Request) -> str:
    direct_ip = request.client.host if request.client else None

    # Only trust forwarded-IP headers when the TCP peer is a known proxy.
    # An external client can freely forge these headers if we skip this check.
    if direct_ip and _is_trusted_proxy(direct_ip):
        # Priority order matters:
        #   1. CF-Connecting-IP  — set exclusively by Cloudflare; clients cannot forge it
        #      when the request arrives via the Cloudflare Tunnel.
        #   2. X-Real-IP        — set directly by Render's LB / Nginx; clients cannot
        #      inject it because the proxy overwrites (not appends) this header.
        #   3. X-Forwarded-For  — least reliable: proxies *append* to it, so a client
        #      can prepend fake IPs. Checked last as a fallback.
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip and cf_ip.strip():
            return cf_ip.strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()

        xff = request.headers.get("x-forwarded-for")
        if xff:
            # Take the leftmost entry only — valid when the proxy *prepends*
            # the real client IP (Cloudflare / most CDNs). For Render, prefer
            # X-Real-IP above so we never reach this branch with spoofed data.
            leftmost = xff.split(",")[0].strip()
            if leftmost:
                return leftmost

    return direct_ip or "unknown"


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
    ok = await _window(key_ratelimit(f"public:{identifier}", "api"), 120, 60)
    if not ok:
        raise HTTPException(429, "Public rate limit exceeded")


async def rate_limit_public_asset(request: Request):
    identifier = _client_identifier(request)
    ok = await _window(key_ratelimit(f"public:{identifier}", "asset"), 240, 60)
    if not ok:
        raise HTTPException(429, "Asset rate limit exceeded")


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
