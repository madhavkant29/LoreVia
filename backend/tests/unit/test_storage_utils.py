import asyncio

import pytest

from app.utils.storage_utils import bounded_storage_map


@pytest.mark.asyncio
async def test_bounded_storage_map_preserves_input_order_and_concurrency_limit():
    active = 0
    peak_active = 0

    async def read(value: int) -> int:
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        try:
            await asyncio.sleep(0)
            return value * 2
        finally:
            active -= 1

    values = await bounded_storage_map(range(8), read, concurrency=3)

    assert values == [0, 2, 4, 6, 8, 10, 12, 14]
    assert peak_active == 3


@pytest.mark.asyncio
async def test_bounded_storage_map_returns_immediately_for_empty_inputs():
    async def unexpected(_: object) -> object:
        raise AssertionError("operation should not be invoked")

    assert await bounded_storage_map([], unexpected, concurrency=4) == []
