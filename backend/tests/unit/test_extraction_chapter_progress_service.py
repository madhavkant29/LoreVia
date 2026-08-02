import uuid
from types import SimpleNamespace

import pytest

from app.services import extraction_chapter_progress_service
from app.services.extraction_chapter_progress_service import update_chapter_processing_progress


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _FakeDb:
    def __init__(self, processed_count):
        self.processed_count = processed_count
        self.commits = 0
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _FakeResult(self.processed_count)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_update_chapter_processing_progress_updates_state_and_invalidates_cache(monkeypatch):
    book = SimpleNamespace(
        id=uuid.uuid4(),
        total_chapters=5,
        writer_workspace={"processing": {"started_at": "existing"}},
    )
    chapter = SimpleNamespace(title="Storm Front")
    db = _FakeDb(processed_count=3)
    invalidated = []

    monkeypatch.setattr(
        extraction_chapter_progress_service,
        "get_processing_started_at",
        lambda book: "started",
    )

    def fake_update_state(book_arg, **kwargs):
        assert book_arg is book
        return {
            "processing": {
                **kwargs,
                "progress_pct": 60,
                "eta_seconds": 120,
            }
        }

    async def fake_invalidate(db_arg, *, book_id):
        invalidated.append((db_arg, book_id))

    monkeypatch.setattr(
        extraction_chapter_progress_service,
        "update_book_processing_state",
        fake_update_state,
    )
    monkeypatch.setattr(
        extraction_chapter_progress_service,
        "invalidate_advisor_caches_for_book",
        fake_invalidate,
    )

    processed_count, processing_total = await update_chapter_processing_progress(
        db,
        book=book,
        chapter=chapter,
        chapter_number=4,
        queue_wait_ms=25,
        extraction_diagnostics={"ok": True},
    )

    assert processed_count == 3
    assert processing_total == 5
    assert db.commits == 2
    assert db.statements
    assert invalidated == [(db, book.id)]
    assert book.writer_workspace["processing"]["stage"] == "chapter_complete"
    assert book.writer_workspace["processing"]["chapter_title"] == "Storm Front"
    assert book.writer_workspace["processing"]["parser_diagnostics"] == {"ok": True}


@pytest.mark.asyncio
async def test_update_chapter_processing_progress_uses_processed_count_when_total_missing(
    monkeypatch,
):
    book = SimpleNamespace(id=uuid.uuid4(), total_chapters=None, writer_workspace={})
    db = _FakeDb(processed_count=2)

    monkeypatch.setattr(
        extraction_chapter_progress_service,
        "get_processing_started_at",
        lambda book: None,
    )
    monkeypatch.setattr(
        extraction_chapter_progress_service,
        "update_book_processing_state",
        lambda book, **kwargs: {"processing": kwargs},
    )

    async def fake_invalidate(*args, **kwargs):
        return None

    monkeypatch.setattr(
        extraction_chapter_progress_service,
        "invalidate_advisor_caches_for_book",
        fake_invalidate,
    )

    processed_count, processing_total = await update_chapter_processing_progress(
        db,
        book=book,
        chapter=SimpleNamespace(title="Chapter"),
        chapter_number=2,
        queue_wait_ms=None,
        extraction_diagnostics=None,
    )

    assert processed_count == 2
    assert processing_total == 2
    assert db.commits == 2
    assert book.writer_workspace["processing"]["total_chapters"] == 2
