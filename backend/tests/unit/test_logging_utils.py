import json
import logging
import sys

from starlette.requests import Request

from app.utils.logging import JSONFormatter, public_error_message, request_log_context, sanitize_validation_errors
from app.utils.request_context import set_request_id


def test_public_error_message_maps_common_status_codes() -> None:
    assert public_error_message(400) == "Invalid request."
    assert public_error_message(401) == "Authentication failed."
    assert public_error_message(404) == "Not found."
    assert public_error_message(500) == "Something went wrong. Please try again."


def test_request_log_context_includes_request_metadata() -> None:
    scope = {"type": "http", "method": "POST", "path": "/api/v1/books", "headers": []}
    request = Request(scope)
    set_request_id("req-123")

    context = request_log_context(request, status_code=422, detail="hidden")

    assert context["request_id"] == "req-123"
    assert context["method"] == "POST"
    assert context["path"] == "/api/v1/books"
    assert context["status_code"] == 422
    assert context["detail"] == "hidden"


def test_sanitize_validation_errors_removes_raw_input() -> None:
    errors = [
        {"loc": ("body", "password"), "msg": "Field required", "type": "missing", "input": "secret"},
        {"loc": ("body", "email"), "msg": "Invalid email", "type": "value_error"},
    ]

    sanitized = sanitize_validation_errors(errors)

    assert sanitized[0] == {"loc": ("body", "password"), "msg": "Field required", "type": "missing"}
    assert sanitized[1] == {"loc": ("body", "email"), "msg": "Invalid email", "type": "value_error"}


def test_json_formatter_serializes_extras_and_exception() -> None:
    formatter = JSONFormatter()
    try:
        record = logging.LogRecord(
            name="lorevia.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-456"
        record.book_id = "book-1"
        try:
            raise ValueError("boom")
        except ValueError:
            record.exc_info = sys.exc_info()

        payload = json.loads(formatter.format(record))

        assert payload["message"] == "failed"
        assert payload["request_id"] == "req-456"
        assert payload["book_id"] == "book-1"
        assert "ValueError" in payload["exc"]
    finally:
        set_request_id(None)
