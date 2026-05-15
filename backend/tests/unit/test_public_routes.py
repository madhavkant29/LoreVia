from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import public
from app.schemas.public import PublicBookManualIn, PublicChapterIn


class _ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _Result:
    def __init__(self, *, scalar=None, scalar_one=None, all_rows=None, scalars=None):
        self._scalar = scalar
        self._scalar_one = scalar if scalar_one is None else scalar_one
        self._all_rows = [] if all_rows is None else all_rows
        self._scalars = [] if scalars is None else scalars

    def scalar(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar_one

    def all(self):
        return list(self._all_rows)

    def scalars(self):
        return _ScalarList(self._scalars)


class _FakeDB:
    def __init__(self, *, get_values=None, execute_values=None):
        self._get_values = list(get_values or [])
        self._execute_values = list(execute_values or [])
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.refreshes = []

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0)

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushes += 1
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshes.append(value)


@pytest.fixture(autouse=True)
def _enable_public_mode(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", True, raising=False)


def test_public_mode_guard_blocks_when_disabled(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", False, raising=False)
    with pytest.raises(HTTPException) as exc:
        public.ensure_public_mode_enabled()
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_list_public_books_returns_cached_payload(monkeypatch):
    async def _fake_cache_get(_key):
        return [{"id": "cached"}]

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    payload = await public.list_public_books(db=_FakeDB())
    assert payload == [{"id": "cached"}]


@pytest.mark.asyncio
async def test_list_public_books_builds_and_caches_rows(monkeypatch):
    captured = {}

    async def _fake_cache_get(_key):
        return None

    async def _fake_cache_set(key, value, ttl):
        captured["args"] = (key, value, ttl)

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    book = SimpleNamespace(
        id=uuid.uuid4(),
        title="Public Novel",
        author="M. Author",
        genre="Fantasy",
        public_description="Desc",
        format="pdf",
        work_type="novel",
        status="ready",
        total_chapters=3,
        copyright_warning=False,
        created_at="now",
        archived_at=None,
    )
    db = _FakeDB(execute_values=[_Result(all_rows=[(book, "public_author")])])

    payload = await public.list_public_books(db=db)

    assert payload[0]["title"] == "Public Novel"
    assert payload[0]["author_username"] == "public_author"
    assert captured["args"][1] == payload
    assert captured["args"][2] == 300


@pytest.mark.asyncio
async def test_get_public_book_returns_cached_payload(monkeypatch):
    async def _fake_cache_get(_key):
        return {"id": "cached"}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    payload = await public.get_public_book(uuid.uuid4(), db=_FakeDB())
    assert payload == {"id": "cached"}


@pytest.mark.asyncio
async def test_get_public_book_raises_for_missing_or_hidden_book(monkeypatch):
    async def _fake_cache_get(_key):
        return None

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    db = _FakeDB(get_values=[None])
    with pytest.raises(HTTPException) as exc:
        await public.get_public_book(uuid.uuid4(), db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_public_book_builds_payload(monkeypatch):
    async def _fake_cache_get(_key):
        return None

    cached = {}

    async def _fake_cache_set(key, value, ttl):
        cached["args"] = (key, value, ttl)

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        is_public=True,
        hidden_at=None,
        archived_at=None,
        title="Public Novel",
        author="M. Author",
        genre="Fantasy",
        public_description="Desc",
        format="pdf",
        work_type="novel",
        status="ready",
        total_chapters=2,
        copyright_warning=False,
        user_id=uuid.uuid4(),
    )
    author_user = SimpleNamespace(username="public_author")
    db = _FakeDB(
        get_values=[book, author_user],
        execute_values=[_Result(all_rows=[(1, "One", "First"), (2, "Two", "Second")])],
    )

    payload = await public.get_public_book(book_id, db=db)

    assert payload["chapters"][0]["title"] == "One"
    assert payload["author_username"] == "public_author"
    assert cached["args"][1]["id"] == str(book_id)


@pytest.mark.asyncio
async def test_get_public_chapter_returns_cached_payload(monkeypatch):
    async def _fake_cache_get(_key):
        return {"chapter_number": 1}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    payload = await public.get_public_chapter(uuid.uuid4(), 1, db=_FakeDB())
    assert payload["chapter_number"] == 1


@pytest.mark.asyncio
async def test_get_public_chapter_raises_for_missing_book_or_chapter(monkeypatch):
    async def _fake_cache_get(_key):
        return None

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    db = _FakeDB(get_values=[None])
    with pytest.raises(HTTPException) as exc:
        await public.get_public_chapter(uuid.uuid4(), 1, db=db)
    assert exc.value.status_code == 404

    book = SimpleNamespace(id=uuid.uuid4(), is_public=True, hidden_at=None, archived_at=None)
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=None)])
    with pytest.raises(HTTPException) as exc:
        await public.get_public_chapter(book.id, 4, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_public_chapter_builds_payload(monkeypatch):
    async def _fake_cache_get(_key):
        return None

    cached = {}

    async def _fake_cache_set(key, value, ttl):
        cached["args"] = (key, value, ttl)

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    monkeypatch.setattr(public, "deserialize_manuscript_content", lambda _raw: {"text": "chapter text", "html": "<p>x</p>"})
    monkeypatch.setattr(public, "download_book", lambda _key: b"chapter")
    monkeypatch.setattr(public, "get_presigned_url", lambda key: f"https://signed/{key}")

    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, is_public=True, hidden_at=None, archived_at=None, title="Book", total_chapters=5)
    chapter = SimpleNamespace(number=2, title="Two", description="Desc", s3_key="chapters/2.txt")
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=chapter)])

    payload = await public.get_public_chapter(book_id, 2, db=db)

    assert payload["text_url"] == "https://signed/chapters/2.txt"
    assert payload["text_content"] == "chapter text"
    assert cached["args"][2] == 3600


@pytest.mark.asyncio
async def test_create_public_book_manual_requires_chapters():
    body = PublicBookManualIn(title="Title", chapters=[])
    with pytest.raises(HTTPException) as exc:
        await public.create_public_book_manual(body=body, db=_FakeDB(), current_user=SimpleNamespace(id=uuid.uuid4()))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_public_book_manual_persists_book_and_chapters(monkeypatch):
    uploaded = []
    invalidated = []
    charged = {}
    monkeypatch.setattr(public, "upload_text", lambda key, text: uploaded.append((key, text)))
    monkeypatch.setattr(public, "count_tokens", lambda text: len(text.split()))
    async def _fake_charge(_db, _user, *, source_id, metadata):
        charged["source_id"] = source_id
        charged["metadata"] = metadata

    async def _fake_cache_del(key):
        invalidated.append(key)

    monkeypatch.setattr(public, "cache_del", _fake_cache_del)
    monkeypatch.setattr(public, "charge_public_share_points", _fake_charge)
    user = SimpleNamespace(id=uuid.uuid4())
    body = PublicBookManualIn(
        title="Title",
        author="Author",
        genre="Genre",
        description="Desc",
        chapters=[
            PublicChapterIn(title="One", text="alpha beta", description="D1"),
            PublicChapterIn(title="Two", text="gamma", description="D2"),
        ],
    )
    db = _FakeDB()

    payload = await public.create_public_book_manual(body=body, db=db, current_user=user)

    book = db.added[0]
    assert payload["visibility"] == "public"
    assert book.total_chapters == 2
    assert book.total_tokens == 3
    assert len(uploaded) == 2
    assert charged["metadata"]["entrypoint"] == "manual_public_book"
    assert invalidated == [public.key_public_books()]


@pytest.mark.asyncio
async def test_create_public_book_manual_surfaces_insufficient_points(monkeypatch):
    async def _fake_charge(*_args, **_kwargs):
        raise ValueError("Public sharing costs 10 points.")

    monkeypatch.setattr(public, "charge_public_share_points", _fake_charge)

    with pytest.raises(HTTPException) as exc:
        await public.create_public_book_manual(
            body=PublicBookManualIn(
                title="Title",
                chapters=[PublicChapterIn(title="One", text="alpha")],
            ),
            db=_FakeDB(),
            current_user=SimpleNamespace(id=uuid.uuid4()),
        )

    assert exc.value.status_code == 400
    assert "Public sharing costs 10 points." in exc.value.detail


@pytest.mark.asyncio
async def test_append_public_chapter_raises_for_foreign_book():
    book = SimpleNamespace(user_id=uuid.uuid4(), is_public=True)
    db = _FakeDB(get_values=[book])
    body = PublicChapterIn(title="Title", text="text", description="desc")

    with pytest.raises(HTTPException) as exc:
        await public.append_public_chapter(uuid.uuid4(), body=body, db=db, current_user=SimpleNamespace(id=uuid.uuid4()))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_append_public_chapter_updates_counts_and_invalidates_cache(monkeypatch):
    invalidated = []
    monkeypatch.setattr(public, "upload_text", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(public, "count_tokens", lambda text: len(text.split()))

    async def _fake_cache_del(key):
        invalidated.append(key)

    monkeypatch.setattr(public, "cache_del", _fake_cache_del)
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, is_public=True, total_tokens=2, total_chapters=1)
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar_one=2)])
    body = PublicChapterIn(title="Next", text="one two three", description="desc")

    payload = await public.append_public_chapter(book_id, body=body, db=db, current_user=SimpleNamespace(id=user_id))

    assert payload == {"book_id": str(book_id), "chapter_number": 2, "saved": True}
    assert book.total_chapters == 2
    assert book.total_tokens == 5
    assert len(invalidated) == 3
