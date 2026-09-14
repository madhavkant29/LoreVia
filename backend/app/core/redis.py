import asyncio
import hashlib
import json
import logging
import time
import weakref
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.config import settings
from app.utils.observability_metrics import record_redis_lookup

_redis_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, aioredis.Redis] = (
    weakref.WeakKeyDictionary()
)
log = logging.getLogger("lorevia.redis")

ADVISOR_CACHE_TTL_SECONDS = 10 * 60
PROACTIVE_SCAN_CACHE_TTL_SECONDS = 5 * 60
SUGGESTION_SCAN_CACHE_TTL_SECONDS = 10 * 60
BOOK_AGGREGATE_CACHE_TTL_SECONDS = 2 * 60
STORY_CONTEXT_CACHE_TTL_SECONDS = 10 * 60
USER_DASHBOARD_CACHE_TTL_SECONDS = 2 * 60
# Stats include usage and allowance display values, so use a shorter TTL than
# the broader dashboard while still avoiding duplicate aggregate reads.
USER_STATS_CACHE_TTL_SECONDS = 60
READER_DERIVED_CACHE_TTL_SECONDS = 2 * 60
PUBLIC_PROFILE_CACHE_TTL_SECONDS = 5 * 60
PUBLIC_FORUM_COMMENTS_CACHE_TTL_SECONDS = 2 * 60
SYNOPSIS_CACHE_TTL_SECONDS = 7 * 86400  # 604800
EMBEDDING_CACHE_TTL_SECONDS = 30 * 60
CROSS_BOOK_INTEL_CACHE_TTL_SECONDS = 30 * 60
REVISION_INTELLIGENCE_CACHE_TTL_SECONDS = 2 * 60
REDIS_OPERATION_EXCEPTIONS = (RedisError, TimeoutError, OSError)


@dataclass(frozen=True)
class CachePolicy:
    namespace: str
    owner: str
    ttl_seconds: int | None
    invalidation: str
    source_of_truth: str


CACHE_POLICIES: tuple[CachePolicy, ...] = (
    CachePolicy(
        "advisor:book",
        "advisor",
        ADVISOR_CACHE_TTL_SECONDS,
        "Book cache-version marker in key plus TTL",
        "Postgres and LLM recomputation",
    ),
    CachePolicy(
        "advisor:series",
        "advisor",
        ADVISOR_CACHE_TTL_SECONDS,
        "Series cache-version marker in key plus TTL",
        "Postgres and LLM recomputation",
    ),
    CachePolicy(
        "advisor:book:*:proactive",
        "advisor",
        PROACTIVE_SCAN_CACHE_TTL_SECONDS,
        "Book cache-version marker in key plus TTL",
        "Postgres and LLM recomputation",
    ),
    CachePolicy(
        "advisor:book:*:suggestions",
        "advisor",
        SUGGESTION_SCAN_CACHE_TTL_SECONDS,
        "Book cache-version marker in key plus TTL",
        "Postgres and LLM recomputation",
    ),
    CachePolicy(
        "advisor:book:*:synopsis",
        "advisor",
        SYNOPSIS_CACHE_TTL_SECONDS,
        "Content hash key and TTL",
        "Book/chapter content in Postgres",
    ),
    CachePolicy(
        "story_context",
        "advisor",
        STORY_CONTEXT_CACHE_TTL_SECONDS,
        "Book or series cache-version marker in key plus TTL",
        "Postgres manuscript intelligence tables",
    ),
    CachePolicy(
        "series_story_context",
        "advisor",
        STORY_CONTEXT_CACHE_TTL_SECONDS,
        "Series cache-version marker in key plus TTL",
        "Postgres manuscript intelligence tables",
    ),
    CachePolicy(
        "book_overview",
        "books",
        BOOK_AGGREGATE_CACHE_TTL_SECONDS,
        "Book cache-version marker in key plus TTL",
        "Postgres book aggregate queries",
    ),
    CachePolicy(
        "writer_workspace",
        "books",
        BOOK_AGGREGATE_CACHE_TTL_SECONDS,
        "Book cache-version marker in key plus TTL",
        "Postgres book/workspace records",
    ),
    CachePolicy(
        "writing_dashboard",
        "dashboard",
        USER_DASHBOARD_CACHE_TTL_SECONDS,
        "User dashboard cache-version marker and day marker in key plus TTL",
        "Postgres user/book/progress records",
    ),
    CachePolicy(
        "user_stats",
        "dashboard",
        USER_STATS_CACHE_TTL_SECONDS,
        "User dashboard cache-version marker plus short TTL",
        "Postgres usage, allowance, reading, and writing aggregates",
    ),
    CachePolicy(
        "reader_events",
        "reader",
        READER_DERIVED_CACHE_TTL_SECONDS,
        "Book and reader-progress cache-version markers in key plus TTL",
        "Postgres reader event queries",
    ),
    CachePolicy(
        "reader_timeline",
        "reader",
        READER_DERIVED_CACHE_TTL_SECONDS,
        "Book and reader-progress cache-version markers in key plus TTL",
        "Postgres reader timeline queries",
    ),
    CachePolicy(
        "reader_relationship_evolution",
        "reader",
        READER_DERIVED_CACHE_TTL_SECONDS,
        "Book and reader-progress cache-version markers in key plus TTL",
        "Postgres relationship/event queries",
    ),
    CachePolicy(
        "public:user_profile",
        "public",
        PUBLIC_PROFILE_CACHE_TTL_SECONDS,
        "Public profile cache-version marker in key plus TTL",
        "Postgres public profile queries",
    ),
    CachePolicy(
        "public:forum",
        "public",
        PUBLIC_FORUM_COMMENTS_CACHE_TTL_SECONDS,
        "Public forum cache-version marker in key plus TTL",
        "Postgres public forum tables",
    ),
    CachePolicy(
        "public:books",
        "public",
        300,
        "Explicit delete on public catalog/profile changes plus TTL",
        "Postgres public book records",
    ),
    CachePolicy(
        "public:book",
        "public",
        300,
        "Explicit delete on admin/public book changes plus TTL",
        "Postgres public book records",
    ),
    CachePolicy(
        "public:chapter",
        "public",
        3600,
        "TTL and public book moderation/publish invalidation paths",
        "Postgres public chapter records",
    ),
    CachePolicy(
        "character:profile",
        "characters",
        None,
        "TTL from settings.REDIS_TTL_CHARACTER_PROFILE",
        "Postgres character records",
    ),
    CachePolicy(
        "chapter:summary",
        "reader",
        None,
        "TTL from settings.REDIS_TTL_SUMMARY",
        "Postgres chapter summaries or LLM recomputation",
    ),
    CachePolicy(
        "relationship:graph",
        "reader",
        None,
        "TTL from settings.REDIS_TTL_GRAPH",
        "Postgres relationship records",
    ),
    CachePolicy(
        "book:search",
        "reader",
        None,
        "TTL from settings.REDIS_TTL_SEARCH",
        "Postgres/vector search recomputation",
    ),
    CachePolicy(
        "recall",
        "reader",
        None,
        "TTL from settings.REDIS_TTL_RECALL",
        "Postgres reader/book records",
    ),
    CachePolicy(
        "embedding",
        "embeddings",
        EMBEDDING_CACHE_TTL_SECONDS,
        "Text/model hash plus TTL",
        "OpenAI embedding API and tracked DB usage",
    ),
    CachePolicy(
        "cross_book_intelligence",
        "intelligence",
        CROSS_BOOK_INTEL_CACHE_TTL_SECONDS,
        "Input snapshot hash plus TTL",
        "Postgres book/intelligence records",
    ),
    CachePolicy(
        "revision_intelligence",
        "books",
        REVISION_INTELLIGENCE_CACHE_TTL_SECONDS,
        "Book cache-version marker in key plus TTL",
        "Postgres manuscript and intelligence records",
    ),
)


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
        redis_kwargs.setdefault(
            "socket_connect_timeout", max(float(settings.REDIS_CONNECT_TIMEOUT_SECONDS), 0.05)
        )
        redis_kwargs.setdefault(
            "socket_timeout", max(float(settings.REDIS_SOCKET_TIMEOUT_SECONDS), 0.05)
        )
        redis_kwargs.setdefault("health_check_interval", 30)
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
    await _cache_set_json_best_effort(key, value, ttl)


async def cache_acquire_lock(key: str, value: object, ttl: int) -> bool | None:
    try:
        r = await get_redis()
        return bool(
            await _bounded_cache_operation(
                r.set(key, json.dumps(value, default=str), ex=ttl, nx=True)
            )
        )
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_cache_lock_failed", extra={"cache_key": key}, exc_info=True)
        return None


async def cache_set_if_absent(key: str, value: object, ttl: int) -> bool:
    r = await get_redis()
    return bool(
        await _bounded_cache_operation(r.set(key, json.dumps(value, default=str), ex=ttl, nx=True))
    )


async def cache_get(key: str) -> object | None:
    return await _cache_get_json_best_effort(key)


async def cache_del(key: str) -> None:
    try:
        r = await get_redis()
        await _bounded_cache_operation(r.delete(key))
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_cache_delete_failed", extra={"cache_key": key}, exc_info=True)


async def cache_get_int(key: str, default: int = 0) -> int:
    try:
        r = await get_redis()
        value = await _bounded_cache_operation(r.get(key))
        record_redis_lookup(hit=value is not None)
        return int(value) if value is not None else default
    except REDIS_OPERATION_EXCEPTIONS:
        record_redis_lookup(hit=False)
        log.warning("redis_cache_get_int_failed", extra={"cache_key": key}, exc_info=True)
        return default


async def cache_incr(key: str, default: int = 1) -> int:
    try:
        r = await get_redis()
        if await _bounded_cache_operation(r.exists(key)):
            return int(await _bounded_cache_operation(r.incr(key)))
        await _bounded_cache_operation(r.set(key, str(default)))
        return default
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_cache_increment_failed", extra={"cache_key": key}, exc_info=True)
        return default


async def cache_set_version_marker(key: str) -> int:
    candidate = int(time.time() * 1000)
    try:
        r = await get_redis()
        increment = getattr(r, "incr", None)
        if increment is not None:
            return int(await _bounded_cache_operation(increment(key)))
        existing = await _bounded_cache_operation(r.get(key))
        if existing is not None:
            try:
                candidate = max(candidate, int(existing) + 1)
            except ValueError:
                pass
        await _bounded_cache_operation(r.set(key, str(candidate)))
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning(
            "redis_cache_version_marker_failed",
            extra={"cache_key": key},
            exc_info=True,
        )
    return candidate


async def cache_set_version_markers(keys: list[str]) -> list[int]:
    unique_keys = list(dict.fromkeys(key for key in keys if key))
    if not unique_keys:
        return []
    try:
        r = await get_redis()
        pipeline_factory = getattr(r, "pipeline", None)
        if pipeline_factory is not None:
            pipeline = pipeline_factory(transaction=False)
            for key in unique_keys:
                pipeline.incr(key)
            values = await _bounded_cache_operation(pipeline.execute())
            return [int(value) for value in values]
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning(
            "redis_cache_version_markers_failed",
            extra={"marker_count": len(unique_keys)},
            exc_info=True,
        )
        return [int(time.time() * 1000) for _key in unique_keys]
    return [await cache_set_version_marker(key) for key in unique_keys]


async def _bounded_cache_operation(awaitable: Awaitable[Any]) -> Any:
    timeout = max(float(settings.REDIS_CACHE_OPERATION_TIMEOUT_SECONDS), 0.05)
    return await asyncio.wait_for(awaitable, timeout=timeout)


async def _cache_get_json_best_effort(key: str) -> object | None:
    try:
        r = await get_redis()
        data = await _bounded_cache_operation(r.get(key))
    except REDIS_OPERATION_EXCEPTIONS:
        record_redis_lookup(hit=False)
        log.warning("redis_cache_get_failed", extra={"cache_key": key}, exc_info=True)
        return None
    record_redis_lookup(hit=bool(data))
    if not data:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        log.warning("redis_cache_payload_invalid", extra={"cache_key": key})
        try:
            await _bounded_cache_operation(r.delete(key))
        except REDIS_OPERATION_EXCEPTIONS:
            log.warning(
                "redis_cache_delete_invalid_payload_failed", extra={"cache_key": key}, exc_info=True
            )
        return None


async def _cache_set_json_best_effort(key: str, value: object, ttl: int) -> None:
    try:
        r = await get_redis()
        await _bounded_cache_operation(r.setex(key, ttl, json.dumps(value, default=str)))
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_cache_set_failed", extra={"cache_key": key}, exc_info=True)


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _redis_key_prefix(key: object) -> str:
    if isinstance(key, bytes):
        key = key.decode("utf-8", errors="replace")
    text = str(key)
    parts = text.split(":", 2)
    if len(parts) == 1:
        return parts[0]
    if parts[0] in {"advisor", "public", "cache_version"}:
        return f"{parts[0]}:{parts[1]}"
    return parts[0]


async def get_redis_diagnostics(*, scan_limit: int = 1000) -> dict[str, object]:
    diagnostics: dict[str, object] = {
        "ok": False,
        "memory_mb": 0.0,
        "connected_clients": 0,
        "key_count": 0,
        "key_prefix_counts": {},
        "key_prefix_samples": {},
        "key_scan_truncated": False,
    }
    try:
        r = await get_redis()
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_diagnostics_connect_failed", exc_info=True)
        return diagnostics | {"error": "connect_failed"}

    diagnostics["ok"] = True
    try:
        memory = await r.info("memory")
        diagnostics["memory_mb"] = round(_coerce_int(memory.get("used_memory")) / 1024 / 1024, 2)
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_diagnostics_memory_failed", exc_info=True)

    try:
        clients = await r.info("clients")
        diagnostics["connected_clients"] = _coerce_int(clients.get("connected_clients"))
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_diagnostics_clients_failed", exc_info=True)

    try:
        diagnostics["key_count"] = _coerce_int(await r.dbsize())
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_diagnostics_dbsize_failed", exc_info=True)

    try:
        cursor: int | str = 0
        scanned = 0
        prefix_counts: dict[str, int] = {}
        prefix_samples: dict[str, list[str]] = {}
        while True:
            cursor, keys = await r.scan(cursor=cursor, count=200)
            for key in keys:
                scanned += 1
                prefix = _redis_key_prefix(key)
                prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
                samples = prefix_samples.setdefault(prefix, [])
                if len(samples) < 3:
                    samples.append(
                        key.decode("utf-8", errors="replace")
                        if isinstance(key, bytes)
                        else str(key)
                    )
                if scanned >= scan_limit:
                    diagnostics["key_scan_truncated"] = True
                    break
            if cursor in (0, "0") or scanned >= scan_limit:
                break
        diagnostics["key_prefix_counts"] = dict(sorted(prefix_counts.items()))
        diagnostics["key_prefix_samples"] = dict(sorted(prefix_samples.items()))
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_diagnostics_scan_failed", exc_info=True)

    return diagnostics


async def store_refresh_session(user_id: str, session_id: str, ttl_seconds: int) -> None:
    r = await get_redis()
    await r.setex(key_refresh_session(user_id, session_id), ttl_seconds, "1")


async def refresh_session_active(user_id: str, session_id: str) -> bool:
    r = await get_redis()
    return bool(await r.exists(key_refresh_session(user_id, session_id)))


async def consume_refresh_session(user_id: str, session_id: str) -> bool:
    r = await get_redis()
    return bool(await r.getdel(key_refresh_session(user_id, session_id)))


async def remember_webhook_event(event_id: str, ttl_seconds: int = 7 * 24 * 3600) -> bool:
    r = await get_redis()
    return bool(await r.set(key_webhook_event(event_id), "1", ex=ttl_seconds, nx=True))


async def consume_billing_confirmation_token(token_id: str, ttl_seconds: int) -> bool:
    r = await get_redis()
    return bool(
        await r.set(key_billing_confirmation_token(token_id), "1", ex=max(1, ttl_seconds), nx=True)
    )


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
    value = await r.getdel(key)
    if not value:
        return None
    await delete_key_if_value(key_password_reset_user(value), token)
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
    value = await r.getdel(key)
    if not value:
        return None
    await delete_key_if_value(key_email_verification_user(value), token)
    return value


async def store_email_preferences_token(
    token: str, payload: dict[str, str], ttl_seconds: int
) -> None:
    r = await get_redis()
    await r.setex(key_email_preferences_token(token), ttl_seconds, json.dumps(payload))


async def get_email_preferences_token_payload(token: str) -> dict[str, str] | None:
    r = await get_redis()
    data = await r.get(key_email_preferences_token(token))
    if not data:
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        await r.delete(key_email_preferences_token(token))
        return None
    return payload if isinstance(payload, dict) else None


async def store_email_unsubscribe_token(
    token: str, payload: dict[str, str], ttl_seconds: int
) -> None:
    r = await get_redis()
    await r.setex(key_email_unsubscribe_token(token), ttl_seconds, json.dumps(payload))


async def consume_email_unsubscribe_token(token: str) -> dict[str, str] | None:
    r = await get_redis()
    key = key_email_unsubscribe_token(token)
    data = await r.get(key)
    if not data:
        return None
    await r.delete(key)
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


# ── Key builders — single source of truth ────────────────────────────────────
def key_character_profile(character_id: str) -> str:
    return f"character:profile:{character_id}"


def key_chapter_summary(chapter_id: str, mode: str) -> str:
    return f"chapter:summary:{chapter_id}:{mode}"


def key_analysis_inflight(chapter_id: str) -> str:
    return f"analysis:inflight:{chapter_id}"


def key_analysis_queued(chapter_id: str) -> str:
    return f"analysis:queued:{chapter_id}"


def key_extraction_inflight(book_id: str, chapter_number: int) -> str:
    return f"extraction:inflight:{book_id}:{chapter_number}"


def key_extraction_inflight_book(book_id: str) -> str:
    return f"extraction:inflight_book:{book_id}"


INFLIGHT_BOOK_TTL_SECONDS = 3600

_DELETE_IF_OWNER_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


async def delete_key_if_value(key: str, expected_value: str) -> bool:
    try:
        r = await get_redis()
        eval_method = getattr(r, "eval", None)
        if callable(eval_method):
            result = await _bounded_cache_operation(
                eval_method(_DELETE_IF_OWNER_SCRIPT, 1, key, expected_value)
            )
            return bool(result)

        current_value = await _bounded_cache_operation(r.get(key))
        if isinstance(current_value, bytes):
            current_value = current_value.decode()
        if current_value != expected_value:
            return False
        return bool(await _bounded_cache_operation(r.delete(key)))
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("redis_cache_owner_delete_failed", extra={"cache_key": key}, exc_info=True)
        return False


async def cache_delete_if_owner(key: str, owner_token: str) -> bool:
    serialized = json.dumps(owner_token, default=str)
    if await delete_key_if_value(key, serialized):
        return True
    return await delete_key_if_value(key, owner_token)


def key_cron_lock(task_name: str) -> str:
    return f"cron:lock:{task_name}"


def key_chapter_recovery_inflight(chapter_id: str) -> str:
    return f"chapter_recovery:inflight:{chapter_id}"


def key_revision_digest_refresh(book_id: str) -> str:
    return f"notification:revision_digest_refresh:{book_id}"


def key_world_analysis_refresh(scope: str, target_id: str) -> str:
    return f"world_analysis:refresh:{scope}:{target_id}"


def key_revision_intelligence_fill(book_id: str, version: int) -> str:
    return f"revision_intelligence:fill:{book_id}:{version}"


def key_maintenance_cursor(name: str) -> str:
    return f"maintenance:cursor:{name}"


def key_relationship_graph(book_id: str, chapter: int) -> str:
    return f"relationship:graph:{book_id}:{chapter}"


def key_search_results(book_id: str, query: str, chapter: int) -> str:
    q_hash = hashlib.md5(query.encode(), usedforsecurity=False).hexdigest()[:8]
    return f"book:search:{book_id}:{q_hash}:{chapter}"


def key_memory_recall(user_id: str, book_id: str) -> str:
    return f"recall:{user_id}:{book_id}"


def key_book_status(book_id: str) -> str:
    return f"book:status:{book_id}"


def key_ratelimit(user_id: str, action: str) -> str:
    return f"ratelimit:{user_id}:{action}"


def key_refresh_session(user_id: str, session_id: str) -> str:
    return f"refresh_session:{user_id}:{session_id}"


def key_admin_step_up(user_id: str, session_id: str) -> str:
    return f"admin_step_up:{user_id}:{session_id}"


def key_webhook_event(event_id: str) -> str:
    return f"webhook:event:{event_id}"


def key_billing_confirmation_token(token_id: str) -> str:
    return f"billing_confirmation:consumed:{token_id}"


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


def key_email_preferences_token(token: str) -> str:
    return f"email_preferences:{_hash_ephemeral_token(token)}"


def key_email_unsubscribe_token(token: str) -> str:
    return f"email_unsubscribe:{_hash_ephemeral_token(token)}"


def key_grounded_answer(book_id: str, chapter: int, question: str) -> str:
    q_hash = hashlib.md5(question.strip().lower().encode(), usedforsecurity=False).hexdigest()[:10]
    return f"grounded_answer:{book_id}:{chapter}:{q_hash}"


def key_advisor_response_cache(book_id: str, cache_key: str, version: int = 0) -> str:
    return f"advisor:book:{book_id}:v{version}:message:{cache_key}"


def key_editorial_review_cache(book_id: str, cache_key: str, version: int = 0) -> str:
    return f"advisor:book:{book_id}:v{version}:editorial:{cache_key}"


def key_prose_tighten_cache(book_id: str, cache_key: str, version: int = 0) -> str:
    return f"advisor:book:{book_id}:v{version}:prose:{cache_key}"


def key_voice_consistency_cache(book_id: str, cache_key: str, version: int = 0) -> str:
    return f"advisor:book:{book_id}:v{version}:voice:{cache_key}"


def key_proactive_scan_cache(book_id: str, cache_key: str, version: int = 0) -> str:
    return f"advisor:book:{book_id}:v{version}:proactive:{cache_key}"


def key_suggestion_scan_cache(book_id: str, cache_key: str, version: int = 0) -> str:
    return f"advisor:book:{book_id}:v{version}:suggestions:{cache_key}"


def key_series_advisor_response_cache(series_id: str, cache_key: str, version: int = 0) -> str:
    return f"advisor:series:{series_id}:v{version}:message:{cache_key}"


def key_series_continuity_cache(
    series_id: str, book_id: str, cache_key: str, version: int = 0
) -> str:
    return f"advisor:series:{series_id}:v{version}:continuity:{book_id}:{cache_key}"


def key_book_cache_version(book_id: str) -> str:
    return f"cache_version:book:{book_id}"


def key_series_cache_version(series_id: str) -> str:
    return f"cache_version:series:{series_id}"


def key_user_dashboard_cache_version(user_id: str) -> str:
    return f"cache_version:user_dashboard:{user_id}"


def key_user_stats_cache(user_id: str, version: int) -> str:
    return f"user_stats:{user_id}:v{version}"


def key_story_context_cache(book_id: str, version: int, total_ch: int) -> str:
    return f"story_context:{book_id}:v{version}:chapters:{total_ch}"


def key_series_story_context_cache(series_key: str, version: int) -> str:
    return f"series_story_context:{series_key}:v{version}"


def key_book_overview_cache(book_id: str, viewer_id: str, access_key: str, version: int) -> str:
    return f"book_overview:{book_id}:{viewer_id}:{access_key}:v{version}"


def key_writer_workspace_cache(book_id: str, viewer_id: str, access_key: str, version: int) -> str:
    return f"writer_workspace:{book_id}:{viewer_id}:{access_key}:v{version}"


def key_writing_dashboard_cache(user_id: str, version: int, day_marker: str) -> str:
    return f"writing_dashboard:{user_id}:v{version}:{day_marker}"


def key_public_profile_cache_version(user_id: str) -> str:
    return f"cache_version:public_profile:{user_id}"


def key_public_catalog_cache_version() -> str:
    return "cache_version:public_catalog"


def key_public_uploads_overview(version: int) -> str:
    return f"public:uploads_overview:v{version}"


def key_public_book_analytics(book_id: str, version: int) -> str:
    return f"public:book_analytics:{book_id}:v{version}"


def key_public_user_profile(user_id: str, username: str, version: int) -> str:
    return f"public:user_profile:{user_id}:{username}:v{version}"


def key_public_forum_comments(version: int, post_id: str) -> str:
    return f"public:forum:comments:v{version}:{post_id}"


def key_reader_progress_cache_version(book_id: str, user_id: str) -> str:
    return f"cache_version:reader_progress:{book_id}:{user_id}"


def key_reader_events_cache(
    book_id: str, user_id: str, visible_chapter: int, book_version: int, progress_version: int
) -> str:
    return f"reader_events:{book_id}:{user_id}:chapter:{visible_chapter}:bookv:{book_version}:readv:{progress_version}"


def key_reader_timeline_cache(
    book_id: str, user_id: str, book_version: int, progress_version: int
) -> str:
    return f"reader_timeline:{book_id}:{user_id}:bookv:{book_version}:readv:{progress_version}"


def key_relationship_evolution_cache(
    book_id: str, user_id: str, chapter: int, book_version: int, progress_version: int
) -> str:
    return f"reader_relationship_evolution:{book_id}:{user_id}:chapter:{chapter}:bookv:{book_version}:readv:{progress_version}"


def key_revision_intelligence_cache(book_id: str, version: int) -> str:
    return f"revision_intelligence:{book_id}:bookv:{version}"


async def _book_cache_write_version(book_id: str, expected_version: int | None) -> int | None:
    version = await get_book_cache_version(book_id)
    if expected_version is not None and version != expected_version:
        return None
    return version


async def _series_cache_write_version(series_id: str, expected_version: int | None) -> int | None:
    version = await get_series_cache_version(series_id)
    if expected_version is not None and version != expected_version:
        return None
    return version


async def get_advisor_response_cache(
    book_id: str, cache_key: str, *, version: int | None = None
) -> dict | None:
    version = await get_book_cache_version(book_id) if version is None else version
    payload = await _cache_get_json_best_effort(
        key_advisor_response_cache(book_id, cache_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_advisor_response_cache(
    book_id: str, cache_key: str, payload: object, *, expected_version: int | None = None
) -> None:
    version = await _book_cache_write_version(book_id, expected_version)
    if version is None:
        return
    await _cache_set_json_best_effort(
        key_advisor_response_cache(book_id, cache_key, version),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_editorial_review_cache(
    book_id: str, cache_key: str, *, version: int | None = None
) -> dict | None:
    version = await get_book_cache_version(book_id) if version is None else version
    payload = await _cache_get_json_best_effort(
        key_editorial_review_cache(book_id, cache_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_editorial_review_cache(
    book_id: str, cache_key: str, payload: object, *, expected_version: int | None = None
) -> None:
    version = await _book_cache_write_version(book_id, expected_version)
    if version is None:
        return
    await _cache_set_json_best_effort(
        key_editorial_review_cache(book_id, cache_key, version),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_prose_tighten_cache(
    book_id: str, cache_key: str, *, version: int | None = None
) -> dict | None:
    version = await get_book_cache_version(book_id) if version is None else version
    payload = await _cache_get_json_best_effort(
        key_prose_tighten_cache(book_id, cache_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_prose_tighten_cache(
    book_id: str, cache_key: str, payload: object, *, expected_version: int | None = None
) -> None:
    version = await _book_cache_write_version(book_id, expected_version)
    if version is None:
        return
    await _cache_set_json_best_effort(
        key_prose_tighten_cache(book_id, cache_key, version),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_voice_consistency_cache(
    book_id: str, cache_key: str, *, version: int | None = None
) -> dict | None:
    version = await get_book_cache_version(book_id) if version is None else version
    payload = await _cache_get_json_best_effort(
        key_voice_consistency_cache(book_id, cache_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_voice_consistency_cache(
    book_id: str, cache_key: str, payload: object, *, expected_version: int | None = None
) -> None:
    version = await _book_cache_write_version(book_id, expected_version)
    if version is None:
        return
    await _cache_set_json_best_effort(
        key_voice_consistency_cache(book_id, cache_key, version),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_proactive_scan_cache(
    book_id: str, cache_key: str, *, version: int | None = None
) -> dict | None:
    version = await get_book_cache_version(book_id) if version is None else version
    payload = await _cache_get_json_best_effort(
        key_proactive_scan_cache(book_id, cache_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_proactive_scan_cache(
    book_id: str, cache_key: str, payload: object, *, expected_version: int | None = None
) -> None:
    version = await _book_cache_write_version(book_id, expected_version)
    if version is None:
        return
    await _cache_set_json_best_effort(
        key_proactive_scan_cache(book_id, cache_key, version),
        payload,
        PROACTIVE_SCAN_CACHE_TTL_SECONDS,
    )


async def get_suggestion_scan_cache(
    book_id: str, cache_key: str, *, version: int | None = None
) -> dict | None:
    version = await get_book_cache_version(book_id) if version is None else version
    payload = await _cache_get_json_best_effort(
        key_suggestion_scan_cache(book_id, cache_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_suggestion_scan_cache(
    book_id: str, cache_key: str, payload: object, *, expected_version: int | None = None
) -> None:
    version = await _book_cache_write_version(book_id, expected_version)
    if version is None:
        return
    await _cache_set_json_best_effort(
        key_suggestion_scan_cache(book_id, cache_key, version),
        payload,
        SUGGESTION_SCAN_CACHE_TTL_SECONDS,
    )


def key_synopsis_cache(book_id: str, spoiler_level: str, content_hash: str) -> str:
    return f"advisor:book:{book_id}:synopsis:{spoiler_level}:{content_hash}"


async def get_synopsis_cache(book_id: str, spoiler_level: str, content_hash: str) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_synopsis_cache(book_id, spoiler_level, content_hash)
    )
    return payload if isinstance(payload, dict) else None


async def set_synopsis_cache(
    book_id: str, spoiler_level: str, content_hash: str, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_synopsis_cache(book_id, spoiler_level, content_hash),
        payload,
        SYNOPSIS_CACHE_TTL_SECONDS,
    )


async def get_series_advisor_response_cache(
    series_id: str, cache_key: str, *, version: int | None = None
) -> dict | None:
    version = await get_series_cache_version(series_id) if version is None else version
    payload = await _cache_get_json_best_effort(
        key_series_advisor_response_cache(series_id, cache_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_series_advisor_response_cache(
    series_id: str, cache_key: str, payload: object, *, expected_version: int | None = None
) -> None:
    version = await _series_cache_write_version(series_id, expected_version)
    if version is None:
        return
    await _cache_set_json_best_effort(
        key_series_advisor_response_cache(series_id, cache_key, version),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_series_continuity_cache(
    series_id: str, book_id: str, cache_key: str, *, version: int | None = None
) -> dict | None:
    version = await get_series_cache_version(series_id) if version is None else version
    payload = await _cache_get_json_best_effort(
        key_series_continuity_cache(series_id, book_id, cache_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_series_continuity_cache(
    series_id: str,
    book_id: str,
    cache_key: str,
    payload: object,
    *,
    expected_version: int | None = None,
) -> None:
    version = await _series_cache_write_version(series_id, expected_version)
    if version is None:
        return
    await _cache_set_json_best_effort(
        key_series_continuity_cache(series_id, book_id, cache_key, version),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def invalidate_advisor_cache_namespaces(
    *,
    book_id: str | None = None,
    series_ids: list[str] | None = None,
) -> None:
    keys = [key_book_cache_version(book_id)] if book_id else []
    keys.extend(key_series_cache_version(series_id) for series_id in series_ids or [])
    await cache_set_version_markers(keys)


async def get_book_cache_version(book_id: str) -> int:
    return await cache_get_int(key_book_cache_version(book_id), default=0)


async def get_series_cache_version(series_id: str) -> int:
    return await cache_get_int(key_series_cache_version(series_id), default=0)


async def get_user_dashboard_cache_version(user_id: str) -> int:
    return await cache_get_int(key_user_dashboard_cache_version(user_id), default=0)


async def get_reader_progress_cache_version(book_id: str, user_id: str) -> int:
    return await cache_get_int(key_reader_progress_cache_version(book_id, user_id), default=0)


async def get_public_profile_cache_version(user_id: str) -> int:
    return await cache_get_int(key_public_profile_cache_version(user_id), default=0)


async def get_public_catalog_cache_version() -> int:
    return await cache_get_int(key_public_catalog_cache_version(), default=0)


async def mark_book_cache_dirty(book_id: str) -> int:
    return await cache_set_version_marker(key_book_cache_version(book_id))


async def mark_series_cache_dirty(series_id: str) -> int:
    return await cache_set_version_marker(key_series_cache_version(series_id))


async def mark_user_dashboard_cache_dirty(user_id: str) -> int:
    return await cache_set_version_marker(key_user_dashboard_cache_version(user_id))


async def mark_reader_progress_cache_dirty(book_id: str, user_id: str) -> int:
    return await cache_set_version_marker(key_reader_progress_cache_version(book_id, user_id))


async def mark_public_profile_cache_dirty(user_id: str) -> int:
    return await cache_set_version_marker(key_public_profile_cache_version(user_id))


async def mark_public_catalog_cache_dirty() -> int:
    return await cache_set_version_marker(key_public_catalog_cache_version())


async def get_story_context_cache(book_id: str, version: int, total_ch: int) -> str | None:
    payload = await _cache_get_json_best_effort(key_story_context_cache(book_id, version, total_ch))
    return payload if isinstance(payload, str) else None


async def set_story_context_cache(book_id: str, version: int, total_ch: int, payload: str) -> None:
    await _cache_set_json_best_effort(
        key_story_context_cache(book_id, version, total_ch),
        payload,
        STORY_CONTEXT_CACHE_TTL_SECONDS,
    )


async def get_series_story_context_cache(series_key: str, version: int) -> str | None:
    payload = await _cache_get_json_best_effort(key_series_story_context_cache(series_key, version))
    return payload if isinstance(payload, str) else None


async def set_series_story_context_cache(series_key: str, version: int, payload: str) -> None:
    await _cache_set_json_best_effort(
        key_series_story_context_cache(series_key, version),
        payload,
        STORY_CONTEXT_CACHE_TTL_SECONDS,
    )


async def get_revision_intelligence_cache(book_id: str, version: int) -> dict | None:
    payload = await _cache_get_json_best_effort(key_revision_intelligence_cache(book_id, version))
    return payload if isinstance(payload, dict) else None


async def set_revision_intelligence_cache(
    book_id: str,
    version: int,
    payload: object,
) -> None:
    current_version = await get_book_cache_version(book_id)
    if current_version != version:
        return
    await _cache_set_json_best_effort(
        key_revision_intelligence_cache(book_id, version),
        payload,
        REVISION_INTELLIGENCE_CACHE_TTL_SECONDS,
    )


async def get_book_overview_cache(
    book_id: str, viewer_id: str, access_key: str, version: int
) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_book_overview_cache(book_id, viewer_id, access_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_book_overview_cache(
    book_id: str, viewer_id: str, access_key: str, version: int, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_book_overview_cache(book_id, viewer_id, access_key, version),
        payload,
        BOOK_AGGREGATE_CACHE_TTL_SECONDS,
    )


async def get_writer_workspace_cache(
    book_id: str, viewer_id: str, access_key: str, version: int
) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_writer_workspace_cache(book_id, viewer_id, access_key, version)
    )
    return payload if isinstance(payload, dict) else None


async def set_writer_workspace_cache(
    book_id: str, viewer_id: str, access_key: str, version: int, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_writer_workspace_cache(book_id, viewer_id, access_key, version),
        payload,
        BOOK_AGGREGATE_CACHE_TTL_SECONDS,
    )


async def get_writing_dashboard_cache(user_id: str, version: int, day_marker: str) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_writing_dashboard_cache(user_id, version, day_marker)
    )
    return payload if isinstance(payload, dict) else None


async def set_writing_dashboard_cache(
    user_id: str, version: int, day_marker: str, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_writing_dashboard_cache(user_id, version, day_marker),
        payload,
        USER_DASHBOARD_CACHE_TTL_SECONDS,
    )


async def get_reader_events_cache(
    book_id: str, user_id: str, visible_chapter: int, book_version: int, progress_version: int
) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_reader_events_cache(book_id, user_id, visible_chapter, book_version, progress_version)
    )
    return payload if isinstance(payload, dict) else None


async def set_reader_events_cache(
    book_id: str,
    user_id: str,
    visible_chapter: int,
    book_version: int,
    progress_version: int,
    payload: object,
) -> None:
    await _cache_set_json_best_effort(
        key_reader_events_cache(book_id, user_id, visible_chapter, book_version, progress_version),
        payload,
        READER_DERIVED_CACHE_TTL_SECONDS,
    )


async def get_reader_timeline_cache(
    book_id: str, user_id: str, book_version: int, progress_version: int
) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_reader_timeline_cache(book_id, user_id, book_version, progress_version)
    )
    return payload if isinstance(payload, dict) else None


async def set_reader_timeline_cache(
    book_id: str, user_id: str, book_version: int, progress_version: int, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_reader_timeline_cache(book_id, user_id, book_version, progress_version),
        payload,
        READER_DERIVED_CACHE_TTL_SECONDS,
    )


async def get_relationship_evolution_cache(
    book_id: str, user_id: str, chapter: int, book_version: int, progress_version: int
) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_relationship_evolution_cache(book_id, user_id, chapter, book_version, progress_version)
    )
    return payload if isinstance(payload, dict) else None


async def set_relationship_evolution_cache(
    book_id: str,
    user_id: str,
    chapter: int,
    book_version: int,
    progress_version: int,
    payload: object,
) -> None:
    await _cache_set_json_best_effort(
        key_relationship_evolution_cache(book_id, user_id, chapter, book_version, progress_version),
        payload,
        READER_DERIVED_CACHE_TTL_SECONDS,
    )


async def get_public_user_profile_cache(user_id: str, username: str, version: int) -> dict | None:
    payload = await _cache_get_json_best_effort(key_public_user_profile(user_id, username, version))
    return payload if isinstance(payload, dict) else None


async def set_public_user_profile_cache(
    user_id: str, username: str, version: int, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_public_user_profile(user_id, username, version),
        payload,
        PUBLIC_PROFILE_CACHE_TTL_SECONDS,
    )


async def get_public_forum_comments_cache(version: int, post_id: str) -> list | None:
    payload = await _cache_get_json_best_effort(key_public_forum_comments(version, post_id))
    return payload if isinstance(payload, list) else None


async def set_public_forum_comments_cache(version: int, post_id: str, payload: object) -> None:
    await _cache_set_json_best_effort(
        key_public_forum_comments(version, post_id),
        payload,
        PUBLIC_FORUM_COMMENTS_CACHE_TTL_SECONDS,
    )


def key_public_books() -> str:
    return "public:books"


def key_public_catalog_page(
    *,
    version: int,
    catalog: str,
    content_source_type: str,
    search: str,
    limit: int,
) -> str:
    filters = json.dumps(
        {
            "catalog": catalog,
            "content_source_type": content_source_type,
            "search": search,
            "limit": limit,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(filters.encode("utf-8")).hexdigest()[:16]
    return f"public:catalog:v{version}:{digest}"


def key_public_book_detail(book_id: str) -> str:
    return f"public:book:{book_id}"


def key_public_chapter(book_id: str, chapter_num: int) -> str:
    return f"public:chapter:{book_id}:{chapter_num}"


def key_public_forum_cache_version() -> str:
    return "public:forum:version"


def key_public_forum_posts(
    version: int, q: str, page: int, page_size: int, thread_type: str | None = None
) -> str:
    query_hash = hashlib.md5(q.strip().lower().encode("utf-8"), usedforsecurity=False).hexdigest()[
        :10
    ]
    thread_type_key = (thread_type or "all").strip().lower()
    return f"public:forum:posts:v{version}:{thread_type_key}:{query_hash}:{page}:{page_size}"


def key_public_forum_post_detail(version: int, post_id: str) -> str:
    return f"public:forum:post:v{version}:{post_id}"


def key_embedding_cache(*, feature: str, model: str, text: str) -> str:
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embedding:{model}:{feature}:{text_hash}"


async def get_embedding_cache(*, feature: str, model: str, text: str) -> list[float] | None:
    payload = await _cache_get_json_best_effort(
        key_embedding_cache(feature=feature, model=model, text=text)
    )
    if isinstance(payload, list) and all(isinstance(v, (int, float)) for v in payload):
        return [float(v) for v in payload]
    return None


async def set_embedding_cache(*, feature: str, model: str, text: str, vector: list[float]) -> None:
    await _cache_set_json_best_effort(
        key_embedding_cache(feature=feature, model=model, text=text),
        vector,
        EMBEDDING_CACHE_TTL_SECONDS,
    )


def key_cross_book_intelligence(books_hash: str, snapshot_hash: str) -> str:
    return f"cross_book_intelligence:{books_hash}:{snapshot_hash}"


async def get_cross_book_intelligence_cache(books_hash: str, snapshot_hash: str) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_cross_book_intelligence(books_hash, snapshot_hash)
    )
    return payload if isinstance(payload, dict) else None


async def set_cross_book_intelligence_cache(
    books_hash: str, snapshot_hash: str, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_cross_book_intelligence(books_hash, snapshot_hash),
        payload,
        CROSS_BOOK_INTEL_CACHE_TTL_SECONDS,
    )
