from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.utils.books import chapter_versions


@pytest.mark.asyncio
async def test_snapshot_chapter_version_swallows_storage_io_but_propagates_unexpected_errors(
    monkeypatch,
):
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        number=1,
        title="One",
        s3_key="chapters/one.txt",
        word_count=12,
    )

    monkeypatch.setattr(
        chapter_versions,
        "download_book",
        lambda _key: (_ for _ in ()).throw(OSError("object missing")),
    )
    assert (
        await chapter_versions.snapshot_chapter_version(
            SimpleNamespace(), book, chapter, note="before edit"
        )
        is None
    )

    monkeypatch.setattr(
        chapter_versions,
        "download_book",
        lambda _key: (_ for _ in ()).throw(RuntimeError("storage client regression")),
    )
    with pytest.raises(RuntimeError, match="storage client regression"):
        await chapter_versions.snapshot_chapter_version(
            SimpleNamespace(), book, chapter, note="before edit"
        )
