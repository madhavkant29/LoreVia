import pytest
from fastapi import HTTPException

from app.utils.internal_job_utils import verify_internal_job_secret


def test_verify_internal_job_secret_rejects_when_not_configured(monkeypatch):
    monkeypatch.setattr(
        "app.utils.internal_job_utils.settings.INTERNAL_JOB_SECRET", None, raising=False
    )

    with pytest.raises(HTTPException) as exc_info:
        verify_internal_job_secret("anything")

    assert exc_info.value.status_code == 503


def test_verify_internal_job_secret_rejects_invalid_secret(monkeypatch):
    monkeypatch.setattr(
        "app.utils.internal_job_utils.settings.INTERNAL_JOB_SECRET",
        "expected-secret",
        raising=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        verify_internal_job_secret("wrong-secret")

    assert exc_info.value.status_code == 403


def test_verify_internal_job_secret_accepts_matching_secret(monkeypatch):
    monkeypatch.setattr(
        "app.utils.internal_job_utils.settings.INTERNAL_JOB_SECRET",
        "expected-secret",
        raising=False,
    )

    verify_internal_job_secret("expected-secret")
