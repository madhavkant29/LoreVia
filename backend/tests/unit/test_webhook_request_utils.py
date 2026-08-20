from __future__ import annotations

import pytest
from fastapi import HTTPException, Request

from app.utils.webhook_request_utils import (
    PADDLE_WEBHOOK_MAX_BODY_BYTES,
    read_paddle_webhook_body,
)


def _request(chunks: list[bytes], *, content_length: str | None = None) -> Request:
    messages = [
        {
            "type": "http.request",
            "body": chunk,
            "more_body": index < len(chunks) - 1,
        }
        for index, chunk in enumerate(chunks)
    ]

    async def receive():
        if messages:
            return messages.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    headers = []
    if content_length is not None:
        headers.append((b"content-length", content_length.encode("ascii")))
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers}, receive)


@pytest.mark.asyncio
async def test_read_paddle_webhook_body_accepts_exact_limit_and_preserves_bytes():
    first = b"a" * (PADDLE_WEBHOOK_MAX_BODY_BYTES // 2)
    second = b"b" * (PADDLE_WEBHOOK_MAX_BODY_BYTES - len(first))

    payload = await read_paddle_webhook_body(_request([first, second]))

    assert payload == first + second


@pytest.mark.asyncio
async def test_read_paddle_webhook_body_rejects_oversized_stream():
    request = _request([b"a" * PADDLE_WEBHOOK_MAX_BODY_BYTES, b"b"])

    with pytest.raises(HTTPException) as exc_info:
        await read_paddle_webhook_body(request)

    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_read_paddle_webhook_body_rejects_oversized_content_length_before_reading():
    request = _request([], content_length=str(PADDLE_WEBHOOK_MAX_BODY_BYTES + 1))

    with pytest.raises(HTTPException) as exc_info:
        await read_paddle_webhook_body(request)

    assert exc_info.value.status_code == 413
