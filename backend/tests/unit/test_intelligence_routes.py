from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import intelligence
from app.schemas.intelligence import QARequest


@pytest.fixture(autouse=True)
def _stub_llm_reservation_lifecycle(monkeypatch):
    async def reserve(**kwargs):
        return SimpleNamespace(
            id="test-reservation", operation=kwargs["operation"], user_id=kwargs["user_id"]
        )

    async def finish(*_args, **_kwargs):
        return None

    monkeypatch.setattr(intelligence, "reserve_llm_call", reserve)
    monkeypatch.setattr(intelligence, "finish_llm_reservation_counts", finish)
    monkeypatch.setattr(intelligence, "fail_llm_reservation", finish)
    monkeypatch.setattr("app.services.llm_control_service.reserve_llm_call", reserve)
    monkeypatch.setattr("app.services.llm_control_service.finish_llm_reservation", finish)
    monkeypatch.setattr("app.services.llm_control_service.fail_llm_reservation", finish)


class _ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _Row:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


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

    def one(self):
        if self._all_rows:
            return self._all_rows[0]
        return None

    def fetchall(self):
        return list(self._all_rows)


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


class _FakeStream:
    def __init__(self, parts):
        self._parts = list(parts)

    def __aiter__(self):
        self._iter = iter(self._parts)
        return self

    async def __anext__(self):
        try:
            content = next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc
        return SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(delta=SimpleNamespace(content=content))],
        )


class _FakeStreamingClient:
    def __init__(self, parts):
        self.closed = False
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._parts = list(parts)

    async def _create(self, **_kwargs):
        return _FakeStream(self._parts)

    async def close(self):
        self.closed = True


class _ExplodingStreamingClient:
    def __init__(self):
        self.closed = False
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **_kwargs):
        raise RuntimeError("database_url=postgresql://user:secret@example.com/app")

    async def close(self):
        self.closed = True


def test_cosine_similarity_handles_edge_cases():
    from app.utils.intelligence_utils import _cosine_similarity

    assert _cosine_similarity(None, [1.0]) == 0.0
    assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


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
            "citations": [
                {
                    "chapter_num": 1,
                    "chapter_title": "One",
                    "excerpt": "Snippet",
                    "source_type": "summary",
                }
            ],
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
            [
                {
                    "chapter_num": 2,
                    "chapter_title": "Two",
                    "excerpt": "Evidence",
                    "source_type": "passage",
                    "relevance": 0.9,
                }
            ],
        )

    monkeypatch.setattr(intelligence, "build_grounded_qa_context", _fake_build_grounded_qa_context)
    client = _FakeClient("Grounded answer")
    monkeypatch.setattr(intelligence, "get_client", lambda: client)
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Lore Book")
    user = SimpleNamespace(id=book.user_id)
    db = _FakeDB(
        get_values=[book, user],
        execute_values=[_Result(scalar=0), _Result(scalar=0), _Result(scalar=0)],
    )

    payload = await intelligence.qa_endpoint(
        book.id,
        QARequest(question="Who?", current_chapter=2),
        db=db,
        current_user=user,
        _=None,
    )

    assert payload.answer == "Grounded answer"
    assert payload.citations[0].chapter_num == 2
    assert cached["args"][1]["answer"] == "Grounded answer"
    assert client.closed is True


@pytest.mark.asyncio
async def test_qa_stream_endpoint_streams_and_caches(monkeypatch):
    async def _fake_cache_get(_key):
        return None

    cached = {}

    async def _fake_cache_set(key, value, ttl):
        cached["args"] = (key, value, ttl)

    async def _fake_build_grounded_qa_context(**_kwargs):
        return (
            ["Context block"],
            [
                {
                    "chapter_num": 2,
                    "chapter_title": "Two",
                    "excerpt": "Evidence",
                    "source_type": "passage",
                    "relevance": 0.9,
                }
            ],
        )

    monkeypatch.setattr(intelligence, "cache_get", _fake_cache_get)
    monkeypatch.setattr(intelligence, "cache_set", _fake_cache_set)
    monkeypatch.setattr(intelligence, "build_grounded_qa_context", _fake_build_grounded_qa_context)
    client = _FakeStreamingClient(["Grounded", " answer"])
    monkeypatch.setattr(intelligence, "get_client", lambda: client)
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Lore Book")
    user = SimpleNamespace(id=book.user_id)
    db = _FakeDB(
        get_values=[book], execute_values=[_Result(scalar=0), _Result(scalar=0), _Result(scalar=0)]
    )

    response = await intelligence.qa_stream_endpoint(
        book.id,
        QARequest(question="Who?", current_chapter=2),
        db=db,
        current_user=user,
        _=None,
    )
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(chunks)

    assert "event: delta" in body
    assert "Grounded answer" in body
    assert cached["args"][1]["answer"] == "Grounded answer"
    assert client.closed is True


@pytest.mark.asyncio
async def test_qa_stream_endpoint_hides_internal_errors(monkeypatch):
    async def _fake_cache_get(_key):
        return None

    async def _fake_build_grounded_qa_context(**_kwargs):
        return (["Context block"], [])

    monkeypatch.setattr(intelligence, "cache_get", _fake_cache_get)
    monkeypatch.setattr(intelligence, "build_grounded_qa_context", _fake_build_grounded_qa_context)
    client = _ExplodingStreamingClient()
    monkeypatch.setattr(intelligence, "get_client", lambda: client)
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Lore Book")
    user = SimpleNamespace(id=book.user_id)
    db = _FakeDB(
        get_values=[book], execute_values=[_Result(scalar=0), _Result(scalar=0), _Result(scalar=0)]
    )

    response = await intelligence.qa_stream_endpoint(
        book.id,
        QARequest(question="Who?", current_chapter=2),
        db=db,
        current_user=user,
        _=None,
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert "Something went wrong. Please try again." in body
    assert "secret@example.com" not in body
    assert client.closed is True


@pytest.mark.asyncio
async def test_cross_book_intelligence_validates_book(monkeypatch):
    db = _FakeDB(get_values=[None])
    with pytest.raises(HTTPException) as exc:
        await intelligence.cross_book_intelligence(
            uuid.uuid4(), db=db, current_user=SimpleNamespace(id=uuid.uuid4())
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cross_book_intelligence_returns_series_matches(monkeypatch):
    user_id = uuid.uuid4()
    series_id = uuid.uuid4()
    book_id = uuid.uuid4()
    other_book_id = uuid.uuid4()

    book = SimpleNamespace(id=book_id, user_id=user_id, primary_series_id=series_id)
    series = SimpleNamespace(id=series_id, name="Saga")
    other_book = SimpleNamespace(id=other_book_id)

    async def _fake_snapshot_hash(_db, _book_ids):
        return "abc123"

    async def _fake_cache_get(_books_hash, _snapshot_hash):
        return None

    async def _fake_cache_set(_books_hash, _snapshot_hash, _payload):
        pass

    async def _fake_char_matches(_db, _book_ids, threshold=0.9, limit=20):
        return [
            {
                "left_book_id": str(book_id),
                "left_name": "Aoi",
                "right_book_id": str(other_book_id),
                "right_name": "Aoi Prime",
                "similarity": 1.0,
            }
        ]

    async def _fake_wiki_matches(_db, _book_ids, threshold=0.9, limit=20):
        return [
            {
                "left_book_id": str(book_id),
                "left_name": "Archive",
                "right_book_id": str(other_book_id),
                "right_name": "Grand Archive",
                "similarity": 1.0,
                "entry_type": "location",
            }
        ]

    monkeypatch.setattr(intelligence, "compute_cross_book_snapshot_hash", _fake_snapshot_hash)
    monkeypatch.setattr(intelligence, "get_cross_book_intelligence_cache", _fake_cache_get)
    monkeypatch.setattr(intelligence, "set_cross_book_intelligence_cache", _fake_cache_set)
    monkeypatch.setattr(intelligence, "get_cross_book_character_matches", _fake_char_matches)
    monkeypatch.setattr(intelligence, "get_cross_book_wiki_matches", _fake_wiki_matches)

    db = _FakeDB(
        get_values=[book, series],
        execute_values=[
            _Result(scalars=[book, other_book]),
        ],
    )

    payload = await intelligence.cross_book_intelligence(
        book_id, db=db, current_user=SimpleNamespace(id=user_id)
    )

    assert payload.series_name == "Saga"
    assert payload.character_matches[0].left_name == "Aoi"
    assert payload.wiki_matches[0].entry_type == "location"
    assert payload.cached is False


@pytest.mark.asyncio
async def test_cross_book_intelligence_returns_cached_result(monkeypatch):
    user_id = uuid.uuid4()
    series_id = uuid.uuid4()
    book_id = uuid.uuid4()
    other_book_id = uuid.uuid4()

    book = SimpleNamespace(id=book_id, user_id=user_id, primary_series_id=series_id)
    series = SimpleNamespace(id=series_id, name="Saga")
    other_book = SimpleNamespace(id=other_book_id)

    async def _fake_snapshot_hash(_db, _book_ids):
        return "abc123"

    async def _fake_cache_get(_books_hash, _snapshot_hash):
        return {
            "series_name": "Saga",
            "comparison_book_ids": sorted([str(book_id), str(other_book_id)]),
            "character_matches": [],
            "wiki_matches": [],
        }

    monkeypatch.setattr(intelligence, "compute_cross_book_snapshot_hash", _fake_snapshot_hash)
    monkeypatch.setattr(intelligence, "get_cross_book_intelligence_cache", _fake_cache_get)

    db = _FakeDB(
        get_values=[book, series],
        execute_values=[
            _Result(scalars=[book, other_book]),
        ],
    )

    payload = await intelligence.cross_book_intelligence(
        book_id, db=db, current_user=SimpleNamespace(id=user_id)
    )

    assert payload.cached is True
    assert payload.series_name == "Saga"
