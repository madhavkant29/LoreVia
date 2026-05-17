from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from app.api.v1.routes import books
from app.utils.llm_usage_utils import LlmUsageSummary
from app.schemas.books import (
    BookModeBody,
    BookNoteBody,
    CharacterCreateBody,
    CharacterMergeBody,
    CharacterPartitionBody,
    CharacterPartitionTargetBody,
    CharacterUpdateBody,
    CharacterEventOut,
    ChapterConsistencyReport,
    MajorEventOut,
    ObsidianVaultNoteBody,
    ReadabilityRequestBody,
    RelationshipCreateBody,
    RelationshipUpdateBody,
    SeriesBody,
    SeriesBookStatusBody,
    SeriesCreateBody,
    SeriesMembershipBody,
    WriterWorkspaceBody,
)


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
async def test_update_mode_and_events_routes(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="reader", source_kind=None)
    db = _FakeDB()

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "book_out", _async_value({"id": str(book.id), "mode": "author"}))

    with pytest.raises(HTTPException) as exc:
        await books.update_book_mode(book.id, BookModeBody(mode="bad"), db=db, current_user=user)
    assert exc.value.detail == "Invalid mode"

    await books.update_book_mode(book.id, BookModeBody(mode="author"), db=db, current_user=user)
    assert book.mode == "author"
    assert book.source_kind == "single_upload"

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
    db = _FakeDB(execute_values=[_Result(all_rows=event_rows), _Result(scalars=[character])])
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
    db = _FakeDB(execute_values=[_Result(scalar=progress)])
    payload = await books.get_reader_safe_book_events(book.id, chapter=None, db=db, current_user=user)
    assert [event.event_title for event in payload.major_events] == ["Seen"]
    assert [event.character_name for event in payload.character_events] == ["Iris"]


@pytest.mark.asyncio
async def test_import_manuscript_content_text_flow_updates_progress_and_reports(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, mode="reader", total_chapters=0)
    chapter = SimpleNamespace(id=uuid.uuid4(), s3_key="chapters/1.json", title="Chapter 1")
    report = ChapterConsistencyReport(
        chapter_number=1,
        chapter_title="Chapter 1",
        summary="Good",
        new_characters=[],
        relationship_changes=[],
        plot_threads_opened=[],
        plot_threads_resolved=[],
        continuity_flags=[],
    )
    added_words = {}
    cache_invalidated = {"called": 0}

    async def _fake_process(*_args, **_kwargs):
        return None

    async def _fake_replace(*_args, **_kwargs):
        return None

    async def _fake_analyse(*_args, **_kwargs):
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
    monkeypatch.setattr(books, "analyse_chapter", _fake_analyse)
    monkeypatch.setattr(books, "build_chapter_consistency_report", _async_value(report))
    monkeypatch.setattr(books, "build_chapter_report_notification", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "build_continuity_risk_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(books, "sync_chapter_content_from_novel_scenes", _fake_replace)
    monkeypatch.setattr(
        books,
        "invalidate_advisor_caches",
        lambda: cache_invalidated.__setitem__("called", cache_invalidated["called"] + 1),
    )

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
    assert payload.chapter_content_versions == {1: 1}
    assert payload.mode == "author"
    assert payload.chapter_reports[0].chapter_title == "Chapter 1"
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

    async def _fake_analyse(*_args, **_kwargs):
        return None

    async def _fake_report(_db, _book, chapter_number):
        return ChapterConsistencyReport(
            chapter_number=chapter_number,
            chapter_title=f"Chapter {chapter_number}",
            summary="Good",
            new_characters=[],
            relationship_changes=[],
            plot_threads_opened=[],
            plot_threads_resolved=[],
            continuity_flags=[],
        )

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
    monkeypatch.setattr(books, "analyse_chapter", _fake_analyse)
    monkeypatch.setattr(books, "build_chapter_consistency_report", _fake_report)
    monkeypatch.setattr(books, "build_chapter_report_notification", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books, "build_continuity_risk_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(books, "sync_chapter_content_from_novel_scenes", _fake_replace)
    monkeypatch.setattr(books, "invalidate_advisor_caches", lambda: None)

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
        files=[_upload("story.pdf", b"%PDF-1.4 mock")],
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
    monkeypatch.setattr(books, "get_owned_series", _async_value(series))
    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "build_series_bible_payload", _async_value({"series_id": str(series.id)}))
    monkeypatch.setattr(books, "compute_words_read_for_book", _async_value(1200))
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
    assert listed[0].books[0].marked_complete_in_series is False

    bible = await books.get_series_bible(series.id, db=_FakeDB(), current_user=user)
    assert bible["series_id"] == str(series.id)

    db = _FakeDB(execute_values=[_Result(scalar=None)])
    with pytest.raises(HTTPException) as exc:
        await books.add_book_to_series(series.id, book.id, SeriesMembershipBody(position=0), db=db, current_user=user)
    assert exc.value.detail == "Position must be at least 1"

    async def _fake_list_series(_db, current_user):
        return [SimpleNamespace(id=series.id, name=series.name)]

    monkeypatch.setattr(books, "list_series", _fake_list_series)
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
async def test_book_notes_obsidian_and_workspace_routes(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, writer_workspace={"goal_calendar": []})
    chapter_version = {"id": "v1", "chapter_number": 1, "created_at": datetime.now(UTC)}
    note = {"id": "n1", "book_id": str(book.id), "body": "note"}
    obsidian_note = {"path": "Lore/Scene.md", "source": "user_notes", "content": "text", "persisted": True}

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "list_user_notes", _async_value([note]))
    monkeypatch.setattr(books, "book_out", _async_value({"id": str(book.id)}))
    monkeypatch.setattr(books, "list_book_notes", _async_value([note]))
    monkeypatch.setattr(books, "save_book_note", _async_value(note))
    monkeypatch.setattr(books, "delete_book_note", _async_value(None))
    monkeypatch.setattr(books, "list_obsidian_notes", _async_value([obsidian_note]))
    monkeypatch.setattr(books, "save_obsidian_vault_note", _async_value(obsidian_note))
    monkeypatch.setattr(books, "delete_obsidian_note", _async_value(None))
    monkeypatch.setattr(books, "import_obsidian_notes_zip", _async_value([obsidian_note]))
    monkeypatch.setattr(books, "export_obsidian_notes_zip", lambda notes: b"zip")
    monkeypatch.setattr(books, "build_obsidian_graph", lambda notes: {"node_count": len(notes), "edge_count": 0, "nodes": [], "edges": []})
    monkeypatch.setattr(books, "list_obsidian_note_relations", _async_value({"path": "Lore/Scene.md", "outgoing": [], "incoming": []}))
    monkeypatch.setattr(books, "build_prewriting_check", _async_value({"upcoming_chapter": 4, "active_characters": [], "unresolved_threads": [], "recent_events": [], "alerts": []}))
    monkeypatch.setattr(books, "build_story_health_payload", _async_value({"score": 82, "status": "healthy", "summary": "Good", "metrics": []}))
    monkeypatch.setattr(books, "list_chapter_consistency_reports", _async_value([]))
    monkeypatch.setattr(books, "list_chapter_versions", _async_value([chapter_version]))
    monkeypatch.setattr(books, "build_writer_workspace_payload", lambda _current_book: books.normalize_writer_workspace(_workspace_payload()))
    monkeypatch.setattr(books, "normalize_writer_workspace", lambda payload: payload)
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

    assert await books.list_book_obsidian_notes(book.id, db=_FakeDB(), current_user=user) == [obsidian_note]
    assert await books.save_book_obsidian_note(book.id, ObsidianVaultNoteBody(path="Lore/Scene.md", content="text"), db=_FakeDB(), current_user=user) == obsidian_note
    response = await books.delete_book_obsidian_note(book.id, "Lore/Scene.md", db=_FakeDB(), current_user=user)
    assert response.status_code == 204
    assert await books.import_book_obsidian_notes(book.id, _upload("notes.zip", b"zipdata"), db=_FakeDB(), current_user=user, _=None) == [obsidian_note]

    response = await books.export_book_obsidian_notes(book.id, db=_FakeDB(), current_user=user)
    assert response.media_type == "application/zip"

    graph = await books.get_book_obsidian_graph(book.id, db=_FakeDB(), current_user=user)
    assert graph["node_count"] == 1
    relations = await books.get_book_obsidian_note_relations(book.id, path="Lore/Scene.md", db=_FakeDB(), current_user=user)
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
async def test_export_cover_archive_hide_and_delete_routes(monkeypatch):
    user = _user()
    book = _book(user_id=user.id, title="Atlas Draft")
    chapter = SimpleNamespace(number=1, title="One", s3_key="chapters/1.json")

    monkeypatch.setattr(books, "get_owned_book", _async_value(book))
    monkeypatch.setattr(books, "require_author_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(books.storage, "download_book", lambda _key: b"stored")
    monkeypatch.setattr(books, "deserialize_manuscript_content", lambda _raw: {"text": "SCENE\nBody", "html": "<p>Body</p>"})
    monkeypatch.setattr(books, "strip_scene_metadata_from_manuscript_text", lambda text: text.replace("SCENE\n", ""))
    monkeypatch.setattr(books, "build_writer_workspace_payload", lambda _book: {"manuscript_front_matter": {"title": "Atlas Draft"}})
    monkeypatch.setattr(books, "list_novel_scenes", _async_value([{"source": "manual", "status": "active"}]))
    monkeypatch.setattr(books, "list_obsidian_notes", _async_value([{"path": "Lore/Scene.md"}]))
    monkeypatch.setattr(books, "get_book_with_collaboration_access", _async_value((book, None)))
    monkeypatch.setattr(books, "manuscript_pdf_compiled", lambda **_kwargs: b"pdf")
    monkeypatch.setattr(books, "manuscript_epub_compiled", lambda **_kwargs: b"epub")
    monkeypatch.setattr(books, "manuscript_obsidian_vault_zip", lambda **_kwargs: b"zip")
    monkeypatch.setattr(books, "manuscript_docx", lambda **_kwargs: b"docx")

    db = _FakeDB(execute_values=[_Result(all_rows=[])])
    with pytest.raises(HTTPException) as exc:
        await books.export_manuscript(book.id, db=db, current_user=user)
    assert exc.value.status_code == 404

    for fmt, media_type in (
        ("pdf", "application/pdf"),
        ("epub", "application/epub+zip"),
        ("obsidian", "application/zip"),
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
        expected_name = "Atlas-Draft-manuscript-vault.zip" if fmt == "obsidian" else f"Atlas-Draft-manuscript.{fmt}"
        assert response.headers["Content-Disposition"] == f'attachment; filename="{expected_name}"'

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
    secondary = SimpleNamespace(id=other_id, book_id=book.id)
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
        "compose_character_description",
        lambda trait_state, archetype, arc_summary, personality_tags, motivations, relationship_summaries=None: (
            f"{archetype}:{trait_state.get('eyes', 'na')}|{len(relationship_summaries or [])}"
        ),
    )
    monkeypatch.setattr(books, "character_status", lambda _character: "active")
    monkeypatch.setattr(books, "build_character_arc_tracker", lambda *_args, **_kwargs: {"goal": "Protect the city", "diagnostics": []})
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
    monkeypatch.setattr(books, "build_character_bible_obsidian_context", _async_value(context))
    monkeypatch.setattr(books, "load_obsidian_vault_overrides", _async_value({"Character/Iris.md": "override"}))
    monkeypatch.setattr(books, "character_bible_obsidian_folder", lambda **_kwargs: (b"zip", "atlas"))
    monkeypatch.setattr(books, "character_bible_markdown", lambda **_kwargs: ("# Bible", "atlas"))
    monkeypatch.setattr(books, "character_bible_pdf", lambda **_kwargs: b"pdf")
    monkeypatch.setattr(books, "character_bible_docx", lambda **_kwargs: b"docx")
    monkeypatch.setattr(books, "character_bible_obsidian_preview", lambda **_kwargs: {"root_folder": "Atlas", "files": []})
    monkeypatch.setattr(books, "list_obsidian_vault_notes", _async_value([{"path": "Characters/Iris.md", "source": "character_bible", "content": "bio"}]))
    monkeypatch.setattr(books, "save_obsidian_vault_note", _async_value({"path": "Characters/Iris.md", "source": "character_bible", "content": "bio", "persisted": True}))

    db = _FakeDB(
        get_values=[book],
        execute_values=[
            _Result(scalars=[character, other_character]),
            _Result(scalars=[relationship]),
            _Result(scalars=[]),
            _Result(scalars=[]),
        ],
    )
    payload = await books.get_book_characters(book.id, db=db, current_user=user)
    assert payload[0]["description"] == "hero:green|1"
    assert payload[0]["goal"] == "Protect the city"
    assert payload[0]["arc_tracker"]["goal"] == "Protect the city"

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
        db=_FakeDB(get_values=[character, secondary]),
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
        db=_FakeDB(get_values=[relationship]),
        current_user=user,
    )
    assert updated_rel["rel_type"] == "family"

    deleted_rel = await books.delete_book_relationship(book.id, relationship.id, db=_FakeDB(get_values=[relationship]), current_user=user)
    assert deleted_rel["deleted"] == str(relationship.id)

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
        ("obsidian_folder", "application/zip"),
    ):
        response = await books.export_character_bible(book.id, format=fmt, db=_FakeDB(), current_user=user)
        assert response.media_type == media_type
        extension = "zip" if fmt == "obsidian_folder" else fmt
        assert response.headers["Content-Disposition"] == f'attachment; filename="atlas-character-bible.{extension}"'

    preview = await books.preview_character_bible_obsidian(book.id, db=_FakeDB(), current_user=user)
    assert preview["root_folder"] == "Atlas"
    notes = await books.list_character_bible_obsidian_notes(book.id, db=_FakeDB(), current_user=user)
    assert notes[0]["path"] == "Characters/Iris.md"
    saved = await books.save_character_bible_obsidian_note(
        book.id,
        ObsidianVaultNoteBody(path="Characters/Iris.md", content="bio"),
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
        await books.get_book_cover_public(book.id, token="ok", db=_FakeDB())
    assert exc.value.status_code == 503

    with pytest.raises(HTTPException) as exc:
        await books.get_book_character_card_public(book.id, character.id, token="ok", db=_FakeDB())
    assert exc.value.status_code == 503
