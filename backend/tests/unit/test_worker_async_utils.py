from __future__ import annotations

import asyncio

from app.utils import worker_async_utils


def test_run_worker_coro_reuses_same_loop_and_close_resets_it():
    worker_async_utils.close_worker_loop()

    async def _loop_id() -> int:
        return id(asyncio.get_running_loop())

    first_loop_id = worker_async_utils.run_worker_coro(_loop_id())
    second_loop_id = worker_async_utils.run_worker_coro(_loop_id())

    assert first_loop_id == second_loop_id

    original_loop = worker_async_utils.get_worker_loop()
    worker_async_utils.close_worker_loop()

    assert original_loop.is_closed() is True

    third_loop_id = worker_async_utils.run_worker_coro(_loop_id())
    assert third_loop_id != first_loop_id

    worker_async_utils.close_worker_loop()
