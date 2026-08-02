from __future__ import annotations

import contextvars
import uuid

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_request_user_id: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "request_user_id", default=None
)


def set_request_id(request_id: str | None) -> None:
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_user_id(user_id: uuid.UUID | None) -> None:
    _request_user_id.set(user_id)


def get_request_user_id() -> uuid.UUID | None:
    return _request_user_id.get()
