from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")

_worker_loop: asyncio.AbstractEventLoop | None = None


def has_worker_loop() -> bool:
    return _worker_loop is not None and not _worker_loop.is_closed()


def get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop


def run_worker_coro(coro: Awaitable[T]) -> T:
    loop = get_worker_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def close_worker_loop() -> None:
    global _worker_loop

    loop = _worker_loop
    _worker_loop = None
    if loop is None or loop.is_closed():
        return

    asyncio.set_event_loop(loop)
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.run_until_complete(loop.shutdown_default_executor())
    loop.close()
    asyncio.set_event_loop(None)
