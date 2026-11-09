"""Ping only this container's Celery worker without importing application tasks."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

from celery import Celery

from app.utils.celery_broker_utils import normalize_celery_redis_url

WORKER_ROLES = frozenset({"extraction", "analysis", "embedding", "intelligence", "maintenance"})
PING_TIMEOUT_SECONDS = 5.0


def healthcheck_broker_settings(environ: Mapping[str, str]) -> tuple[str, dict]:
    source = (environ.get("CELERY_BROKER_URL") or "").strip() or (
        environ.get("REDIS_URL") or ""
    ).strip()
    if not source:
        raise ValueError("CELERY_BROKER_URL or REDIS_URL is required")
    return normalize_celery_redis_url(source)


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    if len(arguments) != 1 or arguments[0] not in WORKER_ROLES:
        print("Usage: python -m app.workers.healthcheck <worker-role>", file=sys.stderr)
        return 2

    hostname = os.environ.get("HOSTNAME", "").strip()
    if not hostname:
        print("Celery health check requires HOSTNAME", file=sys.stderr)
        return 2

    destination = f"worker-{arguments[0]}@{hostname}"
    try:
        broker_url, broker_ssl_options = healthcheck_broker_settings(os.environ)
        app = Celery("lorevia", broker=broker_url)
        if broker_ssl_options:
            app.conf.broker_use_ssl = broker_ssl_options
        reply = app.control.inspect(destination=[destination], timeout=PING_TIMEOUT_SECONDS).ping()
    except Exception as exc:
        print(f"Celery health ping failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    worker_reply = reply.get(destination) if isinstance(reply, dict) else None
    if isinstance(worker_reply, dict) and worker_reply.get("ok") == "pong":
        return 0
    print(f"Celery worker did not respond: {destination}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
