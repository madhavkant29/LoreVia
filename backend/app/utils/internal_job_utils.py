from __future__ import annotations

from hmac import compare_digest

from fastapi import HTTPException

from app.core.config import settings


def verify_internal_job_secret(provided_secret: str | None) -> None:
    configured_secret = (settings.INTERNAL_JOB_SECRET or "").strip()
    if not configured_secret:
        raise HTTPException(503, "Internal jobs are not configured.")
    if not provided_secret or not compare_digest(provided_secret, configured_secret):
        raise HTTPException(403, "Forbidden")
