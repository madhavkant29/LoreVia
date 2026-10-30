import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book
from app.models.character import Character, CharacterState
from app.models.user import User
from app.services import extraction_character_persistence_service
from app.services.extraction_character_persistence_service import (
    _accept_existing_character_match,
    _build_observed_state_snapshot,
    _changed,
    _diff,
    _observed_trait_keys,
)


@pytest.mark.asyncio
async def test_existing_curated_character_keeps_manual_profile_during_extraction_match(db):
    user = User(
        email="curated-extraction@lorevia.app", username="curatedextract", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Curated cast", format="manual", s3_key="books/curated.txt")
    db.add(book)
    await db.flush()
    character = Character(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Mara Vale",
        first_chapter=1,
        aliases=["Captain Vale"],
        goal="protect her sister",
        trait_state={"hair": {"value": "black", "confidence": 0.9}},
        analysis_metadata={"user_curated": True, "review_note": "Keep her profile"},
    )
    db.add(character)
    await db.flush()
    key_cache: dict = {}
    pending_candidates: dict = {}
    pending_updates: dict = {}

    accepted = await _accept_existing_character_match(
        db,
        book_id=book.id,
        chapter_number=2,
        entity={
            "name": "Mara Vale",
            "aliases": ["The Captain"],
            "goal": "seek a crown",
            "traits": {"hair": {"value": "red", "confidence": 0.99}},
            "confidence": 0.95,
            "evidence": {"mention_count": 2},
        },
        existing_id=character.id,
        existing_characters=[character],
        character_key_cache=key_cache,
        pending_first_chapter_candidates=pending_candidates,
        pending_first_chapter_updates=pending_updates,
        reason_code="name_match",
        source_batch_key="book:2:1",
    )
    await db.flush()

    assert accepted is True
    assert character.aliases == ["Captain Vale"]
    assert character.goal == "protect her sister"
    assert character.trait_state["hair"]["value"] == "black"
    assert character.analysis_metadata["review_note"] == "Keep her profile"
    states = (
        (
            await db.execute(
                select(CharacterState).where(CharacterState.character_id == character.id)
            )
        )
        .scalars()
        .all()
    )
    assert states == []


def test_observed_state_snapshot_preserves_conflicting_incoming_value():
    merged = {"eyes": {"value": "blue", "confidence": 0.9, "type": "objective"}}
    observed = {"eyes": {"value": "green", "confidence": 0.8, "type": "objective"}}

    snapshot = _build_observed_state_snapshot(merged, observed)

    assert snapshot["eyes"]["value"] == "green"
    assert merged["eyes"]["value"] == "blue"


def test_state_change_detects_equal_confidence_value_contradiction():
    old = {"eyes": {"value": "blue", "confidence": 0.8}}
    new = {"eyes": {"value": "green", "confidence": 0.8}}

    assert _changed(old, new) is True
    assert _diff(old, new) == "eyes: blue->green"


@pytest.mark.asyncio
async def test_cluster_mentions_skip_duplicate_source_position_from_overlap(monkeypatch):
    calls = []

    async def record(_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        extraction_character_persistence_service, "record_character_mention", record
    )
    span = {"chunk_index": 0, "start": 23, "end": 27}
    await extraction_character_persistence_service._record_entity_cluster_mentions(
        object(),
        book_id=uuid.uuid4(),
        chapter_number=1,
        entity={
            "name": "Mara",
            "cluster_members": [
                {
                    "name": "Mara",
                    "source_batch_key": "book:1:1",
                    "source_text": "Mara opened the gate.",
                    "source_mentions": [span],
                    "evidence": {"mention_count": 1, "strong_mention_count": 1},
                },
                {
                    "name": "Mara",
                    "source_batch_key": "book:1:2",
                    "source_text": "Mara opened the gate.",
                    "source_mentions": [span],
                    "evidence": {"mention_count": 1, "strong_mention_count": 1},
                },
            ],
        },
        matched_character_id=None,
        resolver_status="pending",
        resolver_reasons=[],
    )

    assert len(calls) == 1
    assert calls[0]["evidence"]["mention_count"] == 1
    assert calls[0]["evidence"]["source_mentions"] == [span]


@pytest.mark.asyncio
async def test_cluster_mentions_do_not_count_alias_inside_full_name_twice(monkeypatch):
    calls = []

    async def record(_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        extraction_character_persistence_service, "record_character_mention", record
    )
    await extraction_character_persistence_service._record_entity_cluster_mentions(
        object(),
        book_id=uuid.uuid4(),
        chapter_number=1,
        entity={
            "name": "Mara Vale",
            "cluster_members": [
                {
                    "name": "Mara",
                    "source_batch_key": "book:1:1",
                    "source_text": "Mara Vale waited. Mara answered.",
                    "source_mentions": [
                        {"chunk_index": 0, "start": 0, "end": 4},
                        {"chunk_index": 0, "start": 18, "end": 22},
                    ],
                    "evidence": {"mention_count": 2, "strong_mention_count": 2},
                },
                {
                    "name": "Mara Vale",
                    "source_batch_key": "book:1:1",
                    "source_text": "Mara Vale waited. Mara answered.",
                    "source_mentions": [{"chunk_index": 0, "start": 0, "end": 9}],
                    "evidence": {"mention_count": 1, "strong_mention_count": 1},
                },
            ],
        },
        matched_character_id=None,
        resolver_status="pending",
        resolver_reasons=[],
    )

    assert [(call["raw_name"], call["evidence"]["mention_count"]) for call in calls] == [
        ("Mara", 1),
        ("Mara Vale", 1),
    ]
    assert calls[0]["evidence"]["source_mentions"] == [{"chunk_index": 0, "start": 18, "end": 22}]
    assert calls[1]["evidence"]["source_mentions"] == [{"chunk_index": 0, "start": 0, "end": 9}]


def test_state_change_ignores_case_and_whitespace_only_difference():
    old = {"hair": {"value": "Dark Brown", "confidence": 0.8}}
    new = {"hair": {"value": "  dark   brown ", "confidence": 0.8}}

    assert _changed(old, new) is False
    assert _diff(old, new) == "minor update"


def test_observed_trait_keys_exclude_carried_profile_traits():
    assert _observed_trait_keys(
        {
            "eyes": {"value": "green", "confidence": 0.8},
            "hair": {"confidence": 0.9},
        }
    ) == ["eyes"]
