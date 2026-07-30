import uuid
from types import SimpleNamespace

import pytest

from app.services import extraction_chapter_record_service
from app.services.extraction_chapter_record_service import stage_chapter_for_extraction


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeDb:
    def __init__(self, chapter):
        self.chapter = chapter
        self.execute_calls = 0
        self.flush_calls = 0
        self.added = []

    async def execute(self, _statement):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _ScalarResult(self.chapter)
        return _ScalarResult(None)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_calls += 1


@pytest.mark.asyncio
async def test_stage_chapter_for_extraction_updates_existing_chapter_and_resets_generated_rows(
    monkeypatch,
):
    synced = []

    async def fake_sync_chapter_media(db, book, chapter, ch_data):
        synced.append((db, book, chapter, ch_data))

    monkeypatch.setattr(
        extraction_chapter_record_service,
        "_sync_chapter_media",
        fake_sync_chapter_media,
    )

    book = SimpleNamespace(id=uuid.uuid4())
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        number=3,
        s3_key="chapter-key",
        title="Old",
        description="Old description",
        chapter_kind="chapter",
        processed=True,
        word_count=1,
        content_version=1,
        analysis_state={"status": "done"},
    )
    db = _FakeDb(chapter)

    result = await stage_chapter_for_extraction(
        db,
        book,
        {
            "number": 3,
            "title": "New",
            "description": "New description",
            "chapter_kind": "prologue",
            "content_version": 2,
            "text": "One two [[IMAGE:map]]",
            "images": [{"marker": "[[IMAGE:map]]"}],
        },
        3,
    )

    assert result is chapter
    assert chapter.title == "New"
    assert chapter.description == "New description"
    assert chapter.chapter_kind == "prologue"
    assert chapter.processed is False
    assert chapter.word_count == 2
    assert chapter.content_version == 2
    assert chapter.analysis_state["status"] == "pending"
    assert chapter.analysis_state["source_integrity"]["media_marker_count"] == 1
    assert chapter.analysis_state["source_integrity"]["stored_media_count"] == 1
    assert db.flush_calls == 2
    assert db.execute_calls == 5
    assert synced and synced[0][2] is chapter
