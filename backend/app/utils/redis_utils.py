from collections.abc import Awaitable
from typing import TypeVar
import inspect

T = TypeVar("T")


async def maybe_await(value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value
