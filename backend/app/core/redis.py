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
