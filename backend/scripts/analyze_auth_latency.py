"""Summarize production request logs for the auth-cache decision gate."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

UUID_SEGMENT = re.compile(
    r"(?<=/)[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}(?=/|$)"
)
INTEGER_SEGMENT = re.compile(r"(?<=/)\d+(?=/|$)")
EXCLUDED_PREFIXES = (
    "/health",
    "/api/v1/admin",
    "/api/v1/billing",
)


def normalize_route(path: str) -> str:
    path_only = str(path or "").split("?", 1)[0]
    path_only = UUID_SEGMENT.sub("{id}", path_only)
    return INTEGER_SEGMENT.sub("{id}", path_only)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return round(ordered[index], 2)


def _eligible_request(record: dict[str, Any]) -> bool:
    path = str(record.get("path") or "")
    return bool(
        record.get("message") == "request_complete"
        and str(record.get("method") or "").upper() == "GET"
        and 200 <= int(record.get("status_code") or 0) < 400
        and int(record.get("auth_db_lookup_count") or 0) > 0
        and not path.startswith(EXCLUDED_PREFIXES)
    )


def analyze_records(
    records: Iterable[dict[str, Any]],
    *,
    minimum_samples: int = 100,
    minimum_days: int = 7,
) -> dict[str, Any]:
    groups: dict[str, list[tuple[float, float, str | None]]] = defaultdict(list)
    rejected = 0
    for record in records:
        if not _eligible_request(record):
            rejected += 1
            continue
        route = normalize_route(str(record.get("path") or ""))
        observed_date = None
        try:
            observed_date = (
                datetime.fromisoformat(str(record.get("ts") or "").replace("Z", "+00:00"))
                .date()
                .isoformat()
            )
        except ValueError:
            pass
        groups[route].append(
            (
                max(float(record.get("auth_db_lookup_time_ms") or 0), 0.0),
                max(float(record.get("duration_ms") or 0), 0.0),
                observed_date,
            )
        )

    routes: list[dict[str, Any]] = []
    for route, samples in groups.items():
        auth_values = [sample[0] for sample in samples]
        request_values = [sample[1] for sample in samples]
        observed_days = len({sample[2] for sample in samples if sample[2] is not None})
        auth_p95 = percentile(auth_values, 0.95)
        request_p95 = percentile(request_values, 0.95)
        p95_share = round(auth_p95 / request_p95, 4) if request_p95 > 0 else 0.0
        routes.append(
            {
                "route": route,
                "samples": len(samples),
                "observed_days": observed_days,
                "auth_db_lookup_ms": {
                    "p50": percentile(auth_values, 0.50),
                    "p95": auth_p95,
                    "p99": percentile(auth_values, 0.99),
                },
                "request_duration_p95_ms": request_p95,
                "auth_share_of_request_p95": p95_share,
                "measurement_threshold_met": bool(
                    len(samples) >= minimum_samples
                    and observed_days >= minimum_days
                    and auth_p95 >= 50
                    and p95_share >= 0.20
                ),
            }
        )
    routes.sort(key=lambda item: (-item["samples"], item["route"]))
    return {
        "eligible_samples": sum(item["samples"] for item in routes),
        "rejected_records": rejected,
        "minimum_samples": minimum_samples,
        "minimum_days": minimum_days,
        "routes": routes,
        "measurement_candidates": [
            item["route"] for item in routes if item["measurement_threshold_met"]
        ],
        "note": (
            "A measurement candidate still requires corroborating database-pool evidence "
            "and a tested invalidation design before caching."
        ),
    }


def read_json_lines(streams: Iterable[TextIO]) -> Iterable[dict[str, Any]]:
    for stream in streams:
        for line in stream:
            try:
                value = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(value, dict):
                yield value


def _open_inputs(paths: list[str]) -> tuple[list[TextIO], list[TextIO]]:
    if not paths or paths == ["-"]:
        return [sys.stdin], []
    streams: list[TextIO] = []
    owned: list[TextIO] = []
    for raw_path in paths:
        if raw_path == "-":
            streams.append(sys.stdin)
            continue
        stream = Path(raw_path).open(encoding="utf-8")
        streams.append(stream)
        owned.append(stream)
    return streams, owned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="JSONL log files, or - for stdin")
    parser.add_argument("--minimum-samples", type=int, default=100)
    parser.add_argument("--minimum-days", type=int, default=7)
    args = parser.parse_args(argv)
    streams, owned = _open_inputs(args.paths)
    try:
        report = analyze_records(
            read_json_lines(streams),
            minimum_samples=max(1, int(args.minimum_samples)),
            minimum_days=max(1, int(args.minimum_days)),
        )
    finally:
        for stream in owned:
            stream.close()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
