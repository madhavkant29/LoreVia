import json
import logging
import sys
from unittest.mock import Mock

import sentry_sdk
from starlette.requests import Request

from app.utils.logging import (
    JSONFormatter,
    public_error_message,
    redact_sensitive_text,
    request_log_context,
    sanitize_validation_errors,
    scrub_sensitive_data,
    scrub_sentry_event,
)
from app.utils.logging.errors import public_stored_error_message, report_caught_failure
from app.utils.request_context import set_request_id


def test_public_error_message_maps_common_status_codes() -> None:
    assert public_error_message(400) == "Invalid request."
    assert public_error_message(401) == "Authentication failed."
    assert public_error_message(404) == "Not found."
    assert public_error_message(500) == "Something went wrong. Please try again."


def test_public_stored_error_message_retains_safe_validation_but_masks_legacy_raw_text():
    assert public_stored_error_message("Uploaded content is too large.") == (
        "Uploaded content is too large."
    )
    assert public_stored_error_message("SQL parameters: private manuscript text") == (
        "Something went wrong. Please try again."
    )
    assert public_stored_error_message(None) == "Something went wrong. Please try again."


def test_report_caught_failure_sends_only_static_event_and_failure_type(monkeypatch):
    capture = Mock()
    monkeypatch.setattr(sentry_sdk, "capture_message", capture)

    report_caught_failure(
        "manuscript_export_storage_failed", RuntimeError("private manuscript text")
    )

    capture.assert_called_once_with("manuscript_export_storage_failed", level="error")
    assert "private manuscript text" not in str(capture.call_args)


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
        {
            "loc": ("body", "password"),
            "msg": "Field required",
            "type": "missing",
            "input": "secret",
        },
        {"loc": ("body", "email"), "msg": "Invalid email", "type": "value_error"},
    ]

    sanitized = sanitize_validation_errors(errors)

    assert sanitized[0] == {"loc": ("body", "password"), "msg": "Field required", "type": "missing"}
    assert sanitized[1] == {"loc": ("body", "email"), "msg": "Invalid email", "type": "value_error"}


def test_redact_sensitive_text_scrubs_secret_values() -> None:
    message = (
        "authorization=Bearer abc123 "
        "database_url=postgresql://user:supersecret@example.com/app "
        "openai_api_key=sk-live-secret"
    )

    redacted = redact_sensitive_text(message)

    assert "abc123" not in redacted
    assert "supersecret" not in redacted
    assert "sk-live-secret" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_sensitive_text_scrubs_capability_jwt_in_path() -> None:
    token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJ1c2VyLTEiLCJ0eXBlIjoiYXNzZXQifQ."
        "c2lnbmF0dXJlLXRoYXQtbXVzdC1ub3QtYmUtbG9nZ2Vk"
    )

    redacted = redact_sensitive_text(f"/api/v1/beta-review/{token}/progress")

    assert token not in redacted
    assert redacted == "/api/v1/beta-review/[REDACTED]/progress"


def test_request_log_context_scrubs_capability_jwt_from_path() -> None:
    token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJ1c2VyLTEiLCJ0eXBlIjoiYXNzZXQifQ."
        "c2lnbmF0dXJlLXRoYXQtbXVzdC1ub3QtYmUtbG9nZ2Vk"
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/api/v1/beta-review/{token}",
            "headers": [],
        }
    )

    context = request_log_context(request)

    assert token not in context["path"]
    assert context["path"] == "/api/v1/beta-review/[REDACTED]"


def test_scrub_sensitive_data_redacts_sensitive_keys_recursively() -> None:
    payload = {
        "authorization": "Bearer abc123",
        "nested": {
            "cookie": "session=secret",
            "session_id": "refresh-session-123",
            "safe": "hello",
        },
    }

    scrubbed = scrub_sensitive_data(payload)

    assert scrubbed["authorization"] == "[REDACTED]"
    assert scrubbed["nested"]["cookie"] == "[REDACTED]"
    assert scrubbed["nested"]["session_id"] == "[REDACTED]"
    assert scrubbed["nested"]["safe"] == "hello"


def test_scrub_sentry_event_redacts_request_headers_and_extras() -> None:
    event = {
        "request": {
            "headers": {
                "authorization": "Bearer abc123",
                "x-request-id": "req-1",
            },
            "data": {
                "openai_api_key": "sk-secret",
                "prompt": "hello",
            },
        },
        "extra": {
            "database_url": "postgresql://user:pass@example.com/app",
        },
    }

    scrubbed = scrub_sentry_event(event)

    assert scrubbed["request"]["headers"]["authorization"] == "[REDACTED]"
    assert scrubbed["request"]["headers"]["x-request-id"] == "req-1"
    assert "data" not in scrubbed["request"]
    assert scrubbed["extra"]["database_url"] == "[REDACTED]"
    assert "data" in event["request"]


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
            raise ValueError("openai_api_key=sk-secret")
        except ValueError:
            record.exc_info = sys.exc_info()

        payload = json.loads(formatter.format(record))

        assert payload["message"] == "failed"
        assert payload["request_id"] == "req-456"
        assert payload["book_id"] == "book-1"
        assert "ValueError" in payload["exc"]
        assert "sk-secret" not in payload["exc"]
    finally:
        set_request_id(None)


def test_json_formatter_redacts_sensitive_message_text() -> None:
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="lorevia.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="authorization=%s session_id=%s database_url=%s",
        args=("Bearer abc123", "refresh-session-123", "postgresql://user:secret@example.com/app"),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert "abc123" not in payload["message"]
    assert "refresh-session-123" not in payload["message"]
    assert "secret@example.com" not in payload["message"]
    assert "[REDACTED]" in payload["message"]
