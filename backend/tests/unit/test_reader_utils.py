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
