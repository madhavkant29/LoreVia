import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import Request
from openai import APIConnectionError
from tenacity import wait_none

from app.core import redis as redis_utils
from app.engine.embeddings import embedder


def _stub_embedding_response(embedding: list[float]) -> MagicMock:
    item = MagicMock()
    item.embedding = embedding
    r = MagicMock()
    r.data = [item]
    return r


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def get(self, key):
        return self.values.get(key)

    async def setex(self, key, ttl, value):
        self.values[key] = value

    async def set(self, key, value, ex=None, nx=None):
        self.values[key] = value
        return True

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)


def test_get_client_disables_hidden_sdk_retries(monkeypatch):
    captured: dict[str, object] = {}
    client = object()
    monkeypatch.setattr(embedder, "_EMBEDDING_CLIENT", None)
    monkeypatch.setattr(embedder, "_EMBEDDING_CLIENT_CACHE_KEY", None)

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return client

    monkeypatch.setattr(embedder, "AsyncOpenAI", fake_openai)
    monkeypatch.setattr(embedder.settings, "OPENAI_API_KEY", "test-key")

    assert embedder.get_client() is client
    assert captured == {"api_key": "test-key", "max_retries": 0}


@pytest.mark.asyncio
async def test_get_client_reuses_and_closes_cached_client(monkeypatch):
    clients = [MagicMock(), MagicMock()]
    for client in clients:
        client.close = AsyncMock()
    calls = 0
    monkeypatch.setattr(embedder, "_EMBEDDING_CLIENT", None)
    monkeypatch.setattr(embedder, "_EMBEDDING_CLIENT_CACHE_KEY", None)

    def fake_openai(**_kwargs):
        nonlocal calls
        client = clients[calls]
        calls += 1
        return client

    monkeypatch.setattr(embedder, "AsyncOpenAI", fake_openai)

    first = embedder.get_client()
    second = embedder.get_client()
    await embedder.close_embedding_client()
    third = embedder.get_client()

    assert first is second
    assert third is clients[1]
    assert calls == 2
    clients[0].close.assert_awaited_once()


def test_get_client_recreates_closed_cached_client(monkeypatch):
    clients = [MagicMock(), MagicMock()]
    clients[0].is_closed.side_effect = [False, True]
    clients[1].is_closed.return_value = False
    monkeypatch.setattr(embedder, "_EMBEDDING_CLIENT", None)
    monkeypatch.setattr(embedder, "_EMBEDDING_CLIENT_CACHE_KEY", None)
    monkeypatch.setattr(embedder, "AsyncOpenAI", MagicMock(side_effect=clients))

    assert embedder.get_client() is clients[0]
    assert embedder.get_client() is clients[0]
    assert embedder.get_client() is clients[1]
    assert embedder.get_client() is clients[1]


def test_embedding_client_does_not_reuse_a_client_from_a_previous_event_loop(monkeypatch):
    clients = [MagicMock(), MagicMock()]
    for client in clients:
        client.is_closed.return_value = False
        client.close = AsyncMock()
    monkeypatch.setattr(embedder, "_EMBEDDING_CLIENT", None)
    monkeypatch.setattr(embedder, "_EMBEDDING_CLIENT_CACHE_KEY", None)
    monkeypatch.setattr(embedder, "AsyncOpenAI", MagicMock(side_effect=clients))

    async def resolve():
        return embedder.get_client(), asyncio.get_running_loop()

    first_client, first_loop = asyncio.run(resolve())
    second_client, second_loop = asyncio.run(resolve())

    assert first_client is clients[0]
    assert second_client is clients[1]
    assert first_loop is not second_loop
    assert embedder._EMBEDDING_CLIENT_CACHE_KEY[1] is second_loop
    asyncio.run(embedder.close_embedding_client())
    clients[1].close.assert_awaited_once()


@pytest.mark.asyncio
async def test_embedding_retry_is_bounded_at_the_provider_call(monkeypatch):
    calls = 0
    response = SimpleNamespace(data=[])

    async def fake_create_tracked_embedding(**_kwargs):
        nonlocal calls
        calls += 1
        if calls < 2:
            raise APIConnectionError(
                request=Request("POST", "https://api.openai.com/v1/embeddings")
            )
        return response

    monkeypatch.setattr(embedder, "create_tracked_embedding", fake_create_tracked_embedding)
    call_without_wait = embedder._create_embedding_with_retry.retry_with(wait=wait_none())

    assert await call_without_wait(client=object()) is response
    assert calls == 2


@pytest.mark.asyncio
async def test_embed_text_hits_redis_cache_skips_openai(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(redis_utils, "get_redis", AsyncMock(return_value=fake_redis))

    cached_vector = [0.1, 0.2, 0.3]
    cache_key = redis_utils.key_embedding_cache(
        feature="semantic_search_query",
        model="text-embedding-3-small",
        text="test query",
    )
    fake_redis.values[cache_key] = json.dumps(cached_vector)

    mock_client = MagicMock()
    mock_client.close = AsyncMock()

    from app.engine.embeddings.embedder import embed_text

    with patch("app.engine.embeddings.embedder.get_client", return_value=mock_client):
        result = await embed_text(
            "test query",
            db=None,
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            feature="semantic_search_query",
        )

    assert result == cached_vector
    assert mock_client.embeddings.create.call_count == 0


@pytest.mark.asyncio
async def test_embed_text_cache_hit_still_requires_customer_attribution(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(redis_utils, "get_redis", AsyncMock(return_value=fake_redis))
    cache_key = redis_utils.key_embedding_cache(
        feature="semantic_search_query",
        model="text-embedding-3-small",
        text="cached query",
    )
    fake_redis.values[cache_key] = json.dumps([0.1, 0.2])

    with pytest.raises(HTTPException) as exc_info:
        await embedder.embed_text(
            "cached query",
            user_id=None,
            feature="semantic_search_query",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["kind"] == "llm_attribution"


@pytest.mark.asyncio
async def test_embed_text_cache_miss_calls_openai_and_writes_cache(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(redis_utils, "get_redis", AsyncMock(return_value=fake_redis))

    expected_vector = [0.4, 0.5, 0.6]
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = AsyncMock(
        return_value=_stub_embedding_response(expected_vector)
    )

    from app.engine.embeddings.embedder import embed_text

    with patch("app.engine.embeddings.embedder.get_client", return_value=mock_client):
        result = await embed_text(
            "novel query",
            db=None,
            user_id=None,
            feature="semantic_search_query",
            billing_scope="system",
        )

    assert result == expected_vector
    assert mock_client.embeddings.create.call_count >= 1

    cache_key = redis_utils.key_embedding_cache(
        feature="semantic_search_query",
        model="text-embedding-3-small",
        text="novel query",
    )
    assert cache_key in fake_redis.values
    cached = json.loads(fake_redis.values[cache_key])
    assert cached == expected_vector


@pytest.mark.asyncio
async def test_embed_text_different_features_use_separate_cache(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(redis_utils, "get_redis", AsyncMock(return_value=fake_redis))

    vector_search = [0.1, 0.2]
    vector_character = [0.3, 0.4]

    responses = iter(
        [_stub_embedding_response(vector_search), _stub_embedding_response(vector_character)]
    )
    call_count = 0

    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_client.embeddings = MagicMock()

    async def _fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        return next(responses)

    mock_client.embeddings.create = _fake_create

    from app.engine.embeddings.embedder import embed_text

    with patch("app.engine.embeddings.embedder.get_client", return_value=mock_client):
        r1 = await embed_text(
            "same text",
            user_id=None,
            feature="semantic_search_query",
            billing_scope="system",
        )
        r2 = await embed_text(
            "same text",
            user_id=None,
            feature="character_embedding",
            billing_scope="system",
        )

    assert r1 == vector_search
    assert r2 == vector_character
    assert call_count == 2

    key_search = redis_utils.key_embedding_cache(
        feature="semantic_search_query",
        model="text-embedding-3-small",
        text="same text",
    )
    key_char = redis_utils.key_embedding_cache(
        feature="character_embedding",
        model="text-embedding-3-small",
        text="same text",
    )
    assert key_search != key_char
    assert json.loads(fake_redis.values[key_search]) == vector_search
    assert json.loads(fake_redis.values[key_char]) == vector_character


@pytest.mark.asyncio
async def test_embed_text_same_query_twice_one_api_call(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(redis_utils, "get_redis", AsyncMock(return_value=fake_redis))

    expected_vector = [0.7, 0.8, 0.9]
    call_count = 0

    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_client.embeddings = MagicMock()

    async def _fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        return _stub_embedding_response(expected_vector)

    mock_client.embeddings.create = _fake_create

    from app.engine.embeddings.embedder import embed_text

    with patch("app.engine.embeddings.embedder.get_client", return_value=mock_client):
        r1 = await embed_text(
            "what happened to the amulet",
            user_id=None,
            feature="semantic_search_query",
            billing_scope="system",
        )
        r2 = await embed_text(
            "what happened to the amulet",
            user_id=None,
            feature="semantic_search_query",
            billing_scope="system",
        )

    assert r1 == expected_vector
    assert r2 == expected_vector
    assert call_count == 1


@pytest.mark.asyncio
async def test_embed_text_empty_string(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(redis_utils, "get_redis", AsyncMock(return_value=fake_redis))

    expected_vector = [0.0, 0.0]
    mock_client = MagicMock()
    mock_client.close = AsyncMock()
    mock_client.embeddings = MagicMock()
    mock_client.embeddings.create = AsyncMock(
        return_value=_stub_embedding_response(expected_vector)
    )

    from app.engine.embeddings.embedder import embed_text

    with patch("app.engine.embeddings.embedder.get_client", return_value=mock_client):
        result = await embed_text(
            "",
            user_id=None,
            feature="embedding",
            billing_scope="system",
        )

    assert result == expected_vector

    cache_key = redis_utils.key_embedding_cache(
        feature="embedding",
        model="text-embedding-3-small",
        text="",
    )
    assert cache_key in fake_redis.values
