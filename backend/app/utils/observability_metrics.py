"""Cheap request/task-scoped counters for latency and cost diagnostics."""

from __future__ import annotations

import contextvars
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class OperationMetrics:
    db_query_count: int = 0
    db_query_time_ms: float = 0.0
    redis_lookup_count: int = 0
    redis_hit_count: int = 0
    storage_operation_count: int = 0
    storage_bytes_read: int = 0
    storage_bytes_written: int = 0
    llm_client_creation_count: int = 0
    auth_db_lookup_count: int = 0
    auth_db_lookup_time_ms: float = 0.0


_operation_metrics: contextvars.ContextVar[OperationMetrics | None] = contextvars.ContextVar(
    "operation_metrics", default=None
)


def begin_operation_metrics() -> contextvars.Token[OperationMetrics | None]:
    return _operation_metrics.set(OperationMetrics())


def finish_operation_metrics(
    token: contextvars.Token[OperationMetrics | None],
) -> dict[str, Any]:
    metrics = _operation_metrics.get()
    _operation_metrics.reset(token)
    if metrics is None:
        return {}
    payload = asdict(metrics)
    lookups = metrics.redis_lookup_count
    payload["redis_hit_rate"] = round(metrics.redis_hit_count / lookups, 4) if lookups else None
    payload["db_query_time_ms"] = round(metrics.db_query_time_ms, 2)
    payload["auth_db_lookup_time_ms"] = round(metrics.auth_db_lookup_time_ms, 2)
    return payload


def _current() -> OperationMetrics | None:
    return _operation_metrics.get()


def record_db_query(duration_ms: float) -> None:
    if metrics := _current():
        metrics.db_query_count += 1
        metrics.db_query_time_ms += max(float(duration_ms), 0.0)


def record_redis_lookup(*, hit: bool) -> None:
    if metrics := _current():
        metrics.redis_lookup_count += 1
        metrics.redis_hit_count += int(hit)


def record_storage_operation(*, bytes_read: int = 0, bytes_written: int = 0) -> None:
    if metrics := _current():
        metrics.storage_operation_count += 1
        metrics.storage_bytes_read += max(int(bytes_read), 0)
        metrics.storage_bytes_written += max(int(bytes_written), 0)


def record_llm_client_creation() -> None:
    if metrics := _current():
        metrics.llm_client_creation_count += 1


def record_auth_db_lookup(duration_ms: float) -> None:
    if metrics := _current():
        metrics.auth_db_lookup_count += 1
        metrics.auth_db_lookup_time_ms += max(float(duration_ms), 0.0)
