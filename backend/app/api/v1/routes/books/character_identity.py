from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.schemas.character import CharacterReviewOut
from app.services.character_identity_action_service import (
    get_book_character_review_for_user,
    get_character_identity_diagnostics_for_user,
    undo_character_identity_action_for_user,
)
from app.services.character_listing_service import list_book_characters_for_viewer

router = APIRouter()


@router.get("/{book_id}/characters")
async def get_book_characters(
    book_id: uuid.UUID,
    include: str | None = Query(
        None, description="Comma-separated sub-objects: arc_tracker, analysis_metadata, tags"
    ),
    fields: str | None = Query(None, description="Comma-separated character fields to keep"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await list_book_characters_for_viewer(
        db,
        book_id=book_id,
        current_user=current_user,
        include=include,
        fields=fields,
    )


@router.get("/{book_id}/character-review", response_model=CharacterReviewOut)
async def get_book_character_review(
    book_id: uuid.UUID,
    include_quarantined: bool = Query(True),
    include_places: bool = Query(False),
    include_rejected: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await get_book_character_review_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        include_quarantined=include_quarantined,
        include_places=include_places,
        include_rejected=include_rejected,
    )


@router.get("/{book_id}/characters/identity-diagnostics")
async def get_character_identity_diagnostics(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await get_character_identity_diagnostics_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
    )


@router.post("/{book_id}/characters/identity-actions/{action_id}/undo")
async def undo_character_identity_action(
    book_id: uuid.UUID,
    action_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await undo_character_identity_action_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        action_id=action_id,
    )
