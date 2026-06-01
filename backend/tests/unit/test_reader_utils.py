from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from app.models.book import Book
from app.utils import reader_utils


def _build_book(mode: str) -> Book:
    return Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Atlas",
        format="pdf",
        s3_key="books/atlas.pdf",
        status="ready",
        mode=mode,
    )


@pytest.mark.asyncio
async def test_summary_visible_chapter_set_uses_full_scope_in_author_mode(monkeypatch):
    book = _build_book("author")
    current_user = SimpleNamespace(id=uuid.uuid4(), tier="pro")

    monkeypatch.setattr(
        reader_utils,
        "full_available_chapter_set",
        AsyncMock(return_value={1, 2, 3, 4}),
    )

    visible = await reader_utils.summary_visible_chapter_set(AsyncMock(), book, current_user)

    assert visible == {1, 2, 3, 4}


@pytest.mark.asyncio
async def test_summary_visible_chapter_set_stays_read_scoped_in_reader_mode(monkeypatch):
    book = _build_book("reader")
    current_user = SimpleNamespace(id=uuid.uuid4(), tier="pro")

    monkeypatch.setattr(
        reader_utils,
        "read_chapter_set",
        AsyncMock(return_value={1, 2, 3, 4}),
    )
    monkeypatch.setattr(
        reader_utils,
        "read_available_chapter_set",
        AsyncMock(return_value={1, 2, 3}),
    )

    visible = await reader_utils.summary_visible_chapter_set(AsyncMock(), book, current_user)

    assert visible == {1, 2, 3}


@pytest.mark.asyncio
async def test_timeline_visible_chapter_set_uses_full_scope_in_author_mode(monkeypatch):
    book = _build_book("author")
    current_user = SimpleNamespace(id=uuid.uuid4(), tier="pro")

    monkeypatch.setattr(
        reader_utils,
        "full_available_chapter_set",
        AsyncMock(return_value={1, 2, 3, 4}),
    )

    visible = await reader_utils.timeline_visible_chapter_set(AsyncMock(), book, current_user)

    assert visible == {1, 2, 3, 4}


@pytest.mark.asyncio
async def test_timeline_visible_chapter_set_uses_read_progress_in_reader_mode(monkeypatch):
    book = _build_book("reader")
    current_user = SimpleNamespace(id=uuid.uuid4(), tier="pro")

    monkeypatch.setattr(
        reader_utils,
        "read_chapter_set",
        AsyncMock(return_value={1, 2}),
    )

    visible = await reader_utils.timeline_visible_chapter_set(AsyncMock(), book, current_user)

    assert visible == {1, 2}


@pytest.mark.asyncio
async def test_timeline_visible_chapter_set_expands_sparse_reader_progress(monkeypatch):
    book = _build_book("reader")
    current_user = SimpleNamespace(id=uuid.uuid4(), tier="pro")

    monkeypatch.setattr(
        reader_utils,
        "read_chapter_set",
        AsyncMock(return_value={3}),
    )

    visible = await reader_utils.timeline_visible_chapter_set(AsyncMock(), book, current_user)

    assert visible == {1, 2, 3}


def test_timeline_plot_thread_span_uses_visible_window_when_intro_is_missing():
    span = reader_utils.timeline_plot_thread_span(None, None, {1, 2, 3})

    assert span == (1, 3)


def test_timeline_plot_thread_span_clamps_to_visible_window():
    span = reader_utils.timeline_plot_thread_span(2, 5, {1, 2, 3})

    assert span == (2, 3)


@pytest.mark.asyncio
async def test_queue_analysis_if_missing_skips_duplicate_inflight(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        s3_key="chapters/test/1.txt",
        title="One",
        analysis_state={"status": "queued", "generated_modes": [], "attempt_count": 1},
    )
    db = AsyncMock()

    monkeypatch.setattr(reader_utils, "chapter_has_detailed_summary", AsyncMock(return_value=False))

    called = {"queued": False}

    class _Task:
        @staticmethod
        def apply_async(*args, **kwargs):
            called["queued"] = True

    monkeypatch.setattr("app.workers.tasks.analysis_tasks.analyse_chapter_task", _Task(), raising=False)

    await reader_utils.queue_analysis_if_missing(db, chapter)

    assert called["queued"] is False


@pytest.mark.asyncio
async def test_queue_analysis_if_missing_dispatches_without_request_time_db_write(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        s3_key="chapters/test/1.txt",
        title="One",
        analysis_state={},
    )
    db = AsyncMock()
    dispatched: list[dict] = []

    monkeypatch.setattr(reader_utils, "chapter_has_detailed_summary", AsyncMock(return_value=False))
    monkeypatch.setattr(reader_utils, "cache_set_if_absent", AsyncMock(return_value=True))

    class _Task:
        @staticmethod
        def apply_async(*args, **kwargs):
            dispatched.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr("app.workers.tasks.analysis_tasks.analyse_chapter_task", _Task(), raising=False)

    queued = await reader_utils.queue_analysis_if_missing(db, chapter)

    assert queued is True
    db.commit.assert_not_called()
    assert chapter.analysis_state == {}
    assert dispatched == [
        {
            "args": (),
            "kwargs": {
                "args": [str(chapter.id), str(chapter.book_id)],
                "kwargs": {"is_reprocessing": False},
                "queue": "analysis",
            },
        }
    ]


@pytest.mark.asyncio
async def test_queue_analysis_if_missing_clears_queued_key_when_dispatch_fails(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        s3_key="chapters/test/1.txt",
        title="One",
        analysis_state={},
    )
    db = AsyncMock()
    deleted_keys: list[str] = []

    monkeypatch.setattr(reader_utils, "chapter_has_detailed_summary", AsyncMock(return_value=False))
    monkeypatch.setattr(reader_utils, "cache_set_if_absent", AsyncMock(return_value=True))

    async def _fake_cache_del(key):
        deleted_keys.append(key)

    monkeypatch.setattr(reader_utils, "cache_del", _fake_cache_del)

    class _Task:
        @staticmethod
        def apply_async(*args, **kwargs):
            raise RuntimeError("broker unavailable")

    monkeypatch.setattr("app.workers.tasks.analysis_tasks.analyse_chapter_task", _Task(), raising=False)

    queued = await reader_utils.queue_analysis_if_missing(db, chapter)

    assert queued is False
    db.commit.assert_not_called()
    assert deleted_keys == [reader_utils.key_analysis_queued(str(chapter.id))]


@pytest.mark.asyncio
async def test_build_summary_collection_reports_newly_scheduled_analysis_as_queued(monkeypatch):
    book = _build_book("author")
    current_user = SimpleNamespace(id=book.user_id, tier="pro")
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        number=1,
        title="One",
        analysis_state={},
    )
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [chapter])),
        SimpleNamespace(all=lambda: []),
    ]

    monkeypatch.setattr(reader_utils, "summary_visible_chapter_set", AsyncMock(return_value={1}))
    monkeypatch.setattr(reader_utils, "queue_analysis_if_missing", AsyncMock(return_value=True))
    monkeypatch.setattr(reader_utils, "get_or_generate_summary", AsyncMock(return_value={"status": "pending"}))

    payload = await reader_utils.build_summary_collection_payload(
        db,
        book=book,
        current_user=current_user,
        progress=SimpleNamespace(current_chapter=0),
        intelligence_map={1: True},
    )

    assert payload["summaries"] == [
        {
            "chapter_number": 1,
            "chapter_title": "One",
            "read": True,
            "available": False,
            "status": "queued",
            "content": None,
            "key_events": [],
        }
    ]
