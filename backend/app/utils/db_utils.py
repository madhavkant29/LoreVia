"""Database utility helpers for transient read-query failures."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from sqlalchemy.engine import Result
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

from app.utils.retry_utils import NON_LLM_MAX_RETRIES

logger = logging.getLogger(__name__)
READ_RETRY_MAX_DELAY_SECONDS = 1.0
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
TRANSIENT_TRANSACTION_SQLSTATES = frozenset({"40001", "40P01", "55P03"})
TRANSIENT_TRANSACTION_ERROR_MARKERS = (
    "deadlock detected",
    "could not serialize access",
    "lock not available",
)


def is_retryable_read_db_error(exc: BaseException) -> bool:
    if not isinstance(exc, DBAPIError):
        return False
    if getattr(exc, "connection_invalidated", False):
        return True
    message = " ".join(
        str(part).lower() for part in (getattr(exc, "orig", None), exc) if part is not None
    )
    return any(marker in message for marker in TRANSIENT_READ_DB_ERROR_MARKERS)


def is_retryable_transaction_db_error(exc: BaseException) -> bool:
    """Return whether PostgreSQL aborted a transaction for a transient lock conflict."""
    if not isinstance(exc, DBAPIError):
        return False
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate in TRANSIENT_TRANSACTION_SQLSTATES:
        return True
    message = " ".join(str(part).lower() for part in (orig, exc) if part is not None)
    return any(marker in message for marker in TRANSIENT_TRANSACTION_ERROR_MARKERS)


async def execute_read_with_retry(
    db: AsyncSession,
    statement: Executable,
    *,
    attempts: int = NON_LLM_MAX_RETRIES + 1,
    retry_delay_seconds: float = 0.05,
) -> Result[Any]:
    return await run_read_with_retry(
        db,
        lambda: db.execute(statement),
        attempts=attempts,
        retry_delay_seconds=retry_delay_seconds,
    )


async def run_read_with_retry[ReadResult](
    db: AsyncSession,
    operation: Callable[[], Awaitable[ReadResult]],
    *,
    attempts: int = NON_LLM_MAX_RETRIES + 1,
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
                delay = min(
                    READ_RETRY_MAX_DELAY_SECONDS,
                    retry_delay_seconds * (2**attempt_index),
                )
                await asyncio.sleep(delay)

    raise RuntimeError("Read query retry loop exited without returning or raising")
