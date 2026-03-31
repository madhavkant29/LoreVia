import redis.asyncio as aioredis
from app.core.config import settings
import json
import hashlib

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def cache_set(key: str, value: object, ttl: int) -> None:
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value))


async def cache_get(key: str) -> object | None:
    r = await get_redis()
    data = await r.get(key)
    return json.loads(data) if data else None


async def cache_del(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


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


# ── Key builders — single source of truth ────────────────────────────────────
def key_character_profile(character_id: str) -> str:
    return f"character:profile:{character_id}"

def key_chapter_summary(chapter_id: str, mode: str) -> str:
    return f"chapter:summary:{chapter_id}:{mode}"

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


def key_grounded_answer(book_id: str, chapter: int, question: str) -> str:
    q_hash = hashlib.md5(question.strip().lower().encode()).hexdigest()[:10]
    return f"grounded_answer:{book_id}:{chapter}:{q_hash}"
