from __future__ import annotations

from fastapi import Request

from app.utils.request_context import get_request_id


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
        "path": request.url.path,
    }
    context.update({key: value for key, value in extra.items() if value is not None})
    return context


def sanitize_validation_errors(errors: list[dict[str, object]]) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for error in errors:
        sanitized.append({key: value for key, value in error.items() if key != "input"})
    return sanitized
