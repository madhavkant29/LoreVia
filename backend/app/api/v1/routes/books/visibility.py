import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.books import BookVisibilitySummaryOut
from app.services.book_visibility_service import build_book_visibility_summary
from app.utils.books.collaboration_access import (
    get_book_with_collaboration_access,
    require_book_owner_access,
)

router = APIRouter()


@router.get("/{book_id}/visibility-summary", response_model=BookVisibilitySummaryOut)
async def get_book_visibility_summary(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    require_book_owner_access(book, current_user, collaborator)
    return await build_book_visibility_summary(db, book, None, current_user.id)
