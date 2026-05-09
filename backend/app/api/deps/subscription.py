from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.book import Book
from app.models.user import User
from app.utils.billing_utils import (
    ARCHITECT_TIER,
    AUTHOR_TIER,
    ADMIN_TIER,
    UNLIMITED_BOOK_TIERS,
    user_access_tier,
)


async def check_upload_limit(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_access_tier(current_user) in UNLIMITED_BOOK_TIERS:
        return
    count = (await db.execute(
        select(func.count()).select_from(Book).where(Book.user_id == current_user.id)
    )).scalar() or 0
    if count >= settings.FREE_MAX_BOOKS:
        raise HTTPException(403, f"Free tier limited to {settings.FREE_MAX_BOOKS} books. Upgrade to Reader or Author.")


async def require_pro(current_user: User = Depends(get_current_user)):
    if user_access_tier(current_user) not in (AUTHOR_TIER, ARCHITECT_TIER, ADMIN_TIER):
        raise HTTPException(403, "This feature requires an Author or Lore Architect subscription.")


async def require_power(current_user: User = Depends(get_current_user)):
    if user_access_tier(current_user) not in (ARCHITECT_TIER, ADMIN_TIER):
        raise HTTPException(403, "This feature requires a Lore Architect subscription.")
