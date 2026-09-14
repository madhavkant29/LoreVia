from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta

from scripts import analyze_auth_latency


def _request(
    path: str,
    *,
    auth_ms: float,
    duration_ms: float,
    ts: str = "2026-09-01T12:00:00+00:00",
) -> dict:
    return {
        "message": "request_complete",
        "method": "GET",
        "path": path,
        "status_code": 200,
        "auth_db_lookup_count": 1,
        "auth_db_lookup_time_ms": auth_ms,
        "duration_ms": duration_ms,
        "ts": ts,
    }


def test_auth_latency_report_normalizes_routes_and_applies_measurement_gate():
    records = [
        _request(
            f"/api/v1/books/123e4567-e89b-42d3-a456-426614174000/chapters/{index}",
            auth_ms=60,
            duration_ms=200,
            ts=(
                datetime(2026, 9, 1, tzinfo=UTC) + timedelta(days=(index - 1) % 7)
            ).isoformat(),
        )
        for index in range(1, 101)
    ]

    report = analyze_auth_latency.analyze_records(records)

    assert report["eligible_samples"] == 100
    assert report["measurement_candidates"] == ["/api/v1/books/{id}/chapters/{id}"]
    assert report["routes"][0]["auth_db_lookup_ms"]["p95"] == 60
    assert report["routes"][0]["auth_share_of_request_p95"] == 0.3
    assert report["routes"][0]["observed_days"] == 7


def test_auth_latency_report_excludes_sensitive_and_non_authenticated_reads():
    records = [
        _request("/api/v1/admin/session", auth_ms=100, duration_ms=200),
        _request("/api/v1/billing/subscription", auth_ms=100, duration_ms=200),
        {
            **_request("/api/v1/books/page", auth_ms=0, duration_ms=20),
            "auth_db_lookup_count": 0,
        },
    ]

    report = analyze_auth_latency.analyze_records(records, minimum_samples=1)

    assert report["eligible_samples"] == 0
    assert report["rejected_records"] == 3
    assert report["routes"] == []


def test_auth_latency_cli_ignores_non_json_lines(monkeypatch, capsys):
    stream = io.StringIO(
        "not json\n"
        + json.dumps(_request("/api/v1/books/page", auth_ms=10, duration_ms=100))
        + "\n"
    )
    monkeypatch.setattr(analyze_auth_latency.sys, "stdin", stream)

    assert (
        analyze_auth_latency.main(
            ["-", "--minimum-samples", "1", "--minimum-days", "1"]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["eligible_samples"] == 1
    assert report["measurement_candidates"] == []
