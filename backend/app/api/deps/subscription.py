from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.config import settings
from app.api.deps.auth import get_current_user
from app.models.book import Book
from app.models.user import User


async def check_upload_limit(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.tier in ("pro", "power", "admin"):
        return
    count = (await db.execute(
        select(func.count()).select_from(Book).where(Book.user_id == current_user.id)
    )).scalar() or 0
    if count >= settings.FREE_MAX_BOOKS:
        raise HTTPException(403, f"Free tier limited to {settings.FREE_MAX_BOOKS} books. Upgrade to Pro.")


async def require_pro(current_user: User = Depends(get_current_user)):
    if current_user.tier not in ("pro", "power", "admin"):
        raise HTTPException(403, "This feature requires Pro or Power subscription.")


async def require_power(current_user: User = Depends(get_current_user)):
    if current_user.tier not in ("power", "admin"):
        raise HTTPException(403, "This feature requires a Power subscription.")
