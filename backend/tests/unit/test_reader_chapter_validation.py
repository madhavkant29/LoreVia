"""Tests for chapter validation in reader routes."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import reader


class _FakeDB:
    def __init__(self, *, get_values=None, execute_values=None):
        self._get_values = list(get_values or [])
        self._execute_values = list(execute_values or [])

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0)

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)


def _user(user_id: uuid.UUID):
    return SimpleNamespace(id=user_id, tier="reader", email="reader@example.com")


@pytest.mark.asyncio
async def test_get_chapter_validates_empty_project():
    """Test that get_chapter returns helpful error for empty projects."""
    user_id = uuid.uuid4()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Empty Project",
        total_chapters=0,
        is_editor_project=True,
        mode="author",
        format="manual",
        is_public=False,
        is_truncated=False,
        total_tokens=0,
    )
    db = _FakeDB(get_values=[book])
    
    with pytest.raises(HTTPException) as exc_info:
        await reader.get_chapter(book.id, 1, db=db, current_user=_user(user_id))
    
    assert exc_info.value.status_code == 400
    assert "no chapters yet" in exc_info.value.detail.lower()
    assert "create your first chapter" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_chapter_validates_chapter_number_range():
    """Test that get_chapter validates chapter number is within valid range."""
    user_id = uuid.uuid4()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test Book",
        total_chapters=5,
        is_editor_project=False,
        mode="reader",
        format="epub",
        is_public=False,
        is_truncated=False,
        total_tokens=0,
    )
    db = _FakeDB(get_values=[book])
    
    # Test chapter number too high
    with pytest.raises(HTTPException) as exc_info:
        await reader.get_chapter(book.id, 10, db=db, current_user=_user(user_id))
    
    assert exc_info.value.status_code == 404
    assert "does not exist" in exc_info.value.detail.lower()
    assert "5 chapters" in exc_info.value.detail.lower()
    
    # Test chapter number too low
    db = _FakeDB(get_values=[book])
    with pytest.raises(HTTPException) as exc_info:
        await reader.get_chapter(book.id, 0, db=db, current_user=_user(user_id))
    
    assert exc_info.value.status_code == 400
    assert "invalid chapter number" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_chapter_validates_none_total_chapters():
    """Test that get_chapter handles books with None total_chapters."""
    user_id = uuid.uuid4()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Processing Book",
        total_chapters=None,
        is_editor_project=False,
        mode="reader",
        format="epub",
        is_public=False,
        is_truncated=False,
        total_tokens=0,
    )
    db = _FakeDB(get_values=[book])
    
    with pytest.raises(HTTPException) as exc_info:
        await reader.get_chapter(book.id, 1, db=db, current_user=_user(user_id))
    
    assert exc_info.value.status_code == 400
    assert "no chapters yet" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_summary_validates_chapter_range(monkeypatch):
    """Test that get_summary validates chapter number is within valid range."""
    user_id = uuid.uuid4()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test Book",
        total_chapters=3,
        is_editor_project=False,
        mode="reader",
        format="epub",
        is_public=False,
        is_truncated=False,
        total_tokens=0,
    )
    
    async def _fake_access(*_args, **_kwargs):
        return book, None

    monkeypatch.setattr(reader, "get_book_with_collaboration_access", _fake_access)
    monkeypatch.setattr(reader, "summary_mode_allowed", lambda *a, **kw: True)
    db = _FakeDB()
    
    with pytest.raises(HTTPException) as exc_info:
        await reader.get_summary(book.id, 10, mode="short", db=db, current_user=_user(user_id), _=None)
    
    assert exc_info.value.status_code == 404
    assert "does not exist" in exc_info.value.detail.lower()
