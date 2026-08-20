from __future__ import annotations

from fastapi import HTTPException, Request

PADDLE_WEBHOOK_MAX_BODY_BYTES = 1024 * 1024


async def read_paddle_webhook_body(request: Request) -> bytes:
    """Read a Paddle webhook body without accepting more than one MiB."""

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = None
        if declared_size is not None and declared_size > PADDLE_WEBHOOK_MAX_BODY_BYTES:
            raise HTTPException(413, "Paddle webhook payload exceeds 1 MiB.")

    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > PADDLE_WEBHOOK_MAX_BODY_BYTES:
            raise HTTPException(413, "Paddle webhook payload exceeds 1 MiB.")
    return bytes(payload)
