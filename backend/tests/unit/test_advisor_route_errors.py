import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.utils.advisor_route_errors import advisor_scan_failure_category


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (HTTPException(429, {"kind": "llm_budget"}), "budget_exhausted"),
        (HTTPException(429, "LLM capacity is temporarily busy. Retry shortly."), "capacity_busy"),
        (HTTPException(503, "Provider unavailable."), "ai_unavailable"),
        (HTTPException(429, {"kind": "unrecognized"}), "ai_unavailable"),
        (SQLAlchemyError("database failed"), "database_unavailable"),
        (ValueError("invalid result"), "invalid_ai_response"),
        (RuntimeError("unexpected"), "ai_unavailable"),
    ],
)
def test_advisor_scan_failure_category_is_actionable_without_exposing_error_text(error, expected):
    assert advisor_scan_failure_category(error) == expected
