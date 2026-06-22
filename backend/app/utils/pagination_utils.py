"""
Shared pagination helpers — limit / offset validation and response
construction for list endpoints.
"""

from collections.abc import Sequence
from typing import TypeVar

from fastapi import HTTPException

from app.schemas.common import PaginatedResponse

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 100

T = TypeVar("T")


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
