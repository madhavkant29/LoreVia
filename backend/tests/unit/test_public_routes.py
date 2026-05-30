from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import public
from app.schemas.public import PublicBookManualIn, PublicBookShareBody, PublicChapterIn
from app.utils import public_utils


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


async def _async_empty_analytics_map(*_args, **_kwargs):
    return {}


async def _async_empty_book_analytics(*_args, **_kwargs):
    return public.PublicBookAnalyticsOut()


@pytest.fixture(autouse=True)
def _enable_public_mode(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", True, raising=False)


def test_public_mode_guard_blocks_when_disabled(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", False, raising=False)
    with pytest.raises(HTTPException) as exc:
        public.ensure_public_mode_enabled()
    assert exc.value.status_code == 503


def test_public_forum_read_guard_blocks_when_status_is_internal(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "internal", raising=False)
    with pytest.raises(HTTPException) as exc:
        public.ensure_public_forum_read_enabled()
    assert exc.value.status_code == 404


def test_public_forum_write_guard_blocks_when_status_is_beta(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "beta", raising=False)
    with pytest.raises(HTTPException) as exc:
        public.ensure_public_forum_write_enabled()
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_public_user_profile_is_not_blocked_by_forum_status(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "internal", raising=False)

    async def _fake_get_public_user_profile(_db, *, username):
        return {
            "user_id": "user-1",
            "username": username,
            "reputation_score": 0,
            "reputation_likes_received": 0,
            "reputation_dislikes_received": 0,
            "trust_level": "Trusted",
            "forum_post_count": 0,
            "forum_comment_count": 0,
            "current_project": None,
            "public_books_count": 0,
            "public_books": [],
            "public_analytics": {
                "total_book_views": 0,
                "total_unique_readers_30d": 0,
                "total_chapter_views": 0,
                "total_public_books": 0,
                "total_chapters": 0,
                "total_words": 0,
                "latest_published_at": None,
                "open_forum_discussions_count": 0,
            },
            "created_at": "2026-05-16T00:00:00Z",
        }

    monkeypatch.setattr(public, "get_public_user_profile", _fake_get_public_user_profile)

    payload = await public.get_public_user_profile_endpoint(username="writer", db=_FakeDB())

    assert payload["username"] == "writer"


@pytest.mark.asyncio
async def test_list_public_beta_forum_posts_returns_cached_payload(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "public", raising=False)
    cached_post = {
        "id": str(uuid.uuid4()),
        "thread_type": "novel",
        "book_id": str(uuid.uuid4()),
        "author_user_id": str(uuid.uuid4()),
        "author_username": "writer",
        "author_reputation_score": 10,
        "author_trust_level": "Trusted",
        "title": "Sky Harbor",
        "author": "Writer",
        "genre": "Fantasy",
        "work_type": "novel",
        "headline": "Need readers",
        "body": "Looking for beta readers for a fantasy manuscript.",
        "desired_beta_reader_count": 5,
        "allow_contact_requests": True,
        "status": "open",
        "viewer_interest_status": None,
        "interest_count": 1,
        "comment_count": 2,
        "rating_summary": {
            "average_rating": 4.5,
            "rating_count": 2,
            "positive_rating_count": 2,
            "neutral_rating_count": 0,
            "negative_rating_count": 0,
        },
        "discoverability_score": 400.0,
        "created_at": "2026-05-16T00:00:00Z",
        "updated_at": "2026-05-16T00:00:00Z",
    }

    async def _fake_cache_get_int(_key, default=1):
        return default

    async def _fake_cache_get(_key):
        return {"items": [cached_post], "total": 1, "page": 1, "page_size": 20, "has_more": False}

    monkeypatch.setattr(public, "cache_get_int", _fake_cache_get_int)
    monkeypatch.setattr(public, "cache_get", _fake_cache_get)

    payload = await public.list_public_beta_forum_posts(db=_FakeDB(), page=1, page_size=20, current_user=None)

    assert payload.items[0].id == cached_post["id"]
    assert payload.total == 1


@pytest.mark.asyncio
async def test_list_public_beta_forum_posts_caches_anonymous_page(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "public", raising=False)
    cached = {}

    async def _fake_cache_get_int(_key, default=1):
        return default

    async def _fake_cache_get(_key):
        return None

    async def _fake_cache_set(key, value, ttl):
        cached["args"] = (key, value, ttl)

    async def _fake_list_public_forum_posts(_db, **kwargs):
        return public.PublicForumPostListOut(items=[], total=3, page=kwargs["page"], page_size=kwargs["page_size"], has_more=True)

    monkeypatch.setattr(public, "cache_get_int", _fake_cache_get_int)
    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    monkeypatch.setattr(public, "list_public_forum_posts", _fake_list_public_forum_posts)

    payload = await public.list_public_beta_forum_posts(db=_FakeDB(), q=" sky ", page=2, page_size=15, current_user=None)

    assert payload.page == 2
    assert payload.page_size == 15
    assert cached["args"][1]["total"] == 3
    assert cached["args"][2] == 120


@pytest.mark.asyncio
async def test_list_public_beta_forum_comments_uses_anonymous_cache(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "public", raising=False)
    comment_payload = {
        "id": str(uuid.uuid4()),
        "post_id": str(uuid.uuid4()),
        "book_id": str(uuid.uuid4()),
        "author_user_id": str(uuid.uuid4()),
        "author_username": "reader",
        "author_reputation_score": 3,
        "author_trust_level": "Trusted",
        "body": "Great premise",
        "like_count": 1,
        "dislike_count": 0,
        "reaction": None,
        "can_edit": False,
        "created_at": "2026-05-16T00:00:00Z",
        "updated_at": "2026-05-16T00:00:00Z",
    }

    async def _fake_cache_get_int(_key, default=1):
        return default

    async def _fake_get_comments_cache(_version, _post_id):
        return [comment_payload]

    monkeypatch.setattr(public, "cache_get_int", _fake_cache_get_int)
    monkeypatch.setattr(public, "get_public_forum_comments_cache", _fake_get_comments_cache)

    payload = await public.list_public_beta_forum_comments(post_id=uuid.uuid4(), db=_FakeDB(), current_user=None)

    assert payload.items[0].body == "Great premise"


@pytest.mark.asyncio
async def test_list_public_beta_forum_comments_caches_anonymous_payload(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "public", raising=False)
    cached = {}

    async def _fake_cache_get_int(_key, default=1):
        return default

    async def _fake_get_comments_cache(_version, _post_id):
        return None

    async def _fake_set_comments_cache(version, post_id, payload):
        cached["args"] = (version, post_id, payload)

    async def _fake_list_comments(_db, *, post_id, current_user):
        return [
            public.PublicForumCommentOut(
                id=str(uuid.uuid4()),
                post_id=str(post_id),
                book_id=None,
                author_user_id=str(uuid.uuid4()),
                author_username="reader",
                author_reputation_score=4,
                author_trust_level="Trusted",
                body="Looks fun",
                like_count=0,
                dislike_count=0,
                reaction=None,
                can_edit=False,
                created_at="2026-05-16T00:00:00Z",
                updated_at="2026-05-16T00:00:00Z",
            )
        ]

    monkeypatch.setattr(public, "cache_get_int", _fake_cache_get_int)
    monkeypatch.setattr(public, "get_public_forum_comments_cache", _fake_get_comments_cache)
    monkeypatch.setattr(public, "set_public_forum_comments_cache", _fake_set_comments_cache)
    monkeypatch.setattr(public, "list_public_forum_comments", _fake_list_comments)

    post_id = uuid.uuid4()
    payload = await public.list_public_beta_forum_comments(post_id=post_id, db=_FakeDB(), current_user=None)

    assert payload.items[0].body == "Looks fun"
    assert cached["args"][1] == str(post_id)


@pytest.mark.asyncio
async def test_list_public_books_returns_cached_payload(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics_map", _async_empty_analytics_map)

    async def _fake_cache_get(_key):
        return [{"id": "cached"}]

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    payload = await public.list_public_books(db=_FakeDB())
    assert payload == [{"id": "cached"}]


@pytest.mark.asyncio
async def test_list_creator_public_uploads_uses_creator_catalog(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics_map", _async_empty_analytics_map)

    async def _fake_list_public_books(**kwargs):
        return [{"id": "creator-book"}]

    monkeypatch.setattr(public, "list_public_books", _fake_list_public_books)

    payload = await public.list_creator_public_uploads(db=_FakeDB(), search="writer")

    assert payload == [{"id": "creator-book"}]


@pytest.mark.asyncio
async def test_public_uploads_analytics_route_returns_overview(monkeypatch):
    async def _fake_build_overview(_db):
        return {"total_public_books": 2}

    monkeypatch.setattr(public, "build_public_uploads_overview", _fake_build_overview)

    payload = await public.get_public_uploads_analytics(db=_FakeDB())

    assert payload["total_public_books"] == 2


@pytest.mark.asyncio
async def test_list_public_books_builds_and_caches_rows(monkeypatch):
    captured = {}

    async def _fake_cache_get(_key):
        return None

    async def _fake_cache_set(key, value, ttl):
        captured["args"] = (key, value, ttl)

    async def _fake_active_forum_post_map(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    monkeypatch.setattr(public, "_active_forum_post_map", _fake_active_forum_post_map)
    monkeypatch.setattr(public, "build_public_book_analytics_map", _async_empty_analytics_map)
    book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        hidden_at=None,
        title="Public Novel",
        author="M. Author",
        genre="Fantasy",
        public_description="Desc",
        format="manual",
        source_kind="public_demo",
        work_type="novel",
        status="ready",
        total_chapters=3,
        copyright_warning=False,
        created_at=datetime.now(UTC),
        archived_at=None,
    )
    db = _FakeDB(execute_values=[_Result(all_rows=[(book, "public_author")])])

    payload = await public.list_public_books(db=db)

    assert payload[0]["title"] == "Public Novel"
    assert payload[0]["author_username"] == "public_author"
    assert captured["args"][1] == payload
    assert captured["args"][2] == 300


@pytest.mark.asyncio
async def test_list_public_books_includes_approved_user_shared_books(monkeypatch):
    async def _fake_cache_get(_key):
        return None

    async def _fake_cache_set(_key, _value, _ttl):
        return None

    async def _fake_active_forum_post_map(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    monkeypatch.setattr(public, "_active_forum_post_map", _fake_active_forum_post_map)
    monkeypatch.setattr(public, "build_public_book_analytics_map", _async_empty_analytics_map)
    demo_book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        hidden_at=None,
        archived_at=None,
        title="Demo",
        author="Demo Author",
        genre="Fantasy",
        public_description="Demo desc",
        format="manual",
        source_kind="public_demo",
        work_type="novel",
        status="ready",
        total_chapters=2,
        copyright_warning=False,
        created_at=datetime.now(UTC),
    )
    shared_book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        hidden_at=None,
        archived_at=None,
        title="Shared",
        author="Shared Author",
        genre="Sci-Fi",
        public_description="Shared desc",
        format="pdf",
        source_kind="user_public_share",
        work_type="novel",
        status="ready",
        total_chapters=5,
        copyright_warning=False,
        created_at=datetime.now(UTC),
        public_share_status="approved",
    )
    db = _FakeDB(execute_values=[_Result(all_rows=[(demo_book, "demo_user"), (shared_book, "shared_user")])])

    payload = await public.list_public_books(db=db)

    assert [item["title"] for item in payload] == ["Demo", "Shared"]


@pytest.mark.asyncio
async def test_get_public_book_returns_cached_payload(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)

    async def _fake_cache_get(_key):
        return {"id": "cached"}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, is_public=True, source_kind="public_demo", hidden_at=None, archived_at=None)
    payload = await public.get_public_book(book_id, db=_FakeDB(get_values=[book]))
    assert payload["id"] == "cached"
    assert payload["analytics"]["book_view_count"] == 0


@pytest.mark.asyncio
async def test_get_public_book_skips_cache_for_user_shared_samples(monkeypatch):
    cache_get_calls = []
    cache_set_calls = []

    async def _fake_cache_get(_key):
        cache_get_calls.append(_key)
        return {"id": "cached"}

    async def _fake_cache_set(*args):
        cache_set_calls.append(args)

    async def _fake_active_forum_post_map(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    monkeypatch.setattr(public, "_active_forum_post_map", _fake_active_forum_post_map)
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        is_public=True,
        source_kind="user_public_share",
        public_share_status="approved",
        hidden_at=None,
        archived_at=None,
        title="Shared Novel",
        author="A. Writer",
        genre="Fantasy",
        public_description="Shared",
        format="pdf",
        work_type="novel",
        status="ready",
        total_chapters=1,
        copyright_warning=False,
        user_id=uuid.uuid4(),
        created_at=datetime.now(UTC),
    )
    author_user = SimpleNamespace(username="shared_writer")
    db = _FakeDB(
        get_values=[book, author_user],
        execute_values=[_Result(all_rows=[(1, "One", "First")])],
    )

    payload = await public.get_public_book(book_id, db=db)

    assert payload["id"] == str(book_id)
    assert cache_get_calls == []
    assert cache_set_calls == []


@pytest.mark.asyncio
async def test_get_public_book_ignores_cached_payload_when_book_is_no_longer_visible(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)

    async def _fake_cache_get(_key):
        return {"id": "cached"}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    hidden_book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        source_kind="public_demo",
        hidden_at="2026-05-16T00:00:00Z",
        archived_at=None,
    )

    with pytest.raises(HTTPException) as exc:
        await public.get_public_book(hidden_book.id, db=_FakeDB(get_values=[hidden_book]))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_public_book_raises_for_missing_or_hidden_book(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)

    async def _fake_cache_get(_key):
        return None

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    db = _FakeDB(get_values=[None])
    with pytest.raises(HTTPException) as exc:
        await public.get_public_book(uuid.uuid4(), db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_public_book_builds_payload(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)

    async def _fake_cache_get(_key):
        return None

    cached = {}

    async def _fake_cache_set(key, value, ttl):
        cached["args"] = (key, value, ttl)

    async def _fake_active_forum_post_map(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    monkeypatch.setattr(public, "_active_forum_post_map", _fake_active_forum_post_map)
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        is_public=True,
        source_kind="public_demo",
        hidden_at=None,
        archived_at=None,
        title="Public Novel",
        author="M. Author",
        genre="Fantasy",
        public_description="Desc",
        format="manual",
        work_type="novel",
        status="ready",
        total_chapters=2,
        copyright_warning=False,
        user_id=uuid.uuid4(),
        created_at=datetime.now(UTC),
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
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)

    async def _fake_cache_get(_key):
        return {"chapter_number": 1}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    book = SimpleNamespace(id=uuid.uuid4(), is_public=True, source_kind="public_demo", hidden_at=None, archived_at=None)
    payload = await public.get_public_chapter(book.id, 1, db=_FakeDB(get_values=[book]))
    assert payload["chapter_number"] == 1


@pytest.mark.asyncio
async def test_get_public_chapter_skips_cache_for_user_shared_samples(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)

    cache_get_calls = []
    cache_set_calls = []

    async def _fake_cache_get(_key):
        cache_get_calls.append(_key)
        return {"chapter_number": 9}

    async def _fake_cache_set(*args):
        cache_set_calls.append(args)

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    monkeypatch.setattr(public, "cache_set", _fake_cache_set)
    monkeypatch.setattr(public, "deserialize_manuscript_content", lambda _raw: {"text": "fresh text", "html": None})
    monkeypatch.setattr(public, "download_book", lambda _key: b"chapter")
    monkeypatch.setattr(public, "get_presigned_url", lambda key: f"https://signed/{key}")

    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        is_public=True,
        source_kind="user_public_share",
        public_share_status="approved",
        hidden_at=None,
        archived_at=None,
        title="Shared Book",
        total_chapters=3,
    )
    chapter = SimpleNamespace(number=2, title="Two", description="Desc", s3_key="chapters/2.txt")
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=chapter)])

    payload = await public.get_public_chapter(book_id, 2, db=db)

    assert payload["chapter_number"] == 2
    assert payload["text_content"] == "fresh text"
    assert cache_get_calls == []
    assert cache_set_calls == []


@pytest.mark.asyncio
async def test_get_public_chapter_ignores_cached_payload_when_book_is_no_longer_visible(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)

    async def _fake_cache_get(_key):
        return {"chapter_number": 1}

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    private_book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=False,
        source_kind="user_public_share",
        hidden_at=None,
        archived_at=None,
        public_share_status="approved",
    )

    with pytest.raises(HTTPException) as exc:
        await public.get_public_chapter(private_book.id, 1, db=_FakeDB(get_values=[private_book]))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_public_chapter_raises_for_missing_book_or_chapter(monkeypatch):
    monkeypatch.setattr(public, "build_public_book_analytics", _async_empty_book_analytics)

    async def _fake_cache_get(_key):
        return None

    monkeypatch.setattr(public, "cache_get", _fake_cache_get)
    db = _FakeDB(get_values=[None])
    with pytest.raises(HTTPException) as exc:
        await public.get_public_chapter(uuid.uuid4(), 1, db=db)
    assert exc.value.status_code == 404

    book = SimpleNamespace(id=uuid.uuid4(), is_public=True, source_kind="public_demo", hidden_at=None, archived_at=None)
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
    book = SimpleNamespace(id=book_id, is_public=True, source_kind="public_demo", hidden_at=None, archived_at=None, title="Book", total_chapters=5)
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
        await public.create_public_book_manual(db=_FakeDB(), body=body, admin_user=SimpleNamespace(id=uuid.uuid4()))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_public_book_manual_persists_book_and_chapters(monkeypatch):
    uploaded = []
    invalidated = []
    monkeypatch.setattr(public_utils, "upload_text", lambda key, text: uploaded.append((key, text)))
    monkeypatch.setattr(public_utils, "count_tokens", lambda text: len(text.split()))

    async def _fake_cache_del(key):
        invalidated.append(key)

    monkeypatch.setattr(public_utils, "cache_del", _fake_cache_del)
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

    payload = await public.create_public_book_manual(db=db, body=body, admin_user=user)

    book = db.added[0]
    assert payload["visibility"] == "public"
    assert payload["public_kind"] == "public_demo"
    assert payload["approval_status"] == "approved"
    assert book.source_kind == "public_demo"
    assert book.total_chapters == 2
    assert book.total_tokens == 3
    assert len(uploaded) == 2
    assert invalidated == [public_utils.key_public_books()]


@pytest.mark.asyncio
async def test_append_public_chapter_raises_for_foreign_book():
    book = SimpleNamespace(user_id=uuid.uuid4(), is_public=True, source_kind="public_demo")
    db = _FakeDB(get_values=[book])
    body = PublicChapterIn(title="Title", text="text", description="desc")

    with pytest.raises(HTTPException) as exc:
        await public.append_public_chapter(db=db, book_id=uuid.uuid4(), body=body, admin_user=SimpleNamespace(id=uuid.uuid4()))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_append_public_chapter_updates_counts_and_invalidates_cache(monkeypatch):
    invalidated = []
    monkeypatch.setattr(public_utils, "upload_text", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(public_utils, "count_tokens", lambda text: len(text.split()))

    async def _fake_cache_del(key):
        invalidated.append(key)

    monkeypatch.setattr(public_utils, "cache_del", _fake_cache_del)
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, is_public=True, source_kind="public_demo", total_tokens=2, total_chapters=1)
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar_one=2)])
    body = PublicChapterIn(title="Next", text="one two three", description="desc")

    payload = await public.append_public_chapter(db=db, book_id=book_id, body=body, admin_user=SimpleNamespace(id=user_id))

    assert payload == {"book_id": str(book_id), "chapter_number": 2, "saved": True}
    assert book.total_chapters == 2
    assert book.total_tokens == 5
    assert len(invalidated) == 3


@pytest.mark.asyncio
async def test_publish_user_shared_book_requires_explicit_confirmation():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        user_id=user_id,
        is_public=False,
        hidden_at=None,
        archived_at=None,
        source_kind="single_upload",
        status="ready",
        public_description=None,
    )

    with pytest.raises(HTTPException) as exc:
            await public.publish_user_shared_book(
                book_id,
                PublicBookShareBody(confirm_public_share=False, description="Share me"),
                db=_FakeDB(get_values=[book]),
                current_user=SimpleNamespace(id=user_id, tier="author"),
            )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_publish_user_shared_book_creates_pending_approval_request(monkeypatch):
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        user_id=user_id,
        is_public=False,
        hidden_at=None,
        archived_at=None,
        source_kind="single_upload",
        status="ready",
        public_description=None,
    )
    db = _FakeDB(get_values=[book])

    payload = await public.publish_user_shared_book(
        book_id,
        PublicBookShareBody(confirm_public_share=True, description="Public draft"),
        db=db,
        current_user=SimpleNamespace(id=user_id, tier="author"),
    )

    assert payload == {
        "book_id": str(book_id),
        "status": "ready",
        "visibility": "private",
        "public_kind": "user_public_share",
        "approval_status": "pending",
        "message": "Public sample request submitted for manual approval.",
    }
    assert book.is_public is False
    assert book.source_kind == "user_public_share"
    assert book.public_description == "Public draft"
    assert book.public_share_status == "pending"


@pytest.mark.asyncio
async def test_publish_user_shared_book_refreshes_copyright_signals_before_request(monkeypatch):
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        user_id=user_id,
        is_public=False,
        hidden_at=None,
        archived_at=None,
        source_kind="single_upload",
        status="ready",
        public_description=None,
        s3_key="books/sample.pdf",
        format="pdf",
        isbn=None,
        copyright_warning=False,
    )
    db = _FakeDB(get_values=[book])

    monkeypatch.setattr(public, "download_book", lambda _key: b"%PDF-1.4 sample")

    async def _fake_evaluate_document_copyright(*, format_name, raw, existing_isbn=None):
        assert format_name == "pdf"
        assert raw == b"%PDF-1.4 sample"
        assert existing_isbn is None
        return {"isbn": "9780306406157", "copyright_warning": True}

    monkeypatch.setattr(public, "evaluate_document_copyright", _fake_evaluate_document_copyright)

    payload = await public.publish_user_shared_book(
        book_id,
        PublicBookShareBody(confirm_public_share=True, description="Public draft"),
        db=db,
        current_user=SimpleNamespace(id=user_id, tier="author"),
    )

    assert payload["approval_status"] == "pending"
    assert book.isbn == "9780306406157"
    assert book.copyright_warning is True


@pytest.mark.asyncio
async def test_publish_user_shared_book_resubmits_approved_book_for_fresh_review():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        user_id=user_id,
        is_public=False,
        hidden_at=None,
        archived_at=None,
        source_kind="user_public_share",
        status="ready",
        public_description="Old",
        public_share_status="approved",
    )
    db = _FakeDB(get_values=[book])

    payload = await public.publish_user_shared_book(
        book_id,
        PublicBookShareBody(confirm_public_share=True, description="Approved draft"),
        db=db,
        current_user=SimpleNamespace(id=user_id, tier="author"),
    )

    assert payload == {
        "book_id": str(book_id),
        "status": "ready",
        "visibility": "private",
        "public_kind": "user_public_share",
        "approval_status": "pending",
        "message": "Public sample request submitted for manual approval.",
    }
    assert book.is_public is False
    assert book.public_share_status == "pending"
    assert book.public_description == "Approved draft"


@pytest.mark.asyncio
async def test_unpublish_user_shared_book_clears_prior_approval_state(monkeypatch):
    invalidated = []

    async def _fake_cache_del(key):
        invalidated.append(key)

    monkeypatch.setattr(public, "cache_del", _fake_cache_del)
    user_id = uuid.uuid4()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        is_public=True,
        source_kind="user_public_share",
        public_share_status="approved",
        public_share_requested_at="2026-05-16T00:00:00Z",
        public_share_approved_at="2026-05-16T00:00:00Z",
        public_share_approved_by_user_id=uuid.uuid4(),
        status="ready",
    )
    db = _FakeDB(get_values=[book])

    payload = await public.unpublish_user_shared_book(
        book.id,
        db=db,
        current_user=SimpleNamespace(id=user_id),
    )

    assert book.is_public is False
    assert book.public_share_status == "not_requested"
    assert book.public_share_requested_at is None
    assert book.public_share_approved_at is None
    assert book.public_share_approved_by_user_id is None
    assert payload["approval_status"] == "not_requested"
