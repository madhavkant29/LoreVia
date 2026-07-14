from types import SimpleNamespace
import uuid

import pytest

from app.services import extraction_chapter_embedding_service
from app.services.extraction_chapter_embedding_service import persist_chapter_chunks_with_embeddings


class _FakeDb:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


@pytest.mark.asyncio
async def test_persist_chapter_chunks_with_embeddings_adds_book_chunks(monkeypatch):
    calls = []

    def fake_chunk_text(text, config):
        calls.append(("chunk", text, config.target_tokens))
        return ["first chunk", "second chunk"]

    def fake_build_chunk_embedding_text(*, chapter_number, chapter_title, text):
        return f"{chapter_number}:{chapter_title}:{text}"

    async def fake_embed_batch(batch, *, db, user_id, book_id, feature):
        calls.append(("embed", list(batch), user_id, book_id, feature))
        return [[1.0, 0.0], [0.0, 1.0]][: len(batch)]

    monkeypatch.setattr(extraction_chapter_embedding_service, "chunk_text", fake_chunk_text)
    monkeypatch.setattr(
        extraction_chapter_embedding_service,
        "build_chunk_embedding_text",
        fake_build_chunk_embedding_text,
    )
    monkeypatch.setattr(extraction_chapter_embedding_service, "embed_batch", fake_embed_batch)
    monkeypatch.setattr(extraction_chapter_embedding_service.settings, "EXTRACTION_EMBED_BATCH_SIZE", 10)
    monkeypatch.setattr(extraction_chapter_embedding_service.settings, "EXTRACTION_EMBED_CONCURRENCY", 2)

    db = _FakeDb()
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    chapter = SimpleNamespace(id=uuid.uuid4(), title="Storm")

    chunks = await persist_chapter_chunks_with_embeddings(
        db,
        book=book,
        chapter=chapter,
        chapter_number=3,
        ch_data={"title": "Fallback", "text": "chapter text"},
    )

    assert chunks == ["first chunk", "second chunk"]
    assert [item.text for item in db.added] == ["first chunk", "second chunk"]
    assert [item.chunk_index for item in db.added] == [0, 1]
    assert [item.token_count for item in db.added] == [2, 2]
    assert db.added[0].book_id == book.id
    assert db.added[0].chapter_id == chapter.id
    assert calls[0][0] == "chunk"
    assert calls[1] == (
        "embed",
        ["3:Storm:first chunk", "3:Storm:second chunk"],
        book.user_id,
        book.id,
        "chapter_chunk_embedding",
    )
