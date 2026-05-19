import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import BookChunk
from app.models.user import User
from app.utils.character_utils import (
    backfill_character_first_chapters_for_chapter_text,
    build_character_analysis_payload,
)


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


@pytest.mark.asyncio
async def test_backfill_character_first_chapters_repairs_stale_first_appearance(db):
    user = User(email="character-utils@lorevia.app", username="character-utils", password_hash="hash")
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

    chapter_one = Chapter(book_id=book.id, number=1, title="Chapter 1", s3_key="chapters/1.txt", processed=True)
    chapter_two = Chapter(book_id=book.id, number=2, title="Chapter 2", s3_key="chapters/2.txt", processed=True)
    db.add_all([chapter_one, chapter_two])
    await db.flush()

    db.add_all([
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
    ])

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
