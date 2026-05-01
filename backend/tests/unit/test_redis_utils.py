import pytest

from app.utils.redis_utils import maybe_await


@pytest.mark.asyncio
async def test_maybe_await_returns_direct_value():
    assert await maybe_await(7) == 7


@pytest.mark.asyncio
async def test_maybe_await_awaits_coroutine():
    async def _value():
        return 11

    assert await maybe_await(_value()) == 11
