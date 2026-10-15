"""Regression tests for the manuscript ingestion reliability fixes.

These tests exercise the real session/ORM code paths that previously left
books stuck in "processing" with no author-visible failure state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.intelligence import ChapterSummary
from app.models.operations import BookProcessingRun, TaskExecution
from app.models.user import User
from app.services.extraction_budget_service import _mark_budget_blocked
from app.services.first_impression_service import queue_first_impression
from app.services.pipeline_state_service import complete_book_after_analysis
from app.services.processing_pause_service import settle_terminal_processing_failure
from app.utils.books.imports import parse_import_upload
from app.utils.processing_error_utils import friendly_processing_error
from app.utils.upload_security_utils import _validate_text_upload


async def _create_user(db: AsyncSession, *, tier: str = "author") -> User:
    user = User(
        email=f"ingest-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"ingest{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier=tier,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_book(db: AsyncSession, *, user: User, status: str = "processing") -> Book:
    book = Book(
        user_id=user.id,
        title="Ingestion Regression",
        format="txt",
        work_type="novel",
        s3_key=f"books/{user.id}/{uuid.uuid4()}/manuscript.txt",
        status=status,
        mode="author",
    )
    db.add(book)
    await db.flush()
    return book


class TestFriendlyProcessingError:
    def test_maps_legacy_doc(self):
        message = friendly_processing_error(
            "Legacy .doc files require additional system dependencies."
        )
        assert "docx" in message.lower()

    def test_maps_unreadable_document(self):
        message = friendly_processing_error("fitz.FileDataError: cannot open broken file")
        assert "couldn't read" in message.lower() or "could not read" in message.lower()

    def test_maps_empty_text(self):
        message = friendly_processing_error("missing_chapter_payload:book:1")
        assert "readable text" in message.lower()

    def test_maps_budget(self):
        message = friendly_processing_error("budget_exhausted: free token budget used")
        assert "allowance" in message.lower()

    def test_unknown_error_uses_generic_message(self):
        message = friendly_processing_error("KeyError('internal-secret-detail')")
        assert "internal-secret-detail" not in message

    def test_empty_error_uses_generic_message(self):
        assert friendly_processing_error(None)
        assert friendly_processing_error("")


@pytest.mark.asyncio
async def test_settle_terminal_failure_marks_book_failed_for_initial_upload(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_book(db, user=user)
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind="initial_upload",
        status="running",
    )
    db.add(run)
    await db.flush()
    execution = TaskExecution(
        identity_key=f"terminal-{uuid.uuid4().hex}",
        task_name="extraction_tasks.process_book",
        feature="processing",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        status="running",
    )
    db.add(execution)
    await db.flush()

    await settle_terminal_processing_failure(
        db,
        execution,
        error="missing_chapter_payload:book:1",
        completed_at=datetime.now(UTC),
    )
    await db.commit()
    await db.refresh(book)

    assert run.status == "failed_terminal"
    assert book.status == "failed"
    processing = book.writer_workspace["processing"]
    assert processing["status"] == "failed"
    assert processing["retry_actions"] == ["retry_extraction"]
    assert "readable text" in processing["last_error"].lower()


@pytest.mark.asyncio
async def test_queue_first_impression_ineligible_commit_keeps_session_state(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_book(db, user=user, status="processing")
    await db.commit()

    loaded_book = await db.get(Book, book.id)
    assert loaded_book is not None

    result = await queue_first_impression(
        db,
        book_id=book.id,
        user_id=user.id,
        strict=False,
    )

    assert result is None
    # A rollback here would expire every loaded ORM object and the caller's
    # next synchronous attribute access would raise MissingGreenlet.
    assert sa_inspect(loaded_book).expired is False
    assert loaded_book.id == book.id


@pytest.mark.asyncio
async def test_complete_book_after_analysis_marks_book_ready(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_book(db, user=user)
    book.total_chapters = 1
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Chapter 1",
        s3_key=f"chapters/{book.id}/1.txt",
        word_count=1200,
        processed=True,
    )
    db.add(chapter)
    await db.flush()
    db.add(
        ChapterSummary(
            chapter_id=chapter.id,
            mode="detailed",
            content="Mira enters the archive and meets the archivist.",
        )
    )
    await db.commit()

    finalized = await complete_book_after_analysis(db, book_id=book.id)

    assert finalized is True
    refreshed = await db.get(Book, book.id)
    assert refreshed is not None
    assert refreshed.status == "ready"
    processing = refreshed.writer_workspace["processing"]
    assert processing["status"] == "ready"
    assert processing["is_fully_ready"] is True


@pytest.mark.asyncio
async def test_mark_budget_blocked_writes_author_visible_failure(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_book(db, user=user)

    await _mark_budget_blocked(
        db,
        book=book,
        reason="budget_exhausted: free token budget already used",
    )
    await db.refresh(book)

    assert book.status == "failed"
    processing = book.writer_workspace["processing"]
    assert processing["status"] == "failed"
    assert "allowance" in processing["last_error"].lower()


class TestUploadInputValidation:
    def test_blank_text_upload_is_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _validate_text_upload("empty.txt", b"   \n\n  ")
        assert exc.value.status_code == 400
        assert "empty" in str(exc.value.detail).lower()

    def test_utf8_text_upload_is_accepted(self):
        _validate_text_upload("ok.txt", b"Chapter 1\nText")


@pytest.mark.asyncio
async def test_parse_import_upload_maps_corrupt_docx_to_400():
    with pytest.raises(HTTPException) as exc:
        await parse_import_upload("broken.docx", b"this is not a zip archive", True)
    assert exc.value.status_code == 400
    assert "broken.docx" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_parse_import_upload_maps_corrupt_pdf_to_400():
    with pytest.raises(HTTPException) as exc:
        await parse_import_upload("broken.pdf", b"%PDF-1.4 not really a pdf", True)
    assert exc.value.status_code == 400


def test_build_import_preview_maps_corrupt_docx_to_400():
    from app.utils.books.imports import build_import_preview

    with pytest.raises(HTTPException) as exc:
        build_import_preview(
            format_name="docx",
            work_type="novel",
            raw=b"this is not a docx",
        )
    assert exc.value.status_code == 400


def test_build_import_preview_supports_scrivener_archives():
    from app.utils.books.imports import build_import_preview
    from app.utils.scrivener_utils import build_scrivener_archive

    archive = build_scrivener_archive(
        "River & Ash",
        [
            {"title": "Arrival", "text": "Nora crossed the river. A bell rang."},
            {"title": "The Gate", "text": "The gate was already open."},
        ],
    )
    preview = build_import_preview(format_name="scrivener", work_type="novel", raw=archive)

    assert preview["chapter_count"] >= 1
    assert preview["total_words"] > 0
    assert preview["detected_language"]


def test_build_import_preview_maps_corrupt_scrivener_to_400():
    from app.utils.books.imports import build_import_preview

    with pytest.raises(HTTPException) as exc:
        build_import_preview(format_name="scrivener", work_type="novel", raw=b"not a zip")
    assert exc.value.status_code == 400


class TestLlmCoordinationRetryClassification:
    """Transient capacity errors must pause the run, never fail it terminally.

    Regression: the provider circuit breaker's "LLM provider capacity" wording
    did not match the coordination matcher, so chapters that had started were
    marked failed_terminal during provider outages instead of pausing.
    """

    @pytest.mark.parametrize(
        "message",
        [
            "LLM capacity is temporarily busy. Retry shortly.",
            "LLM provider capacity is temporarily unavailable. Retry shortly.",
            "System AI capacity is temporarily busy. Retry shortly.",
            "llm coordination window exhausted",
        ],
    )
    @pytest.mark.parametrize("status_code", [429, 503])
    def test_capacity_errors_are_classified_as_coordination(self, message, status_code):
        from app.utils.ingestion_utils import is_llm_coordination_retry_error

        exc = HTTPException(status_code, message)
        assert is_llm_coordination_retry_error(exc) is True

    def test_unrelated_provider_errors_are_not_capacity_pauses(self):
        from app.utils.ingestion_utils import is_llm_coordination_retry_error

        assert is_llm_coordination_retry_error(HTTPException(503, "upstream boom")) is False
        assert is_llm_coordination_retry_error(HTTPException(500, "LLM capacity")) is False

