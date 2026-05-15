import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.utils.notification_utils import build_revision_digest_notification


def test_build_revision_digest_notification_includes_revision_summary():
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Sky of Ash")
    payload = {
        "tagline": "Know what your edit breaks before your readers do.",
        "summary": {
            "hero_message": "2 downstream logic risks need attention first.",
            "active_item_count": 5,
            "high_severity_count": 2,
            "task_ready_count": 4,
            "recent_edit_label": "You changed Chapter 2: removed silver gate.",
        },
        "change_impacts": [
            {
                "id": "impact-1",
                "title": "Chapter 2 assumption may break later payoff",
            }
        ],
    }

    notification = build_revision_digest_notification(book, payload)

    assert notification is not None
    assert notification.kind == "revision_digest"
    assert notification.title == "2 revision risks surfaced in Sky of Ash"
    assert "Top issue: Chapter 2 assumption may break later payoff." in notification.body
    assert notification.data["active_item_count"] == 5
    assert notification.data["high_severity_count"] == 2
    assert notification.data["signature"] == "5:2:You changed Chapter 2: removed silver gate.:impact-1"


def test_build_revision_digest_notification_returns_none_when_no_active_items():
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Sky of Ash", created_at=datetime.now(UTC))
    payload = {
        "summary": {
            "hero_message": "Clear",
            "active_item_count": 0,
            "high_severity_count": 0,
            "task_ready_count": 0,
        },
        "change_impacts": [],
    }

    assert build_revision_digest_notification(book, payload) is None
