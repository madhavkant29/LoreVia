from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import intelligence
from app.api.v1.routes import world_building_documents
from app.api.v1.routes.advisor import chat as advisor_chat
from app.api.v1.routes.advisor import suggestions as advisor_suggestions
from app.api.v1.routes.books import notes as book_notes
from app.api.v1.routes.books import series as book_series
from app.api.v1.routes.reader import core as reader_core
from app.schemas.advisor import WhatsTheWordRequest
from app.schemas.intelligence import QARequest


class _FakeDB:
    def __init__(self, *, get_value=None):
        self.get_value = get_value

    async def get(self, *_args, **_kwargs):
        return self.get_value


def _free_user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        tier="free",
        created_at=datetime(2026, 4, 1, tzinfo=UTC),
    )


def _book(user_id: uuid.UUID):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Gate Test",
        total_chapters=1,
    )


def _async_value(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner


@pytest.fixture
def deny_author_access(monkeypatch):
    monkeypatch.setattr(
        "app.utils.billing_utils.has_authoring_access", lambda *_args, **_kwargs: False
    )


async def _assert_forbidden(coro):
    with pytest.raises(HTTPException) as exc_info:
        await coro
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_free_owner_cannot_load_notes_vault(monkeypatch, deny_author_access):
    user = _free_user()
    book = _book(user.id)
    monkeypatch.setattr(book_notes, "get_owned_book", _async_value(book))

    await _assert_forbidden(
        book_notes.list_book_vault_notes(book.id, db=_FakeDB(), current_user=user)
    )


@pytest.mark.asyncio
async def test_free_owner_cannot_load_reader_summary(monkeypatch, deny_author_access):
    user = _free_user()
    book = _book(user.id)
    monkeypatch.setattr(
        reader_core, "get_book_with_collaboration_access", _async_value((book, None))
    )

    await _assert_forbidden(
        reader_core.get_summary(book.id, 1, db=_FakeDB(), current_user=user, _=None)
    )


@pytest.mark.asyncio
async def test_free_owner_cannot_use_ask_lorevia(monkeypatch, deny_author_access):
    user = _free_user()
    book = _book(user.id)
    body = QARequest(question="Where is the clue?", current_chapter=1)

    await _assert_forbidden(
        intelligence.qa_endpoint(
            book.id, body, db=_FakeDB(get_value=book), current_user=user, _=None
        )
    )


@pytest.mark.asyncio
async def test_free_owner_cannot_use_world_building(monkeypatch, deny_author_access):
    user = _free_user()
    book = _book(user.id)
    monkeypatch.setattr(
        world_building_documents, "get_owned_world_building_book", _async_value(book)
    )

    await _assert_forbidden(
        world_building_documents.list_world_documents(
            book.id, db=_FakeDB(get_value=book), current_user=user
        )
    )


@pytest.mark.asyncio
async def test_free_owner_cannot_use_advisor_extra_tools(deny_author_access):
    user = _free_user()
    book = _book(user.id)

    await _assert_forbidden(
        advisor_suggestions.advisor_suggestions(
            book.id, db=_FakeDB(get_value=book), current_user=user
        )
    )
    await _assert_forbidden(
        advisor_chat.whats_the_word(
            book.id,
            WhatsTheWordRequest(description="a precise word for a quiet fear"),
            db=_FakeDB(get_value=book),
            current_user=user,
            _=None,
        )
    )


@pytest.mark.asyncio
async def test_free_owner_cannot_list_series(deny_author_access):
    user = _free_user()

    await _assert_forbidden(book_series.list_series(db=_FakeDB(), current_user=user))
