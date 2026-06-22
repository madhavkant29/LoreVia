import uuid
from types import SimpleNamespace

import pytest

from app.services import chapter_recovery_service


class _FakeDB:
    def __init__(self):
        self.commits = 0
        self.refreshes = []

    async def commit(self):
        self.commits += 1

    async def refresh(self, item):
        self.refreshes.append(item)

    async def execute(self, *_args, **_kwargs):
        raise AssertionError("execute should not be used in this test")


@pytest.mark.asyncio
async def test_resolve_reader_chapter_payload_returns_source_fallback_for_missing_chapter(
    monkeypatch,
):
    book = SimpleNamespace(
        id=uuid.uuid4(),
        format="pdf",
        preserve_chapter_numbers=False,
        preserve_source_chapters=False,
        work_type="novel",
        s3_key="books/atlas.pdf",
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "parse_chapter_from_source",
        lambda *_args, **_kwargs: {
            "title": "Recovered",
            "text": "Recovered text",
            "images": [{"bytes": b"x", "marker": "[[IMAGE:1]]"}],
        },
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "serialize_inline_images",
        lambda images: [{"count": len(images)}],
    )

    payload = await chapter_recovery_service.resolve_reader_chapter_payload(
        _FakeDB(),
        book=book,
        chapter=None,
        chapter_num=2,
    )

    assert payload is not None
    assert payload["chapter_title"] == "Recovered"
    assert payload["text_content"] == "Recovered text"
    assert payload["media"] == [{"count": 1}]
    assert payload["analysis_status"] is None


@pytest.mark.asyncio
async def test_resolve_reader_chapter_payload_queues_repair_for_mismatched_source_integrity(
    monkeypatch,
):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        number=1,
        title="One",
        s3_key="chapters/atlas/1.json",
        content_version=2,
        analysis_state={"status": "queued", "generated_modes": [], "attempt_count": 1},
    )
    book = SimpleNamespace(
        id=uuid.uuid4(),
        format="pdf",
        preserve_chapter_numbers=False,
        preserve_source_chapters=False,
        work_type="novel",
        s3_key="books/atlas.pdf",
    )
    db = _RepairDB()

    monkeypatch.setattr(chapter_recovery_service, "download_book", lambda _key: b"payload")
    monkeypatch.setattr(
        chapter_recovery_service,
        "deserialize_manuscript_content",
        lambda _raw: {"text": "", "html": None},
    )

    async def _fake_serialize_media(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        chapter_recovery_service,
        "serialize_chapter_media",
        _fake_serialize_media,
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "chapter_body_needs_scene_workspace_fallback",
        lambda *_args, **_kwargs: False,
    )

    async def _fake_queue(
        _db, *, book, chapter, current_user=None, reason="source_integrity_mismatch"
    ):
        chapter.analysis_state = {
            **(chapter.analysis_state or {}),
            "source_integrity": {
                "text_present": False,
                "media_marker_count": 0,
                "stored_media_count": 0,
                "recovery_status": "queued",
                "last_recovery_error": reason,
            },
        }
        return True

    monkeypatch.setattr(chapter_recovery_service, "queue_chapter_repair_if_needed", _fake_queue)

    payload = await chapter_recovery_service.resolve_reader_chapter_payload(
        db,
        book=book,
        chapter=chapter,
        chapter_num=1,
    )

    assert payload is not None
    assert payload["text_content"] == ""
    assert payload["source_integrity"]["recovery_status"] == "queued"


@pytest.mark.asyncio
async def test_resolve_reader_chapter_payload_merges_fallback_media_when_markers_exist(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        number=2,
        title="Two",
        s3_key="chapters/atlas/2.json",
        content_version=1,
        analysis_state={"status": "queued", "generated_modes": [], "attempt_count": 1},
    )
    book = SimpleNamespace(
        id=uuid.uuid4(),
        format="pdf",
        preserve_chapter_numbers=False,
        preserve_source_chapters=False,
        work_type="novel",
        s3_key="books/atlas.pdf",
    )
    db = _RepairDB()

    monkeypatch.setattr(chapter_recovery_service, "download_book", lambda _key: b"payload")
    monkeypatch.setattr(
        chapter_recovery_service,
        "deserialize_manuscript_content",
        lambda _raw: {"text": "[[IMAGE:1]] Stored text", "html": None},
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "serialize_chapter_media",
        _async_empty_media,
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "parse_chapter_from_source",
        lambda *_args, **_kwargs: {
            "title": "Two",
            "text": "[[IMAGE:1]] Stored text",
            "html": None,
            "images": [{"marker": "[[IMAGE:1]]", "url": "/api/v1/reader/media/demo"}],
        },
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "serialize_inline_images",
        lambda images: [{"marker": image["marker"], "url": image["url"]} for image in images],
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "merge_media_items",
        lambda stored, fallback: [*stored, *fallback],
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "chapter_body_needs_scene_workspace_fallback",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(chapter_recovery_service, "queue_chapter_repair_if_needed", _async_true)

    payload = await chapter_recovery_service.resolve_reader_chapter_payload(
        db,
        book=book,
        chapter=chapter,
        chapter_num=2,
    )

    assert payload is not None
    assert payload["media"] == [{"marker": "[[IMAGE:1]]", "url": "/api/v1/reader/media/demo"}]


@pytest.mark.asyncio
async def test_repair_chapter_payload_from_source_persists_recovered_state(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        number=1,
        title="One",
        s3_key="chapters/atlas/1.json",
        content_version=2,
        analysis_state={"status": "queued", "generated_modes": [], "attempt_count": 1},
    )
    book = SimpleNamespace(
        id=uuid.uuid4(),
        format="pdf",
        preserve_chapter_numbers=False,
        preserve_source_chapters=False,
        work_type="novel",
        s3_key="books/atlas.pdf",
    )
    db = _RepairDB()

    uploads: list[tuple[str, str]] = []

    monkeypatch.setattr(
        chapter_recovery_service,
        "parse_chapter_from_source",
        lambda *_args, **_kwargs: {
            "title": "One",
            "text": "[[IMAGE:1]] repaired",
            "images": [{"bytes": b"x", "marker": "[[IMAGE:1]]"}],
        },
    )
    monkeypatch.setattr(
        chapter_recovery_service,
        "upload_text",
        lambda key, content: uploads.append((key, content)) or key,
    )
    monkeypatch.setattr(
        chapter_recovery_service, "upload_binary", lambda key, raw, content_type=None: key
    )
    monkeypatch.setattr(chapter_recovery_service, "cache_del", _async_none)

    result = await chapter_recovery_service.repair_chapter_payload_from_source(
        db,
        book=book,
        chapter=chapter,
    )

    assert result is True
    assert uploads
    assert chapter.analysis_state["source_integrity"]["recovery_status"] == "recovered"
    assert db.commits == 1


async def _async_none(*_args, **_kwargs):
    return None


async def _async_empty_media(*_args, **_kwargs):
    return []


class _RepairDB(_FakeDB):
    def __init__(self):
        super().__init__()
        self.added = []
        self.deleted = []

    async def execute(self, *_args, **_kwargs):
        return _EmptyResult()

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_queue_chapter_repair_if_needed_marks_state_and_enqueues(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        number=3,
        analysis_state={"status": "pending", "generated_modes": [], "attempt_count": 1},
    )
    book = SimpleNamespace(id=uuid.uuid4())
    db = _FakeDB()
    queued: list[dict] = []

    class _Task:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            queued.append({"args": args, "queue": queue, "kwargs": kwargs})

    monkeypatch.setattr(chapter_recovery_service, "cache_set_if_absent", _async_true)
    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.repair_chapter_payload_task", _Task(), raising=False
    )

    scheduled = await chapter_recovery_service.queue_chapter_repair_if_needed(
        db,
        book=book,
        chapter=chapter,
    )

    assert scheduled is True
    assert chapter.analysis_state["source_integrity"]["recovery_status"] == "queued"
    assert queued[0]["args"] == [str(book.id), chapter.number]
    assert db.commits == 1


async def _async_true(*_args, **_kwargs):
    return True


class _EmptyResult:
    def all(self):
        return []
