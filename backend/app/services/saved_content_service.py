"""Bounded keyset reads for a user's saved quotes and notes."""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models.book import Book, BookNote, Chapter
from app.models.intelligence import QuoteEntry
from app.utils.tag_utils import ENTITY_TYPE_NOTE, list_custom_tags_for_entity_ids


def _encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(row_id)}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        if created_at.tzinfo is None:
            raise ValueError("Cursor timestamp must include timezone")
        return created_at, uuid.UUID(str(payload["id"]))
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise HTTPException(400, "Invalid saved-content cursor") from exc


async def list_saved_quotes_page(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 100))
    statement = (
        select(QuoteEntry, Book.title, Chapter.title)
        .join(Book, Book.id == QuoteEntry.book_id)
        .outerjoin(
            Chapter,
            and_(
                Chapter.book_id == QuoteEntry.book_id,
                Chapter.number == QuoteEntry.chapter_number,
            ),
        )
        .where(QuoteEntry.user_id == user_id)
    )
    if cursor:
        created_at, row_id = _decode_cursor(cursor)
        statement = statement.where(
            or_(
                QuoteEntry.created_at < created_at,
                and_(QuoteEntry.created_at == created_at, QuoteEntry.id < row_id),
            )
        )
    rows = list(
        (
            await db.execute(
                statement.order_by(QuoteEntry.created_at.desc(), QuoteEntry.id.desc()).limit(
                    bounded_limit + 1
                )
            )
        ).all()
    )
    has_more = len(rows) > bounded_limit
    page_rows = rows[:bounded_limit]
    return {
        "items": [
            {
                "id": str(quote.id),
                "book_id": str(quote.book_id),
                "book_title": book_title,
                "chapter_number": quote.chapter_number,
                "chapter_title": chapter_title,
                "character_name": quote.character_name,
                "quote_text": quote.quote_text,
                "note": quote.note,
                "created_at": quote.created_at,
            }
            for quote, book_title, chapter_title in page_rows
        ],
        "next_cursor": (
            _encode_cursor(page_rows[-1][0].created_at, page_rows[-1][0].id)
            if has_more and page_rows
            else None
        ),
        "has_more": has_more,
    }


async def list_saved_notes_page(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 50,
    cursor: str | None = None,
    include_body: bool = False,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 100))
    statement = (
        select(BookNote, Book, Chapter.title)
        .join(Book, Book.id == BookNote.book_id)
        .outerjoin(
            Chapter,
            and_(Chapter.book_id == BookNote.book_id, Chapter.number == BookNote.chapter_number),
        )
        .where(BookNote.user_id == user_id)
    )
    if not include_body:
        statement = statement.options(
            load_only(
                BookNote.id,
                BookNote.book_id,
                BookNote.chapter_number,
                BookNote.title,
                BookNote.created_at,
                BookNote.updated_at,
            )
        )
    if cursor:
        updated_at, row_id = _decode_cursor(cursor)
        statement = statement.where(
            or_(
                BookNote.updated_at < updated_at,
                and_(BookNote.updated_at == updated_at, BookNote.id < row_id),
            )
        )
    rows = list(
        (
            await db.execute(
                statement.order_by(BookNote.updated_at.desc(), BookNote.id.desc()).limit(
                    bounded_limit + 1
                )
            )
        ).all()
    )
    has_more = len(rows) > bounded_limit
    page_rows = rows[:bounded_limit]
    tags = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_NOTE,
        entity_ids=[note.id for note, _book, _chapter_title in page_rows],
    )
    return {
        "items": [
            {
                "id": str(note.id),
                "book_id": str(book.id),
                "book_title": book.title,
                "chapter_number": note.chapter_number,
                "chapter_title": chapter_title,
                "title": note.title,
                "body": note.body if include_body else None,
                "tags": tags.get(note.id, []),
                "created_at": note.created_at,
                "updated_at": note.updated_at,
            }
            for note, book, chapter_title in page_rows
        ],
        "next_cursor": (
            _encode_cursor(page_rows[-1][0].updated_at, page_rows[-1][0].id)
            if has_more and page_rows
            else None
        ),
        "has_more": has_more,
    }
