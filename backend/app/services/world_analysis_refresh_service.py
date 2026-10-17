"""Deduplicated dispatch for durable world-analysis refreshes."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.core.redis import (
    cache_acquire_lock,
    cache_delete_if_owner,
    key_world_analysis_refresh,
)

WORLD_ANALYSIS_REFRESH_LOCK_TTL_SECONDS = 900
log = logging.getLogger("lorevia.world_analysis_refresh")


async def enqueue_world_analysis_refresh(
    *,
    scope: str,
    target_id: uuid.UUID,
) -> str | None:
    if scope not in {"book", "series"}:
        raise ValueError("World-analysis scope must be book or series")
    job_id = str(uuid.uuid4())
    lock_key = key_world_analysis_refresh(scope, str(target_id))
    acquired = await cache_acquire_lock(
        lock_key,
        job_id,
        ttl=WORLD_ANALYSIS_REFRESH_LOCK_TTL_SECONDS,
    )
    if not acquired:
        return None
    try:
        from app.workers.tasks.intelligence_tasks import refresh_world_analysis_task

        refresh_world_analysis_task.apply_async(
            kwargs={"scope": scope, "target_id": str(target_id)},
            task_id=job_id,
            queue="intelligence",
            headers={"enqueued_at": datetime.now(UTC).isoformat()},
        )
    except Exception:
        await cache_delete_if_owner(lock_key, job_id)
        log.warning(
            "world_analysis_refresh_dispatch_failed",
            extra={"scope": scope, "target_id": str(target_id)},
            exc_info=True,
        )
        return None
    return job_id
