from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.advisor_suggestion_jobs_service import ADVISOR_SUGGESTION_HARD_LIMIT
from app.utils.billing_utils import PRIORITY_QUEUE_NAMES
from app.utils.queue_utils import queue_for_user
from app.workers.celery_app import celery_app
from app.workers.queues.queues import TASK_QUEUES
from app.workers.tasks.intelligence_tasks import generate_advisor_suggestions_task


def test_architect_user_routes_to_priority_queue(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    user = SimpleNamespace(tier="architect", created_at=datetime.now(UTC) - timedelta(days=20))

    assert queue_for_user(user, "extraction") == "extraction_priority"
    assert queue_for_user(user, "analysis") == "analysis_priority"


def test_priority_queues_in_worker_q_flag():
    queue_names = {queue.name for queue in TASK_QUEUES}

    assert "extraction_priority" in queue_names
    assert "analysis_priority" in queue_names

    priority_queue_names = set(PRIORITY_QUEUE_NAMES)
    assert priority_queue_names <= queue_names, (
        "Every priority queue in PRIORITY_QUEUE_NAMES must be registered in TASK_QUEUES. "
        "Missing: " + ", ".join(sorted(priority_queue_names - queue_names))
    )


def test_maintenance_tasks_route_to_a_dedicated_registered_queue():
    queue_names = {queue.name for queue in TASK_QUEUES}

    assert "maintenance" in queue_names
    assert celery_app.conf.task_routes["maintenance_tasks.*"] == {"queue": "maintenance"}


def test_export_tasks_route_to_the_registered_maintenance_queue():
    queue_names = {queue.name for queue in TASK_QUEUES}

    assert "maintenance" in queue_names
    assert celery_app.conf.task_routes["export_tasks.*"] == {"queue": "maintenance"}


def test_export_cleanup_and_public_asset_backfill_are_scheduled():
    scheduled_tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}

    assert "maintenance_tasks.cleanup_expired_manuscript_exports" in scheduled_tasks
    assert "maintenance_tasks.backfill_public_assets" in scheduled_tasks


def test_advisor_suggestions_scan_has_longer_effective_limit_than_interactive_tasks():
    """Multi-group audits must not inherit the one-minute intelligence limit."""
    assert generate_advisor_suggestions_task.soft_time_limit == 15 * 60
    assert generate_advisor_suggestions_task.time_limit == 20 * 60
    assert (
        generate_advisor_suggestions_task.time_limit
        == ADVISOR_SUGGESTION_HARD_LIMIT.total_seconds()
    )
    assert celery_app.conf.task_annotations["intelligence_tasks.*"]["soft_time_limit"] == 60
