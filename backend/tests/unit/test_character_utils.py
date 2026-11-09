import uuid
from datetime import UTC, datetime, timezone

import pytest

from app.models.book import Book, Chapter
from app.models.character import Character, CharacterAlias
from app.models.intelligence import BookChunk
from app.models.user import User
from app.utils.characters import serialization as character_serialization
from app.utils.characters.candidates import build_character_analysis_payload
from app.utils.characters.governance import infer_character_trust_tier, is_cast_visible_character
from app.utils.characters.manual import (
    backfill_character_first_chapters_for_chapter_text,
    find_earliest_character_mention_chapters,
)
from app.utils.characters.presentation import build_character_dossier_summary
from app.utils.characters.review import set_character_review_state
from app.utils.characters.serialization import serialize_book_character


def test_build_character_analysis_payload_fills_consistent_defaults():
    character = Character(
        book_id=uuid.uuid4(),
        name="Captain Mira",
        first_chapter=1,
        mention_count=1,
        is_manual=False,
    )
    character.analysis_metadata = {
        "summary_quality": "",
        "quality_flags": ["generic_summary", " "],
        "rejected_duplicate_candidates": ["Mira", ""],
    }

    payload = build_character_analysis_payload(character)

    assert payload["evidence_count"] == 1
    assert payload["summary_quality"] == "generic"
    assert payload["grounding_passage_count"] == 1
    assert payload["confidence_band"] == "medium"
    assert payload["needs_review"] is True
    assert payload["quality_flags"] == ["generic_summary", "light_grounding"]
    assert payload["rejected_duplicate_candidates"] == ["Mira"]


def test_build_character_analysis_payload_preserves_manual_character_reason():
    character = Character(
        book_id=uuid.uuid4(),
        name="Aunt May",
        first_chapter=2,
        mention_count=0,
        is_manual=True,
    )
    character.analysis_metadata = {}

    payload = build_character_analysis_payload(character)

    assert payload["persistence_reason"] == "manual_character"
    assert payload["confidence_band"] == "medium"
    assert payload["quality_flags"] == []


def test_build_character_analysis_payload_exposes_narrator_source_evidence():
    character = Character(book_id=uuid.uuid4(), name="Arun Vale", first_chapter=2, mention_count=1)
    citation = {"chapter_number": 2, "excerpt": "I told her I was Arun Vale"}
    character.analysis_metadata = {"first_person_self_identification": citation}

    assert (
        build_character_analysis_payload(character)["first_person_self_identification"] == citation
    )

    character.analysis_metadata = {"first_person_self_identification": "invalid"}
    assert build_character_analysis_payload(character)["first_person_self_identification"] is None


def test_build_character_analysis_payload_marks_common_single_token_as_review_only():
    character = Character(
        book_id=uuid.uuid4(),
        name="Actually",
        first_chapter=1,
        mention_count=1,
        is_manual=False,
    )
    character.analysis_metadata = {
        "quality_flags": ["generic_summary", "light_grounding"],
        "grounding_passage_count": 1,
    }

    payload = build_character_analysis_payload(character)

    assert payload["trust_tier"] == "review_only"
    assert "common_single_token" in payload["trust_reasons"]
    assert payload["needs_review"] is True


def test_infer_character_trust_tier_keeps_grounded_single_name_visible():
    character = Character(
        book_id=uuid.uuid4(),
        name="Grete",
        first_chapter=1,
        mention_count=2,
        personality_tags=["sharp"],
    )
    character.analysis_metadata = {
        "grounding_passage_count": 2,
        "quality_flags": [],
    }

    trust_tier, reasons = infer_character_trust_tier(character)

    assert trust_tier == "visible"
    assert reasons == ["legacy_visible"]
    assert is_cast_visible_character(character) is True


def test_build_character_dossier_summary_requires_cross_chapter_support_for_single_tokens():
    dossier = build_character_dossier_summary(
        name="Grete",
        aliases=[],
        evidence={
            "mention_count": 2,
            "chapter_numbers": [1],
            "has_dialogue_or_action": True,
            "verifier": {
                "local": {
                    "person_ner_mentions": 1,
                    "mid_sentence_mentions": 1,
                },
                "final": {
                    "confidence_band": "accept",
                },
            },
        },
    )

    assert dossier["strict_auto_eligible"] is False
    assert "insufficient_cross_chapter_support" in dossier["strict_auto_reason_codes"]


def test_set_character_review_state_controls_cast_visibility():
    character = Character(
        book_id=uuid.uuid4(),
        name="Actually",
        first_chapter=1,
        mention_count=1,
    )

    set_character_review_state(
        character,
        visibility_state="quarantined",
        approval_state="pending_review",
        approval_source="manual_review",
        reason_codes=["sentence_start_common_word"],
    )

    payload = build_character_analysis_payload(character)

    assert character.visibility_state == "quarantined"
    assert character.approval_state == "pending_review"
    assert is_cast_visible_character(character) is False
    assert payload["approval_reason_codes"] == ["sentence_start_common_word"]


def test_serialize_book_character_includes_declared_profile_fields():
    book_id = uuid.uuid4()
    character_id = uuid.uuid4()
    alias_id = uuid.uuid4()
    created_at = datetime(2026, 6, 11, tzinfo=UTC)
    character = Character(
        id=character_id,
        book_id=book_id,
        name="Captain Mira",
        aliases=["Mira"],
        role="mc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=8,
        trait_state={"build": {"value": "slight", "confidence": 0.8, "type": "objective"}},
        hair="silver",
        eyes="gray",
        build="slight",
        age_descriptor="middle-aged",
        distinguishing="scar over left eyebrow",
        personality_tags=["focused"],
        motivations=["Keep the crew alive"],
        fears=["Losing command"],
        created_at=created_at,
    )
    character.alias_records = [
        CharacterAlias(
            id=alias_id,
            book_id=book_id,
            character_id=character_id,
            alias_text="The Captain",
            normalized_alias="captain",
            alias_kind="title",
            source="extraction",
            confidence=0.82,
            created_at=created_at,
        ),
    ]

    payload = serialize_book_character(
        character,
        rel_summaries={},
        states=[],
        relationships=[],
        counterpart_names={},
        voice_profile=None,
        total_chapters=4,
    )

    assert payload["alias_records"] == [
        {
            "id": str(alias_id),
            "book_id": str(book_id),
            "character_id": str(character_id),
            "alias_text": "The Captain",
            "normalized_alias": "captain",
            "alias_kind": "title",
            "source": "extraction",
            "confidence": 0.82,
            "created_at": created_at,
        }
    ]
    assert payload["hair"] == "silver"
    assert payload["eyes"] == "gray"
    assert payload["build"] == "slight"
    assert payload["age_descriptor"] == "middle-aged"
    assert payload["distinguishing"] == "scar over left eyebrow"


def test_serialize_character_alias_records_returns_empty_for_uninspectable_object():
    assert character_serialization.serialize_character_alias_records(object()) == []


def test_serialize_character_alias_records_propagates_unexpected_inspection_errors(monkeypatch):
    def fail_inspect(_character):
        raise RuntimeError("inspection regression")

    monkeypatch.setattr(character_serialization, "inspect", fail_inspect)

    with pytest.raises(RuntimeError, match="inspection regression"):
        character_serialization.serialize_character_alias_records(object())


@pytest.mark.asyncio
async def test_backfill_character_first_chapters_repairs_stale_first_appearance(db):
    user = User(
        email="character-utils@lorevia.app", username="character-utils", password_hash="hash"
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Repair Test",
        format="epub",
        s3_key="books/repair-test.epub",
        status="ready",
        total_chapters=2,
    )
    db.add(book)
    await db.flush()

    chapter_one = Chapter(
        book_id=book.id, number=1, title="Chapter 1", s3_key="chapters/1.txt", processed=True
    )
    chapter_two = Chapter(
        book_id=book.id, number=2, title="Chapter 2", s3_key="chapters/2.txt", processed=True
    )
    db.add_all([chapter_one, chapter_two])
    await db.flush()

    db.add_all(
        [
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_one.id,
                chunk_index=0,
                text="Captain Mira steps onto the deck before sunrise.",
                embedding=[0.0] * 1536,
                token_count=8,
            ),
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_two.id,
                chunk_index=0,
                text="Mira orders the crew toward the storm wall.",
                embedding=[0.0] * 1536,
                token_count=8,
            ),
        ]
    )

    character = Character(
        book_id=book.id,
        name="Captain Mira",
        aliases=["Mira"],
        first_chapter=2,
        last_seen_chapter=2,
        mention_count=2,
    )
    db.add(character)
    await db.commit()

    changed = await backfill_character_first_chapters_for_chapter_text(
        db,
        book_id=book.id,
        chapter_number=1,
        chapter_text="Captain Mira steps onto the deck before sunrise.",
    )

    assert changed is True
    assert character.first_chapter == 1
    assert character.last_seen_chapter == 2


@pytest.mark.asyncio
async def test_find_earliest_character_mention_chapters_batches_lookups(db):
    user = User(
        email="character-utils-batch@lorevia.app",
        username="character-utils-batch",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Batch Lookup Test",
        format="epub",
        s3_key="books/batch-lookup.epub",
        status="ready",
        total_chapters=3,
    )
    db.add(book)
    await db.flush()

    chapter_one = Chapter(
        book_id=book.id, number=1, title="Chapter 1", s3_key="chapters/1.txt", processed=True
    )
    chapter_two = Chapter(
        book_id=book.id, number=2, title="Chapter 2", s3_key="chapters/2.txt", processed=True
    )
    chapter_three = Chapter(
        book_id=book.id, number=3, title="Chapter 3", s3_key="chapters/3.txt", processed=True
    )
    db.add_all([chapter_one, chapter_two, chapter_three])
    await db.flush()

    db.add_all(
        [
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_one.id,
                chunk_index=0,
                text="Captain Mira steps onto the deck before sunrise.",
                embedding=[0.0] * 1536,
                token_count=8,
            ),
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_two.id,
                chunk_index=0,
                text="Jon Ember studies the storm map in silence.",
                embedding=[0.0] * 1536,
                token_count=8,
            ),
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_three.id,
                chunk_index=0,
                text="Mira and Jon Ember argue over the route.",
                embedding=[0.0] * 1536,
                token_count=9,
            ),
        ]
    )
    await db.commit()

    resolved = await find_earliest_character_mention_chapters(
        db,
        book_id=book.id,
        candidates_by_key={
            "mira": ["Captain Mira", "Mira"],
            "jon": ["Jon Ember"],
            "missing": ["Asha Vale"],
        },
        upto_chapter=3,
    )

    assert resolved == {"mira": 1, "jon": 2}
