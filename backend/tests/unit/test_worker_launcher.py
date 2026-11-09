from importlib import import_module

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.workers.celery_app import celery_app
from app.workers.worker_launcher import WORKER_ROLES, main, worker_arguments


def test_worker_arguments_use_role_specific_config(monkeypatch):
    monkeypatch.setattr(settings, "EXTRACTION_WORKER_CONCURRENCY", 3)
    arguments = worker_arguments("extraction")
    assert arguments[-1] == "3"
    assert "extraction,extraction_priority" in arguments


def test_maintenance_worker_consumes_only_the_maintenance_queue(monkeypatch):
    monkeypatch.setattr(settings, "MAINTENANCE_WORKER_CONCURRENCY", 1)

    arguments = worker_arguments("maintenance")

    assert arguments[-1] == "1"
    assert arguments[arguments.index("--queues") + 1] == "maintenance"


def test_worker_arguments_reject_unknown_role():
    with pytest.raises(ValueError, match="Unknown worker role"):
        worker_arguments("unknown")


def test_worker_arguments_reject_zero_concurrency(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_WORKER_CONCURRENCY", 0)
    with pytest.raises(ValueError, match="must be at least 1"):
        worker_arguments("embedding")


def test_settings_reject_invalid_worker_concurrency():
    with pytest.raises(ValidationError, match="EXTRACTION_WORKER_CONCURRENCY"):
        Settings(EXTRACTION_WORKER_CONCURRENCY=0)


@pytest.mark.parametrize(
    ("role_name", "expected_modules"),
    [
        ("extraction", ("app.workers.tasks.extraction_tasks",)),
        ("analysis", ("app.workers.tasks.analysis_tasks",)),
        ("embedding", ("app.workers.tasks.embedding_tasks",)),
        (
            "intelligence",
            (
                "app.workers.tasks.intelligence_tasks",
                "app.workers.tasks.voice_chapter_tasks",
                "app.workers.tasks.maintenance_tasks",
            ),
        ),
        (
            "maintenance",
            ("app.workers.tasks.maintenance_tasks", "app.workers.tasks.export_tasks"),
        ),
    ],
)
def test_worker_role_imports_only_tasks_for_its_queues(role_name, expected_modules):
    assert WORKER_ROLES[role_name].task_modules == expected_modules


def test_beat_imports_only_scheduled_maintenance_tasks():
    assert list(celery_app.conf.include) == ["app.workers.tasks.maintenance_tasks"]
    import_module("app.workers.tasks.maintenance_tasks")
    assert {entry["task"] for entry in celery_app.conf.beat_schedule.values()} <= set(
        celery_app.tasks
    )


def test_intelligence_worker_registers_processing_recovery_task():
    for module_name in WORKER_ROLES["intelligence"].task_modules:
        import_module(module_name)
    assert "maintenance_tasks.repair_processing_books" in celery_app.tasks


def test_worker_main_sets_role_modules_before_starting_worker(monkeypatch):
    observed = {}
    monkeypatch.setattr(celery_app.conf, "include", celery_app.conf.include)

    def capture_worker_main(arguments):
        observed["arguments"] = arguments
        observed["modules"] = celery_app.conf.include

    monkeypatch.setattr(celery_app, "worker_main", capture_worker_main)
    main(["intelligence"])

    assert observed["modules"] == WORKER_ROLES["intelligence"].task_modules
    assert observed["arguments"][observed["arguments"].index("--queues") + 1] == "intelligence"
