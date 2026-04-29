import logging
import uuid

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_token_version
from app.core.security import decode_token
from app.models.user import User
from app.utils.auth_cookies import get_auth_token

bearer = HTTPBearer(auto_error=False)
log = logging.getLogger("lorevia.auth")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = get_auth_token(request, credentials.credentials if credentials else None)
    if not token:
        raise HTTPException(401, "Invalid or expired token")

    # Decode the JWT â€” only catch unexpected decode failures here.
    # All intentional 401s are raised directly so they are never swallowed.
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

    if not payload or payload.get("type") != "access":
        raise HTTPException(401, "Invalid or expired token")

    claimed_version = payload.get("ver")
    if claimed_version is None:
        raise HTTPException(401, "Invalid or expired token")

    user_id = payload["sub"]

    try:
        current_version = await get_token_version(user_id)
    except Exception:
        log.exception("redis_unavailable_during_auth", extra={"user_id": user_id})
        raise HTTPException(503, "Authentication service temporarily unavailable")

    if int(claimed_version) != current_version:
        # Do NOT bump the version here â€” bumping on every mismatch causes the
        # stored version to drift away from valid tokens (e.g., after a Redis
        # restart) and permanently locks users out on each retry.
        # Version is bumped only on explicit logout / password change.
        raise HTTPException(401, "Session expired. Please sign in again.")

    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(401, "User not found")

    return user


async def get_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.tier != "admin":
        raise HTTPException(403, "Admin only")
    return current_user
