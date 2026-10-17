from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from fastapi import Request

from app.utils.request_context import get_request_id

REDACTED_VALUE = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "session_id",
    "token",
    "secret",
    "api_key",
    "apikey",
    "database_url",
    "dsn",
    "password",
    "passwd",
    "service_role",
    "supabase_service_role_key",
    "openai_api_key",
    "paddle_api_key",
    "resend_api_key",
)
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)\b(bearer)(\s+)([A-Za-z0-9._~+/=-]+)"),
    re.compile(
        r"(?i)\b(authorization|cookie|x-api-key|session_id|database_url|supabase_service_role_key|openai_api_key|paddle_api_key|resend_api_key)\b([^\S\r\n]*[:=][^\S\r\n]*)([^\s,;]+)"
    ),
    re.compile(r"(?i)\b(postgresql(?:\+psycopg)?://)([^:\s/@]+):([^@\s]+)@"),
    re.compile(r"(?i)\b(rediss?://)([^:\s/@]+):([^@\s]+)@"),
)
JWT_TEXT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?![A-Za-z0-9_-])"
)


def _normalize_sensitive_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(key or "").strip().lower())


def is_sensitive_key(key: object) -> bool:
    normalized = _normalize_sensitive_key(key)
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def redact_sensitive_text(value: str | None) -> str | None:
    if value is None:
        return None

    redacted = value
    for pattern in SENSITIVE_TEXT_PATTERNS:
        if pattern.pattern.startswith("(?i)\\b(bearer)"):
            redacted = pattern.sub(r"\1\2" + REDACTED_VALUE, redacted)
        elif "postgresql" in pattern.pattern or "rediss" in pattern.pattern:
            redacted = pattern.sub(r"\1\2:" + REDACTED_VALUE + "@", redacted)
        else:
            redacted = pattern.sub(r"\1\2" + REDACTED_VALUE, redacted)
    return JWT_TEXT_PATTERN.sub(REDACTED_VALUE, redacted)


def scrub_sensitive_data(value: object, *, key: object | None = None) -> object:
    if key is not None and is_sensitive_key(key):
        return REDACTED_VALUE

    if isinstance(value, str):
        return redact_sensitive_text(value) or ""

    if isinstance(value, Mapping):
        return {
            str(item_key): scrub_sensitive_data(item_value, key=item_key)
            for item_key, item_value in value.items()
        }

    if isinstance(value, tuple):
        return tuple(scrub_sensitive_data(item) for item in value)

    if isinstance(value, list):
        return [scrub_sensitive_data(item) for item in value]

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return type(value)(scrub_sensitive_data(item) for item in value)

    return value


def scrub_sentry_event(event: dict[str, object], _hint: object | None = None) -> dict[str, object]:
    return scrub_sensitive_data(event)  # type: ignore[return-value]


def public_error_message(status_code: int) -> str:
    if status_code == 400:
        return "Invalid request."
    if status_code == 401:
        return "Authentication failed."
    if status_code == 403:
        return "You do not have access to this resource."
    if status_code == 404:
        return "Not found."
    if status_code == 409:
        return "Request conflict."
    if status_code == 413:
        return "Uploaded content is too large."
    if status_code == 422:
        return "Invalid request."
    if status_code == 429:
        return "Too many requests. Please try again later."
    if status_code >= 500:
        return "Something went wrong. Please try again."
    return "Request could not be completed."


def request_log_context(request: Request, **extra: object) -> dict[str, object]:
    context: dict[str, object] = {
        "request_id": get_request_id(),
        "method": request.method,
        "path": redact_sensitive_text(request.url.path),
    }
    context.update(
        {
            key: scrub_sensitive_data(value, key=key)
            for key, value in extra.items()
            if value is not None
        }
    )
    return context


def sanitize_validation_errors(errors: list[dict[str, object]]) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for error in errors:
        sanitized.append(
            {
                key: scrub_sensitive_data(value, key=key)
                for key, value in error.items()
                if key != "input"
            }
        )
    return sanitized
