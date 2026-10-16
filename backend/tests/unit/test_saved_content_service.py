from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.models.book import Book, BookNote, Chapter
from app.models.intelligence import QuoteEntry
from app.models.user import User
from app.services.saved_content_service import list_saved_notes_page, list_saved_quotes_page


async def _saved_content_rows(db):
    user = User(email="saved-content@example.com", password_hash="hashed")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Saved Atlas",
        format="pdf",
        s3_key="books/saved-atlas.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="The Gate",
        s3_key="chapters/saved-atlas/1.json",
    )
    db.add(chapter)
    await db.flush()
    tied = datetime(2026, 9, 12, 9, 0, tzinfo=UTC)
    for index in range(3):
        db.add(
            QuoteEntry(
                user_id=user.id,
                book_id=book.id,
                chapter_number=1,
                quote_text=f"Quote {index}",
                created_at=tied,
            )
        )
        db.add(
            BookNote(
                user_id=user.id,
                book_id=book.id,
                chapter_number=1,
                title=f"Note {index}",
                body=f"Body {index}",
                created_at=tied,
                updated_at=tied,
            )
        )
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_saved_quote_cursor_pages_do_not_skip_tied_timestamps(db):
    user = await _saved_content_rows(db)

    first = await list_saved_quotes_page(db, user_id=user.id, limit=2)
    second = await list_saved_quotes_page(db, user_id=user.id, limit=2, cursor=first["next_cursor"])

    ids = [item["id"] for item in [*first["items"], *second["items"]]]
    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert first["has_more"] is True
    assert second["has_more"] is False


@pytest.mark.asyncio
async def test_saved_note_pages_omit_body_by_default_and_include_it_on_request(db):
    user = await _saved_content_rows(db)

    metadata_page = await list_saved_notes_page(db, user_id=user.id, limit=2)
    body_page = await list_saved_notes_page(db, user_id=user.id, limit=2, include_body=True)

    assert all(item["body"] is None for item in metadata_page["items"])
    assert all(item["body"].startswith("Body ") for item in body_page["items"])
    assert metadata_page["items"][0]["book_title"] == "Saved Atlas"
    assert metadata_page["items"][0]["chapter_title"] == "The Gate"


@pytest.mark.asyncio
async def test_saved_content_rejects_malformed_cursor(db):
    user = await _saved_content_rows(db)

    with pytest.raises(HTTPException) as exc_info:
        await list_saved_quotes_page(db, user_id=user.id, cursor="not-a-cursor")

    assert exc_info.value.status_code == 400
