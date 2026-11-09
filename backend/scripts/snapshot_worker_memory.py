"""Print read-only cgroup and process memory metrics from a Linux worker container."""

from __future__ import annotations

import json
import os
from pathlib import Path

if __name__ == "__main__":
    cgroup = Path("/sys/fs/cgroup")
    memory_stat = cgroup / "memory.stat"
    stat = dict(line.split() for line in memory_stat.read_text().splitlines())
    totals = {name: 0 for name in ("Rss", "Pss", "Private_Clean", "Private_Dirty")}
    readable_processes = 0
    for rollup in Path("/proc").glob("[0-9]*/smaps_rollup"):
        if rollup.parent.name == str(os.getpid()):
            continue
        try:
            lines = rollup.read_text().splitlines()
        except OSError:
            continue
        readable_processes += 1
        for line in lines:
            name, _, value = line.partition(":")
            if name in totals:
                totals[name] += int(value.split()[0]) * 1024
    metrics = {
        "cgroup_current_mib": round(int((cgroup / "memory.current").read_text()) / 1048576, 1),
        "cgroup_anon_mib": round(int(stat["anon"]) / 1048576, 1),
        "cgroup_file_mib": round(int(stat["file"]) / 1048576, 1),
        "processes_with_smaps": readable_processes,
    }
    metrics.update(
        {f"process_{name.lower()}_mib": round(value / 1048576, 1) for name, value in totals.items()}
    )
    print(json.dumps(metrics, sort_keys=True))
