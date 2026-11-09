from __future__ import annotations

from fastapi import HTTPException
from openai import OpenAIError
from sqlalchemy.exc import SQLAlchemyError

ADVISOR_STREAM_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    OSError,
    TimeoutError,
    OpenAIError,
    SQLAlchemyError,
)

ADVISOR_CONTENT_READ_ERRORS = (
    RuntimeError,
    ValueError,
    UnicodeError,
    OSError,
)


def advisor_scan_failure_category(error: Exception) -> str:
    """Expose an actionable scan failure class without leaking provider details."""
    if isinstance(error, SQLAlchemyError):
        return "database_unavailable"
    if isinstance(error, HTTPException):
        detail = error.detail
        if isinstance(detail, dict) and detail.get("kind") == "llm_budget":
            return "budget_exhausted"
        if (
            error.status_code == 429
            and isinstance(detail, str)
            and detail.startswith("LLM capacity is temporarily busy.")
        ):
            return "capacity_busy"
    if isinstance(error, (ValueError, TypeError, KeyError, IndexError)):
        return "invalid_ai_response"
    return "ai_unavailable"
