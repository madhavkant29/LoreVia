import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import uuid
import pytest

from app.engine.analysis.summariser import derive_summary_modes_from_detailed
from app.models.book import Book
from app.utils.ingestion_utils import (
    apply_chapter_number_strategy,
    build_ingestion_progress_state,
    build_chapter_dispatch_plan,
    extract_queue_wait_ms,
    is_book_hidden,
    is_retryable_processing_error,
    mark_book_processing_cancelled,
    regroup_prose_chapters_for_reading,
    update_book_processing_state,
)


def test_build_chapter_dispatch_plan_staggers_non_eager_chapters():
    plan = build_chapter_dispatch_plan(
        [1, 2, 3, 4, 5],
        eager_limit=1,
        dispatch_window=2,
        dispatch_delay_seconds=3,
    )

    assert [(item.chapter_number, item.countdown) for item in plan] == [
        (1, 0),
        (2, 3),
        (3, 3),
        (4, 6),
        (5, 6),
    ]


def test_extract_queue_wait_ms_ignores_missing_and_invalid_headers():
    assert extract_queue_wait_ms(None) is None
    assert extract_queue_wait_ms({}) is None
    assert extract_queue_wait_ms({"enqueued_at": "nope"}) is None


def test_extract_queue_wait_ms_uses_epoch_seconds():
    now = time.time()
    wait_ms = extract_queue_wait_ms({"enqueued_at": str(now - 1.25)})

    assert wait_ms is not None
    assert 1000 <= wait_ms <= 4000


def test_build_ingestion_progress_state_computes_progress_and_eta():
    started_at = datetime.now(UTC) - timedelta(minutes=4)

    payload = build_ingestion_progress_state(
        status="processing",
        stage="chapter_complete",
        total_chapters=12,
        completed_chapters=3,
        started_at=started_at,
        queue_wait_ms=42,
        chapter_number=4,
        chapter_title="Chapter Four",
    )

    assert payload["status"] == "processing"
    assert payload["stage"] == "chapter_complete"
    assert payload["chapters_completed"] == 3
    assert payload["chapters_total"] == 12
    assert payload["progress_pct"] == 25.0
    assert payload["queue_wait_ms"] == 42
    assert payload["last_chapter_number"] == 4
    assert payload["last_chapter_title"] == "Chapter Four"
    assert payload["eta_seconds"] is not None
    assert payload["started_at"].endswith("+00:00")
    assert payload["updated_at"].endswith("+00:00")


def test_update_book_processing_state_preserves_parser_diagnostics():
    book = Book(
        user_id=uuid.uuid4(),
        title="Diagnostics Story",
        format="pdf",
        s3_key="books/diagnostics.pdf",
    )
    started_at = datetime.now(UTC) - timedelta(minutes=2)
    book.writer_workspace = {
        "processing": build_ingestion_progress_state(
            status="processing",
            stage="parsed",
            total_chapters=3,
            completed_chapters=0,
            started_at=started_at,
            parser_diagnostics={"source": "pdf", "chapter_count": 3},
        )
    }

    workspace = update_book_processing_state(
        book,
        status="processing",
        stage="chapter_complete",
        total_chapters=3,
        completed_chapters=1,
        started_at=started_at,
    )

    assert workspace["processing"]["parser_diagnostics"]["chapter_count"] == 3


@pytest.mark.asyncio
async def test_is_book_hidden_detects_hidden_books():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=datetime.now(UTC))

    assert await is_book_hidden(db, uuid.uuid4()) is True


@pytest.mark.asyncio
async def test_is_book_hidden_returns_false_for_visible_books():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)

    assert await is_book_hidden(db, uuid.uuid4()) is False


@pytest.mark.asyncio
async def test_mark_book_processing_cancelled_rolls_back_and_marks_failed():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    book = Book(
        user_id=uuid.uuid4(),
        title="Cancelled Story",
        format="pdf",
        s3_key="books/cancelled.pdf",
    )
    started_at = datetime.now(UTC) - timedelta(minutes=3)
    book.writer_workspace = {
        "processing": build_ingestion_progress_state(
            status="processing",
            stage="embedding",
            total_chapters=12,
            completed_chapters=4,
            started_at=started_at,
            queue_wait_ms=18,
        )
    }

    await mark_book_processing_cancelled(
        db,
        book,
        stage="embedding",
        rollback=True,
        queue_wait_ms=18,
        chapter_number=5,
        chapter_title="Chapter Five",
        last_error="Book was removed while processing.",
    )

    assert book.status == "failed"
    processing = book.writer_workspace["processing"]
    assert processing["status"] == "failed"
    assert processing["stage"] == "cancelled"
    assert processing["chapters_completed"] == 4
    assert processing["chapters_total"] == 12
    assert processing["queue_wait_ms"] == 18
    assert processing["last_chapter_number"] == 5
    assert processing["last_chapter_title"] == "Chapter Five"
    assert processing["last_error"] == "Book was removed while processing."
    db.rollback.assert_awaited_once()
    db.commit.assert_awaited_once()


def test_is_retryable_processing_error_distinguishes_transient_failures():
    class RetryableError(Exception):
        status_code = 503

    class PermanentError(Exception):
        pass

    assert is_retryable_processing_error(RetryableError("service unavailable"))
    assert not is_retryable_processing_error(PermanentError("parse failure"))


def test_derive_summary_modes_from_detailed_prefers_key_events():
    payload = {
        "content": "Aoi confronts Ren in the archive. They uncover a sealed ledger. The chapter ends with a pact.",
        "key_events": [
            {"event_title": "Archive confrontation", "description": "Aoi corners Ren over the missing ledger."},
            {"event_title": "Ledger discovery", "description": "They find the sealed ledger behind a false wall."},
        ],
        "char_changes": [],
        "clues": [],
        "themes": [],
    }

    derived = derive_summary_modes_from_detailed(payload)

    assert "Aoi confronts Ren" in derived["short"]["content"]
    assert "1. Archive confrontation: Aoi corners Ren over the missing ledger." in derived["key_points"]["content"]
    assert "2. Ledger discovery: They find the sealed ledger behind a false wall." in derived["key_points"]["content"]


def test_apply_chapter_number_strategy_preserves_clean_contiguous_numbers():
    chapters = [
        {"number": 1, "source_number": 1, "title": "Chapter 1", "text": "One"},
        {"number": 2, "source_number": 2, "title": "Chapter 2", "text": "Two"},
        {"number": 3, "source_number": 3, "title": "Chapter 3", "text": "Three"},
    ]

    normalized = apply_chapter_number_strategy(chapters, preserve_chapter_numbers=True)

    assert [chapter["number"] for chapter in normalized] == [1, 2, 3]


def test_apply_chapter_number_strategy_falls_back_for_gaps():
    chapters = [
        {"number": 1, "source_number": 1, "title": "Chapter 1", "text": "One"},
        {"number": 2, "source_number": 3, "title": "Chapter 3", "text": "Three"},
    ]

    normalized = apply_chapter_number_strategy(chapters, preserve_chapter_numbers=True)

    assert [chapter["number"] for chapter in normalized] == [1, 2]


def test_apply_chapter_number_strategy_preserves_letter_derived_sequence():
    chapters = [
        {"number": 1, "source_number": 1, "title": "Chapter A", "text": "One"},
        {"number": 2, "source_number": 2, "title": "Chapter B", "text": "Two"},
        {"number": 3, "source_number": 3, "title": "Chapter C", "text": "Three"},
    ]

    normalized = apply_chapter_number_strategy(chapters, preserve_chapter_numbers=True)

    assert [chapter["number"] for chapter in normalized] == [1, 2, 3]


def test_apply_chapter_number_strategy_can_normalize_non_preserved_titles():
    chapters = [
        {"number": 4, "title": "A false heading", "text": ("one " * 4000).strip() + "."},
        {"number": 9, "title": "Another false heading", "text": ("two " * 4000).strip() + "."},
    ]

    normalized = apply_chapter_number_strategy(
        chapters,
        preserve_chapter_numbers=False,
        generic_titles=True,
    )

    assert [chapter["number"] for chapter in normalized] == [1, 2]
    assert [chapter["title"] for chapter in normalized] == ["Chapter 1", "Chapter 2"]


def test_regroup_prose_chapters_for_reading_merges_tiny_sections_into_fuller_chapters():
    chapters = [
        {"number": 1, "title": "Split 1", "text": ("alpha " * 3400).strip() + "."},
        {"number": 2, "title": "Split 2", "text": ("beta " * 3200).strip() + "."},
        {"number": 3, "title": "Split 3", "text": ("gamma " * 1400).strip() + "."},
        {"number": 4, "title": "Split 4", "text": ("delta " * 200).strip() + "."},
    ]

    regrouped = regroup_prose_chapters_for_reading(chapters)

    assert len(regrouped) == 1
    assert "alpha" in regrouped[0]["text"]
    assert "delta" in regrouped[0]["text"]


def test_apply_chapter_number_strategy_regroups_non_preserved_chapters_before_renumbering():
    chapters = [
        {"number": 8, "title": "Noise 1", "text": ("alpha " * 3400).strip() + "."},
        {"number": 9, "title": "Noise 2", "text": ("beta " * 3200).strip() + "."},
        {"number": 10, "title": "Noise 3", "text": ("gamma " * 3000).strip() + "."},
    ]

    normalized = apply_chapter_number_strategy(
        chapters,
        preserve_chapter_numbers=False,
        generic_titles=True,
    )

    assert len(normalized) == 2
    assert [chapter["number"] for chapter in normalized] == [1, 2]
    assert [chapter["title"] for chapter in normalized] == ["Chapter 1", "Chapter 2"]


def test_apply_chapter_number_strategy_keeps_distinct_titled_sections_separate():
    chapters = [
        {"number": 1, "title": "One", "text": "Aoi enters the archive and meets Ren."},
        {"number": 2, "title": "Two", "text": "Ren reveals the ledger and the hidden room."},
        {"number": 3, "title": "Three", "text": "They form a pact and leave before dawn."},
    ]

    normalized = apply_chapter_number_strategy(
        chapters,
        preserve_chapter_numbers=False,
        generic_titles=True,
    )

    assert len(normalized) == 3
    assert [chapter["number"] for chapter in normalized] == [1, 2, 3]
