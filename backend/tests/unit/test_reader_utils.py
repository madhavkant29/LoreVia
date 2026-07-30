import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

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


def test_normalize_summary_response_only_swallows_invalid_json(monkeypatch):
    fallback = reader_utils.normalize_summary_response("{not json", ["event"], [], [])
    assert fallback["content"] == "{not json"
    assert fallback["key_events"] == ["event"]

    def _json_bug(_value: str):
        raise RuntimeError("json wrapper bug")

    monkeypatch.setattr(reader_utils.json, "loads", _json_bug)

    with pytest.raises(RuntimeError, match="json wrapper bug"):
        reader_utils.normalize_summary_response('{"summary": "ok"}', [], [], [])


@pytest.mark.asyncio
async def test_serialize_chapter_media_only_swallows_storage_io(monkeypatch):
    media = SimpleNamespace(
        id=uuid.uuid4(),
        marker="[[IMAGE:map]]",
        storage_key="media/map.png",
        asset_type="image",
        content_type="image/png",
        caption="Map",
        sort_order=1,
        created_at=None,
    )
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(all=lambda: [(media, uuid.uuid4())])
    monkeypatch.setattr(reader_utils, "get_presigned_url", lambda _key: None)

    def _storage_missing(_key: str) -> bytes:
        raise OSError("object unavailable")

    monkeypatch.setattr(reader_utils, "download_book", _storage_missing)

    items = await reader_utils.serialize_chapter_media(db, uuid.uuid4())

    assert items[0]["content_base64"] is None

    def _unexpected_download_bug(_key: str) -> bytes:
        raise RuntimeError("download wrapper bug")

    monkeypatch.setattr(reader_utils, "download_book", _unexpected_download_bug)

    with pytest.raises(RuntimeError, match="download wrapper bug"):
        await reader_utils.serialize_chapter_media(db, uuid.uuid4())


def test_parse_chapter_from_source_only_swallows_storage_and_parser_failures(monkeypatch):
    book = SimpleNamespace(
        s3_key="books/source.pdf",
        format="pdf",
        preserve_chapter_numbers=False,
        preserve_source_chapters=False,
        work_type="novel",
    )

    def _storage_missing(_key: str) -> bytes:
        raise OSError("object unavailable")

    monkeypatch.setattr(reader_utils, "download_book", _storage_missing)

    assert reader_utils.parse_chapter_from_source(book, 1) is None

    monkeypatch.setattr(reader_utils, "download_book", lambda _key: b"pdf")

    def _parser_failure(*_args, **_kwargs):
        raise RuntimeError("invalid pdf")

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf", _parser_failure)

    assert reader_utils.parse_chapter_from_source(book, 1) is None

    def _parser_bug(*_args, **_kwargs):
        raise AssertionError("parser invariant")

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf", _parser_bug)

    with pytest.raises(AssertionError, match="parser invariant"):
        reader_utils.parse_chapter_from_source(book, 1)


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

    monkeypatch.setattr(
        "app.workers.tasks.analysis_tasks.analyse_chapter_task", _Task(), raising=False
    )

    await reader_utils.queue_analysis_if_missing(db, chapter)

    assert called["queued"] is False


@pytest.mark.asyncio
async def test_queue_analysis_if_missing_creates_durable_execution(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        number=1,
        s3_key="chapters/test/1.txt",
        title="One",
        analysis_state={},
    )
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(user_id=uuid.uuid4(), total_chapters=1)
    dispatched: list[dict] = []

    monkeypatch.setattr(reader_utils, "chapter_has_detailed_summary", AsyncMock(return_value=False))
    monkeypatch.setattr(reader_utils, "cache_set_if_absent", AsyncMock(return_value=True))

    async def _enqueue(_db, **kwargs):
        dispatched.append(kwargs)
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr("app.services.task_execution_service.enqueue_analysis_execution", _enqueue)

    queued = await reader_utils.queue_analysis_if_missing(db, chapter)

    assert queued is True
    db.commit.assert_not_called()
    assert chapter.analysis_state == {}
    assert dispatched[0]["chapter_id"] == chapter.id
    assert dispatched[0]["book_id"] == chapter.book_id


@pytest.mark.asyncio
async def test_queue_analysis_if_missing_clears_queued_key_when_dispatch_fails(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        number=1,
        s3_key="chapters/test/1.txt",
        title="One",
        analysis_state={},
    )
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(user_id=uuid.uuid4(), total_chapters=1)
    deleted_keys: list[str] = []

    monkeypatch.setattr(reader_utils, "chapter_has_detailed_summary", AsyncMock(return_value=False))
    monkeypatch.setattr(reader_utils, "cache_set_if_absent", AsyncMock(return_value=True))

    async def _fake_cache_del(key):
        deleted_keys.append(key)

    monkeypatch.setattr(reader_utils, "cache_del", _fake_cache_del)

    async def _raise(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.services.task_execution_service.enqueue_analysis_execution", _raise)

    queued = await reader_utils.queue_analysis_if_missing(db, chapter)

    assert queued is False
    db.commit.assert_not_called()
    assert deleted_keys == [reader_utils.key_analysis_queued(str(chapter.id))]


@pytest.mark.asyncio
async def test_build_summary_collection_does_not_enqueue_missing_analysis_by_default(monkeypatch):
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
    queue_analysis = AsyncMock(return_value=True)
    monkeypatch.setattr(reader_utils, "queue_analysis_if_missing", queue_analysis)

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
            "chapter_kind": "chapter",
            "read": True,
            "available": False,
            "status": "pending",
            "content": None,
            "key_events": [],
        }
    ]
    queue_analysis.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_summary_collection_can_enqueue_missing_analysis_when_requested(monkeypatch):
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
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [])),
    ]

    monkeypatch.setattr(reader_utils, "summary_visible_chapter_set", AsyncMock(return_value={1}))
    queue_analysis = AsyncMock(return_value=True)
    monkeypatch.setattr(reader_utils, "queue_analysis_if_missing", queue_analysis)

    payload = await reader_utils.build_summary_collection_payload(
        db,
        book=book,
        current_user=current_user,
        progress=SimpleNamespace(current_chapter=0),
        intelligence_map={1: True},
        enqueue_missing_analysis=True,
    )

    assert payload["summaries"][0]["status"] == "queued"
    queue_analysis.assert_awaited_once_with(
        db,
        chapter,
        current_user,
        detailed_summary_chapter_ids=set(),
    )
