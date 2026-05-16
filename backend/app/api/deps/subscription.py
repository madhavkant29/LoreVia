from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.models.user import User
from app.utils.billing_utils import (
    ARCHITECT_TIER,
    AUTHOR_TIER,
    ADMIN_TIER,
    ensure_upload_capacity,
    user_access_tier,
)


async def check_upload_limit(
    db: AsyncSession,
    current_user: User,
    *,
    requested_uploads: int = 1,
    released_uploads: int = 0,
    context: str | None = None,
):
    await ensure_upload_capacity(
        db,
        current_user,
        requested_uploads=requested_uploads,
        released_uploads=released_uploads,
        context=context,
    )


async def require_pro(current_user: User = Depends(get_current_user)):
    if user_access_tier(current_user) not in (AUTHOR_TIER, ARCHITECT_TIER, ADMIN_TIER):
        raise HTTPException(403, "This feature requires an Author or Architect subscription.")


async def require_power(current_user: User = Depends(get_current_user)):
    if user_access_tier(current_user) not in (ARCHITECT_TIER, ADMIN_TIER):
        raise HTTPException(403, "This feature requires an Architect subscription.")
