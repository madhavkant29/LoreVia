import asyncio
import hashlib
import json
import time
import weakref
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import redis.asyncio as aioredis

from app.core.config import settings

_redis_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, aioredis.Redis] = weakref.WeakKeyDictionary()


def _hash_ephemeral_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_redis_url(raw_url: str) -> tuple[str, dict]:
    if not raw_url.startswith("rediss://"):
        return raw_url, {}

    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["ssl_cert_reqs"] = (query.get("ssl_cert_reqs") or "required").lower()
    normalized_url = urlunsplit(parts._replace(query=urlencode(query)))
    return normalized_url, {}


async def get_redis() -> aioredis.Redis:
    loop = asyncio.get_running_loop()
    client = _redis_clients.get(loop)
    if client is None:
        redis_url, redis_kwargs = _normalize_redis_url(settings.REDIS_URL)
        client = aioredis.from_url(redis_url, decode_responses=True, **redis_kwargs)
        _redis_clients[loop] = client
    return client


async def close_redis(loop: asyncio.AbstractEventLoop | None = None) -> None:
    target_loop = loop or asyncio.get_running_loop()
    client = _redis_clients.pop(target_loop, None)
    if client is not None:
        await client.aclose()


async def close_all_redis_clients() -> None:
    clients = list(_redis_clients.items())
    _redis_clients.clear()
    for _, client in clients:
        await client.aclose()


async def cache_set(key: str, value: object, ttl: int) -> None:
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value, default=str))


async def cache_set_if_absent(key: str, value: object, ttl: int) -> bool:
    r = await get_redis()
    return bool(await r.set(key, json.dumps(value, default=str), ex=ttl, nx=True))


async def cache_get(key: str) -> object | None:
    r = await get_redis()
    data = await r.get(key)
    return json.loads(data) if data else None


async def cache_del(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


async def cache_get_int(key: str, default: int = 0) -> int:
    r = await get_redis()
    value = await r.get(key)
    return int(value) if value is not None else default


async def cache_incr(key: str, default: int = 1) -> int:
    r = await get_redis()
    if await r.exists(key):
        return int(await r.incr(key))
    await r.set(key, str(default))
    return default


async def cache_set_version_marker(key: str) -> int:
    r = await get_redis()
    candidate = int(time.time() * 1000)
    existing = await r.get(key)
    if existing is not None:
        try:
            candidate = max(candidate, int(existing) + 1)
        except ValueError:
            pass
    await r.set(key, str(candidate))
    return candidate


async def get_token_version(user_id: str) -> int:
    r = await get_redis()
    key = key_token_version(user_id)
    value = await r.get(key)
    if value is None:
        await r.set(key, "1")
        return 1
    return int(value)


async def bump_token_version(user_id: str) -> int:
    r = await get_redis()
    key = key_token_version(user_id)
    if await r.get(key) is None:
        await r.set(key, "1")
    return int(await r.incr(key))


async def store_refresh_session(user_id: str, session_id: str, ttl_seconds: int) -> None:
    r = await get_redis()
    await r.setex(key_refresh_session(user_id, session_id), ttl_seconds, "1")


async def refresh_session_active(user_id: str, session_id: str) -> bool:
    r = await get_redis()
    return bool(await r.exists(key_refresh_session(user_id, session_id)))


async def revoke_refresh_session(user_id: str, session_id: str) -> None:
    r = await get_redis()
    await r.delete(key_refresh_session(user_id, session_id))


async def remember_webhook_event(event_id: str, ttl_seconds: int = 7 * 24 * 3600) -> bool:
    r = await get_redis()
    return bool(await r.set(key_webhook_event(event_id), "1", ex=ttl_seconds, nx=True))


async def store_password_reset_token(token: str, user_id: str, ttl_seconds: int) -> None:
    r = await get_redis()
    previous_token = await r.get(key_password_reset_user(user_id))
    token_hash = _hash_ephemeral_token(token)
    async with r.pipeline(transaction=True) as pipe:
        if previous_token:
            pipe.delete(key_password_reset(_hash_ephemeral_token(previous_token)))
        pipe.setex(key_password_reset(token_hash), ttl_seconds, user_id)
        pipe.setex(key_password_reset_user(user_id), ttl_seconds, token)
        await pipe.execute()


async def consume_password_reset_token(token: str) -> str | None:
    r = await get_redis()
    key = key_password_reset(_hash_ephemeral_token(token))
    value = await r.get(key)
    if not value:
        return None
    async with r.pipeline(transaction=True) as pipe:
        pipe.delete(key)
        pipe.delete(key_password_reset_user(value))
        await pipe.execute()
    return value


async def begin_password_reset_cooldown(user_id: str, ttl_seconds: int) -> bool:
    r = await get_redis()
    return bool(await r.set(key_password_reset_cooldown(user_id), "1", ex=ttl_seconds, nx=True))


async def store_email_verification_token(token: str, user_id: str, ttl_seconds: int) -> None:
    r = await get_redis()
    previous_token = await r.get(key_email_verification_user(user_id))
    async with r.pipeline(transaction=True) as pipe:
        if previous_token:
            pipe.delete(key_email_verification(previous_token))
        pipe.setex(key_email_verification(token), ttl_seconds, user_id)
        pipe.setex(key_email_verification_user(user_id), ttl_seconds, token)
        await pipe.execute()


async def consume_email_verification_token(token: str) -> str | None:
    r = await get_redis()
    key = key_email_verification(token)
    value = await r.get(key)
    if not value:
        return None
    async with r.pipeline(transaction=True) as pipe:
        pipe.delete(key)
        pipe.delete(key_email_verification_user(value))
        await pipe.execute()
    return value


# ── Key builders — single source of truth ────────────────────────────────────
def key_character_profile(character_id: str) -> str:
    return f"character:profile:{character_id}"

def key_chapter_summary(chapter_id: str, mode: str) -> str:
    return f"chapter:summary:{chapter_id}:{mode}"


def key_analysis_inflight(chapter_id: str) -> str:
    return f"analysis:inflight:{chapter_id}"


def key_extraction_inflight(book_id: str, chapter_number: int) -> str:
    return f"extraction:inflight:{book_id}:{chapter_number}"


def key_chapter_recovery_inflight(chapter_id: str) -> str:
    return f"chapter_recovery:inflight:{chapter_id}"

def key_relationship_graph(book_id: str, chapter: int) -> str:
    return f"relationship:graph:{book_id}:{chapter}"

def key_search_results(book_id: str, query: str, chapter: int) -> str:
    q_hash = hashlib.md5(query.encode()).hexdigest()[:8]
    return f"book:search:{book_id}:{q_hash}:{chapter}"

def key_memory_recall(user_id: str, book_id: str) -> str:
    return f"recall:{user_id}:{book_id}"

def key_book_status(book_id: str) -> str:
    return f"book:status:{book_id}"

def key_ratelimit(user_id: str, action: str) -> str:
    return f"ratelimit:{user_id}:{action}"


def key_token_version(user_id: str) -> str:
    return f"token_version:{user_id}"


def key_refresh_session(user_id: str, session_id: str) -> str:
    return f"refresh_session:{user_id}:{session_id}"


def key_webhook_event(event_id: str) -> str:
    return f"webhook:event:{event_id}"


def key_password_reset(token: str) -> str:
    return f"password_reset:{token}"


def key_password_reset_user(user_id: str) -> str:
    return f"password_reset_user:{user_id}"


def key_password_reset_cooldown(user_id: str) -> str:
    return f"password_reset_cooldown:{user_id}"


def key_email_verification(token: str) -> str:
    return f"email_verification:{token}"


def key_email_verification_user(user_id: str) -> str:
    return f"email_verification_user:{user_id}"


def key_grounded_answer(book_id: str, chapter: int, question: str) -> str:
    q_hash = hashlib.md5(question.strip().lower().encode()).hexdigest()[:10]
    return f"grounded_answer:{book_id}:{chapter}:{q_hash}"


def key_advisor_task(task_id: str) -> str:
    return f"advisor:task:{task_id}"


def key_public_books() -> str:
    return "public:books"


def key_public_book_detail(book_id: str) -> str:
    return f"public:book:{book_id}"


def key_public_chapter(book_id: str, chapter_num: int) -> str:
    return f"public:chapter:{book_id}:{chapter_num}"


def key_public_forum_cache_version() -> str:
    return "public:forum:version"


def key_public_forum_posts(version: int, q: str, page: int, page_size: int) -> str:
    query_hash = hashlib.md5(q.strip().lower().encode("utf-8")).hexdigest()[:10]
    return f"public:forum:posts:v{version}:{query_hash}:{page}:{page_size}"


def key_public_forum_post_detail(version: int, post_id: str) -> str:
    return f"public:forum:post:v{version}:{post_id}"
