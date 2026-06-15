from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1.router import api_router
from app.api.v1.routes import books
from app.api.v1.routes.books import imports
from app.utils.llm_usage_utils import LlmUsageSummary
from app.schemas.books import (
    BookModeBody,
    BookNoteBody,
    CharacterCreateBody,
    CharacterCandidateAttachBody,
    CharacterMergeBody,
    CharacterPartitionBody,
    CharacterPartitionTargetBody,
    RelationshipCandidateAcceptBody,
    RelationshipCandidateAttachBody,
    CharacterUpdateBody,
    CharacterEventOut,
    ChapterConsistencyReport,
    MajorEventOut,
    NovelPrefaceBody,
    NovelSettingsBody,
    VaultNoteBody,
    ReadabilityRequestBody,
    RelationshipCreateBody,
    RelationshipUpdateBody,
    SeriesBody,
    SeriesBookStatusBody,
    SeriesCreateBody,
    SeriesMembershipBody,
    WriterWorkspaceBody,
)


def test_books_collection_route_accepts_no_trailing_slash():
    paths = {
        route.path
        for route in api_router.routes
        if "GET" in getattr(route, "methods", set())
    }

    assert "/books" in paths
    assert "/books/" in paths


class _ScalarList:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


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

    def scalar_one_or_none(self):
        return self._scalar


class _FakeDB:
    def __init__(self, *, get_values=None, execute_values=None, scalar_values=None):
        self._get_values = list(get_values or [])
        self._execute_values = list(execute_values or [])
        self._scalar_values = list(scalar_values or [])
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshes = []

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0)

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)

    async def scalar(self, *_args, **_kwargs):
        return self._scalar_values.pop(0)

    def add(self, value):
        self.added.append(value)
        if getattr(value, "id", None) is None:
            value.id = uuid.uuid4()
        if hasattr(value, "created_at") and getattr(value, "created_at", None) is None:
            value.created_at = datetime.now(UTC)

    async def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshes.append(value)

    async def delete(self, value):
        self.deleted.append(value)


def _async_value(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner


def _user(*, user_id: uuid.UUID | None = None, tier: str = "author"):
    return SimpleNamespace(id=user_id or uuid.uuid4(), tier=tier)


def _book(*, user_id: uuid.UUID, mode: str = "author", **overrides):
    data = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "title": "Atlas",
        "author": "M. Author",
        "genre": "Fantasy",
        "format": "txt",
        "work_type": "novel",
        "status": "ready",
        "mode": mode,
        "source_kind": "single_upload",
        "preserve_chapter_numbers": False,
        "preserve_source_chapters": False,
        "cover_s3_key": None,
        "total_chapters": 3,
        "total_tokens": 0,
        "total_words": 0,
        "is_truncated": False,
        "is_public": False,
        "public_description": None,
        "copyright_warning": False,
        "primary_series_id": None,
        "series_name": None,
        "series_order": None,
        "writer_workspace": {},
        "archived_at": None,
        "hidden_at": None,
        "created_at": datetime.now(UTC),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _upload(name: str, raw: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(raw))


def _workspace_payload():
    return {
        "word_count_goals": {"chapter_target": None, "book_target": None, "session_target": None},
        "goal_calendar": [],
        "corkboard_cards": [],
        "templates": [],
        "revision_board": {"items": [], "last_generated_at": None},
        "publishing": {
            "active_preset": "standard_manuscript",
            "trim_size": "6x9",
            "include_title_page": True,
            "mirror_margins": True,
        },
        "manuscript_front_matter": {
            "author_name": "",
            "pen_name": "",
            "contact_email": "",
            "contact_phone": "",
            "contact_address": "",
            "title": "",
            "subtitle": "",
            "header_last_name": "",
            "header_title": "",
            "approximate_word_count_override": None,
            "dedication": "",
            "acknowledgments": "",
            "epigraph": "",
            "prologue": "",
            "include_dedication": False,
            "include_acknowledgments": False,
            "include_epigraph": False,
            "include_prologue": False,
        },
    }


@pytest.mark.asyncio
async def test_books_helpers_cover_clean_upload_magic_and_event_normalization():
    assert books._clean_text(" <b>Hello</b> ") == "Hello"
    assert books._clean_optional_text("  ") is None

    upload = _upload("sample.txt", b"chapter text")
    assert await books._read_upload_bounded(upload, 32, "Book file") == b"chapter text"

    oversized = _upload("big.txt", b"x" * 9)
    with pytest.raises(HTTPException) as exc:
        await books._read_upload_bounded(oversized, 4, "Book file")
    assert exc.value.status_code == 413

    assert books._validate_cover_magic(b"\xff\xd8\xffpayload")[0] == "jpg"
    assert books._validate_cover_magic(b"RIFF1234WEBPrest")[0] == "webp"
    with pytest.raises(HTTPException) as exc:
        books._validate_cover_magic(b"<svg></svg>")
    assert exc.value.status_code == 400

    major = books._normalize_book_major_event(
        chapter_number=2,
        chapter_title="Storm",
        event={"event_title": "Key Falls", "description": "The silver key drops.", "involved_characters": ["a"]},
        character_names_by_id={"a": "Iris"},
    )
    assert major["involved_character_names"] == ["Iris"]

    character = SimpleNamespace(id=uuid.uuid4(), name="Iris", first_chapter=1, role="mc")
    event = books._normalize_book_character_event(
        character=character,
        event={"event": "Learns truth", "impact": "Shift", "importance": 7, "growth_direction": "up"},
    )
    assert event["character_name"] == "Iris"
    assert event["growth_direction"] == "up"


@pytest.mark.asyncio
async def test_upload_book_endpoint_validates_and_persists(monkeypatch):
    user = _user()

    with pytest.raises(HTTPException) as exc:
        await books.upload_book_endpoint(
            file=_upload("", b"payload"),
            title="Atlas",
            db=_FakeDB(),
            current_user=user,
            __=None,
        )
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        await books.upload_book_endpoint(
            file=_upload("atlas.txt", b"payload"),
            title="Atlas",
            visibility="bad",
            db=_FakeDB(),
            current_user=user,
            __=None,
        )
    assert exc.value.detail == "Invalid visibility"

    with pytest.raises(HTTPException) as exc:
        await books.upload_book_endpoint(
            file=_upload("atlas.txt", b"payload"),
            title="Atlas",
            visibility="public",
            db=_FakeDB(),
            current_user=user,
            __=None,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Main upload flow only supports private manuscripts. Use the explicit public-sharing route after upload."

    uploaded = {}
    notified = {}
    queued = {}

    def _fake_require_author_access(current_user):
        notified["author_id"] = current_user.id

    async def _fake_resolve_series(_db, _user_id, _series_ids):
        return [SimpleNamespace(id=uuid.uuid4(), name="Saga")]

    monkeypatch.setattr(books, "require_author_access", _fake_require_author_access)
    monkeypatch.setattr(books, "resolve_upload_format_and_work_type", lambda *_args: ("txt", "novel"))
    monkeypatch.setattr(books, "resolve_owned_series_ids", _fake_resolve_series)
    monkeypatch.setattr(books, "check_upload_limit", _async_value(None))
    monkeypatch.setattr(books.storage, "upload_book_bytes", lambda raw, owner, filename: uploaded.setdefault("book", (raw, owner, filename)) or "books/mock.txt")
    monkeypatch.setattr(books.storage, "upload_binary", lambda key, raw, content_type: uploaded.setdefault("cover", (key, raw, content_type)) or key)
    monkeypatch.setattr(books, "build_upload_processing_notification", lambda book, mode, size: SimpleNamespace(book_id=book.id, mode=mode, size=size))
    monkeypatch.setattr(books, "queue_for_user", lambda *_args: "extraction")
    monkeypatch.setattr(books.process_book_task, "apply_async", lambda *args, **kwargs: queued.update({"args": args, "kwargs": kwargs}))

    db = _FakeDB()
    payload = await books.upload_book_endpoint(
        file=_upload("atlas.txt", b"chapter text"),
        cover_file=_upload("cover.png", b"\x89PNGpayload"),
        title=" Atlas ",
        genre=" Fantasy ",
        author=" M. Author ",
        series_ids=["1"],
        visibility="private",
        description=" Desc ",
        mode="author",
        auto_extract_cover="false",
        preserve_chapter_numbers="true",
        preserve_source_chapters="true",
        db=db,
        current_user=user,
        __=None,
    )

    book = next(item for item in db.added if item.__class__.__name__ == "Book")
    assert payload["status"] == "processing"
    assert payload["visibility"] == "private"
    assert book.is_public is False
    assert book.mode == "author"
    assert book.preserve_chapter_numbers is True
    assert book.preserve_source_chapters is True
    assert uploaded["book"][0] == b"chapter text"
    assert uploaded["cover"][2] == "image/png"
    assert queued["kwargs"]["queue"] == "extraction"
    assert db.commits == 2


@pytest.mark.asyncio
async def test_upload_book_endpoint_rejects_disguised_pdf(monkeypatch):
    user = _user()

    monkeypatch.setattr(books, "resolve_owned_series_ids", _async_value([]))
    monkeypatch.setattr(books, "check_upload_limit", _async_value(None))

    with pytest.raises(HTTPException) as exc_info:
        await books.upload_book_endpoint(
            file=_upload("atlas.pdf", b"<html>nope</html>"),
            title="Atlas",
            visibility="private",
            mode="reader",
            work_type="novel",
            db=_FakeDB(),
            current_user=user,
            __=None,
        )

    assert exc_info.value.status_code == 400
    assert "valid PDF" in exc_info.value.detail


@pytest.mark.asyncio
async def test_free_users_cannot_upload_or_preview_manuscripts(monkeypatch):
    monkeypatch.setattr("app.utils.billing_utils.has_authoring_access", lambda *_args, **_kwargs: False)
    user = SimpleNamespace(
        id=uuid.uuid4(),
        tier="free",
        created_at=datetime.now(UTC) - timedelta(days=20),
    )

    with pytest.raises(HTTPException) as upload_exc:
        await books.upload_book_endpoint(
            file=_upload("atlas.txt", b"chapter text"),
            title="Atlas",
            db=_FakeDB(),
            current_user=user,
            __=None,
        )

    with pytest.raises(HTTPException) as preview_exc:
        await imports.preview_upload_endpoint(
            file=_upload("atlas.txt", b"chapter text"),
            db=_FakeDB(),
            current_user=user,
            __=None,
        )

    assert upload_exc.value.status_code == 403
    assert preview_exc.value.status_code == 403
    assert "requires an Author or Architect plan" in upload_exc.value.detail
    assert "requires an Author or Architect plan" in preview_exc.value.detail


@pytest.mark.asyncio
async def test_update_mode_and_events_routes(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="reader", source_kind=None)
    db = _FakeDB()
    cache_dirty = {"calls": []}

    async def _fake_book_out(_db, current_book, _user_id, collaborator=None):
        return {
            "id": str(current_book.id),
            "mode": current_book.mode,
            "collaboration_role": getattr(collaborator, "role", None),
        }

    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "book_out", _fake_book_out)
    monkeypatch.setattr(books, "mark_book_cache_dirty", lambda book_id: cache_dirty["calls"].append(book_id) or _async_value(None)())

    with pytest.raises(HTTPException) as exc:
        await books.update_book_mode(book.id, BookModeBody(mode="bad"), db=db, current_user=user)
    assert exc.value.detail == "Invalid mode"

    await books.update_book_mode(book.id, BookModeBody(mode="author"), db=db, current_user=user)
    assert book.mode == "author"
    assert book.source_kind == "single_upload"
    assert cache_dirty["calls"] == [str(book.id)]

    character = SimpleNamespace(
        id=uuid.uuid4(),
        name="Iris",
        role="mc",
        first_chapter=1,
        growth_events=[{"event": "Learns truth", "chapter_number": 2, "impact_score": 6}],
    )
    event_rows = [
        (
            2,
            "Storm",
            [{"event_title": "Key Falls", "description": "The silver key drops.", "involved_characters": [str(character.id)]}],
        )
    ]
    db = _FakeDB(get_values=[book], execute_values=[_Result(all_rows=event_rows), _Result(scalars=[character])])
    payload = await books.get_book_events(book.id, db=db, current_user=user)
    assert payload.major_events[0].event_title == "Key Falls"
    assert payload.character_events[0].character_name == "Iris"

    progress = SimpleNamespace(current_chapter=1)
    filtered = SimpleNamespace(
        major_events=[
            MajorEventOut(chapter_number=1, chapter_title=None, event_title="Seen", description="", importance=5),
            MajorEventOut(chapter_number=3, chapter_title=None, event_title="Hidden", description="", importance=5),
        ],
        character_events=[
            CharacterEventOut(
                character_id=str(uuid.uuid4()),
                character_name="Iris",
                chapter_number=1,
                event_title="Beat",
                description="",
                impact_score=3,
            ),
            CharacterEventOut(
                character_id=str(uuid.uuid4()),
                character_name="Vale",
                chapter_number=4,
                event_title="Spoiler",
                description="",
                impact_score=7,
            ),
        ],
    )
    monkeypatch.setattr(books, "get_book_events", _async_value(filtered))
    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=progress)])
    payload = await books.get_reader_safe_book_events(book.id, chapter=None, db=db, current_user=user)
    assert [event.event_title for event in payload.major_events] == ["Seen"]
    assert [event.character_name for event in payload.character_events] == ["Iris"]


@pytest.mark.asyncio
async def test_update_mode_blocks_all_collaborators(monkeypatch):
    owner = uuid.uuid4()
    collaborator_user = _user(tier="free")
    book = _book(user_id=owner, mode="reader", source_kind=None)
    db = _FakeDB()
    editor_share = SimpleNamespace(role="coauthor", permission_can_edit_manuscript=True, permissions={"can_edit_manuscript": True}, scope={})
    read_only_share = SimpleNamespace(role="reader_only", permission_can_edit_manuscript=False, permissions={"can_edit_manuscript": False}, scope={})
    cache_dirty = {"calls": []}

    async def _fake_book_out(_db, current_book, _user_id, collaborator=None):
        return {
            "id": str(current_book.id),
            "mode": current_book.mode,
            "collaboration_role": getattr(collaborator, "role", None),
        }

    monkeypatch.setattr(books, "book_out", _fake_book_out)
    monkeypatch.setattr(books, "mark_book_cache_dirty", lambda book_id: cache_dirty["calls"].append(book_id) or _async_value(None)())

    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, editor_share)))
    with pytest.raises(HTTPException) as exc:
        await books.update_book_mode(book.id, BookModeBody(mode="author"), db=db, current_user=collaborator_user)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Only the book owner can use this route."
    assert cache_dirty["calls"] == []

    book.mode = "reader"
    book.source_kind = None
    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, read_only_share)))
    with pytest.raises(HTTPException) as exc:
        await books.update_book_mode(book.id, BookModeBody(mode="author"), db=db, current_user=collaborator_user)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Only the book owner can use this route."


@pytest.mark.asyncio
async def test_update_mode_allows_owned_book_switch_without_paid_author_plan(monkeypatch):
    user = _user(tier="free")
    book = _book(user_id=user.id, mode="reader", source_kind=None)
    db = _FakeDB()
    cache_dirty = {"calls": []}

    async def _fake_book_out(_db, current_book, _user_id, collaborator=None):
        return {
            "id": str(current_book.id),
            "mode": current_book.mode,
            "collaboration_role": getattr(collaborator, "role", None),
        }

    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "book_out", _fake_book_out)
    monkeypatch.setattr(books, "mark_book_cache_dirty", lambda book_id: cache_dirty["calls"].append(book_id) or _async_value(None)())

    payload = await books.update_book_mode(book.id, BookModeBody(mode="author"), db=db, current_user=user)
    assert payload["mode"] == "author"
    assert payload["collaboration_role"] is None
    assert book.mode == "author"
    assert book.source_kind == "single_upload"
    assert cache_dirty["calls"] == [str(book.id)]


@pytest.mark.asyncio
async def test_import_manuscript_content_text_flow_updates_progress_and_reports(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="reader", total_chapters=0)
    chapter = SimpleNamespace(id=uuid.uuid4(), s3_key="chapters/1.json", title="Chapter 1")
    added_words = {}
    cache_invalidated = {"called": 0}

    async def _fake_process(*_args, **_kwargs):
        return None

    async def _fake_replace(*_args, **_kwargs):
        return None

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "next_chapter_number", _async_value(1))
    monkeypatch.setattr(books, "normalize_book_work_type", lambda *_args, **_kwargs: "novel")
    monkeypatch.setattr(books, "clean_manuscript_html", lambda value: value.strip())
    monkeypatch.setattr(
        books,
        "normalize_imported_chapters",
        lambda chapters, **_kwargs: [
            {"number": 1, "title": chapters[0]["title"], "text": chapters[0]["text"], "html": chapters[0]["html"], "description": None}
        ],
    )
    monkeypatch.setattr(books, "_process_chapter", _fake_process)
    monkeypatch.setattr(books, "extract_novel_scene_candidates", lambda **_kwargs: [{"chapter_number": 1}])
    monkeypatch.setattr(books, "replace_chapter_novel_scenes", _fake_replace)
    monkeypatch.setattr(books, "add_daily_word_progress", lambda _user, words: added_words.setdefault("count", words))
    monkeypatch.setattr(books.storage, "download_book", lambda _key: b"stored text")
    monkeypatch.setattr(books, "deserialize_manuscript_content", lambda _raw: {"text": "stored chapter text"})
    monkeypatch.setattr(books, "sync_chapter_content_from_novel_scenes", _fake_replace)
    dispatched_tasks: list[dict] = []

    def _fake_apply_async(*_args, **kwargs):
        dispatched_tasks.append(kwargs)
        return SimpleNamespace(id="analysis-task-1")

    monkeypatch.setattr(books.analyse_chapter_task, "apply_async", _fake_apply_async)

    async def _fake_invalidate(*_args, **_kwargs):
        cache_invalidated["called"] += 1

    monkeypatch.setattr(books, "invalidate_advisor_caches_for_book", _fake_invalidate)

    db = _FakeDB(
        execute_values=[
            _Result(scalar=None),
            _Result(scalar=chapter),
            _Result(scalar=None),
            _Result(scalar=chapter),
            _Result(all_rows=[]),
        ],
        scalar_values=[1],
    )
    payload = await books.import_manuscript_content(
        book.id,
        text="A new beginning",
        html=" <p>A new beginning</p> ",
        title="Opening",
        files=None,
        work_type=None,
        chapter_number=None,
        replace_existing="false",
        chunk_long_documents="false",
        split_into_chapters="true",
        db=db,
        current_user=user,
        _=None,
    )

    assert payload.imported_chapters == [1]
    assert payload.status == "imported"
    assert payload.chapters_created == 1
    assert payload.analysis_dispatched == 1
    assert payload.analysis_tasks == [
        {
            "chapter_id": str(chapter.id),
            "chapter_number": 1,
            "task_id": "analysis-task-1",
        }
    ]
    assert payload.chapter_content_versions == {1: 1}
    assert payload.mode == "author"
    assert payload.chapter_reports == []
    assert dispatched_tasks == [
        {
            "args": [str(chapter.id), str(book.id)],
            "kwargs": {"is_reprocessing": False},
            "queue": "analysis",
        }
    ]
    assert added_words["count"] == 3
    assert cache_invalidated["called"] == 1
    assert any(item.__class__.__name__ == "ReadingProgress" for item in db.added)


@pytest.mark.asyncio
async def test_import_manuscript_content_rejects_stale_content_version(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="author", total_chapters=1)
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        number=1,
        title="Opening",
        s3_key="chapters/1.json",
        word_count=120,
        content_version=4,
    )

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "next_chapter_number", _async_value(2))
    monkeypatch.setattr(books, "normalize_book_work_type", lambda *_args, **_kwargs: "novel")
    monkeypatch.setattr(
        books,
        "normalize_imported_chapters",
        lambda chapters, **_kwargs: [
            {"number": 1, "title": chapters[0]["title"], "text": chapters[0]["text"], "html": chapters[0]["html"], "description": None}
        ],
    )

    db = _FakeDB(execute_values=[_Result(scalar=existing)])

    with pytest.raises(HTTPException) as exc_info:
        await books.import_manuscript_content(
            book.id,
            text="Updated opening",
            html="<p>Updated opening</p>",
            title="Opening",
            files=None,
            work_type=None,
            chapter_number=1,
            replace_existing="true",
            expected_content_version=3,
            chunk_long_documents="false",
            split_into_chapters="true",
            db=db,
            current_user=user,
            _=None,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["chapter_number"] == 1
    assert exc_info.value.detail["current_content_version"] == 4


@pytest.mark.asyncio
async def test_import_manuscript_content_carries_retained_media_references_on_replace(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="author", total_chapters=1, is_editor_project=True)
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        number=1,
        title="Opening",
        s3_key="chapters/1.json",
        word_count=2,
        content_version=1,
    )
    existing_media = SimpleNamespace(
        marker="[[IMAGE:kept]]",
        asset_type="image",
        content_type="image/png",
        caption="Kept map",
        sort_order=0,
        storage_key="chapter-media/book/kept-map.png",
    )
    captured: dict[str, object] = {}

    async def _fake_persist(_db, _book, **kwargs):
        captured["images"] = kwargs["images"]
        return SimpleNamespace(id=uuid.uuid4(), number=kwargs["chapter_number"])

    async def _noop(*_args, **_kwargs):
        return None

    async def _fake_auto_reprocess(*_args, **_kwargs):
        return False, 0, 0

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "next_chapter_number", _async_value(2))
    monkeypatch.setattr(books, "normalize_book_work_type", lambda *_args, **_kwargs: "novel")
    monkeypatch.setattr(books, "deserialize_manuscript_content", lambda _raw: {"text": "Old body"})
    monkeypatch.setattr(books.storage, "download_book", lambda _key: b'{"text":"Old body"}')
    monkeypatch.setattr(imports, "snapshot_chapter_version", _async_value(SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr(imports, "persist_editor_chapter_content", _fake_persist)
    monkeypatch.setattr(books, "extract_novel_scene_candidates", lambda **_kwargs: [])
    monkeypatch.setattr(books, "replace_chapter_novel_scenes", _noop)
    monkeypatch.setattr(books, "sync_chapter_content_from_novel_scenes", _noop)
    monkeypatch.setattr(books, "invalidate_advisor_caches_for_book", _noop)
    monkeypatch.setattr(
        "app.services.editor_project_service.maybe_auto_reprocess_editor_project",
        _fake_auto_reprocess,
    )

    db = _FakeDB(
        execute_values=[
            _Result(scalar=existing),
            _Result(scalars=[existing_media]),
            _Result(scalar=None),
        ],
        scalar_values=[1],
    )
    payload = await books.import_manuscript_content(
        book.id,
        text="New body",
        html='<p>New body</p><p><img src="/api/v1/reader/media/1" alt="[[IMAGE:kept]]"></p>',
        title="Opening",
        files=None,
        work_type=None,
        chapter_number=1,
        replace_existing="true",
        expected_content_version=1,
        chunk_long_documents="false",
        split_into_chapters="true",
        db=db,
        current_user=user,
        _=None,
    )

    assert payload.imported_chapters == [1]
    assert db.deleted == [existing]
    assert captured["images"] == [
        {
            "marker": "[[IMAGE:kept]]",
            "asset_type": "image",
            "content_type": "image/png",
            "caption": "Kept map",
            "sort_order": 0,
            "storage_key": "chapter-media/book/kept-map.png",
        }
    ]


@pytest.mark.asyncio
async def test_import_manuscript_content_rejects_author_titles_over_four_words(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="author", total_chapters=1)

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        await books.import_manuscript_content(
            book.id,
            text="Updated opening",
            html="<p>Updated opening</p>",
            title="The Last Ember Gate Opens",
            files=None,
            work_type=None,
            chapter_number=1,
            replace_existing="true",
            expected_content_version=1,
            chunk_long_documents="false",
            split_into_chapters="true",
            db=_FakeDB(),
            current_user=user,
            _=None,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Chapter title must be between 1 and 4 words."


@pytest.mark.asyncio
async def test_import_manuscript_content_preserves_source_chapter_count_for_long_file_chapters(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="reader", total_chapters=0, preserve_source_chapters=True)
    long_text = "\n\n".join([
        " ".join(["opening"] * 1800),
        " ".join(["middle"] * 1800),
    ])
    parsed_chapters = [
        {"number": 1, "title": "I", "text": long_text},
        {"number": 2, "title": "II", "text": "Second chapter text."},
        {"number": 3, "title": "III", "text": "Third chapter text."},
    ]
    chapter_rows = [
        SimpleNamespace(id=uuid.uuid4(), s3_key="chapters/1.json", title="I"),
        SimpleNamespace(id=uuid.uuid4(), s3_key="chapters/2.json", title="II"),
        SimpleNamespace(id=uuid.uuid4(), s3_key="chapters/3.json", title="III"),
    ]
    processed_numbers: list[int] = []

    async def _fake_process(_db, _book, payload):
        processed_numbers.append(int(payload["number"]))
        return None

    async def _fake_replace(*_args, **_kwargs):
        return None

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "next_chapter_number", _async_value(1))
    monkeypatch.setattr(books, "normalize_book_work_type", lambda *_args, **_kwargs: "novel")
    monkeypatch.setattr(
        books,
        "parse_book_upload_for_ingestion",
        _async_value({"chapters": parsed_chapters, "screenplay_payload": None, "parser_diagnostics": None}),
    )
    monkeypatch.setattr(books, "_process_chapter", _fake_process)
    monkeypatch.setattr(books, "extract_novel_scene_candidates", lambda **_kwargs: [])
    monkeypatch.setattr(books, "replace_chapter_novel_scenes", _fake_replace)
    monkeypatch.setattr(books, "add_daily_word_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books.storage, "download_book", lambda _key: b"stored text")
    monkeypatch.setattr(books, "deserialize_manuscript_content", lambda _raw: {"text": "stored chapter text"})
    monkeypatch.setattr(books, "sync_chapter_content_from_novel_scenes", _fake_replace)
    monkeypatch.setattr(books, "invalidate_advisor_caches_for_book", _async_value(None))
    monkeypatch.setattr(books.analyse_chapter_task, "apply_async", lambda *_args, **_kwargs: None)

    db = _FakeDB(
        execute_values=[
            _Result(scalar=None),
            *(_Result(scalar=chapter) for chapter in chapter_rows),
            *(_Result(all_rows=[]) for _ in chapter_rows),
        ],
        scalar_values=[3],
    )
    payload = await books.import_manuscript_content(
        book.id,
        text=None,
        html=None,
        title=None,
            files=[_upload("story.pdf", b"%PDF-1.4\nmock body\n%%EOF")],
        work_type=None,
        chapter_number=None,
        replace_existing="false",
        chunk_long_documents="true",
        split_into_chapters="true",
        db=db,
        current_user=user,
        _=None,
    )

    assert processed_numbers == [1, 2, 3]
    assert payload.imported_chapters == [1, 2, 3]
    assert payload.total_chapters == 3


@pytest.mark.asyncio
async def test_import_manuscript_content_preserves_images_and_extracts_pdf_cover(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="reader", total_chapters=0, cover_s3_key=None)
    chapter = SimpleNamespace(id=uuid.uuid4(), s3_key="chapters/1.json", title="Opening")
    processed_payloads: list[dict] = []
    uploaded_cover: dict[str, object] = {}

    async def _fake_process(_db, _book, payload):
        processed_payloads.append(payload)
        return None

    async def _fake_replace(*_args, **_kwargs):
        return None

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "next_chapter_number", _async_value(1))
    monkeypatch.setattr(books, "normalize_book_work_type", lambda *_args, **_kwargs: "novel")
    monkeypatch.setattr(
        books,
        "parse_book_upload_for_ingestion",
        _async_value(
            {
                "chapters": [{
                    "number": 1,
                    "title": "Opening",
                    "text": "Start [[IMAGE:img-1]] End",
                    "images": [{"marker": "[[IMAGE:img-1]]", "bytes": b"img-bytes", "content_type": "image/png"}],
                }],
                "screenplay_payload": None,
                "parser_diagnostics": None,
            }
        ),
    )
    monkeypatch.setattr(books, "_process_chapter", _fake_process)
    monkeypatch.setattr(books, "extract_novel_scene_candidates", lambda **_kwargs: [])
    monkeypatch.setattr(books, "replace_chapter_novel_scenes", _fake_replace)
    monkeypatch.setattr(books, "add_daily_word_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books.storage, "download_book", lambda _key: b"stored text")
    monkeypatch.setattr(books, "deserialize_manuscript_content", lambda _raw: {"text": "stored chapter text"})
    monkeypatch.setattr(books, "sync_chapter_content_from_novel_scenes", _fake_replace)
    monkeypatch.setattr(books, "invalidate_advisor_caches_for_book", _async_value(None))
    monkeypatch.setattr(books.analyse_chapter_task, "apply_async", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda _raw: (b"cover-bytes", "image/png"))

    def _fake_upload_binary(key, raw, content_type=None):
        uploaded_cover.setdefault("payload", (key, raw, content_type))
        return key

    monkeypatch.setattr(
        books.storage,
        "upload_binary",
        _fake_upload_binary,
    )

    db = _FakeDB(
        execute_values=[
            _Result(scalar=None),
            _Result(scalar=chapter),
            _Result(all_rows=[]),
        ],
        scalar_values=[1],
    )
    payload = await books.import_manuscript_content(
        book.id,
        text=None,
        html=None,
        title=None,
        files=[_upload("story.pdf", b"%PDF-1.4\nmock body\n%%EOF")],
        work_type=None,
        chapter_number=None,
        replace_existing="false",
        chunk_long_documents="false",
        split_into_chapters="true",
        db=db,
        current_user=user,
        _=None,
    )

    assert payload.imported_chapters == [1]
    assert processed_payloads[0]["images"][0]["marker"] == "[[IMAGE:img-1]]"
    assert uploaded_cover["payload"][1] == b"cover-bytes"
    assert uploaded_cover["payload"][2] == "image/png"
    assert book.cover_s3_key == uploaded_cover["payload"][0]


@pytest.mark.asyncio
async def test_editor_project_import_persists_parsed_images(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="author", total_chapters=0, is_editor_project=True)
    persisted_payloads: list[dict[str, object]] = []

    async def _fake_persist(*_args, **kwargs):
        persisted_payloads.append(kwargs)
        return SimpleNamespace(id=uuid.uuid4(), number=kwargs["chapter_number"])

    async def _fake_replace(*_args, **_kwargs):
        return None

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "next_chapter_number", _async_value(1))
    monkeypatch.setattr(books, "normalize_book_work_type", lambda *_args, **_kwargs: "novel")
    monkeypatch.setattr(
        books,
        "parse_book_upload_for_ingestion",
        _async_value(
            {
                "chapters": [{
                    "number": 1,
                    "title": "Opening",
                    "text": "Start [[IMAGE:img-1]] End",
                    "images": [{
                        "marker": "[[IMAGE:img-1]]",
                        "bytes": b"img-bytes",
                        "content_type": "image/png",
                        "filename": "image.png",
                    }],
                }],
                "screenplay_payload": None,
                "parser_diagnostics": None,
            }
        ),
    )
    monkeypatch.setattr(imports, "persist_editor_chapter_content", _fake_persist)
    monkeypatch.setattr(books, "extract_novel_scene_candidates", lambda **_kwargs: [])
    monkeypatch.setattr(books, "replace_chapter_novel_scenes", _fake_replace)
    monkeypatch.setattr(books, "add_daily_word_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "invalidate_advisor_caches_for_book", _async_value(None))
    monkeypatch.setattr("app.services.editor_project_service.maybe_auto_reprocess_editor_project", _async_value((False, [], 0)))

    db = _FakeDB(execute_values=[_Result(scalar=None), _Result(scalar=None)], scalar_values=[1])
    payload = await books.import_manuscript_content(
        book.id,
        text=None,
        html=None,
        title=None,
        files=[_upload("story.txt", b"mock body")],
        work_type=None,
        chapter_number=None,
        replace_existing="false",
        chunk_long_documents="false",
        split_into_chapters="true",
        db=db,
        current_user=user,
        _=None,
    )

    assert payload.imported_chapters == [1]
    assert persisted_payloads[0]["images"] == [{
        "marker": "[[IMAGE:img-1]]",
        "bytes": b"img-bytes",
        "content_type": "image/png",
        "filename": "image.png",
    }]


@pytest.mark.asyncio
async def test_series_routes_and_user_stats(monkeypatch):
    user = _user()
    book = _book(user_id=user.id)
    series = SimpleNamespace(id=uuid.uuid4(), user_id=user.id, name="Saga", description="desc", created_at=datetime.now(UTC))
    membership = SimpleNamespace(series_id=series.id, book_id=book.id, position=2, marked_complete=False)
    progress = None

    monkeypatch.setattr(
        books,
        "book_out",
        _async_value(_book(user_id=user.id, id=book.id, title=book.title, marked_complete_in_series=None)),
    )
    monkeypatch.setattr(
        books,
        "build_book_out_list",
        _async_value([_book(user_id=user.id, id=book.id, title=book.title, marked_complete_in_series=None)]),
    )
    monkeypatch.setattr(
        books,
        "build_series_out_list",
        _async_value(
            [
                SimpleNamespace(
                    id=series.id,
                    name=series.name,
                    description=series.description,
                    created_at=series.created_at,
                    books=[SimpleNamespace(id=book.id, marked_complete_in_series=False)],
                )
            ]
        ),
    )
    monkeypatch.setattr(books, "build_single_series_out", _async_value(SimpleNamespace(id=series.id, name=series.name)))
    monkeypatch.setattr(books, "get_owned_series", _async_value(series))
    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "build_series_bible_payload", _async_value({"series_id": str(series.id)}))
    monkeypatch.setattr(books, "compute_words_read_for_books", _async_value({book.id: 1200}))
    monkeypatch.setattr(
        books,
        "build_writing_dashboard_stats",
        _async_value(
            {
                "today": {"words": 1202, "target_words": 1000, "progress_pct": 100},
                "this_week": {"words": 2565, "target_words": 7000, "progress_pct": 37},
                "this_month": {"words": 12165, "target_words": None, "progress_pct": None},
                "this_year": {"words": 59971, "target_words": None, "progress_pct": None},
                "last_24_hours": {"words": 1202, "target_words": None, "progress_pct": None},
                "last_7_days": {"words": 12165, "target_words": None, "progress_pct": None},
                "last_30_days": {"words": 12165, "target_words": None, "progress_pct": None},
                "last_year": {"words": 59971, "target_words": None, "progress_pct": None},
                "heatmap": [{"date": "2026-05-14", "words": 1202}],
                "entries_today": [{"book_id": str(book.id), "chapter_number": 36, "title": "Chapter XXXVI", "words": 763}],
            }
        ),
    )
    monkeypatch.setattr(
        books,
        "calculate_upload_usage_summary",
        _async_value(
            SimpleNamespace(
                manuscript_uploads=3,
                worldbuilding_uploads=4,
                total_uploads=7,
                upload_limit=15,
                uploads_remaining=8,
                upload_limit_unlimited=False,
            )
        ),
    )

    db = _FakeDB(get_values=[book], execute_values=[_Result(scalar=membership)])
    payload = await books.update_book_series(book.id, SeriesBody(series_name="", series_order=None), db=db, current_user=user)
    assert payload.id == book.id
    assert book.primary_series_id is None

    db = _FakeDB(execute_values=[_Result(scalar=None)])
    created = await books.create_series(SeriesCreateBody(name="Saga", description=" Desc "), db=db, current_user=user)
    assert created.name == "Saga"

    db = _FakeDB(execute_values=[_Result(scalar=series)])
    with pytest.raises(HTTPException) as exc:
        await books.create_series(SeriesCreateBody(name="Saga"), db=db, current_user=user)
    assert exc.value.detail == "Series already exists"

    db = _FakeDB(execute_values=[_Result(scalars=[series]), _Result(all_rows=[(membership, book)])])
    listed = await books.list_series(db=db, current_user=user)
    assert listed["items"][0].books[0].marked_complete_in_series is False

    bible = await books.get_series_bible(series.id, db=_FakeDB(), current_user=user)
    assert bible["series_id"] == str(series.id)

    db = _FakeDB(execute_values=[_Result(scalar=None)])
    with pytest.raises(HTTPException) as exc:
        await books.add_book_to_series(series.id, book.id, SeriesMembershipBody(position=0), db=db, current_user=user)
    assert exc.value.detail == "Position must be at least 1"

    db = _FakeDB(execute_values=[_Result(scalar=None)])
    added = await books.add_book_to_series(series.id, book.id, SeriesMembershipBody(position=3), db=db, current_user=user)
    assert added.id == series.id

    membership.marked_complete = False
    db = _FakeDB(execute_values=[_Result(scalar=membership), _Result(scalar=progress)])
    payload = await books.set_series_book_status(
        series.id,
        book.id,
        SeriesBookStatusBody(marked_complete=True),
        db=db,
        current_user=user,
    )
    assert payload.marked_complete_in_series is True
    assert any(item.__class__.__name__ == "ReadingProgress" for item in db.added)

    monkeypatch.setattr(books, "summarize_llm_usage_for_user", _async_value(LlmUsageSummary(
        request_count=12,
        prompt_tokens=3456,
        completion_tokens=789,
        total_tokens=4245,
    )))
    db = _FakeDB(
        execute_values=[_Result(scalars=[book]), _Result(scalars=[SimpleNamespace(book_id=book.id, chapters_read=[1, 2, 3])]), _Result(scalar=2)]
    )
    stats = await books.get_user_stats(db=db, current_user=user)
    assert stats.public.total_words_read == 1200
    assert stats.private.total_uploads == 7
    assert stats.private.worldbuilding_uploads == 4
    assert stats.private.uploads_remaining == 8
    assert stats.private.saved_quotes == 2
    assert stats.private.llm_request_count == 12
    assert stats.private.llm_prompt_tokens == 3456
    assert stats.private.llm_completion_tokens == 789
    assert stats.private.llm_total_tokens == 4245
    assert stats.writing.today.words == 1202
    assert stats.writing.entries_today[0].title == "Chapter XXXVI"


@pytest.mark.asyncio
async def test_book_notes_vault_and_workspace_routes(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, writer_workspace={"goal_calendar": []})
    chapter_version = {"id": "v1", "chapter_number": 1, "created_at": datetime.now(UTC)}
    note = {"id": "n1", "book_id": str(book.id), "body": "note"}
    vault_note = {"path": "Lore/Scene.md", "source": "user_notes", "content": "text", "persisted": True}

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "list_user_notes", _async_value([note]))
    monkeypatch.setattr(books, "book_out", _async_value({"id": str(book.id)}))


    monkeypatch.setattr(books, "list_book_notes", _async_value([note]))
    monkeypatch.setattr(books, "save_book_note", _async_value(note))
    monkeypatch.setattr(books, "delete_book_note", _async_value(None))
    monkeypatch.setattr(books, "list_vault_notes", _async_value([vault_note]))
    monkeypatch.setattr(books, "save_vault_note", _async_value(vault_note))
    monkeypatch.setattr(books, "delete_vault_note", _async_value(None))
    monkeypatch.setattr(books, "import_vault_notes_zip", _async_value([vault_note]))
    monkeypatch.setattr(books, "export_vault_notes_zip", lambda notes: b"zip")
    monkeypatch.setattr(books, "build_vault_graph", lambda notes: {"node_count": len(notes), "edge_count": 0, "nodes": [], "edges": []})
    monkeypatch.setattr(books, "list_vault_note_relations", _async_value({"path": "Lore/Scene.md", "outgoing": [], "incoming": []}))
    monkeypatch.setattr(books, "build_prewriting_check", _async_value({"upcoming_chapter": 4, "active_characters": [], "unresolved_threads": [], "recent_events": [], "alerts": []}))
    monkeypatch.setattr(books, "build_story_health_payload", _async_value({"score": 82, "status": "healthy", "summary": "Good", "metrics": []}))
    monkeypatch.setattr(books, "list_chapter_consistency_reports", _async_value([]))
    monkeypatch.setattr(books, "list_chapter_versions", _async_value([chapter_version]))
    monkeypatch.setattr(books, "build_writer_workspace_response", lambda _current_book: books.WriterWorkspaceOut(**_workspace_payload()))
    monkeypatch.setattr(books, "build_writer_workspace_update", lambda _current_book, updates: {**_workspace_payload(), **updates})
    monkeypatch.setattr(books, "get_book_cache_version", _async_value(0))
    monkeypatch.setattr(books, "get_writer_workspace_cache", _async_value(None))
    monkeypatch.setattr(books, "set_writer_workspace_cache", _async_value(None))
    monkeypatch.setattr(books, "mark_book_cache_dirty", _async_value(1))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "estimate_readability", lambda _text: {"words": 3, "sentences": 1, "paragraphs": 1, "average_sentence_length": 3.0, "reading_ease": 80.0, "grade_level": 4.0, "label": "easy"})
    monkeypatch.setattr(books, "build_emotional_arc_payload", lambda characters: {"focus_character_count": len(characters), "latest_turning_points": [], "characters": []})

    payload = await books.list_saved_notes(db=_FakeDB(), current_user=user)
    assert payload == [note]
    assert await books.get_book(book.id, db=_FakeDB(get_values=[book]), current_user=user)
    assert await books.get_book_notes(book.id, db=_FakeDB(), current_user=user) == [note]
    assert await books.upsert_book_note(book.id, BookNoteBody(body="Text"), db=_FakeDB(), current_user=user) == note

    response = await books.remove_book_note(book.id, uuid.uuid4(), db=_FakeDB(), current_user=user)
    assert response.status_code == 204

    assert await books.list_book_vault_notes(book.id, db=_FakeDB(), current_user=user) == [vault_note]
    assert await books.save_book_vault_note(book.id, VaultNoteBody(path="Lore/Scene.md", content="text"), db=_FakeDB(), current_user=user) == vault_note
    response = await books.delete_book_vault_note(book.id, "Lore/Scene.md", db=_FakeDB(), current_user=user)
    assert response.status_code == 204
    assert await books.import_book_vault_notes(book.id, _upload("notes.zip", b"zipdata"), db=_FakeDB(), current_user=user, _=None) == [vault_note]

    response = await books.export_book_vault_notes(book.id, db=_FakeDB(), current_user=user)
    assert response.media_type == "application/zip"

    graph = await books.get_book_vault_graph(book.id, db=_FakeDB(), current_user=user)
    assert graph["node_count"] == 1
    relations = await books.get_book_vault_note_relations(book.id, path="Lore/Scene.md", db=_FakeDB(), current_user=user)
    assert relations["path"] == "Lore/Scene.md"
    prewriting = await books.get_prewriting_check(book.id, upcoming_chapter=None, db=_FakeDB(), current_user=user)
    assert prewriting["upcoming_chapter"] == 4
    story_health = await books.get_story_health(book.id, db=_FakeDB(), current_user=user)
    assert story_health["score"] == 82
    assert await books.get_book_chapter_reports(book.id, db=_FakeDB(), current_user=user) == []
    assert await books.get_book_chapter_versions(book.id, chapter_number=1, db=_FakeDB(), current_user=user) == [chapter_version]

    workspace = await books.get_writer_workspace(book.id, db=_FakeDB(), current_user=user)
    assert workspace.goal_calendar == []

    updated = await books.update_writer_workspace(
        book.id,
        WriterWorkspaceBody(goal_calendar=[]),
        db=_FakeDB(),
        current_user=user,
    )
    assert updated.goal_calendar == []

    readability = await books.manuscript_readability(
        book.id,
        ReadabilityRequestBody(text="Short test line."),
        db=_FakeDB(),
        current_user=user,
    )
    assert readability.label == "easy"

    char = SimpleNamespace(mention_count=9, name="Iris")
    arc = await books.get_emotional_arc(book.id, db=_FakeDB(execute_values=[_Result(scalars=[char])]), current_user=user)
    assert arc.focus_character_count == 1


@pytest.mark.asyncio
async def test_novel_export_routes_dispatch_formats_and_workspace_preface(monkeypatch):
    user = _user()
    book = _book(
        user_id=user.id,
        title="Atlas Draft",
        writer_workspace={
            "manuscript_front_matter": {"title": "Atlas Draft", "author_name": "M. Author"},
            "novel_preface": "Before the voyage.",
            "novel_front_matter": {"dedication": "For readers."},
            "novel_epub_metadata": {"publisher": "LoreVia Press", "language": "en"},
            "index_format": "roman",
        },
    )
    chapter_id = uuid.uuid4()
    compiled_calls: list[dict[str, object]] = []

    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.utils.book_utils.download_book", lambda _key: b'{"text":"Chapter body","html":"<p>Chapter body</p>"}')
    monkeypatch.setattr("app.utils.book_utils.deserialize_manuscript_content", lambda _raw: {"text": "Chapter body", "html": "<p>Chapter body</p>"})
    monkeypatch.setattr(
        books,
        "build_writer_workspace_payload",
        lambda _book: {
            "manuscript_front_matter": {"title": "Atlas Draft", "author_name": "M. Author"},
            "novel_preface": "Before the voyage.",
            "novel_front_matter": {"dedication": "For readers."},
            "novel_epub_metadata": {"publisher": "LoreVia Press", "language": "en"},
            "index_format": "roman",
        },
    )
    monkeypatch.setattr(books, "novel_pdf_compiled", lambda **kwargs: compiled_calls.append({"format": "pdf", **kwargs}) or b"pdf")
    monkeypatch.setattr(books, "novel_epub_compiled", lambda **kwargs: compiled_calls.append({"format": "epub", **kwargs}) or b"epub")
    monkeypatch.setattr(books, "novel_docx", lambda **kwargs: compiled_calls.append({"format": "docx", **kwargs}) or b"docx")
    monkeypatch.setattr(books, "mark_book_cache_dirty", _async_value(None))

    for fmt, media_type in (
        ("pdf", "application/pdf"),
        ("epub", "application/epub+zip"),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ):
        db = _FakeDB(execute_values=[_Result(all_rows=[(chapter_id, 1, "Opening", "chapters/1.json")])])
        response = await books.export_novel(
            book.id,
            format=fmt,
            preset="large_print",
            include_images=False,
            image_placement="inline",
            include_image_captions=False,
            db=db,
            current_user=user,
        )
        assert response.media_type == media_type
        assert response.headers["Content-Disposition"] == f'attachment; filename="Atlas-Draft-novel.{fmt}"'

    assert [call["format"] for call in compiled_calls] == ["pdf", "epub", "docx"]
    assert all(call["chapters"] == [{"number": 1, "title": "Opening", "text": "Chapter body", "media": []}] for call in compiled_calls)
    assert all(call["preface"] == "Before the voyage." for call in compiled_calls)
    assert all(call["novel_front_matter"] == {"dedication": "For readers."} for call in compiled_calls)
    assert all(call["epub_metadata"] == {"publisher": "LoreVia Press", "language": "en"} for call in compiled_calls)
    assert all(call["preset"] == "large_print" for call in compiled_calls)
    assert all(call["image_placement"] == "inline" for call in compiled_calls)
    assert all(call["include_image_captions"] is False for call in compiled_calls)
    assert all(call["index_format"] == "roman" for call in compiled_calls)

    preview_db = _FakeDB(execute_values=[_Result(all_rows=[(chapter_id, 1, "Opening", "chapters/1.json")])])
    preview_response = await books.export_novel(
        book.id,
        format="pdf",
        preview_chapters=2,
        db=preview_db,
        current_user=user,
    )
    assert preview_response.headers["Content-Disposition"] == 'attachment; filename="Atlas-Draft-novel-preview.pdf"'

    db = _FakeDB()
    result = await books.save_novel_preface(
        book.id,
        NovelPrefaceBody(preface="  Fresh preface.  "),
        db=db,
        current_user=user,
    )

    assert result == {"preface": "Fresh preface."}
    assert book.writer_workspace["novel_preface"] == "Fresh preface."
    assert db.commits == 1

    settings_db = _FakeDB()
    settings_result = await books.save_novel_settings(
        book.id,
        NovelSettingsBody(
            preface="Final preface.",
            front_matter={
                "dedication": "For readers.",
                "acknowledgements": "Thanks.",
                "copyright_page": "Copyright 2026",
                "about_author": "M. Author.",
                "series_book_list": "Atlas Cycle",
            },
            epub_metadata={
                "publisher": "LoreVia Press",
                "language": "en-US",
                "isbn": "9780000000000",
                "description": "A blurb.",
                "series_name": "Atlas",
                "series_number": "1",
            },
        ),
        db=settings_db,
        current_user=user,
    )

    assert settings_result["preface"] == "Final preface."
    assert settings_result["front_matter"]["copyright_page"] == "Copyright 2026"
    assert settings_result["epub_metadata"]["publisher"] == "LoreVia Press"
    assert settings_db.commits == 1


@pytest.mark.asyncio
async def test_get_book_overview_and_writer_workspace_use_cache(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, writer_workspace={"goal_calendar": []})
    cache_store: dict[tuple[str, ...], dict] = {}

    async def _fake_get_book_cache_version(_book_id):
        return 0

    async def _fake_get_book_overview_cache(*key_parts):
        return cache_store.get(("overview", *(str(part) for part in key_parts)))

    async def _fake_set_book_overview_cache(*key_parts_and_payload):
        *key_parts, payload = key_parts_and_payload
        cache_store[("overview", *(str(part) for part in key_parts))] = payload

    async def _fake_get_writer_workspace_cache(*key_parts):
        return cache_store.get(("workspace", *(str(part) for part in key_parts)))

    async def _fake_set_writer_workspace_cache(*key_parts_and_payload):
        *key_parts, payload = key_parts_and_payload
        cache_store[("workspace", *(str(part) for part in key_parts))] = payload

    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "get_book_cache_version", _fake_get_book_cache_version)
    monkeypatch.setattr(books, "get_book_overview_cache", _fake_get_book_overview_cache)
    monkeypatch.setattr(books, "set_book_overview_cache", _fake_set_book_overview_cache)
    monkeypatch.setattr(books, "get_writer_workspace_cache", _fake_get_writer_workspace_cache)
    monkeypatch.setattr(books, "set_writer_workspace_cache", _fake_set_writer_workspace_cache)
    monkeypatch.setattr(
        books,
        "book_out",
        _async_value(
            books.BookOut(
                id=book.id,
                title=book.title,
                author=book.author,
                genre=book.genre,
                format=book.format,
                work_type=book.work_type,
                status=book.status,
                mode=book.mode,
                workspace_shell=book.mode,
                access_class="owner",
                can_switch_workspace_mode=True,
                source_kind=book.source_kind,
                preserve_chapter_numbers=False,
                preserve_source_chapters=False,
                total_chapters=book.total_chapters,
                total_tokens=book.total_tokens,
                total_words=0,
                is_truncated=False,
                series_name=None,
                series_order=None,
                is_public=False,
                public_description=None,
                copyright_warning=False,
                archived_at=None,
                hidden_at=None,
                created_at=book.created_at,
            )
        ),
    )
    monkeypatch.setattr(
        books,
        "build_reading_progress_payload",
        _async_value(
            {
                "current_chapter": 2,
                "scroll_pct": 0.0,
                "chapters_read_count": 2,
                "percent_complete": 66.7,
                "chapters_left": 1,
            }
        ),
    )
    monkeypatch.setattr(
        books,
        "build_chapter_list_payload",
        _async_value(
            {
                "read_upto": 2,
                "current_chapter": 2,
                "chapters": [],
            }
        ),
    )
    monkeypatch.setattr(
        books,
        "build_summary_collection_payload",
        _async_value(
            {
                "read_upto": 2,
                "summaries": [],
            }
        ),
    )
    monkeypatch.setattr(books, "build_writer_workspace_response", lambda _current_book: books.WriterWorkspaceOut(**_workspace_payload()))

    overview_first = await books.get_book_overview(book.id, db=_FakeDB(execute_values=[_Result(scalar=None), _Result(all_rows=[])]), current_user=user)
    overview_second = await books.get_book_overview(book.id, db=_FakeDB(), current_user=user)
    workspace_first = await books.get_writer_workspace(book.id, db=_FakeDB(), current_user=user)
    workspace_second = await books.get_writer_workspace(book.id, db=_FakeDB(), current_user=user)

    assert overview_first.book.title == "Atlas"
    assert overview_second.book.title == "Atlas"
    assert workspace_first.goal_calendar == []
    assert workspace_second.goal_calendar == []


@pytest.mark.asyncio
async def test_list_books_enqueues_stale_processing_repair_before_serializing(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4(), email="owner@getlorevia.com")
    book = _book(user_id=user.id, is_editor_project=True, status="processing")
    enqueued_book_ids: list[uuid.UUID] = []

    async def _fake_enqueue(candidate):
        enqueued_book_ids.append(candidate.id)
        return True

    async def _fake_build_book_out_list(_db, *, books, user_id, collaborators_by_book_id=None):
        return [SimpleNamespace(id=item.id, title=item.title) for item in books]

    monkeypatch.setitem(books.list_books.__globals__, "enqueue_processing_state_repair_if_needed", _fake_enqueue)
    monkeypatch.setattr(books, "build_book_out_list", _fake_build_book_out_list)

    payload = await books.list_books(
        db=_FakeDB(
            execute_values=[
                _Result(scalars=[book]),
                _Result(all_rows=[]),
            ]
        ),
        current_user=user,
    )

    assert enqueued_book_ids == [book.id]
    assert len(payload) == 1
    assert payload[0].id == book.id


@pytest.mark.asyncio
async def test_get_book_enqueues_stale_processing_repair_before_serializing(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, is_editor_project=True, status="processing")
    enqueued_book_ids: list[uuid.UUID] = []

    async def _fake_enqueue(candidate):
        enqueued_book_ids.append(candidate.id)
        return True

    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setitem(books.get_book.__globals__, "enqueue_processing_state_repair_if_needed", _fake_enqueue)
    monkeypatch.setattr(books, "book_out", _async_value(SimpleNamespace(id=book.id)))

    payload = await books.get_book(book.id, db=_FakeDB(), current_user=user)

    assert enqueued_book_ids == [book.id]
    assert payload.id == book.id


@pytest.mark.asyncio
async def test_export_cover_archive_hide_and_delete_routes(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, title="Atlas Draft")
    chapter = SimpleNamespace(number=1, title="One", s3_key="chapters/1.json")
    compiled_calls: list[dict[str, object]] = []
    docx_calls: list[dict[str, object]] = []

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books.storage, "download_book", lambda _key: b"stored")
    monkeypatch.setattr(books, "deserialize_manuscript_content", lambda _raw: {"text": "SCENE\nBody", "html": "<p>Body</p>"})
    monkeypatch.setattr(books, "strip_scene_metadata_from_manuscript_text", lambda text: text.replace("SCENE\n", ""))
    monkeypatch.setattr(books, "build_writer_workspace_payload", lambda _book: {"manuscript_front_matter": {"title": "Atlas Draft"}})
    monkeypatch.setattr(books, "list_novel_scenes", _async_value([{"source": "manual", "status": "active"}]))
    monkeypatch.setattr(books, "list_vault_notes", _async_value([{"path": "Lore/Scene.md"}]))
    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "manuscript_pdf_compiled", lambda **kwargs: compiled_calls.append({"format": "pdf", **kwargs}) or b"pdf")
    monkeypatch.setattr(books, "manuscript_epub_compiled", lambda **kwargs: compiled_calls.append({"format": "epub", **kwargs}) or b"epub")
    monkeypatch.setattr(books, "manuscript_vault_zip", lambda **_kwargs: b"zip")
    monkeypatch.setattr(books, "manuscript_docx", lambda **kwargs: docx_calls.append(kwargs) or b"docx")

    db = _FakeDB(execute_values=[_Result(all_rows=[])])
    with pytest.raises(HTTPException) as exc:
        await books.export_manuscript(book.id, db=db, current_user=user)
    assert exc.value.status_code == 404

    for fmt, media_type in (
        ("pdf", "application/pdf"),
        ("epub", "application/epub+zip"),
        ("vault", "application/zip"),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ):
        db = _FakeDB(execute_values=[_Result(all_rows=[(1, "One", "chapters/1.json")])])
        response = await books.export_manuscript(
            book.id,
            format=fmt,
            include_scene_metadata=False,
            db=db,
            current_user=user,
        )
        assert response.media_type == media_type
        expected_name = "Atlas-Draft-manuscript-vault.zip" if fmt == "vault" else f"Atlas-Draft-manuscript.{fmt}"
        assert response.headers["Content-Disposition"] == f'attachment; filename="{expected_name}"'

    assert [call["format"] for call in compiled_calls] == ["pdf", "epub"]
    assert all(call["chapters"] == [{"number": 1, "title": "One", "text": "Body", "html": None}] for call in compiled_calls)
    assert all(call["font_family"] == "serif" for call in compiled_calls)
    assert all(call["include_toc"] is False for call in compiled_calls)
    assert docx_calls[-1]["include_toc"] is False

    db = _FakeDB(execute_values=[_Result(all_rows=[(1, "One", "chapters/1.json")])])
    await books.export_manuscript(
        book.id,
        format="docx",
        include_toc=True,
        db=db,
        current_user=user,
    )
    assert docx_calls[-1]["include_toc"] is True

    cover_book = _book(user_id=user.id, cover_s3_key="covers/atlas.png")
    monkeypatch.setattr(books, "ensure_book_cover", _async_value(None))
    monkeypatch.setattr(books, "decode_token", lambda _token: {"type": "asset", "sub": str(user.id), "res": f"book-cover:{cover_book.id}"})
    monkeypatch.setattr(books.storage, "download_book", lambda _key: b"png")
    response = await books.get_book_cover_public(cover_book.id, token="ok", db=_FakeDB(get_values=[cover_book]))
    assert response.media_type == "image/png"

    monkeypatch.setattr(books, "book_out", _async_value({"id": str(book.id)}))
    archived = await books.archive_book(book.id, archived=True, db=_FakeDB(get_values=[book]), current_user=user)
    assert archived["id"] == str(book.id)
    hidden = await books.hide_book(book.id, hidden=True, db=_FakeDB(get_values=[book]), current_user=user)
    assert hidden["id"] == str(book.id)
    deleted = await books.delete_book(book.id, db=_FakeDB(get_values=[book]), current_user=user)
    assert deleted["id"] == str(book.id)


@pytest.mark.asyncio
async def test_character_routes_cover_crud_and_exports(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="author")
    character_id = uuid.uuid4()
    other_id = uuid.uuid4()
    character = SimpleNamespace(
        id=character_id,
        book_id=book.id,
        name="Iris",
        aliases=["I"],
        role="mc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=7,
        trait_state={"eyes": "green"},
        personality_tags=["brave"],
        goal="Protect the city",
        motivations=["survive"],
        fears=["loss"],
        lie_they_believe="She has to do everything alone.",
        backstory_wound="Failed her brother once.",
        arc_type="positive change",
        archetype="hero",
        arc_summary="Growing",
        growth_events=[],
        character_type="complex",
        character_type_score=9,
        subtype_scores={"stoic": 4},
        analysis_metadata={"quality_flags": ["generic_summary"], "grounding_passage_count": 0},
    )
    other_character = SimpleNamespace(
        id=other_id,
        book_id=book.id,
        name="Vale",
        aliases=[],
        role="sc",
        first_chapter=1,
        last_seen_chapter=2,
        mention_count=3,
        trait_state={},
        personality_tags=[],
        goal=None,
        motivations=[],
        fears=[],
        lie_they_believe=None,
        backstory_wound=None,
        arc_type=None,
        archetype="ally",
        arc_summary=None,
        growth_events=[],
        character_type="normal",
        character_type_score=5,
        subtype_scores={},
    )
    hidden_character = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Actually",
        aliases=[],
        role=None,
        first_chapter=1,
        last_seen_chapter=1,
        mention_count=1,
        trait_state={},
        personality_tags=[],
        goal=None,
        motivations=[],
        fears=[],
        lie_they_believe=None,
        backstory_wound=None,
        arc_type=None,
        archetype=None,
        arc_summary=None,
        growth_events=[],
        character_type="normal",
        character_type_score=1,
        subtype_scores={},
        analysis_metadata={"quality_flags": ["generic_summary", "light_grounding"], "grounding_passage_count": 1},
    )
    secondary = SimpleNamespace(id=other_id, book_id=book.id, analysis_metadata={})
    relationship = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        character_a_id=character_id,
        character_b_id=other_id,
        rel_type="ally",
        sentiment=0.4,
        description="Trusted",
        from_chapter=1,
        to_chapter=None,
    )

    async def _fake_consolidate(*_args, **_kwargs):
        return None

    def _apply_description(current_character, description):
        current_character.arc_summary = description.strip()

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "consolidate_characters", _fake_consolidate)
    monkeypatch.setattr(books, "is_displayable_character", lambda current: current.name != "Ghost")
    monkeypatch.setattr(books, "relationship_summary_for_character", lambda *_args: "ally summary")
    monkeypatch.setattr(books, "append_unique_summary", lambda mapping, keys, key, dedupe_key, summary: mapping.setdefault(key, []).append(summary))
    monkeypatch.setattr(books, "dedupe_preserve_order", lambda items: list(dict.fromkeys(items)))
    monkeypatch.setattr(
        books,
        "serialize_book_character",
        lambda char, **kwargs: {
            "id": str(char.id),
            "book_id": str(char.book_id),
            "name": char.name,
            "aliases": char.aliases or [],
            "role": char.role,
            "first_chapter": char.first_chapter,
            "last_seen_chapter": getattr(char, "last_seen_chapter", None),
            "mention_count": getattr(char, "mention_count", 0) or 0,
            "status": "active",
            "trait_state": char.trait_state or {},
            "description": f"{char.archetype}:{(char.trait_state or {}).get('eyes', 'na')}|{len((kwargs.get('rel_summaries') or {}).get(str(char.id), []))}",
            "personality_tags": char.personality_tags or [],
            "goal": getattr(char, "goal", None),
            "motivations": char.motivations or [],
            "fears": char.fears or [],
            "lie_they_believe": getattr(char, "lie_they_believe", None),
            "backstory_wound": getattr(char, "backstory_wound", None),
            "arc_type": getattr(char, "arc_type", None),
            "archetype": getattr(char, "archetype", None),
            "arc_summary": getattr(char, "arc_summary", None),
            "growth_events": getattr(char, "growth_events", []) or [],
            "relationship_summaries": list((kwargs.get("rel_summaries") or {}).get(str(char.id), [])),
            "character_type": getattr(char, "character_type", None),
            "character_type_score": getattr(char, "character_type_score", None),
            "subtype_scores": getattr(char, "subtype_scores", {}) or {},
            "analysis_metadata": {
                "persistence_reason": "manual_character" if getattr(char, "is_manual", False) else None,
                "quality_flags": ["generic_summary", "light_grounding"],
                "confidence_band": "low",
                "user_curated": bool((getattr(char, "analysis_metadata", {}) or {}).get("user_curated")),
                "protected_from_repair": bool((getattr(char, "analysis_metadata", {}) or {}).get("protected_from_repair")),
                "review_note": (getattr(char, "analysis_metadata", {}) or {}).get("review_note"),
            },
            "is_manual": getattr(char, "is_manual", False),
            "graph_visibility_override": (
                ((char.trait_state or {}).get("graph_visibility_override") or {}).get("value")
                if isinstance((char.trait_state or {}).get("graph_visibility_override"), dict)
                else getattr(char, "graph_visibility_override", None)
            ),
            "tags": kwargs.get("tags", []) or [],
            "arc_tracker": {"goal": "Protect the city", "diagnostics": []},
        },
    )
    monkeypatch.setattr(books, "merge_characters", _async_value(character))
    monkeypatch.setattr(books, "partition_character", _async_value([character, other_character]))
    monkeypatch.setattr(books, "clean_string_list", lambda values: [value.strip() for value in values if value.strip()])
    monkeypatch.setattr(books, "apply_manual_character_description", _apply_description)
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "create_asset_token", lambda *_args, **_kwargs: "signed-token")
    monkeypatch.setattr(books, "build_character_card_payload", _async_value({"name": "Iris"}))
    monkeypatch.setattr(books, "character_card_markdown", lambda payload: (f"# {payload['name']}", "atlas-draft-iris"))
    monkeypatch.setattr(books, "character_card_pdf", lambda _payload: b"pdf")
    monkeypatch.setattr(books, "character_card_docx", lambda _payload: b"docx")
    monkeypatch.setattr(books, "decode_token", lambda _token: {"type": "asset", "sub": str(user.id), "res": f"character-card:{book.id}:{character.id}"})
    monkeypatch.setattr(books, "list_custom_tags_for_entity_ids", _async_value({}))
    monkeypatch.setattr(books, "get_custom_tags_for_entity", _async_value([]))
    monkeypatch.setattr(books, "refresh_character_duplicate_suggestions", _async_value(None))
    monkeypatch.setattr(books, "mark_character_candidates_merged", _async_value(None))

    context = {
        "book": book,
        "characters": [character],
        "relationships": [relationship],
        "plot_threads": [],
        "wiki_entries": [],
        "chapter_rows": [],
        "chapter_events": [],
        "rel_summaries": {str(character.id): ["ally summary"]},
        "thread_summaries": {str(character.id): ["Thread [ongoing]"]},
    }
    monkeypatch.setattr(books, "build_character_bible_vault_context", _async_value(context))
    monkeypatch.setattr(books, "load_vault_note_overrides", _async_value({"Character/Iris.md": "override"}))
    monkeypatch.setattr(books, "character_bible_vault_folder", lambda **_kwargs: (b"zip", "atlas"))
    monkeypatch.setattr(books, "character_bible_markdown", lambda **_kwargs: ("# Bible", "atlas"))
    monkeypatch.setattr(books, "character_bible_pdf", lambda **_kwargs: b"pdf")
    monkeypatch.setattr(books, "character_bible_docx", lambda **_kwargs: b"docx")
    monkeypatch.setattr(books, "character_bible_vault_preview", lambda **_kwargs: {"root_folder": "Atlas", "files": []})
    monkeypatch.setattr(books, "list_vault_bible_notes", _async_value([{"path": "Characters/Iris.md", "source": "character_bible", "content": "bio"}]))
    monkeypatch.setattr(books, "save_vault_note", _async_value({"path": "Characters/Iris.md", "source": "character_bible", "content": "bio", "persisted": True}))

    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[character, other_character, hidden_character]),
            _Result(scalars=[relationship]),
            _Result(scalars=[]),
            _Result(scalars=[]),
        ],
    )
    payload = await books.get_book_characters(book.id, db=db, current_user=user)
    assert [item["name"] for item in payload] == ["Iris", "Vale"]
    assert payload[0]["description"] == "hero:green|1"
    assert payload[0]["goal"] == "Protect the city"
    assert payload[0]["arc_tracker"]["goal"] == "Protect the city"
    assert payload[0]["analysis_metadata"]["quality_flags"] == ["generic_summary", "light_grounding"]
    assert payload[0]["analysis_metadata"]["confidence_band"] == "low"

    created_character = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Aunt May",
        aliases=["May"],
        role="sc",
        first_chapter=2,
        last_seen_chapter=2,
        mention_count=1,
        trait_state={"eyes": "blue"},
        personality_tags=["sharp"],
        goal="Protect the family",
        motivations=["Keep the household safe"],
        fears=[],
        lie_they_believe=None,
        backstory_wound=None,
        arc_type=None,
        archetype="mentor",
        arc_summary="Keeps careful watch over the family.",
        growth_events=[],
        character_type=None,
        character_type_score=None,
        subtype_scores={},
        analysis_metadata={},
        is_manual=True,
    )
    monkeypatch.setattr(books, "build_manual_character", lambda **_kwargs: created_character)
    create_db = _FakeDB()
    created = await books.create_book_character(
        book.id,
        CharacterCreateBody(name="Aunt May", first_chapter=2, role="sc"),
        db=create_db,
        current_user=user,
    )
    assert created["name"] == "Aunt May"
    assert created["role"] == "sc"
    assert created["is_manual"] is True
    assert created["analysis_metadata"]["persistence_reason"] == "manual_character"
    assert create_db.added == [created_character]
    assert create_db.commits == 1

    db = _FakeDB(get_values=[character, character])
    merged = await books.merge_book_characters(
        book.id,
        CharacterMergeBody(primary_id=character.id, secondary_id=character.id),
        db=db,
        current_user=user,
    )
    assert merged["merged"] == str(character.id)

    db = _FakeDB(get_values=[character, secondary])
    merged = await books.merge_book_characters(
        book.id,
        CharacterMergeBody(primary_id=character.id, secondary_id=secondary.id),
        db=db,
        current_user=user,
    )
    assert merged["merged"] == str(character.id)

    partitioned = await books.partition_book_character(
        book.id,
        character.id,
        CharacterPartitionBody(
            partitions=[
                CharacterPartitionTargetBody(name="Mr. Samsa", aliases=[]),
                CharacterPartitionTargetBody(name="Mrs. Samsa", aliases=[]),
            ]
        ),
        db=_FakeDB(get_values=[character]),
        current_user=user,
    )
    assert partitioned["replaced"] == str(character.id)
    assert partitioned["created"] == [str(character.id), str(other_character.id)]

    with pytest.raises(HTTPException) as exc:
        await books.update_book_character(
            book.id,
            character.id,
            CharacterUpdateBody(role="villain"),
            db=_FakeDB(get_values=[character]),
            current_user=user,
        )
    assert exc.value.detail == "Invalid role"

    updated = await books.update_book_character(
        book.id,
        character.id,
        CharacterUpdateBody(
            name=" Iris Prime ",
            aliases=[" Iris ", ""],
            role="sc",
            description=" Hardened by loss ",
            goal=" Keep the archive safe ",
            lie_they_believe=" She cannot trust anyone ",
            backstory_wound=" A failed mission ",
            arc_type=" redemptive ",
            arc_summary=" Arc ",
            personality_tags=[" calm ", ""],
            motivations=[" truth "],
            fears=["failure"],
        ),
        db=_FakeDB(
            get_values=[character],
            execute_values=[_Result(scalars=[]), _Result(scalars=[]), _Result(scalars=[]), _Result(scalar=None)],
        ),
        current_user=user,
    )
    assert updated["name"] == "Iris Prime"
    assert updated["role"] == "sc"
    assert updated["aliases"] == ["Iris"]
    assert updated["goal"] == "Keep the archive safe"
    assert updated["analysis_metadata"]["user_curated"] is True

    updated_visibility = await books.update_book_character(
        book.id,
        character.id,
        CharacterUpdateBody(graph_visibility="include"),
        db=_FakeDB(
            get_values=[character],
            execute_values=[_Result(scalars=[]), _Result(scalars=[]), _Result(scalars=[]), _Result(scalar=None)],
        ),
        current_user=user,
    )
    assert updated_visibility["graph_visibility_override"] == "include"

    protected_update = await books.update_book_character(
        book.id,
        character.id,
        CharacterUpdateBody(protected_from_repair=True),
        db=_FakeDB(
            get_values=[character],
            execute_values=[_Result(scalars=[]), _Result(scalars=[]), _Result(scalars=[]), _Result(scalar=None)],
        ),
        current_user=user,
    )
    assert protected_update["analysis_metadata"]["protected_from_repair"] is True

    noted_update = await books.update_book_character(
        book.id,
        character.id,
        CharacterUpdateBody(review_note=" Needs manual check "),
        db=_FakeDB(
            get_values=[character],
            execute_values=[_Result(scalars=[]), _Result(scalars=[]), _Result(scalars=[]), _Result(scalar=None)],
        ),
        current_user=user,
    )
    assert noted_update["analysis_metadata"]["review_note"] == "Needs manual check"

    demote_candidate = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(books, "demote_character_to_review_candidate", _async_value(demote_candidate))
    demoted = await books.demote_book_character(
        book.id,
        character.id,
        db=_FakeDB(get_values=[character]),
        current_user=user,
    )
    assert demoted["demoted"] == str(character.id)
    assert demoted["candidate_id"] == str(demote_candidate.id)

    deleted = await books.delete_book_character(book.id, character.id, db=_FakeDB(get_values=[character]), current_user=user)
    assert deleted["deleted"] == str(character.id)

    created_rel = await books.create_book_relationship(
        book.id,
        RelationshipCreateBody(
            character_a_id=character.id,
            character_b_id=secondary.id,
            rel_type="ally",
            sentiment=0.4,
            description=" Trusts ",
            from_chapter=2,
        ),
        db=_FakeDB(get_values=[character, secondary], execute_values=[_Result(scalars=[]), _Result(scalars=[])]),
        current_user=user,
    )
    assert created_rel["rel_type"] == "ally"
    assert created_rel["description"] == "Trusts"

    with pytest.raises(HTTPException) as exc:
        await books.update_book_relationship(
            book.id,
            relationship.id,
            RelationshipUpdateBody(rel_type=" ", sentiment=2.0),
            db=_FakeDB(get_values=[relationship]),
            current_user=user,
        )
    assert exc.value.detail == "Relationship type is required"

    updated_rel = await books.update_book_relationship(
        book.id,
        relationship.id,
        RelationshipUpdateBody(rel_type="family", sentiment=0.8, description=" Strong ", from_chapter=2, to_chapter=3),
        db=_FakeDB(get_values=[relationship, relationship], execute_values=[_Result(scalars=[])]),
        current_user=user,
    )
    assert updated_rel["rel_type"] == "family"

    deleted_rel = await books.delete_book_relationship(book.id, relationship.id, db=_FakeDB(get_values=[relationship]), current_user=user)
    assert deleted_rel["deleted"] == str(relationship.id)

    relationship_candidate = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        chapter_number=3,
        raw_character_a="Grete",
        raw_character_b="Gregor's father",
        matched_character_a_id=character.id,
        matched_character_b_id=secondary.id,
        rel_type="family",
        sentiment=-0.2,
        description="Pressure grows.",
        status="pending",
        reason_codes=["relationship_unresolved"],
        evidence={},
        source_batch_key="relationship:1",
    )

    attached_a = await books.attach_relationship_candidate_a(
        book.id,
        relationship_candidate.id,
        RelationshipCandidateAttachBody(character_id=character.id),
        db=_FakeDB(get_values=[relationship_candidate, character]),
        current_user=user,
    )
    assert attached_a["attached_a"] == str(character.id)

    attached_b = await books.attach_relationship_candidate_b(
        book.id,
        relationship_candidate.id,
        RelationshipCandidateAttachBody(character_id=secondary.id),
        db=_FakeDB(get_values=[relationship_candidate, secondary]),
        current_user=user,
    )
    assert attached_b["attached_b"] == str(secondary.id)

    accepted_candidate = SimpleNamespace(**relationship_candidate.__dict__)
    accepted = await books.accept_relationship_candidate(
        book.id,
        accepted_candidate.id,
        RelationshipCandidateAcceptBody(
            character_a_id=character.id,
            character_b_id=secondary.id,
            rel_type="family",
            sentiment=-0.4,
            description="Household strain",
            from_chapter=3,
        ),
        db=_FakeDB(get_values=[accepted_candidate, character, secondary], execute_values=[_Result(scalars=[]), _Result(scalars=[])]),
        current_user=user,
    )
    assert accepted["rel_type"] == "family"

    resolved = await books.resolve_relationship_candidate(
        book.id,
        relationship_candidate.id,
        db=_FakeDB(get_values=[relationship_candidate]),
        current_user=user,
    )
    assert resolved["resolved"] == str(relationship_candidate.id)

    rejected = await books.reject_relationship_candidate(
        book.id,
        relationship_candidate.id,
        db=_FakeDB(get_values=[relationship_candidate]),
        current_user=user,
    )
    assert rejected["rejected"] == str(relationship_candidate.id)

    shared = await books.share_book_character(book.id, character.id, db=_FakeDB(get_values=[character]), current_user=user)
    assert "signed-token" in shared.share_url

    for fmt, media_type in (
        ("md", "text/markdown; charset=utf-8"),
        ("pdf", "application/pdf"),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ):
        response = await books.export_character_card(book.id, character.id, format=fmt, db=_FakeDB(get_values=[character]), current_user=user)
        assert response.media_type == media_type
        assert response.headers["Content-Disposition"] == f'attachment; filename="atlas-draft-iris-character-card.{fmt}"'

    for fmt, media_type in (
        ("md", "text/markdown; charset=utf-8"),
        ("pdf", "application/pdf"),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("vault_folder", "application/zip"),
    ):
        response = await books.export_character_bible(book.id, format=fmt, db=_FakeDB(), current_user=user)
        assert response.media_type == media_type
        extension = "zip" if fmt == "vault_folder" else fmt
        assert response.headers["Content-Disposition"] == f'attachment; filename="atlas-character-bible.{extension}"'

    preview = await books.preview_character_bible_vault(book.id, db=_FakeDB(), current_user=user)
    assert preview["root_folder"] == "Atlas"
    notes = await books.list_character_bible_vault_notes(book.id, db=_FakeDB(), current_user=user)
    assert notes[0]["path"] == "Characters/Iris.md"
    saved = await books.save_character_bible_vault_note(
        book.id,
        VaultNoteBody(path="Characters/Iris.md", content="bio"),
        db=_FakeDB(),
        current_user=user,
    )
    assert saved["persisted"] is True

    public_payload = await books.get_book_character_card_public(
        book.id,
        character.id,
        token="ok",
        db=_FakeDB(get_values=[book, character]),
    )
    assert public_payload["name"] == "Iris"


@pytest.mark.asyncio
async def test_public_asset_endpoints_respect_public_mode_kill_switch(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", False, raising=False)
    user = _user()
    book = _book(user_id=user.id)
    character = SimpleNamespace(id=uuid.uuid4(), book_id=book.id)

    with pytest.raises(HTTPException) as exc:
        await books.share_book_character(book.id, character.id, db=_FakeDB(), current_user=user)
    assert exc.value.status_code == 503

    with pytest.raises(HTTPException) as exc:
        await books.get_book_character_card_public(book.id, character.id, token="ok", db=_FakeDB())
    assert exc.value.status_code == 503

    # get_book_cover_public is not gated by PUBLIC_MODE_ENABLED because it also
    # serves authenticated cover requests via the token-based proxy (CSP-safe).


@pytest.mark.asyncio
async def test_character_reprocess_routes_delegate_to_repair_workflow(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="author")

    db = _FakeDB()

    class _FakeRepairResult:
        def __init__(self, book_id, dry_run):
            self.book_id = book_id
            self.dry_run = dry_run

        def to_payload(self):
            return {
                "book_id": self.book_id,
                "dry_run": self.dry_run,
                "planned_merges": [],
                "planned_demotions": [],
            }

    class _FakeRepairJob:
        def __init__(self, db, *, book_id, repair_run_id=None):
            self.db = db
            self.book_id = book_id

        async def preview(self):
            return _FakeRepairResult(book_id=str(self.book_id), dry_run=True)

        async def apply(self):
            return _FakeRepairResult(book_id=str(self.book_id), dry_run=False)

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books.characters, "CharacterIdentityRepairJob", _FakeRepairJob)

    preview = await books.preview_book_character_reprocess(
        book.id,
        allow_merge_safe_pairs=True,
        allow_demote_obvious_noise=True,
        db=db,
        current_user=user,
    )
    assert preview["book_id"] == str(book.id)
    assert preview["dry_run"] is True

    applied = await books.apply_book_character_reprocess(
        book.id,
        allow_merge_safe_pairs=True,
        allow_demote_obvious_noise=True,
        db=db,
        current_user=user,
    )
    assert applied["book_id"] == str(book.id)


@pytest.mark.asyncio
async def test_get_book_characters_hides_low_trust_rows_in_author_mode(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="author")
    visible = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Grete",
        aliases=[],
        role="sc",
        first_chapter=1,
        last_seen_chapter=2,
        mention_count=2,
        trait_state={},
        personality_tags=["watchful"],
        motivations=[],
        fears=[],
        archetype="ally",
        arc_summary="A grounded supporting character.",
        analysis_metadata={"grounding_passage_count": 2, "quality_flags": []},
        is_manual=False,
    )
    hidden = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Actually",
        aliases=[],
        role=None,
        first_chapter=1,
        last_seen_chapter=1,
        mention_count=1,
        trait_state={},
        personality_tags=[],
        motivations=[],
        fears=[],
        archetype=None,
        arc_summary=None,
        analysis_metadata={"grounding_passage_count": 1, "quality_flags": ["generic_summary", "light_grounding"]},
        is_manual=False,
    )

    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "collaboration_has_resource", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(books, "list_custom_tags_for_entity_ids", _async_value({}))
    monkeypatch.setattr(books, "relationship_summary_for_character", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "serialize_book_character", lambda char, **_kwargs: {"id": str(char.id), "name": char.name})

    payload = await books.get_book_characters(
        book.id,
        db=_FakeDB(
            execute_values=[
                _Result(scalars=[visible, hidden]),
                _Result(scalars=[]),
                _Result(scalars=[]),
                _Result(scalars=[]),
            ],
        ),
        current_user=user,
    )

    assert payload == [{"id": str(visible.id), "name": "Grete"}]
