from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from botocore.exceptions import BotoCoreError, ClientError

from app.core.storage import delete_object

log = logging.getLogger("lorevia.storage_utils")

STORAGE_IO_EXCEPTIONS = (
    ValueError,
    OSError,
    BotoCoreError,
    ClientError,
)


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
