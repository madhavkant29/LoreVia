"""Measure fresh-process Celery task-import cost without starting a worker."""

from __future__ import annotations

import argparse
import json
import sys
import time

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=("all", "extraction", "analysis", "embedding", "intelligence", "maintenance"),
    )
    mode = parser.parse_args().mode
    started = time.perf_counter()

    from app.workers.celery_app import celery_app
    from app.workers.worker_launcher import WORKER_ROLES

    modules = (
        tuple(sorted({module for role in WORKER_ROLES.values() for module in role.task_modules}))
        if mode == "all"
        else WORKER_ROLES[mode].task_modules
    )
    celery_app.conf.include = modules
    celery_app.loader.import_default_modules()
    registered = sorted(name for name in celery_app.tasks if not name.startswith("celery."))
    elapsed = time.perf_counter() - started

    if sys.platform == "win32":
        import ctypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("page_fault_count", ctypes.c_ulong),
                ("peak_working_set_size", ctypes.c_size_t),
                ("working_set_size", ctypes.c_size_t),
                ("other_counters", ctypes.c_size_t * 6),
            ]

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError("GetProcessMemoryInfo failed")
        peak_mib = counters.peak_working_set_size / 1048576
        metric = "peak_working_set_mib"
    else:
        import resource

        peak_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        metric = "peak_rss_mib"

    print(
        json.dumps(
            {
                "mode": mode,
                "modules": modules,
                "registered_task_count": len(registered),
                "startup_seconds": round(elapsed, 3),
                metric: round(peak_mib, 1),
            },
            sort_keys=True,
        )
    )
