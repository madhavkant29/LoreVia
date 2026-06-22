import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.workers.worker_launcher import worker_arguments


def test_worker_arguments_use_role_specific_config(monkeypatch):
    monkeypatch.setattr(settings, "EXTRACTION_WORKER_CONCURRENCY", 3)
    arguments = worker_arguments("extraction")
    assert arguments[-1] == "3"
    assert "extraction,extraction_priority" in arguments


def test_worker_arguments_reject_unknown_role():
    with pytest.raises(ValueError, match="Unknown worker role"):
        worker_arguments("unknown")


def test_worker_arguments_reject_zero_concurrency(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_WORKER_CONCURRENCY", 0)
    with pytest.raises(ValueError, match="must be at least 1"):
        worker_arguments("embedding")


def test_settings_reject_invalid_worker_concurrency():
    with pytest.raises(ValidationError, match="EXTRACTION_WORKER_CONCURRENCY"):
        Settings(EXTRACTION_WORKER_CONCURRENCY=0)
