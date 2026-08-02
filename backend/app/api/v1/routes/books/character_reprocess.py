from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.services.character_reprocess_service import (
    apply_character_reprocess,
    preview_character_reprocess,
)

router = APIRouter()


@router.get("/{book_id}/character-review/reprocess")
async def preview_book_character_reprocess(
    book_id: uuid.UUID,
    allow_merge_safe_pairs: bool = Query(True),
    allow_demote_obvious_noise: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await preview_character_reprocess(
        db=db,
        current_user=current_user,
        book_id=book_id,
        allow_merge_safe_pairs=allow_merge_safe_pairs,
        allow_demote_obvious_noise=allow_demote_obvious_noise,
    )


@router.post("/{book_id}/character-review/reprocess")
async def apply_book_character_reprocess(
    book_id: uuid.UUID,
    allow_merge_safe_pairs: bool = Query(True),
    allow_demote_obvious_noise: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await apply_character_reprocess(
        db=db,
        current_user=current_user,
        book_id=book_id,
        allow_merge_safe_pairs=allow_merge_safe_pairs,
        allow_demote_obvious_noise=allow_demote_obvious_noise,
    )
