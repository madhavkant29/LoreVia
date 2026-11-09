from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.services.character_identity.repair import CharacterIdentityRepairJob
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book


async def preview_character_reprocess(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    allow_merge_safe_pairs: bool,
    allow_demote_obvious_noise: bool,
) -> dict:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    _ensure_author_mode(book)
    job = CharacterIdentityRepairJob(
        db,
        book_id=book.id,
        allow_merge_safe_pairs=allow_merge_safe_pairs,
        allow_demote_obvious_noise=allow_demote_obvious_noise,
    )
    plan = await job.preview()
    return plan.to_payload()


async def apply_character_reprocess(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    allow_merge_safe_pairs: bool,
    allow_demote_obvious_noise: bool,
) -> dict:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    _ensure_author_mode(book)
    job = CharacterIdentityRepairJob(
        db,
        book_id=book.id,
        allow_merge_safe_pairs=allow_merge_safe_pairs,
        allow_demote_obvious_noise=allow_demote_obvious_noise,
    )
    result = await job.apply()
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return result.to_payload()


def _ensure_author_mode(book) -> None:
    if book.mode != "author":
        raise HTTPException(400, "Character reprocessing is only available in author mode")
