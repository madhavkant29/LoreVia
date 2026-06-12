import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import uuid
import pytest
from fastapi import HTTPException

from app.engine.analysis.summariser import derive_summary_modes_from_detailed
from app.models.book import Book
from app.utils.ingestion_utils import (
    apply_chapter_number_strategy,
    build_ingestion_progress_state,
    build_chapter_dispatch_plan,
    extract_queue_wait_ms,
    is_llm_usage_limit_error,
    is_book_hidden,
    is_retryable_processing_error,
    load_analysis_chapter_payload,
    load_processing_chapter_payload,
    load_staged_chapter_payload,
    mark_book_processing_cancelled,
    merge_processing_pipeline,
    processing_state_for_completed_extraction,
    regroup_prose_chapters_for_reading,
    update_book_processing_state,
)
from app.utils.book_utils import serialize_manuscript_content


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


def test_update_book_processing_state_marks_extraction_succeeded_while_analysis_runs():
    book = Book(
        user_id=uuid.uuid4(),
        title="Analysis Pending Story",
        format="pdf",
        s3_key="books/analysis-pending.pdf",
    )
    started_at = datetime.now(UTC) - timedelta(minutes=2)

    workspace = update_book_processing_state(
        book,
        status="processing",
        stage="analysis",
        total_chapters=3,
        completed_chapters=3,
        started_at=started_at,
    )

    pipeline = workspace["processing"]["pipeline"]
    assert pipeline["extraction"]["status"] == "succeeded"
    assert workspace["processing"]["is_fully_ready"] is False


def test_update_book_processing_state_accepts_progress_pct_override():
    book = Book(
        user_id=uuid.uuid4(),
        title="Scripted Progress Story",
        format="pdf",
        s3_key="books/scripted-progress.pdf",
    )

    workspace = update_book_processing_state(
        book,
        status="processing",
        stage="analysis",
        total_chapters=None,
        completed_chapters=0,
        started_at=datetime.now(UTC),
        progress_pct=66.66,
    )

    assert workspace["processing"]["progress_pct"] == 66.7


def test_merge_processing_pipeline_normalizes_postgres_text_timestamps():
    processing = merge_processing_pipeline(
        {"status": "processing", "stage": "analysis"},
        extraction={"status": "succeeded", "updated_at": "2026-06-06 05:11:51.272085+00"},
    )

    assert processing["pipeline"]["extraction"]["updated_at"] == "2026-06-06T05:11:51.272085+00:00"


def test_processing_state_for_completed_extraction_stays_processing_until_analysis_finishes():
    assert processing_state_for_completed_extraction(analysis_complete=False) == ("processing", "analysis")
    assert processing_state_for_completed_extraction(analysis_complete=True) == ("ready", "complete")


def test_llm_usage_limit_error_detects_token_window_429():
    exc = HTTPException(429, "LLM usage token limit exceeded for the 5-hour window.")

    assert is_llm_usage_limit_error(exc) is True
    assert is_retryable_processing_error(exc) is True


def test_llm_usage_limit_error_ignores_other_429_errors():
    exc = HTTPException(429, "Too many login attempts.")

    assert is_llm_usage_limit_error(exc) is False


@pytest.mark.asyncio
async def test_is_book_hidden_detects_hidden_books():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(first=lambda: (datetime.now(UTC), "active", None)))

    assert await is_book_hidden(db, uuid.uuid4()) is True


@pytest.mark.asyncio
async def test_is_book_hidden_returns_false_for_visible_books():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(first=lambda: (None, "active", None)))

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


@pytest.mark.asyncio
async def test_load_staged_chapter_payload_uses_existing_chapter_key(monkeypatch):
    book_id = uuid.uuid4()
    calls: list[str] = []

    def _fake_download(storage_key: str) -> bytes:
        calls.append(storage_key)
        return serialize_manuscript_content("Chapter body", "<p>Chapter body</p>").encode("utf-8")

    monkeypatch.setattr("app.utils.ingestion_utils.download_book", _fake_download)

    payload = await load_staged_chapter_payload(
        book_id,
        7,
        chapter_s3_key="chapters/custom/chapter-7.txt",
    )

    assert payload == {"format": "rich_text_v1", "text": "Chapter body", "html": "<p>Chapter body</p>"}
    assert calls == ["chapters/custom/chapter-7.txt"]


@pytest.mark.asyncio
async def test_load_staged_chapter_payload_falls_back_to_deterministic_key(monkeypatch):
    book_id = uuid.uuid4()
    calls: list[str] = []

    def _fake_download(storage_key: str) -> bytes:
        calls.append(storage_key)
        if storage_key == "missing-key":
            raise FileNotFoundError(storage_key)
        return serialize_manuscript_content("Recovered chapter").encode("utf-8")

    monkeypatch.setattr("app.utils.ingestion_utils.download_book", _fake_download)

    payload = await load_staged_chapter_payload(
        book_id,
        3,
        chapter_s3_key="missing-key",
    )

    assert payload == {"format": "rich_text_v1", "text": "Recovered chapter", "html": "<p>Recovered chapter</p>"}
    assert calls == ["missing-key", f"chapters/{book_id}/3.txt"]


@pytest.mark.asyncio
async def test_load_processing_chapter_payload_returns_chapter_only_payload(monkeypatch):
    book_id = uuid.uuid4()

    async def _fake_load(*_args, **_kwargs):
        return {"text": "Chapter body", "html": "<p>Chapter body</p>"}

    monkeypatch.setattr("app.utils.ingestion_utils.load_staged_chapter_payload", _fake_load)

    payload = await load_processing_chapter_payload(
        book_id,
        5,
        chapter_s3_key="chapters/custom/5.txt",
        chapter_title="Five",
    )

    assert payload == {
        "number": 5,
        "title": "Five",
        "text": "Chapter body",
        "html": "<p>Chapter body</p>",
    }


@pytest.mark.asyncio
async def test_load_analysis_chapter_payload_validates_book_and_loads_text(monkeypatch):
    book_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    db = AsyncMock()
    db.get = AsyncMock(
        return_value=type(
            "ChapterRow",
            (),
            {
                "id": chapter_id,
                "book_id": book_id,
                "number": 2,
                "s3_key": "chapters/custom/2.txt",
                "title": "Two",
            },
        )()
    )

    async def _fake_load(*_args, **_kwargs):
        return {"number": 2, "title": "Two", "text": "Chapter body", "html": None}

    monkeypatch.setattr("app.utils.ingestion_utils.load_processing_chapter_payload", _fake_load)

    payload = await load_analysis_chapter_payload(db, str(chapter_id), book_id=str(book_id))

    assert payload == {
        "chapter_id": str(chapter_id),
        "title": "Two",
        "text": "Chapter body",
    }


@pytest.mark.asyncio
async def test_load_analysis_chapter_payload_rejects_book_mismatch():
    db = AsyncMock()
    db.get = AsyncMock(
        return_value=type(
            "ChapterRow",
            (),
            {
                "id": uuid.uuid4(),
                "book_id": uuid.uuid4(),
                "number": 1,
                "s3_key": "chapters/custom/1.txt",
                "title": "One",
            },
        )()
    )

    payload = await load_analysis_chapter_payload(db, str(uuid.uuid4()), book_id=str(uuid.uuid4()))

    assert payload is None


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
