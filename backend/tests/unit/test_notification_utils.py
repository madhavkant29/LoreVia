import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.utils.notification_utils import (
    BookReadyStats,
    _book_ready_diagnostic_totals,
    build_book_ready_notification,
    build_revision_digest_notification,
    collect_book_ready_stats,
)


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
                "severity": "high",
                "status": "pending",
            }
        ],
    }

    notification = build_revision_digest_notification(book, payload)

    assert notification is not None
    assert notification.kind == "revision_digest"
    assert notification.title == "2 revision risks surfaced in Sky of Ash"
    assert notification.body == "LoreVia found 5 active revision items, including 2 high-severity risks."
    assert notification.data["active_item_count"] == 5
    assert notification.data["high_severity_count"] == 2
    assert notification.data["top_item_title"] == "Chapter 2 assumption may break later payoff"
    assert notification.data["signature"] == "5:2:You changed Chapter 2: removed silver gate.:impact-1"


def test_build_revision_digest_notification_prefers_active_high_severity_top_issue():
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="First Empty")
    payload = {
        "summary": {
            "hero_message": "1 downstream logic risk need attention first.",
            "active_item_count": 3,
            "high_severity_count": 1,
            "task_ready_count": 3,
            "recent_edit_label": "You changed Chapter 2.",
        },
        "change_impacts": [
            {
                "id": "impact-generic",
                "title": "Chapter 2",
                "severity": "medium",
                "status": "pending",
            },
            {
                "id": "impact-fixed",
                "title": "Fixed high severity issue",
                "severity": "high",
                "status": "fixed",
            },
        ],
        "scene_advice": [
            {
                "id": "scene-1",
                "title": "Gate rule contradiction",
                "severity": "high",
                "status": "pending",
            }
        ],
    }

    notification = build_revision_digest_notification(book, payload)

    assert notification is not None
    assert notification.body == "LoreVia found 3 active revision items, including 1 high-severity risk."
    assert notification.data["recent_edit_label"] == "You changed Chapter 2."
    assert notification.data["top_item_title"] == "Gate rule contradiction"


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


@pytest.mark.parametrize(
    ("writer_workspace", "expected"),
    [
        (
            {
                "processing": {
                    "parser_diagnostics": {
                        "character_extraction": {
                            "totals": {
                                "saved_characters": 4,
                                "relationships_persisted": 2,
                            }
                        }
                    }
                }
            },
            (4, 2),
        ),
        ({}, (0, 0)),
        ({"processing": {"parser_diagnostics": {"character_extraction": {}}}}, (0, 0)),
    ],
)
def test_book_ready_diagnostic_totals_reads_extraction_totals(writer_workspace, expected):
    book = SimpleNamespace(writer_workspace=writer_workspace)
    assert _book_ready_diagnostic_totals(book) == expected


@pytest.mark.asyncio
async def test_collect_book_ready_stats_ignores_empty_chapters(db):
    from app.models.book import Book, Chapter
    from app.models.intelligence import ChapterSummary
    from app.models.user import User

    user = User(email="ready-empty@lorevia.app", username="readyempty", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Ready Draft", format="txt", s3_key="ready.txt", status="processing")
    db.add(book)
    await db.flush()
    populated = Chapter(book_id=book.id, number=1, s3_key="chapter-1.txt", word_count=10)
    empty = Chapter(book_id=book.id, number=2, s3_key="chapter-2.txt", word_count=0)
    db.add_all([populated, empty])
    await db.flush()
    db.add(ChapterSummary(chapter_id=populated.id, mode="detailed", content="summary"))
    await db.commit()

    stats = await collect_book_ready_stats(db, book)

    assert stats.chapter_count == 1
    assert stats.analyzed_chapter_count == 1
    assert stats.analysis_complete is True
