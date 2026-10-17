from app.utils.observability_metrics import (
    begin_operation_metrics,
    finish_operation_metrics,
    record_auth_db_lookup,
    record_db_query,
    record_llm_client_creation,
    record_redis_lookup,
    record_storage_operation,
)


def test_operation_metrics_aggregate_latency_cost_and_cache_signals():
    token = begin_operation_metrics()
    record_db_query(4.25)
    record_db_query(1.75)
    record_redis_lookup(hit=True)
    record_redis_lookup(hit=False)
    record_storage_operation(bytes_read=12)
    record_storage_operation(bytes_written=8)
    record_llm_client_creation()
    record_auth_db_lookup(12.345)

    metrics = finish_operation_metrics(token)

    assert metrics == {
        "db_query_count": 2,
        "db_query_time_ms": 6.0,
        "redis_lookup_count": 2,
        "redis_hit_count": 1,
        "storage_operation_count": 2,
        "storage_bytes_read": 12,
        "storage_bytes_written": 8,
        "llm_client_creation_count": 1,
        "auth_db_lookup_count": 1,
        "auth_db_lookup_time_ms": 12.35,
        "redis_hit_rate": 0.5,
    }


def test_operation_metrics_ignore_work_outside_an_active_scope():
    record_db_query(2)
    record_redis_lookup(hit=True)
    record_storage_operation(bytes_read=10)
    record_llm_client_creation()
    record_auth_db_lookup(3)

    token = begin_operation_metrics()
    metrics = finish_operation_metrics(token)

    assert metrics["db_query_count"] == 0
    assert metrics["redis_lookup_count"] == 0
    assert metrics["storage_operation_count"] == 0
    assert metrics["llm_client_creation_count"] == 0
    assert metrics["auth_db_lookup_count"] == 0
    assert metrics["redis_hit_rate"] is None
