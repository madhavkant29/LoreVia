from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_asset_token
from app.models.character import Character
from app.schemas.books import CharacterShareOut
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book
from app.utils.public.serialization import ensure_public_mode_enabled


async def share_book_character_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
) -> CharacterShareOut:
    ensure_public_mode_enabled()
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")

    token = create_asset_token(
        str(current_user.id),
        f"character-card:{book.id}:{character.id}",
        expires_minutes=7 * 24 * 60,
    )
    return CharacterShareOut(
        share_url=f"/share/character/{book.id}/{character.id}?token={token}",
        expires_in_minutes=7 * 24 * 60,
    )
