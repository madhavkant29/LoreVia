import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import BookChunk
from app.models.user import User
from app.utils.character_utils import backfill_character_first_chapters_for_chapter_text


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
