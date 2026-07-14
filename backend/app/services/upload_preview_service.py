import asyncio
import hashlib
import logging
import uuid
from typing import Any

from app.core.redis import cache_get, cache_set
from app.utils.books.imports import build_import_preview

log = logging.getLogger(__name__)

UPLOAD_PREVIEW_CACHE_TTL_SECONDS = 15 * 60


def upload_preview_cache_key(user_id: uuid.UUID, raw: bytes) -> str:
    return f"upload-preview:{user_id}:{hashlib.sha256(raw).hexdigest()}"


async def load_or_build_upload_preview(
    *,
    user_id: uuid.UUID,
    raw: bytes,
    format_name: str,
    work_type: str,
) -> dict[str, Any]:
    key = upload_preview_cache_key(user_id, raw)
    cached = await cache_get(key)
    if isinstance(cached, dict):
        return cached
    preview = await asyncio.to_thread(
        lambda: build_import_preview(
            format_name=format_name, work_type=work_type, raw=raw, language=None
        )
    )
    await cache_set(key, preview, UPLOAD_PREVIEW_CACHE_TTL_SECONDS)
    return preview
