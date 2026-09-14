from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable

from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.storage import delete_object

log = logging.getLogger("lorevia.storage_utils")

STORAGE_IO_EXCEPTIONS = (
    ValueError,
    OSError,
    BotoCoreError,
    ClientError,
)

async def bounded_storage_map[Item, Result](
    items: Iterable[Item],
    operation: Callable[[Item], Awaitable[Result]],
    *,
    concurrency: int | None = None,
) -> list[Result]:
    """Run independent storage operations with bounded concurrency and stable ordering.

    ``operation`` must not use a shared ``AsyncSession``; this helper is for
    independent object-storage work such as chapter downloads.  Exceptions are
    deliberately propagated just as they are with ``asyncio.gather``.
    """
    values = list(items)
    if not values:
        return []
    configured_concurrency = (
        settings.STORAGE_IO_CONCURRENCY if concurrency is None else concurrency
    )
    bounded_concurrency = max(1, min(int(configured_concurrency), len(values)))
    semaphore = asyncio.Semaphore(bounded_concurrency)

    async def run(item: Item) -> Result:
        async with semaphore:
            return await operation(item)

    return list(await asyncio.gather(*(run(item) for item in values)))


async def delete_storage_key_best_effort(key: str | None, *, context: str = "storage") -> bool:
    if not key:
        return False
    try:
        await asyncio.to_thread(delete_object, key)
        return True
    except STORAGE_IO_EXCEPTIONS:
        log.warning("%s_delete_failed key=%s", context, key, exc_info=True)
        return False


async def delete_storage_keys_best_effort(
    keys: Iterable[str | None], *, context: str = "storage"
) -> list[str]:
    deleted: list[str] = []
    for key in dict.fromkeys(key for key in keys if key):
        if await delete_storage_key_best_effort(key, context=context):
            deleted.append(key)
    return deleted
