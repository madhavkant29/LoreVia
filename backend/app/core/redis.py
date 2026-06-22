import asyncio
import hashlib
import json
import logging
import time
import weakref
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import redis.asyncio as aioredis

from app.core.config import settings

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
READER_DERIVED_CACHE_TTL_SECONDS = 2 * 60
PUBLIC_PROFILE_CACHE_TTL_SECONDS = 5 * 60
PUBLIC_FORUM_COMMENTS_CACHE_TTL_SECONDS = 2 * 60
SYNOPSIS_CACHE_TTL_SECONDS = 7 * 86400  # 604800


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


async def _cache_get_json_best_effort(key: str) -> object | None:
    try:
        r = await get_redis()
        data = await r.get(key)
    except Exception:
        log.warning("redis_cache_get_failed", extra={"cache_key": key}, exc_info=True)
        return None
    if not data:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        log.warning("redis_cache_payload_invalid", extra={"cache_key": key})
        try:
            await r.delete(key)
        except Exception:
            log.warning(
                "redis_cache_delete_invalid_payload_failed", extra={"cache_key": key}, exc_info=True
            )
        return None


async def _cache_set_json_best_effort(key: str, value: object, ttl: int) -> None:
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        log.warning("redis_cache_set_failed", extra={"cache_key": key}, exc_info=True)


async def _cache_delete_by_prefixes_best_effort(prefixes: list[str]) -> None:
    if not prefixes:
        return
    try:
        r = await get_redis()
        keys_to_delete: list[str] = []
        for prefix in prefixes:
            cursor: int | str = 0
            while True:
                cursor, keys = await r.scan(cursor=cursor, match=f"{prefix}*", count=200)
                keys_to_delete.extend(str(key) for key in keys)
                if cursor in (0, "0"):
                    break
        if keys_to_delete:
            await r.delete(*keys_to_delete)
    except Exception:
        log.warning("redis_cache_prefix_delete_failed", extra={"prefixes": prefixes}, exc_info=True)


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
    r = await get_redis()
    eval_method = getattr(r, "eval", None)
    if callable(eval_method):
        result = await eval_method(_DELETE_IF_OWNER_SCRIPT, 1, key, expected_value)
        return bool(result)

    current_value = await r.get(key)
    if isinstance(current_value, bytes):
        current_value = current_value.decode()
    if current_value != expected_value:
        return False
    return bool(await r.delete(key))


async def cache_delete_if_owner(key: str, owner_token: str) -> bool:
    serialized = json.dumps(owner_token, default=str)
    if await delete_key_if_value(key, serialized):
        return True
    return await delete_key_if_value(key, owner_token)


def key_cron_lock(task_name: str) -> str:
    return f"cron:lock:{task_name}"


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
    q_hash = hashlib.md5(question.strip().lower().encode()).hexdigest()[:10]
    return f"grounded_answer:{book_id}:{chapter}:{q_hash}"


def key_advisor_response_cache(book_id: str, cache_key: str) -> str:
    return f"advisor:book:{book_id}:message:{cache_key}"


def key_editorial_review_cache(book_id: str, cache_key: str) -> str:
    return f"advisor:book:{book_id}:editorial:{cache_key}"


def key_prose_tighten_cache(book_id: str, cache_key: str) -> str:
    return f"advisor:book:{book_id}:prose:{cache_key}"


def key_voice_consistency_cache(book_id: str, cache_key: str) -> str:
    return f"advisor:book:{book_id}:voice:{cache_key}"


def key_proactive_scan_cache(book_id: str, cache_key: str) -> str:
    return f"advisor:book:{book_id}:proactive:{cache_key}"


def key_suggestion_scan_cache(book_id: str, cache_key: str) -> str:
    return f"advisor:book:{book_id}:suggestions:{cache_key}"


def key_series_advisor_response_cache(series_id: str, cache_key: str) -> str:
    return f"advisor:series:{series_id}:message:{cache_key}"


def key_series_continuity_cache(series_id: str, book_id: str, cache_key: str) -> str:
    return f"advisor:series:{series_id}:continuity:{book_id}:{cache_key}"


def key_book_cache_version(book_id: str) -> str:
    return f"cache_version:book:{book_id}"


def key_series_cache_version(series_id: str) -> str:
    return f"cache_version:series:{series_id}"


def key_user_dashboard_cache_version(user_id: str) -> str:
    return f"cache_version:user_dashboard:{user_id}"


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


async def get_advisor_response_cache(book_id: str, cache_key: str) -> dict | None:
    payload = await _cache_get_json_best_effort(key_advisor_response_cache(book_id, cache_key))
    return payload if isinstance(payload, dict) else None


async def set_advisor_response_cache(book_id: str, cache_key: str, payload: object) -> None:
    await _cache_set_json_best_effort(
        key_advisor_response_cache(book_id, cache_key),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_editorial_review_cache(book_id: str, cache_key: str) -> dict | None:
    payload = await _cache_get_json_best_effort(key_editorial_review_cache(book_id, cache_key))
    return payload if isinstance(payload, dict) else None


async def set_editorial_review_cache(book_id: str, cache_key: str, payload: object) -> None:
    await _cache_set_json_best_effort(
        key_editorial_review_cache(book_id, cache_key),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_prose_tighten_cache(book_id: str, cache_key: str) -> dict | None:
    payload = await _cache_get_json_best_effort(key_prose_tighten_cache(book_id, cache_key))
    return payload if isinstance(payload, dict) else None


async def set_prose_tighten_cache(book_id: str, cache_key: str, payload: object) -> None:
    await _cache_set_json_best_effort(
        key_prose_tighten_cache(book_id, cache_key),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_voice_consistency_cache(book_id: str, cache_key: str) -> dict | None:
    payload = await _cache_get_json_best_effort(key_voice_consistency_cache(book_id, cache_key))
    return payload if isinstance(payload, dict) else None


async def set_voice_consistency_cache(book_id: str, cache_key: str, payload: object) -> None:
    await _cache_set_json_best_effort(
        key_voice_consistency_cache(book_id, cache_key),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_proactive_scan_cache(book_id: str, cache_key: str) -> dict | None:
    payload = await _cache_get_json_best_effort(key_proactive_scan_cache(book_id, cache_key))
    return payload if isinstance(payload, dict) else None


async def set_proactive_scan_cache(book_id: str, cache_key: str, payload: object) -> None:
    await _cache_set_json_best_effort(
        key_proactive_scan_cache(book_id, cache_key),
        payload,
        PROACTIVE_SCAN_CACHE_TTL_SECONDS,
    )


async def get_suggestion_scan_cache(book_id: str, cache_key: str) -> dict | None:
    payload = await _cache_get_json_best_effort(key_suggestion_scan_cache(book_id, cache_key))
    return payload if isinstance(payload, dict) else None


async def set_suggestion_scan_cache(book_id: str, cache_key: str, payload: object) -> None:
    await _cache_set_json_best_effort(
        key_suggestion_scan_cache(book_id, cache_key),
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


async def get_series_advisor_response_cache(series_id: str, cache_key: str) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_series_advisor_response_cache(series_id, cache_key)
    )
    return payload if isinstance(payload, dict) else None


async def set_series_advisor_response_cache(
    series_id: str, cache_key: str, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_series_advisor_response_cache(series_id, cache_key),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def get_series_continuity_cache(series_id: str, book_id: str, cache_key: str) -> dict | None:
    payload = await _cache_get_json_best_effort(
        key_series_continuity_cache(series_id, book_id, cache_key)
    )
    return payload if isinstance(payload, dict) else None


async def set_series_continuity_cache(
    series_id: str, book_id: str, cache_key: str, payload: object
) -> None:
    await _cache_set_json_best_effort(
        key_series_continuity_cache(series_id, book_id, cache_key),
        payload,
        ADVISOR_CACHE_TTL_SECONDS,
    )


async def invalidate_advisor_cache_namespaces(
    *,
    book_id: str | None = None,
    series_ids: list[str] | None = None,
) -> None:
    prefixes: list[str] = []
    if book_id:
        prefixes.append(f"advisor:book:{book_id}:")
    for series_id in series_ids or []:
        prefixes.append(f"advisor:series:{series_id}:")
    await _cache_delete_by_prefixes_best_effort(prefixes)


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


def key_public_book_detail(book_id: str) -> str:
    return f"public:book:{book_id}"


def key_public_chapter(book_id: str, chapter_num: int) -> str:
    return f"public:chapter:{book_id}:{chapter_num}"


def key_public_forum_cache_version() -> str:
    return "public:forum:version"


def key_public_forum_posts(
    version: int, q: str, page: int, page_size: int, thread_type: str | None = None
) -> str:
    query_hash = hashlib.md5(q.strip().lower().encode("utf-8")).hexdigest()[:10]
    thread_type_key = (thread_type or "all").strip().lower()
    return f"public:forum:posts:v{version}:{thread_type_key}:{query_hash}:{page}:{page_size}"


def key_public_forum_post_detail(version: int, post_id: str) -> str:
    return f"public:forum:post:v{version}:{post_id}"


EMBEDDING_CACHE_TTL_SECONDS = 30 * 60


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


CROSS_BOOK_INTEL_CACHE_TTL_SECONDS = 30 * 60


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
