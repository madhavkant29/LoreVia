"""Database utility helpers for transient read-query failures."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, TypeVar

from sqlalchemy.engine import Result
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

logger = logging.getLogger(__name__)
ReadResult = TypeVar("ReadResult")


TRANSIENT_READ_DB_ERROR_MARKERS = (
    "ssl syscall error: eof detected",
    "consuming input failed",
    "server closed the connection unexpectedly",
    "connection reset by peer",
    "connection is closed",
    "connection not open",
    "could not receive data from server",
    "could not send data to server",
)


def is_retryable_read_db_error(exc: BaseException) -> bool:
    if not isinstance(exc, DBAPIError):
        return False
    if getattr(exc, "connection_invalidated", False):
        return True
    message = " ".join(
        str(part).lower()
        for part in (getattr(exc, "orig", None), exc)
        if part is not None
    )
    return any(marker in message for marker in TRANSIENT_READ_DB_ERROR_MARKERS)


async def execute_read_with_retry(
    db: AsyncSession,
    statement: Executable,
    *,
    attempts: int = 2,
    retry_delay_seconds: float = 0.05,
) -> Result[Any]:
    return await run_read_with_retry(
        db,
        lambda: db.execute(statement),
        attempts=attempts,
        retry_delay_seconds=retry_delay_seconds,
    )


async def run_read_with_retry(
    db: AsyncSession,
    operation: Callable[[], Awaitable[ReadResult]],
    *,
    attempts: int = 2,
    retry_delay_seconds: float = 0.05,
) -> ReadResult:
    max_attempts = max(1, attempts)
    for attempt_index in range(max_attempts):
        try:
            return await operation()
        except DBAPIError as exc:
            is_last_attempt = attempt_index >= max_attempts - 1
            if is_last_attempt or not is_retryable_read_db_error(exc):
                raise
            logger.warning(
                "Retrying read-only database query after transient disconnect",
                extra={"attempt": attempt_index + 1, "max_attempts": max_attempts},
            )
            with suppress(Exception):
                await db.rollback()
            if retry_delay_seconds > 0:
                await asyncio.sleep(retry_delay_seconds)

    raise RuntimeError("Read query retry loop exited without returning or raising")
