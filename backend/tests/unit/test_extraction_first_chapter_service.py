from types import SimpleNamespace
import uuid

import pytest

from app.services import extraction_first_chapter_service
from app.services.extraction_first_chapter_service import backfill_pending_first_chapter_mentions


@pytest.mark.asyncio
async def test_backfill_pending_first_chapter_mentions_updates_first_and_last_seen(monkeypatch):
    book_id = uuid.uuid4()
    character_id = uuid.uuid4()
    character = SimpleNamespace(first_chapter=5, last_seen_chapter=5)
    calls = []

    async def fake_find(db, *, book_id, candidates_by_key, upto_chapter):
        calls.append((db, book_id, candidates_by_key, upto_chapter))
        return {character_id: 2}

    monkeypatch.setattr(
        extraction_first_chapter_service,
        "find_earliest_character_mention_chapters",
        fake_find,
    )

    count = await backfill_pending_first_chapter_mentions(
        object(),
        book_id=book_id,
        chapter_number=7,
        pending_first_chapter_candidates={character_id: ["Ada"]},
        pending_first_chapter_updates={character_id: character},
    )

    assert count == 1
    assert character.first_chapter == 2
    assert character.last_seen_chapter == 5
    assert calls[0][1:] == (book_id, {character_id: ["Ada"]}, 7)


@pytest.mark.asyncio
async def test_backfill_pending_first_chapter_mentions_ignores_missing_update_targets(
    monkeypatch,
):
    character_id = uuid.uuid4()

    async def fake_find(*args, **kwargs):
        return {character_id: 1}

    monkeypatch.setattr(
        extraction_first_chapter_service,
        "find_earliest_character_mention_chapters",
        fake_find,
    )

    count = await backfill_pending_first_chapter_mentions(
        object(),
        book_id=uuid.uuid4(),
        chapter_number=4,
        pending_first_chapter_candidates={character_id: ["Ada"]},
        pending_first_chapter_updates={},
    )

    assert count == 1


@pytest.mark.asyncio
async def test_backfill_pending_first_chapter_mentions_skips_empty_candidates(monkeypatch):
    called = False

    async def fake_find(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        extraction_first_chapter_service,
        "find_earliest_character_mention_chapters",
        fake_find,
    )

    count = await backfill_pending_first_chapter_mentions(
        object(),
        book_id=uuid.uuid4(),
        chapter_number=1,
        pending_first_chapter_candidates={},
        pending_first_chapter_updates={},
    )

    assert count == 0
    assert called is False
