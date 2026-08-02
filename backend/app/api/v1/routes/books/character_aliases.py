from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.schemas.character import CharacterAliasBody, CharacterAliasOut
from app.services.character_alias_service import (
    add_book_character_alias_for_user,
    delete_book_character_alias_for_user,
    list_book_character_aliases_for_user,
)

router = APIRouter()


@router.get("/{book_id}/characters/{character_id}/aliases", response_model=list[CharacterAliasOut])
async def list_book_character_aliases(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await list_book_character_aliases_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )


@router.post(
    "/{book_id}/characters/{character_id}/aliases",
    response_model=CharacterAliasOut,
    status_code=201,
)
async def add_book_character_alias(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterAliasBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await add_book_character_alias_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
        body=body,
    )


@router.delete("/{book_id}/characters/{character_id}/aliases/{alias_id}")
async def delete_book_character_alias(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    alias_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await delete_book_character_alias_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
        alias_id=alias_id,
    )
