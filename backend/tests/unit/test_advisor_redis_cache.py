import pytest

from app.core import redis as redis_utils


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.deleted: list[tuple[str, ...]] = []
        self.setex_calls: list[tuple[str, int, str]] = []

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, ttl, value):
        self.values[key] = value
        self.setex_calls.append((key, ttl, value))

    async def set(self, key, value, ex=None, nx=None):
        self.values[key] = value
        return True

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
        self.deleted.append(tuple(str(key) for key in keys))

    async def scan(self, *, cursor=0, match=None, count=None):
        prefix = str(match or "").rstrip("*")
        keys = [key for key in self.values if key.startswith(prefix)]
        return 0, keys


@pytest.mark.asyncio
async def test_advisor_response_cache_round_trip(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_utils, "get_redis", _fake_get_redis)

    await redis_utils.set_advisor_response_cache("book-1", "cache-key", {"reply": "hello"})
    payload = await redis_utils.get_advisor_response_cache("book-1", "cache-key")

    assert payload == {"reply": "hello"}
    assert fake_redis.setex_calls[0][1] == redis_utils.ADVISOR_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_advisor_response_cache_miss_returns_none(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_utils, "get_redis", _fake_get_redis)

    payload = await redis_utils.get_advisor_response_cache("book-1", "missing")

    assert payload is None


@pytest.mark.asyncio
async def test_advisor_response_cache_invalid_payload_is_treated_as_miss(monkeypatch):
    fake_redis = _FakeRedis()
    fake_redis.values[redis_utils.key_advisor_response_cache("book-1", "bad")] = "{not-json"

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_utils, "get_redis", _fake_get_redis)

    payload = await redis_utils.get_advisor_response_cache("book-1", "bad")

    assert payload is None
    assert fake_redis.deleted[-1] == (redis_utils.key_advisor_response_cache("book-1", "bad"),)


@pytest.mark.asyncio
async def test_invalidate_advisor_cache_namespaces_deletes_book_and_series_keys(monkeypatch):
    fake_redis = _FakeRedis()
    fake_redis.values = {
        redis_utils.key_advisor_response_cache("book-1", "a"): '{"reply":"one"}',
        redis_utils.key_editorial_review_cache("book-1", "b"): '{"review":"two"}',
        redis_utils.key_series_advisor_response_cache("series-1", "c"): '{"reply":"three"}',
        "public:books": '{"ignored":true}',
    }

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_utils, "get_redis", _fake_get_redis)

    await redis_utils.invalidate_advisor_cache_namespaces(
        book_id="book-1",
        series_ids=["series-1"],
    )

    assert redis_utils.key_advisor_response_cache("book-1", "a") not in fake_redis.values
    assert redis_utils.key_editorial_review_cache("book-1", "b") not in fake_redis.values
    assert redis_utils.key_series_advisor_response_cache("series-1", "c") not in fake_redis.values
    assert "public:books" in fake_redis.values


@pytest.mark.asyncio
async def test_story_context_and_dashboard_cache_round_trip(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_utils, "get_redis", _fake_get_redis)

    await redis_utils.set_story_context_cache("book-1", 0, 12, "story")
    await redis_utils.set_writing_dashboard_cache(
        "user-1", 0, "2026-05-22", {"today": {"words": 42}}
    )

    story_payload = await redis_utils.get_story_context_cache("book-1", 0, 12)
    dashboard_payload = await redis_utils.get_writing_dashboard_cache("user-1", 0, "2026-05-22")

    assert story_payload == "story"
    assert dashboard_payload == {"today": {"words": 42}}


@pytest.mark.asyncio
async def test_reader_derived_caches_round_trip(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_utils, "get_redis", _fake_get_redis)

    await redis_utils.set_reader_events_cache(
        "book-1", "user-1", 4, 10, 20, {"major_events": [], "character_events": []}
    )
    await redis_utils.set_reader_timeline_cache(
        "book-1", "user-1", 10, 20, {"chapters": [], "events": []}
    )
    await redis_utils.set_relationship_evolution_cache("book-1", "user-1", 4, 10, 20, {"pairs": []})

    events_payload = await redis_utils.get_reader_events_cache("book-1", "user-1", 4, 10, 20)
    timeline_payload = await redis_utils.get_reader_timeline_cache("book-1", "user-1", 10, 20)
    evolution_payload = await redis_utils.get_relationship_evolution_cache(
        "book-1", "user-1", 4, 10, 20
    )

    assert events_payload == {"major_events": [], "character_events": []}
    assert timeline_payload == {"chapters": [], "events": []}
    assert evolution_payload == {"pairs": []}


@pytest.mark.asyncio
async def test_mark_cache_dirty_updates_version_markers(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_utils, "get_redis", _fake_get_redis)

    await redis_utils.mark_book_cache_dirty("book-1")
    await redis_utils.mark_series_cache_dirty("series-1")
    await redis_utils.mark_user_dashboard_cache_dirty("user-1")
    await redis_utils.mark_reader_progress_cache_dirty("book-1", "user-1")

    assert redis_utils.key_book_cache_version("book-1") in fake_redis.values
    assert redis_utils.key_series_cache_version("series-1") in fake_redis.values
    assert redis_utils.key_user_dashboard_cache_version("user-1") in fake_redis.values
    assert redis_utils.key_reader_progress_cache_version("book-1", "user-1") in fake_redis.values
