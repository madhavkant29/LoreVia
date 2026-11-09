"""Compare legacy and minimal worker pings inside a Linux worker container."""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("legacy", "light"))
    parser.add_argument(
        "role", choices=("extraction", "analysis", "embedding", "intelligence", "maintenance")
    )
    args = parser.parse_args()

    hostname = os.environ.get("HOSTNAME", "").strip()
    if not hostname:
        parser.error("HOSTNAME is required")
    destination = f"worker-{args.role}@{hostname}"
    command = (
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.workers.celery_app",
            "inspect",
            "ping",
            "-d",
            destination,
            "--timeout=5",
        ]
        if args.mode == "legacy"
        else [sys.executable, "-m", "app.workers.healthcheck", args.role]
    )

    memory_current = Path("/sys/fs/cgroup/memory.current")
    baseline = int(memory_current.read_text()) if memory_current.exists() else 0
    cgroup_peak = baseline
    started = time.perf_counter()
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while process.poll() is None:
        if memory_current.exists():
            cgroup_peak = max(cgroup_peak, int(memory_current.read_text()))
        time.sleep(0.01)
    elapsed = time.perf_counter() - started
    child_peak_mib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    print(
        json.dumps(
            {
                "mode": args.mode,
                "role": args.role,
                "exit": process.returncode,
                "elapsed_seconds": round(elapsed, 3),
                "child_peak_rss_mib": round(child_peak_mib, 1),
                "cgroup_peak_delta_mib": round((cgroup_peak - baseline) / 1048576, 1),
            },
            sort_keys=True,
        )
    )
    raise SystemExit(process.returncode)
