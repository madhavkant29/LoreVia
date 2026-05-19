import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.book import Book
from app.models.character import Character, CharacterState
from app.schemas.character import CharacterOut
from app.utils.character_utils import serialize_character_detail

router = APIRouter()


@router.get("/{character_id}", response_model=CharacterOut)
async def get_character(
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404)
    book = await db.get(Book, char.book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    return serialize_character_detail(char)


@router.get("/{character_id}/state")
async def get_character_state(
    character_id: uuid.UUID,
    chapter: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Spoiler-free state at chapter N."""
    state = (await db.execute(
        select(CharacterState)
        .where(CharacterState.character_id == character_id, CharacterState.at_chapter <= chapter)
        .order_by(CharacterState.at_chapter.desc()).limit(1)
    )).scalar()

    if state:
        char = await db.get(Character, character_id)
        if not char:
            raise HTTPException(404)
        book = await db.get(Book, char.book_id)
        if not book or book.user_id != current_user.id:
            raise HTTPException(404)
        return {"trait_state": state.trait_snapshot, "at_chapter": state.at_chapter,
                "arc_note": state.arc_note, "prompt_delta": state.prompt_delta}

    char = await db.get(Character, character_id)
    if not char:
        raise HTTPException(404)
    book = await db.get(Book, char.book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    return {"trait_state": char.trait_state, "at_chapter": 0}
