from __future__ import annotations

from app.workers import celery_app


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
