import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.services import extraction_chapter_embedding_service
from app.services.extraction_chapter_embedding_service import (
    prepare_chapter_chunks_with_embeddings,
    replace_chapter_chunks,
)


class _FakeDb:
    def __init__(self):
        self.added = []
        self.execute_calls = 0

    def add(self, value):
        self.added.append(value)

    def add_all(self, values):
        self.added.extend(values)

    async def execute(self, _statement):
        self.execute_calls += 1


@pytest.mark.asyncio
async def test_prepare_chapter_chunks_with_embeddings_builds_complete_rows(monkeypatch):
    calls = []

    def fake_chunk_text(text, config):
        calls.append(("chunk", text, config.target_tokens))
        return ["first chunk", "second chunk"]

    def fake_build_chunk_embedding_text(*, chapter_number, chapter_title, text):
        return f"{chapter_number}:{chapter_title}:{text}"

    async def fake_embed_batch(batch, *, db, user_id, book_id, feature):
        assert db is None
        calls.append(("embed", list(batch), user_id, book_id, feature))
        return [[1.0, 0.0], [0.0, 1.0]][: len(batch)]

    monkeypatch.setattr(extraction_chapter_embedding_service, "chunk_text", fake_chunk_text)
    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "build_chunk_embedding_text",
        fake_build_chunk_embedding_text,
    )
    monkeypatch.setattr(extraction_chapter_embedding_service, "embed_batch", fake_embed_batch)
    monkeypatch.setattr(
        extraction_chapter_embedding_service.settings, "EXTRACTION_EMBED_BATCH_SIZE", 10
    )
    monkeypatch.setattr(
        extraction_chapter_embedding_service.settings, "EXTRACTION_EMBED_CONCURRENCY", 2
    )

    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    chapter = SimpleNamespace(id=uuid.uuid4(), title="Storm")

    prepared = await prepare_chapter_chunks_with_embeddings(
        book=book,
        chapter=chapter,
        chapter_number=3,
        ch_data={"title": "Fallback", "text": "chapter text"},
    )

    assert prepared.texts == ["first chunk", "second chunk"]
    assert [item.text for item in prepared.rows] == ["first chunk", "second chunk"]
    assert [item.chunk_index for item in prepared.rows] == [0, 1]
    assert [item.token_count for item in prepared.rows] == [2, 2]
    assert prepared.rows[0].book_id == book.id
    assert prepared.rows[0].chapter_id == chapter.id
    assert calls[0][0] == "chunk"
    assert calls[1] == (
        "embed",
        ["3:Storm:first chunk", "3:Storm:second chunk"],
        book.user_id,
        book.id,
        "chapter_chunk_embedding",
    )


@pytest.mark.asyncio
async def test_embedding_batch_failure_cancels_and_drains_siblings(monkeypatch):
    sibling_cancelled = False

    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "chunk_text",
        lambda *_args, **_kwargs: ["first", "second"],
    )
    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "build_chunk_embedding_text",
        lambda **kwargs: kwargs["text"],
    )
    monkeypatch.setattr(
        extraction_chapter_embedding_service.settings, "EXTRACTION_EMBED_BATCH_SIZE", 1
    )
    monkeypatch.setattr(
        extraction_chapter_embedding_service.settings, "EXTRACTION_EMBED_CONCURRENCY", 2
    )

    async def fake_embed_batch(batch, **_kwargs):
        nonlocal sibling_cancelled
        if batch == ["first"]:
            await asyncio.sleep(0)
            raise RuntimeError("embedding failed")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            sibling_cancelled = True
            raise

    monkeypatch.setattr(extraction_chapter_embedding_service, "embed_batch", fake_embed_batch)

    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    chapter = SimpleNamespace(id=uuid.uuid4(), title="Storm")

    with pytest.raises(RuntimeError, match="embedding failed"):
        await prepare_chapter_chunks_with_embeddings(
            book=book,
            chapter=chapter,
            chapter_number=3,
            ch_data={"title": "Storm", "text": "chapter text"},
        )

    assert sibling_cancelled is True


@pytest.mark.asyncio
async def test_embedding_count_mismatch_preserves_existing_chunks(monkeypatch):
    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "chunk_text",
        lambda *_args, **_kwargs: ["first", "second"],
    )
    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "build_chunk_embedding_text",
        lambda **kwargs: kwargs["text"],
    )
    monkeypatch.setattr(
        extraction_chapter_embedding_service.settings, "EXTRACTION_EMBED_BATCH_SIZE", 10
    )

    async def incomplete_embed_batch(*_args, **_kwargs):
        return [[1.0, 0.0]]

    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "embed_batch",
        incomplete_embed_batch,
    )

    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    chapter = SimpleNamespace(id=uuid.uuid4(), title="Storm")

    with pytest.raises(RuntimeError, match="chapter_chunk_embedding_count_mismatch"):
        await prepare_chapter_chunks_with_embeddings(
            book=book,
            chapter=chapter,
            chapter_number=3,
            ch_data={"title": "Storm", "text": "chapter text"},
        )


@pytest.mark.asyncio
async def test_replace_chapter_chunks_swaps_only_prepared_complete_rows(monkeypatch):
    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "chunk_text",
        lambda *_args, **_kwargs: ["first"],
    )
    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "build_chunk_embedding_text",
        lambda **kwargs: kwargs["text"],
    )

    async def fake_embed_batch(*_args, **_kwargs):
        return [[1.0, 0.0]]

    monkeypatch.setattr(extraction_chapter_embedding_service, "embed_batch", fake_embed_batch)
    db = _FakeDb()
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    chapter = SimpleNamespace(id=uuid.uuid4(), title="Storm")
    prepared = await prepare_chapter_chunks_with_embeddings(
        book=book,
        chapter=chapter,
        chapter_number=3,
        ch_data={"title": "Storm", "text": "chapter text"},
    )

    await replace_chapter_chunks(db, prepared, chapter_id=chapter.id)

    assert db.execute_calls == 1
    assert db.added == prepared.rows
