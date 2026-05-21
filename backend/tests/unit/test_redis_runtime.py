from __future__ import annotations

import asyncio
import weakref

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

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = str(value)
        return True
