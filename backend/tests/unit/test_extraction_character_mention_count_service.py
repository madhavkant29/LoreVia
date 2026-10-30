import uuid

import pytest

from app.models.book import Book
from app.models.character import Character, CharacterMention
from app.models.user import User
from app.services.extraction_chapter_record_service import replace_chapter_extraction_records
from app.services.extraction_character_mention_count_service import (
    count_character_mention_evidence,
    reconcile_character_mention_counts,
)


def test_count_character_mention_evidence_deduplicates_aliases_and_chapters():
    character_id = uuid.uuid4()
    rows = [
        (
            character_id,
            1,
            {"source_mentions": [{"chunk_index": 0, "start": 0, "end": 9}]},
        ),
        (
            character_id,
            1,
            {"source_mentions": [{"chunk_index": 0, "start": 0, "end": 4}]},
        ),
        (
            character_id,
            2,
            {"source_mentions": [{"chunk_index": 0, "start": 0, "end": 9}]},
        ),
        (character_id, 2, None),
    ]

    assert count_character_mention_evidence(rows) == {character_id: 3}
    assert count_character_mention_evidence([]) == {}


@pytest.mark.asyncio
async def test_reconcile_character_mentions_does_not_inflate_count_on_chapter_retry(db):
    user = User(email="mention-retry@lorevia.app", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Mention retry",
        format="pdf",
        s3_key="books/mention-retry.pdf",
    )
    db.add(book)
    await db.flush()
    character = Character(
        book_id=book.id,
        name="Mara Vale",
        first_chapter=1,
        mention_count=99,
    )
    db.add(character)
    await db.flush()
    db.add_all(
        [
            CharacterMention(
                book_id=book.id,
                chapter_number=chapter_number,
                raw_name="Mara Vale",
                normalized_name="mara vale",
                matched_character_id=character.id,
                evidence={
                    "source_mentions": [
                        {"chunk_index": 0, "start": index * 20, "end": index * 20 + 9}
                        for index in range(mention_count)
                    ]
                },
            )
            for chapter_number, mention_count in ((1, 2), (2, 3))
        ]
    )
    await db.flush()

    await reconcile_character_mention_counts(
        db,
        book_id=book.id,
        chapter_number=2,
        previous_character_ids=set(),
        characters=[character],
    )
    assert character.mention_count == 5
    assert character.analysis_metadata["mention_count_basis"] == "source_positions"

    previous_ids = await replace_chapter_extraction_records(db, book_id=book.id, chapter_number=2)
    assert previous_ids == {character.id}
    db.add(
        CharacterMention(
            book_id=book.id,
            chapter_number=2,
            raw_name="Mara Vale",
            normalized_name="mara vale",
            matched_character_id=character.id,
            evidence={
                "source_mentions": [
                    {"chunk_index": 0, "start": 0, "end": 9},
                    {"chunk_index": 0, "start": 20, "end": 29},
                ]
            },
        )
    )
    await db.flush()

    await reconcile_character_mention_counts(
        db,
        book_id=book.id,
        chapter_number=2,
        previous_character_ids=previous_ids,
        characters=[character],
    )
    assert character.mention_count == 4

    previous_ids = await replace_chapter_extraction_records(db, book_id=book.id, chapter_number=2)
    await reconcile_character_mention_counts(
        db,
        book_id=book.id,
        chapter_number=2,
        previous_character_ids=previous_ids,
        characters=[character],
    )
    assert character.mention_count == 2
    assert character.analysis_metadata["mention_count_basis"] == "source_positions"

    db.add(
        CharacterMention(
            book_id=book.id,
            chapter_number=2,
            raw_name="Mara Vale",
            normalized_name="mara vale",
            matched_character_id=character.id,
            evidence={},
        )
    )
    await db.flush()
    await reconcile_character_mention_counts(
        db,
        book_id=book.id,
        chapter_number=2,
        previous_character_ids=set(),
        characters=[character],
    )
    assert character.mention_count == 3
    assert character.analysis_metadata["mention_count_basis"] == "mixed_legacy_records"
