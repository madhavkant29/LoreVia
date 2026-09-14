from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.models.character import Character
from app.schemas.books import CharacterPartitionBody
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book
from app.utils.characters.duplicates import refresh_character_duplicate_suggestions
from app.utils.characters.partitioning import partition_character


async def partition_book_character_for_user(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterPartitionBody,
) -> dict[str, object]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character partition is only available in author mode")

    try:
        created = await partition_character(
            db,
            source=character,
            user_id=current_user.id,
            partitions=[{"name": item.name, "aliases": item.aliases} for item in body.partitions],
        )
    except ValueError as exc:
        raise HTTPException(400, "Character partition request is invalid.") from exc

    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {
        "replaced": str(character_id),
        "created": [str(item.id) for item in created],
    }
