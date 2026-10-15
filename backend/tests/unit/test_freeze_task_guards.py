"""Frozen books must not spend provider tokens in workers or dispatch paths."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.services.book_freeze_service import FROZEN_USER_MESSAGE
from app.services.extraction_chapter_analysis_dispatch_service import (
    dispatch_chapter_analysis_after_extraction,
)


def _frozen_book(book_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=book_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Frozen",
        status="failed",
        mode="author",
        language="en",
        writer_workspace={
            "processing": {
                "status": "failed",
                "stage": "failed",
                "frozen": True,
                "freeze_reason": "interrupted_legacy_import",
                "freeze_message": FROZEN_USER_MESSAGE,
                "retry_actions": [],
            }
        },
    )


class _ExplodingDb:
    """Any database call after a frozen short-circuit is a test failure."""

    async def execute(self, *_args, **_kwargs):  # pragma: no cover - failure path
        raise AssertionError("frozen book should not reach the database")

    async def commit(self):  # pragma: no cover - failure path
        raise AssertionError("frozen book should not commit")


@pytest.mark.asyncio
async def test_analysis_skips_frozen_book_without_provider_calls(monkeypatch):
    from app.workers.consumers import analysis_consumer

    book = _frozen_book()
    chapter = SimpleNamespace(id=uuid.uuid4(), book_id=book.id, number=1)
    generate_calls: list[object] = []

    class _Db:
        async def get(self, model, _object_id):
            from app.models.book import Book, Chapter

            if model is Chapter:
                return chapter
            if model is Book:
                return book
            return None

    async def unexpected_generate(*args, **kwargs):  # pragma: no cover - failure path
        generate_calls.append(args)
        raise AssertionError("generate_summary must not run for frozen books")

    monkeypatch.setattr(analysis_consumer, "generate_summary", unexpected_generate)
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: _SessionContext(_Db()))

    result = await analysis_consumer.analyse_chapter(str(chapter.id), "chapter text")

    assert result == {"skipped": "frozen"}
    assert generate_calls == []


class _SessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _GetOnlyDb:
    def __init__(self, book):
        self.book = book

    async def get(self, model, object_id):
        return self.book


@pytest.mark.asyncio
async def test_process_book_skips_frozen_book(monkeypatch):
    from app.services.extraction_book_processing_service import (
        process_book_ingestion_and_queue,
    )

    book = _frozen_book()
    db = _GetOnlyDb(book)
    result = await process_book_ingestion_and_queue(db, book_id=str(book.id))
    assert result == {"skipped": "frozen"}


@pytest.mark.asyncio
async def test_chapter_extraction_skips_frozen_book(monkeypatch):
    from app.services import extraction_chapter_processing_service as service

    book = _frozen_book()
    db = _ExplodingDb()

    async def not_hidden(*_args, **_kwargs):
        return False

    monkeypatch.setattr(service, "is_book_hidden", not_hidden)

    result = await service._process_chapter_in_generation(
        db,
        book,
        {"number": 1, "text": "Mara waits.", "title": "One"},
    )
    assert result is False


@pytest.mark.asyncio
async def test_analysis_dispatch_skips_frozen_book():
    book = _frozen_book()
    db = _ExplodingDb()
    chapter = SimpleNamespace(id=uuid.uuid4())

    await dispatch_chapter_analysis_after_extraction(
        db,
        book=book,
        chapter=chapter,
        chapter_number=1,
        rebuild_run_id=None,
        manual_reprocess=False,
    )


def test_frozen_payload_has_no_retry_and_a_clear_message():
    from app.utils.books.writer_workspace import build_book_processing_payload

    payload = build_book_processing_payload(_frozen_book())
    assert payload is not None
    assert payload["stage"] == "frozen"
    assert payload["retry_available"] is False
    assert payload["frozen"] is True
    assert payload["freeze_message"] == FROZEN_USER_MESSAGE
    assert payload["current_step_label"] == "Import interrupted"
