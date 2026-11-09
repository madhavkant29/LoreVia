from __future__ import annotations

import sys
from dataclasses import dataclass

from app.core.config import settings
from app.workers.celery_app import celery_app


@dataclass(frozen=True)
class WorkerRole:
    queues: str
    concurrency_setting: str
    task_modules: tuple[str, ...]


WORKER_ROLES = {
    "extraction": WorkerRole(
        "extraction,extraction_priority",
        "EXTRACTION_WORKER_CONCURRENCY",
        ("app.workers.tasks.extraction_tasks",),
    ),
    "analysis": WorkerRole(
        "analysis,analysis_priority",
        "ANALYSIS_WORKER_CONCURRENCY",
        ("app.workers.tasks.analysis_tasks",),
    ),
    "embedding": WorkerRole(
        "embedding", "EMBEDDING_WORKER_CONCURRENCY", ("app.workers.tasks.embedding_tasks",)
    ),
    "intelligence": WorkerRole(
        "intelligence",
        "INTELLIGENCE_WORKER_CONCURRENCY",
        (
            "app.workers.tasks.intelligence_tasks",
            "app.workers.tasks.voice_chapter_tasks",
            # pipeline_state_service dispatches repair_processing_books here.
            "app.workers.tasks.maintenance_tasks",
        ),
    ),
    "maintenance": WorkerRole(
        "maintenance",
        "MAINTENANCE_WORKER_CONCURRENCY",
        ("app.workers.tasks.maintenance_tasks", "app.workers.tasks.export_tasks"),
    ),
}


def worker_arguments(role_name: str) -> list[str]:
    role = WORKER_ROLES.get(role_name)
    if role is None:
        raise ValueError(f"Unknown worker role: {role_name}")
    concurrency = int(getattr(settings, role.concurrency_setting))
    if concurrency < 1:
        raise ValueError(f"{role.concurrency_setting} must be at least 1")
    return [
        "worker",
        "--hostname",
        f"worker-{role_name}@%h",
        "--queues",
        role.queues,
        "--loglevel",
        "info",
        "--concurrency",
        str(concurrency),
    ]


def main(argv: list[str] | None = None) -> None:
    arguments = list(argv if argv is not None else sys.argv[1:])
    if len(arguments) != 1:
        raise SystemExit("Usage: python -m app.workers.worker_launcher <worker-role>")
    try:
        worker_args = worker_arguments(arguments[0])
        celery_app.conf.include = WORKER_ROLES[arguments[0]].task_modules
        celery_app.worker_main(worker_args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
