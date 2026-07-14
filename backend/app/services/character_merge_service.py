from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.models.character import Character, CharacterDuplicateSuggestion
from app.services.character_identity.constraints import add_identity_constraint
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book
from app.utils.characters.duplicates import refresh_character_duplicate_suggestions
from app.utils.characters.merging import merge_characters
from app.utils.characters.review import mark_character_candidates_merged


async def merge_book_characters_for_user(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    primary_id: uuid.UUID,
    secondary_id: uuid.UUID,
) -> dict[str, str]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    primary = await db.get(Character, primary_id)
    secondary = await db.get(Character, secondary_id)
    if not primary or not secondary or primary.book_id != book.id or secondary.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if primary.id == secondary.id:
        return {"merged": str(primary.id)}

    merged = await merge_characters(db, primary.id, secondary.id, book.id)
    await mark_character_candidates_merged(
        db,
        book_id=book.id,
        primary_character_id=merged.id,
        secondary_character_id=secondary.id,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(merged)
    return {"merged": str(merged.id)}


async def accept_duplicate_suggestion_for_user(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    suggestion_id: uuid.UUID,
) -> dict[str, str]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    suggestion = await db.get(CharacterDuplicateSuggestion, suggestion_id)
    if not suggestion or suggestion.book_id != book.id:
        raise HTTPException(404, "Duplicate suggestion not found")

    primary = await db.get(Character, suggestion.primary_character_id)
    secondary = await db.get(Character, suggestion.secondary_character_id)
    if not primary or not secondary or primary.book_id != book.id or secondary.book_id != book.id:
        raise HTTPException(404, "Character not found")

    merged = await merge_characters(db, primary.id, secondary.id, book.id)
    suggestion.status = "accepted"
    await mark_character_candidates_merged(
        db,
        book_id=book.id,
        primary_character_id=merged.id,
        secondary_character_id=secondary.id,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {"merged": str(merged.id), "suggestion_id": str(suggestion.id)}


async def dismiss_duplicate_suggestion_for_user(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    suggestion_id: uuid.UUID,
) -> dict[str, str]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    suggestion = await db.get(CharacterDuplicateSuggestion, suggestion_id)
    if not suggestion or suggestion.book_id != book.id:
        raise HTTPException(404, "Duplicate suggestion not found")
    suggestion.status = "dismissed"
    suggestion.auto_dismissed = False
    suggestion.dismissal_reason = "user_keep_separate"
    primary = await db.get(Character, suggestion.primary_character_id)
    secondary = await db.get(Character, suggestion.secondary_character_id)
    if primary and secondary and primary.book_id == book.id and secondary.book_id == book.id:
        await add_identity_constraint(
            db,
            book_id=book.id,
            left_character_id=primary.id,
            right_character_id=secondary.id,
            left_text=primary.name,
            right_text=secondary.name,
            constraint_type="not_same_character",
            reason="user_keep_separate",
            source="manual",
            confidence=1.0,
        )
    await db.commit()
    return {"dismissed": str(suggestion.id)}
