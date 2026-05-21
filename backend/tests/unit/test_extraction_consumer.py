from types import SimpleNamespace
import uuid

import pytest

from app.models.intelligence import CharacterRelationship
from app.workers.consumers import extraction_consumer


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)


@pytest.mark.asyncio
async def test_persist_relationship_records_resolves_alias_only_names(monkeypatch):
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    characters = [
        SimpleNamespace(id=left_id, name="Aikawa Jun", aliases=["Aikawa"]),
        SimpleNamespace(id=right_id, name="Ii", aliases=["Ii-chan"]),
    ]
    db = _FakeDB()
    review_calls: list[dict] = []

    async def _fake_record_candidate(*_args, **kwargs):
        review_calls.append(kwargs)

    monkeypatch.setattr(extraction_consumer, "record_character_candidate", _fake_record_candidate)

    persisted, unresolved, review_count = await extraction_consumer._persist_relationship_records(
        db,
        book_id=uuid.uuid4(),
        chapter_number=3,
        existing_characters=characters,
        relationships=[
            {
                "character_a": "Aikawa",
                "character_b": "Ii-chan",
                "type": "ally",
                "description": "Talk together",
                "source_batch_key": "batch-1",
            }
        ],
        key_cache={},
        persisted_signatures=set(),
    )

    assert persisted == 1
    assert unresolved == []
    assert review_count == 0
    assert review_calls == []
    assert len(db.added) == 1
    assert isinstance(db.added[0], CharacterRelationship)
    assert db.added[0].character_a_id == left_id
    assert db.added[0].character_b_id == right_id


@pytest.mark.asyncio
async def test_persist_relationship_records_quarantines_ambiguous_matches(monkeypatch):
    shared_alias = "Aikawa"
    characters = [
        SimpleNamespace(id=uuid.uuid4(), name="Aikawa Jun", aliases=[shared_alias]),
        SimpleNamespace(id=uuid.uuid4(), name="Aikawa", aliases=[]),
        SimpleNamespace(id=uuid.uuid4(), name="Ii", aliases=["Ii-chan"]),
    ]
    db = _FakeDB()
    review_calls: list[dict] = []

    async def _fake_record_candidate(*_args, **kwargs):
        review_calls.append(kwargs)

    monkeypatch.setattr(extraction_consumer, "record_character_candidate", _fake_record_candidate)

    persisted, unresolved, review_count = await extraction_consumer._persist_relationship_records(
        db,
        book_id=uuid.uuid4(),
        chapter_number=4,
        existing_characters=characters,
        relationships=[
            {
                "character_a": shared_alias,
                "character_b": "Ii-chan",
                "type": "rival",
                "description": "Argue",
                "source_batch_key": "batch-2",
            }
        ],
        key_cache={},
        persisted_signatures=set(),
    )

    assert persisted == 0
    assert len(unresolved) == 1
    assert review_count == 1
    assert len(review_calls) == 1
    assert review_calls[0]["reason_codes"] == ["relationship_unresolved", "relationship_ambiguous_character"]
