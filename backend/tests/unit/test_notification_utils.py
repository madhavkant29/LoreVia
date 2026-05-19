import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.utils.notification_utils import BookReadyStats, build_book_ready_notification, build_revision_digest_notification


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


def test_build_book_ready_notification_stays_honest_while_analysis_is_pending():
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Metamorphosis", writer_workspace={})
    stats = BookReadyStats(
        character_count=3,
        relationship_count=1,
        plot_thread_count=0,
        continuity_issue_count=0,
        chapter_count=12,
        analyzed_chapter_count=4,
    )

    notification = build_book_ready_notification(book, stats)

    assert notification.title == "Metamorphosis finished processing"
    assert "saved 3 characters and 1 relationship" in notification.body
    assert "analysis is still running" in notification.body
    assert notification.data["analysis_complete"] is False
    assert notification.data["character_count"] == 3
    assert notification.data["relationship_count"] == 1
    assert "plot_thread_count" not in notification.data
    assert "continuity_issue_count" not in notification.data


def test_build_book_ready_notification_reports_final_stats_once_analysis_finishes():
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Metamorphosis", writer_workspace={})
    stats = BookReadyStats(
        character_count=7,
        relationship_count=4,
        plot_thread_count=5,
        continuity_issue_count=2,
        chapter_count=12,
        analyzed_chapter_count=12,
    )

    notification = build_book_ready_notification(book, stats)

    assert notification.title == "Metamorphosis is ready"
    assert notification.body == (
        "We found 7 characters, mapped 4 relationships, identified 5 plot threads, and flagged 2 continuity issues."
    )
    assert notification.data["analysis_complete"] is True
    assert notification.data["plot_thread_count"] == 5
    assert notification.data["continuity_issue_count"] == 2


def test_build_book_ready_notification_surfaces_character_extraction_failure():
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Metamorphosis",
        writer_workspace={
            "processing": {
                "parser_diagnostics": {
                    "character_extraction": {
                        "failed_batches": 2,
                    }
                }
            }
        },
    )
    stats = BookReadyStats(
        character_count=0,
        relationship_count=0,
        plot_thread_count=0,
        continuity_issue_count=0,
        chapter_count=12,
        analyzed_chapter_count=4,
    )

    notification = build_book_ready_notification(book, stats)

    assert "character extraction hit an internal issue" in notification.body


def test_build_book_ready_notification_marks_partial_analysis_failure():
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Metamorphosis",
        writer_workspace={
            "processing": {
                "pipeline": {
                    "analysis": {"status": "failed", "failed_chapters": [3, 5]},
                }
            }
        },
    )
    stats = BookReadyStats(
        character_count=3,
        relationship_count=1,
        plot_thread_count=0,
        continuity_issue_count=0,
        chapter_count=8,
        analyzed_chapter_count=4,
    )

    notification = build_book_ready_notification(book, stats)

    assert "analysis pipeline failed" in notification.body
    assert notification.data["analysis_status"] == "failed"
    assert notification.data["retry_actions"] == ["retry_analysis"]
