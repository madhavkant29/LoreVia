"""Normalization helpers for the supportive first-manuscript read."""

from __future__ import annotations

from typing import Any

FIRST_IMPRESSION_STATUSES = {
    "not_started",
    "queued",
    "running",
    "complete",
    "failed",
}


def normalize_first_impression_state(raw: object) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    status = " ".join(str(source.get("status") or "not_started").split()).strip().lower()
    if status not in FIRST_IMPRESSION_STATUSES:
        status = "not_started"

    def clean(key: str) -> str | None:
        value = source.get(key)
        if not isinstance(value, str):
            return None
        return " ".join(value.split()).strip() or None

    return {
        "status": status,
        "job_id": clean("job_id"),
        "report_id": clean("report_id"),
        "request_hash": clean("request_hash"),
        "source_fingerprint": clean("source_fingerprint"),
        "started_at": clean("started_at"),
        "completed_at": clean("completed_at"),
        "error_code": clean("error_code"),
    }
