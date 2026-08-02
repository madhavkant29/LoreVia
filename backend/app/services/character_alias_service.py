from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.models.character import Character, CharacterAlias
from app.schemas.character import CharacterAliasBody
from app.services.character_identity.merge import add_character_alias
from app.services.character_identity.normalization import normalize_name
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book
from app.utils.characters.text import clean_string_list


async def list_book_character_aliases_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
) -> list[CharacterAlias]:
    book, character = await _load_book_character(
        db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )
    aliases = (
        (
            await db.execute(
                select(CharacterAlias)
                .where(
                    CharacterAlias.book_id == book.id,
                    CharacterAlias.character_id == character.id,
                )
                .order_by(CharacterAlias.alias_kind, CharacterAlias.alias_text)
            )
        )
        .scalars()
        .all()
    )
    return list(aliases)


async def add_book_character_alias_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterAliasBody,
) -> CharacterAlias:
    book, character = await _load_book_character(
        db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )
    alias = await add_character_alias(
        db,
        character=character,
        alias_text=body.alias_text,
        alias_kind=body.alias_kind,
        source="manual",
        confidence=body.confidence,
    )
    if alias is None:
        raise HTTPException(400, "Alias is invalid or duplicates the character name")
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(alias)
    return alias


async def delete_book_character_alias_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    alias_id: uuid.UUID,
) -> dict[str, str]:
    book, character = await _load_book_character(
        db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )
    alias = await db.get(CharacterAlias, alias_id)
    if not alias or alias.book_id != book.id or alias.character_id != character.id:
        raise HTTPException(404, "Alias not found")
    normalized_removed = alias.normalized_alias
    character.aliases = [
        value
        for value in clean_string_list(character.aliases or [])
        if normalize_name(value) != normalized_removed
    ]
    await db.delete(alias)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {"deleted": str(alias_id)}


async def _load_book_character(
    db: AsyncSession,
    *,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
) -> tuple[Any, Character]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    return book, character
