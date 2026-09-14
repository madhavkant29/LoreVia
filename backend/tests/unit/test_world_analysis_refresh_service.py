from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import world_analysis_refresh_service


@pytest.mark.asyncio
async def test_enqueue_world_analysis_refresh_deduplicates_existing_target(monkeypatch):
    acquire = AsyncMock(return_value=False)
    monkeypatch.setattr(world_analysis_refresh_service, "cache_acquire_lock", acquire)

    job_id = await world_analysis_refresh_service.enqueue_world_analysis_refresh(
        scope="book",
        target_id=uuid.uuid4(),
    )

    assert job_id is None
    acquire.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_world_analysis_refresh_dispatches_with_queue_metadata(monkeypatch):
    target_id = uuid.uuid4()
    apply_async = Mock()
    monkeypatch.setattr(
        world_analysis_refresh_service,
        "cache_acquire_lock",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.workers.tasks.intelligence_tasks.refresh_world_analysis_task",
        SimpleNamespace(apply_async=apply_async),
    )

    job_id = await world_analysis_refresh_service.enqueue_world_analysis_refresh(
        scope="series",
        target_id=target_id,
    )

    assert job_id
    apply_async.assert_called_once()
    kwargs = apply_async.call_args.kwargs
    assert kwargs["kwargs"] == {"scope": "series", "target_id": str(target_id)}
    assert kwargs["task_id"] == job_id
    assert kwargs["queue"] == "intelligence"
    assert kwargs["headers"]["enqueued_at"]


@pytest.mark.asyncio
async def test_enqueue_world_analysis_refresh_releases_lock_when_dispatch_fails(monkeypatch):
    release = AsyncMock(return_value=True)
    monkeypatch.setattr(
        world_analysis_refresh_service,
        "cache_acquire_lock",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(world_analysis_refresh_service, "cache_delete_if_owner", release)
    monkeypatch.setattr(
        "app.workers.tasks.intelligence_tasks.refresh_world_analysis_task",
        SimpleNamespace(apply_async=Mock(side_effect=RuntimeError("broker unavailable"))),
    )

    job_id = await world_analysis_refresh_service.enqueue_world_analysis_refresh(
        scope="book",
        target_id=uuid.uuid4(),
    )

    assert job_id is None
    release.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_world_analysis_refresh_rejects_unknown_scope():
    with pytest.raises(ValueError, match="scope"):
        await world_analysis_refresh_service.enqueue_world_analysis_refresh(
            scope="workspace",
            target_id=uuid.uuid4(),
        )
