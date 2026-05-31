from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.utils.billing_utils import PRIORITY_QUEUE_NAMES
from app.utils.queue_utils import queue_for_user
from app.workers.queues.queues import TASK_QUEUES


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
