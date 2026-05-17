from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import intelligence
from app.schemas.intelligence import ChatMessage, ChatRequest, QARequest


class _ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _Result:
    def __init__(self, *, scalar=None, all_rows=None, scalars=None):
        self._scalar = scalar
        self._all_rows = [] if all_rows is None else all_rows
        self._scalars = [] if scalars is None else scalars

    def scalar(self):
        return self._scalar

    def all(self):
        return list(self._all_rows)

    def scalars(self):
        return _ScalarList(self._scalars)


class _FakeDB:
    def __init__(self, *, get_values=None, execute_values=None):
        self._get_values = list(get_values or [])
        self._execute_values = list(execute_values or [])
        self.added = []

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0)

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)

    def add(self, value):
        self.added.append(value)


class _FakeClient:
    def __init__(self, content: str):
        self._content = content
        self.closed = False
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )

    async def close(self):
        self.closed = True


def test_cosine_similarity_handles_edge_cases():
    assert intelligence._cosine_similarity(None, [1.0]) == 0.0
    assert intelligence._cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert intelligence._cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert intelligence._cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


@pytest.mark.asyncio
async def test_qa_endpoint_raises_for_missing_book():
    db = _FakeDB(get_values=[None])
    with pytest.raises(HTTPException) as exc:
        await intelligence.qa_endpoint(
            uuid.uuid4(),
            QARequest(question="Q?", current_chapter=2),
            db=db,
            current_user=SimpleNamespace(id=uuid.uuid4()),
            _=None,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_qa_endpoint_returns_cached_payload(monkeypatch):
    async def _fake_cache_get(_key):
        return {
            "answer": "Cached answer",
            "citations": [{"chapter_num": 1, "chapter_title": "One", "excerpt": "Snippet", "source_type": "summary"}],
        }

    monkeypatch.setattr(intelligence, "cache_get", _fake_cache_get)
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Lore Book")
    db = _FakeDB(get_values=[book])

    payload = await intelligence.qa_endpoint(
        book.id,
        QARequest(question="Q?", current_chapter=2),
        db=db,
        current_user=SimpleNamespace(id=book.user_id),
        _=None,
    )

    assert payload.cached is True
    assert payload.answer == "Cached answer"


@pytest.mark.asyncio
async def test_qa_endpoint_builds_answer_and_caches(monkeypatch):
    async def _fake_cache_get(_key):
        return None

    cached = {}

    async def _fake_cache_set(key, value, ttl):
        cached["args"] = (key, value, ttl)

    monkeypatch.setattr(intelligence, "cache_get", _fake_cache_get)
    monkeypatch.setattr(intelligence, "cache_set", _fake_cache_set)
    async def _fake_build_grounded_qa_context(**_kwargs):
        return (
            ["Context block"],
            [{"chapter_num": 2, "chapter_title": "Two", "excerpt": "Evidence", "source_type": "passage", "relevance": 0.9}],
        )

    monkeypatch.setattr(intelligence, "build_grounded_qa_context", _fake_build_grounded_qa_context)
    client = _FakeClient("Grounded answer")
    monkeypatch.setattr(intelligence, "get_client", lambda: client)
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Lore Book")
    db = _FakeDB(get_values=[book])

    payload = await intelligence.qa_endpoint(
        book.id,
        QARequest(question="Who?", current_chapter=2),
        db=db,
        current_user=SimpleNamespace(id=book.user_id),
        _=None,
    )

    assert payload.answer == "Grounded answer"
    assert payload.citations[0].chapter_num == 2
    assert cached["args"][1]["answer"] == "Grounded answer"
    assert client.closed is True


@pytest.mark.asyncio
async def test_character_chat_validates_book_and_character(monkeypatch):
    body = ChatRequest(messages=[ChatMessage(role="user", content="Hi")], current_chapter=1)
    db = _FakeDB(get_values=[None])
    with pytest.raises(HTTPException):
        await intelligence.character_chat(uuid.uuid4(), uuid.uuid4(), body=body, db=db, current_user=SimpleNamespace(id=uuid.uuid4()), _=None)

    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Book")
    db = _FakeDB(get_values=[book, None])
    with pytest.raises(HTTPException):
        await intelligence.character_chat(book_id, uuid.uuid4(), body=body, db=db, current_user=SimpleNamespace(id=user_id), _=None)


@pytest.mark.asyncio
async def test_character_chat_builds_grounded_hint(monkeypatch):
    book_id = uuid.uuid4()
    char_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, title="Book")
    character = SimpleNamespace(id=char_id, book_id=book_id, name="Aoi")
    async def _fake_semantic_search(*_args, **_kwargs):
        return [{"chapter_num": 3, "text": "evidence text"}]

    async def _fake_chat_as_character(**_kwargs):
        return "In character"

    monkeypatch.setattr(intelligence, "semantic_search", _fake_semantic_search)
    monkeypatch.setattr(intelligence, "chat_as_character", _fake_chat_as_character)
    db = _FakeDB(get_values=[book, character])

    payload = await intelligence.character_chat(
        book_id,
        char_id,
        body=ChatRequest(messages=[ChatMessage(role="user", content="What now?")], current_chapter=3),
        db=db,
        current_user=SimpleNamespace(id=user_id),
        _=None,
    )

    assert payload["reply"] == "In character"
    assert payload["grounded_hint"] == "Grounded in chapter 3 evidence."


@pytest.mark.asyncio
async def test_cross_book_intelligence_validates_book(monkeypatch):
    db = _FakeDB(get_values=[None])
    with pytest.raises(HTTPException) as exc:
        await intelligence.cross_book_intelligence(uuid.uuid4(), db=db, current_user=SimpleNamespace(id=uuid.uuid4()))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cross_book_intelligence_returns_series_matches():
    user_id = uuid.uuid4()
    series_id = uuid.uuid4()
    book_id = uuid.uuid4()
    other_book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, primary_series_id=series_id)
    series = SimpleNamespace(id=series_id, name="Saga")
    other_book = SimpleNamespace(id=other_book_id)
    char_a = SimpleNamespace(book_id=book_id, name="Aoi", embedding=[1.0, 0.0])
    char_b = SimpleNamespace(book_id=other_book_id, name="Aoi Prime", embedding=[1.0, 0.0])
    wiki_a = SimpleNamespace(book_id=book_id, name="Archive", embedding=[1.0, 0.0], entry_type="location")
    wiki_b = SimpleNamespace(book_id=other_book_id, name="Grand Archive", embedding=[1.0, 0.0], entry_type=None)
    db = _FakeDB(
        get_values=[book, series],
        execute_values=[
            _Result(scalars=[book, other_book]),
            _Result(scalars=[char_a, char_b]),
            _Result(scalars=[wiki_a, wiki_b]),
        ],
    )

    payload = await intelligence.cross_book_intelligence(book_id, db=db, current_user=SimpleNamespace(id=user_id))

    assert payload["series_name"] == "Saga"
    assert payload["character_matches"][0]["left_name"] == "Aoi"
    assert payload["wiki_matches"][0]["entry_type"] == "location"
