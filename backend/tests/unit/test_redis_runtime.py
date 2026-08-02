from __future__ import annotations

import asyncio
import weakref

import pytest

from app.core import redis as redis_module
from app.utils import worker_async_utils


def test_get_redis_reuses_client_within_loop_and_separates_loops(monkeypatch):
    created_clients: list[_FakeRedisClient] = []

    def _fake_from_url(*_args, **_kwargs):
        client = _FakeRedisClient()
        created_clients.append(client)
        return client

    monkeypatch.setattr(redis_module.aioredis, "from_url", _fake_from_url)
    monkeypatch.setattr(redis_module, "_redis_clients", weakref.WeakKeyDictionary())

    async def _get_twice() -> tuple[_FakeRedisClient, _FakeRedisClient]:
        first = await redis_module.get_redis()
        second = await redis_module.get_redis()
        return first, second

    first, second = asyncio.run(_get_twice())
    third = asyncio.run(redis_module.get_redis())

    assert first is second
    assert third is not first
    assert len(created_clients) == 2


def test_close_redis_and_close_all_redis_clients_close_cached_clients(monkeypatch):
    created_clients: list[_FakeRedisClient] = []

    def _fake_from_url(*_args, **_kwargs):
        client = _FakeRedisClient()
        created_clients.append(client)
        return client

    monkeypatch.setattr(redis_module.aioredis, "from_url", _fake_from_url)
    monkeypatch.setattr(redis_module, "_redis_clients", weakref.WeakKeyDictionary())
    worker_async_utils.close_worker_loop()

    async def _get_and_close_current_loop() -> _FakeRedisClient:
        client = await redis_module.get_redis()
        await redis_module.close_redis()
        return client

    closed_client = worker_async_utils.run_worker_coro(_get_and_close_current_loop())
    assert closed_client.closed is True

    async def _get_client() -> _FakeRedisClient:
        return await redis_module.get_redis()

    remaining_client = worker_async_utils.run_worker_coro(_get_client())
    worker_async_utils.run_worker_coro(redis_module.close_all_redis_clients())

    assert remaining_client.closed is True
    assert len(redis_module._redis_clients) == 0
    worker_async_utils.close_worker_loop()


def test_worker_runtime_can_reuse_loop_scoped_redis_across_sequential_runs(monkeypatch):
    created_clients: list[_FakeRedisClient] = []

    def _fake_from_url(*_args, **_kwargs):
        client = _FakeRedisClient()
        created_clients.append(client)
        return client

    monkeypatch.setattr(redis_module.aioredis, "from_url", _fake_from_url)
    monkeypatch.setattr(redis_module, "_redis_clients", weakref.WeakKeyDictionary())
    worker_async_utils.close_worker_loop()

    async def _set_once() -> bool:
        return await redis_module.cache_set_if_absent("worker:lock", {"ok": True}, 30)

    async def _set_again() -> bool:
        return await redis_module.cache_set_if_absent("worker:lock", {"ok": True}, 30)

    first = worker_async_utils.run_worker_coro(_set_once())
    second = worker_async_utils.run_worker_coro(_set_again())

    assert first is True
    assert second is False
    assert len(created_clients) == 1

    worker_async_utils.run_worker_coro(redis_module.close_all_redis_clients())
    worker_async_utils.close_worker_loop()


class _FakeRedisClient:
    def __init__(self):
        self.closed = False
        self.store: dict[str, str] = {}

    async def aclose(self):
        self.closed = True

    async def get(self, key):
        return self.store.get(key)

    async def getdel(self, key):
        value = self.store.get(key)
        if value is not None:
            del self.store[key]
        return value

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = str(value)
        return True

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.store:
                deleted += 1
                del self.store[key]
        return deleted


@pytest.mark.asyncio
async def test_cache_delete_if_owner_falls_back_when_eval_is_unavailable(monkeypatch):
    fake_redis = _FakeRedisClient()
    fake_redis.store["worker:lock"] = "owner-1"

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_module, "get_redis", _fake_get_redis)

    deleted = await redis_module.cache_delete_if_owner("worker:lock", "owner-1")

    print(f"DEBUG: deleted={deleted}, store={fake_redis.store}")
    assert deleted is True
    assert "worker:lock" not in fake_redis.store


@pytest.mark.asyncio
async def test_cache_delete_if_owner_preserves_key_for_other_owner_without_eval(monkeypatch):
    fake_redis = _FakeRedisClient()
    fake_redis.store["worker:lock"] = "owner-1"

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_module, "get_redis", _fake_get_redis)

    deleted = await redis_module.cache_delete_if_owner("worker:lock", "owner-2")

    assert deleted is False
    assert fake_redis.store["worker:lock"] == "owner-1"


@pytest.mark.asyncio
async def test_consume_refresh_session_is_single_use(monkeypatch):
    fake_redis = _FakeRedisClient()
    session_key = redis_module.key_refresh_session("user-1", "session-1")
    fake_redis.store[session_key] = "1"

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_module, "get_redis", _fake_get_redis)

    assert await redis_module.consume_refresh_session("user-1", "session-1") is True
    assert await redis_module.consume_refresh_session("user-1", "session-1") is False


@pytest.mark.asyncio
async def test_password_reset_and_email_verification_consumption_is_single_use(monkeypatch):
    fake_redis = _FakeRedisClient()
    reset_token = "reset-token"
    verification_token = "verify-token"
    fake_redis.store[
        redis_module.key_password_reset(redis_module._hash_ephemeral_token(reset_token))
    ] = "user-1"
    fake_redis.store[redis_module.key_password_reset_user("user-1")] = reset_token
    fake_redis.store[redis_module.key_email_verification(verification_token)] = "user-1"
    fake_redis.store[redis_module.key_email_verification_user("user-1")] = verification_token

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_module, "get_redis", _fake_get_redis)

    assert await redis_module.consume_password_reset_token(reset_token) == "user-1"
    assert await redis_module.consume_password_reset_token(reset_token) is None
    assert await redis_module.consume_email_verification_token(verification_token) == "user-1"
    assert await redis_module.consume_email_verification_token(verification_token) is None


@pytest.mark.asyncio
async def test_consuming_old_token_preserves_newer_user_pointer(monkeypatch):
    fake_redis = _FakeRedisClient()
    reset_token = "old-reset-token"
    verification_token = "old-verify-token"
    fake_redis.store[
        redis_module.key_password_reset(redis_module._hash_ephemeral_token(reset_token))
    ] = "user-1"
    fake_redis.store[redis_module.key_password_reset_user("user-1")] = "new-reset-token"
    fake_redis.store[redis_module.key_email_verification(verification_token)] = "user-1"
    fake_redis.store[redis_module.key_email_verification_user("user-1")] = "new-verify-token"

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(redis_module, "get_redis", _fake_get_redis)

    assert await redis_module.consume_password_reset_token(reset_token) == "user-1"
    assert fake_redis.store[redis_module.key_password_reset_user("user-1")] == "new-reset-token"
    assert await redis_module.consume_email_verification_token(verification_token) == "user-1"
    assert (
        fake_redis.store[redis_module.key_email_verification_user("user-1")] == "new-verify-token"
    )
