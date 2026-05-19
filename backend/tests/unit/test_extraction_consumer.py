from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from app.workers.consumers import extraction_consumer


@pytest.mark.asyncio
async def test_process_chapter_clears_inflight_key_when_processing_crashes(monkeypatch):
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        hidden_at=None,
        writer_workspace={},
        total_chapters=1,
        mode="reader",
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=book.user_id))
    db.execute = AsyncMock(side_effect=RuntimeError("boom"))

    deleted_keys: list[str] = []

    async def _fake_cache_set_if_absent(*_args, **_kwargs):
        return True

    async def _fake_cache_del(key: str):
        deleted_keys.append(key)

    monkeypatch.setattr(extraction_consumer, "cache_set_if_absent", _fake_cache_set_if_absent)
    monkeypatch.setattr(extraction_consumer, "cache_del", _fake_cache_del)

    with pytest.raises(RuntimeError, match="boom"):
        await extraction_consumer._process_chapter(
            db,
            book,
            {"number": 1, "title": "One", "text": "Failure path."},
        )

    assert deleted_keys == [extraction_consumer.key_extraction_inflight(str(book.id), 1)]
