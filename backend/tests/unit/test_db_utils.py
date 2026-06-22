import pytest
from sqlalchemy.exc import OperationalError

from app.utils.db_utils import (
    execute_read_with_retry,
    is_retryable_read_db_error,
    run_read_with_retry,
)


class FakeReadSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.execute_calls = 0
        self.rollback_calls = 0

    async def execute(self, statement):
        self.execute_calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def rollback(self):
        self.rollback_calls += 1


def _operational_error(message: str, *, connection_invalidated: bool = False) -> OperationalError:
    return OperationalError(
        "SELECT 1",
        {},
        RuntimeError(message),
        connection_invalidated=connection_invalidated,
    )


def test_is_retryable_read_db_error_matches_ssl_eof_disconnect():
    error = _operational_error("consuming input failed: SSL SYSCALL error: EOF detected")

    assert is_retryable_read_db_error(error)


def test_is_retryable_read_db_error_matches_invalidated_connection():
    error = _operational_error("driver disconnected", connection_invalidated=True)

    assert is_retryable_read_db_error(error)


def test_is_retryable_read_db_error_rejects_non_transient_errors():
    error = _operational_error("syntax error at or near FROM")

    assert not is_retryable_read_db_error(error)


@pytest.mark.asyncio
async def test_execute_read_with_retry_retries_transient_disconnect():
    session = FakeReadSession(
        [
            _operational_error("consuming input failed: SSL SYSCALL error: EOF detected"),
            "ok",
        ]
    )

    result = await execute_read_with_retry(
        session,
        "SELECT 1",
        retry_delay_seconds=0,
    )

    assert result == "ok"
    assert session.execute_calls == 2
    assert session.rollback_calls == 1


@pytest.mark.asyncio
async def test_execute_read_with_retry_does_not_retry_non_transient_error():
    error = _operational_error("syntax error at or near FROM")
    session = FakeReadSession([error])

    with pytest.raises(OperationalError):
        await execute_read_with_retry(session, "SELECT broken", retry_delay_seconds=0)

    assert session.execute_calls == 1
    assert session.rollback_calls == 0


@pytest.mark.asyncio
async def test_execute_read_with_retry_raises_after_attempts_are_exhausted():
    session = FakeReadSession(
        [
            _operational_error("connection reset by peer"),
            _operational_error("connection reset by peer"),
        ]
    )

    with pytest.raises(OperationalError):
        await execute_read_with_retry(
            session,
            "SELECT 1",
            attempts=2,
            retry_delay_seconds=0,
        )

    assert session.execute_calls == 2
    assert session.rollback_calls == 1


@pytest.mark.asyncio
async def test_run_read_with_retry_reruns_whole_operation_after_disconnect():
    session = FakeReadSession(
        [
            "first-query-result",
            _operational_error("server closed the connection unexpectedly"),
            "first-query-result-after-retry",
            "second-query-result-after-retry",
        ]
    )
    operation_calls = 0

    async def operation():
        nonlocal operation_calls
        operation_calls += 1
        first_result = await session.execute("SELECT first")
        second_result = await session.execute("SELECT second")
        return [first_result, second_result]

    result = await run_read_with_retry(
        session,
        operation,
        retry_delay_seconds=0,
    )

    assert result == ["first-query-result-after-retry", "second-query-result-after-retry"]
    assert operation_calls == 2
    assert session.execute_calls == 4
    assert session.rollback_calls == 1
