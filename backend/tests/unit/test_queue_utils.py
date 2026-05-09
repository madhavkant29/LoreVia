from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.utils.queue_utils import queue_for_access_tier, queue_for_user


def test_architect_access_uses_priority_queue():
    assert queue_for_access_tier("extraction", "architect") == "extraction_priority"


def test_author_access_keeps_standard_queue():
    assert queue_for_access_tier("analysis", "author") == "analysis"


def test_queue_for_user_respects_effective_paid_tier(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    user = SimpleNamespace(tier="architect", created_at=datetime.now(UTC) - timedelta(days=20))

    assert queue_for_user(user, "analysis") == "analysis_priority"


def test_trial_author_access_does_not_get_architect_priority(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.settings.DEBUG", False, raising=False)
    user = SimpleNamespace(tier="free", created_at=datetime.now(UTC) - timedelta(days=1))

    assert queue_for_user(user, "extraction") == "extraction"
