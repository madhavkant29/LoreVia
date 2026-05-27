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
        return object()

    monkeypatch.setattr(extraction_consumer, "record_relationship_candidate", _fake_record_candidate)

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
        return object()

    monkeypatch.setattr(extraction_consumer, "record_relationship_candidate", _fake_record_candidate)

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
    assert review_calls[0]["reason_codes"] == [
        "relationship_unresolved",
        "character_a_ambiguous",
        "character_b_resolved",
    ]


@pytest.mark.asyncio
async def test_persist_relationship_records_does_not_count_duplicate_same_state_batches(monkeypatch):
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    characters = [
        SimpleNamespace(id=left_id, name="Aikawa Jun", aliases=["Aikawa"]),
        SimpleNamespace(id=right_id, name="Ii", aliases=["Ii-chan"]),
    ]
    db = _FakeDB()

    async def _fake_upsert(*_args, **_kwargs):
        return CharacterRelationship(
            book_id=uuid.uuid4(),
            character_a_id=left_id,
            character_b_id=right_id,
            rel_type="ally",
            description="Talk together",
            from_chapter=3,
        ), False

    monkeypatch.setattr(extraction_consumer, "upsert_relationship_timeline_state", _fake_upsert)

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

    assert persisted == 0
    assert unresolved == []
    assert review_count == 0


@pytest.mark.asyncio
async def test_embed_new_character_candidates_reuses_active_db_session(monkeypatch):
    observed: dict[str, object] = {}

    async def _fake_embed_batch(texts: list[str], **kwargs):
        observed["texts"] = texts
        observed["db"] = kwargs.get("db")
        observed["user_id"] = kwargs.get("user_id")
        observed["book_id"] = kwargs.get("book_id")
        observed["feature"] = kwargs.get("feature")
        return [[0.1, 0.2]]

    monkeypatch.setattr(extraction_consumer, "embed_batch", _fake_embed_batch)

    db = object()
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    entity = {"name": "Mara", "traits": {"eyes": {"value": "green"}}}

    result = await extraction_consumer._embed_new_character_candidates(
        [(entity, set())],
        db=db,
        user_id=user_id,
        book_id=book_id,
    )

    assert result == [[0.1, 0.2]]
    assert observed == {
        "texts": ["Character: Mara. eyes: green"],
        "db": db,
        "user_id": user_id,
        "book_id": book_id,
        "feature": "character_embedding",
    }
