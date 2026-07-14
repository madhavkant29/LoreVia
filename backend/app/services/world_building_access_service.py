from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book


async def get_owned_world_building_book(
    db: AsyncSession, book_id: uuid.UUID, user_id: uuid.UUID
) -> Book:
    book = (
        (
            await db.execute(
                select(Book).where(
                    Book.id == book_id,
                    Book.user_id == user_id,
                )
            )
        )
        .scalars()
        .first()
    )
    if not book:
        raise HTTPException(404, "Book not found")
    return book
