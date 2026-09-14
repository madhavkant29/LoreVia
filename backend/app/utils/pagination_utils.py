"""
Shared pagination helpers — limit / offset validation and response
construction for list endpoints.
"""

import base64
import json
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import TypeVar

from fastapi import HTTPException

from app.schemas.common import PaginatedResponse

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 100

T = TypeVar("T")


def encode_datetime_uuid_cursor(timestamp: datetime, row_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"timestamp": timestamp.isoformat(), "id": str(row_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_datetime_uuid_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(f"{cursor}{padding}").decode("utf-8"))
        timestamp = datetime.fromisoformat(str(payload["timestamp"]))
        if timestamp.tzinfo is None:
            raise ValueError("Cursor timestamp must include a timezone")
        return timestamp, uuid.UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid cursor") from exc


def build_paginated_response[T](
    items: Sequence[T],
    total: int,
    limit: int,
    offset: int,
) -> PaginatedResponse[T]:
    return PaginatedResponse(
        items=list(items),
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


async def validate_pagination(limit: int, offset: int) -> None:
    if limit < 1:
        raise HTTPException(400, "limit must be >= 1")
    if limit > _MAX_LIMIT:
        raise HTTPException(400, f"limit must be <= {_MAX_LIMIT}")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
