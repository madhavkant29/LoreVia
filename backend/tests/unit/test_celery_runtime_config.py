from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.utils.request_context import get_request_id, get_request_user_id, set_request_user_id
from app.workers import celery_app


def test_non_llm_celery_retries_are_capped_at_six() -> None:
    assert celery_app.celery_app.conf.broker_connection_max_retries == 6
    assert celery_app.celery_app.conf.task_max_retries == 6


def test_resolve_celery_redis_settings_defaults_to_redis_url(monkeypatch):
    monkeypatch.setattr(celery_app.settings, "REDIS_URL", "redis://:pw@redis:6379/0")
    monkeypatch.setattr(celery_app.settings, "CELERY_BROKER_URL", None)
    monkeypatch.setattr(celery_app.settings, "CELERY_RESULT_BACKEND", None)

    broker_url, broker_ssl, backend_url, backend_ssl = celery_app._resolve_celery_redis_settings()

    assert broker_url == "redis://:pw@redis:6379/0"
    assert backend_url is None
    assert broker_ssl == {}
    assert backend_ssl == {}


def test_resolve_celery_redis_settings_allows_disabling_result_backend(monkeypatch):
    monkeypatch.setattr(celery_app.settings, "REDIS_URL", "redis://:pw@redis:6379/0")
    monkeypatch.setattr(celery_app.settings, "CELERY_BROKER_URL", "redis://:broker@redis:6379/1")
    monkeypatch.setattr(celery_app.settings, "CELERY_RESULT_BACKEND", "   ")

    broker_url, broker_ssl, backend_url, backend_ssl = celery_app._resolve_celery_redis_settings()

    assert broker_url == "redis://:broker@redis:6379/1"
    assert backend_url is None
    assert broker_ssl == {}
    assert backend_ssl == {}


def test_worker_process_init_detaches_parent_database_pool(monkeypatch):
    dispose = AsyncMock()
    loop = asyncio.new_event_loop()
    monkeypatch.setattr(celery_app, "engine", SimpleNamespace(dispose=dispose))
    monkeypatch.setattr(celery_app, "get_worker_loop", lambda: loop)

    try:
        celery_app._worker_process_init()
    finally:
        loop.close()

    dispose.assert_awaited_once_with(close=False)


def test_task_runtime_installs_and_clears_published_request_context(monkeypatch):
    task = SimpleNamespace(request=SimpleNamespace(headers={"request_id": "request-123"}))
    monkeypatch.setattr(celery_app.settings, "SENTRY_DSN", None)

    celery_app._task_prerun_set_request_id(task=task)
    set_request_user_id(uuid.uuid4())

    assert get_request_id() == "request-123"
    assert get_request_user_id() is not None

    celery_app._task_postrun_clear_request_id()

    assert get_request_id() is None
    assert get_request_user_id() is None


def test_task_runtime_does_not_read_producer_signal_headers(monkeypatch):
    task = SimpleNamespace(request=SimpleNamespace(headers={}))
    monkeypatch.setattr(celery_app.settings, "SENTRY_DSN", None)

    celery_app._task_prerun_set_request_id(
        task=task,
        headers={"request_id": "producer-process-only"},
    )

    assert get_request_id() is None


@pytest.mark.asyncio
async def test_worker_shutdown_disposes_database_even_if_redis_cleanup_fails(monkeypatch):
    dispose = AsyncMock()
    monkeypatch.setattr(celery_app, "engine", SimpleNamespace(dispose=dispose))
    monkeypatch.setattr(
        celery_app,
        "close_all_redis_clients",
        AsyncMock(side_effect=RuntimeError("redis cleanup failed")),
    )

    with pytest.raises(RuntimeError, match="redis cleanup failed"):
        await celery_app._shutdown_worker_async_resources()

    dispose.assert_awaited_once_with()
