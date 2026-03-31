from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.core.redis import get_token_version
from app.models.user import User
import uuid

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(401, "Invalid or expired token")
    claimed_version = payload.get("ver")
    if claimed_version is None:
        raise HTTPException(401, "Invalid or expired token")
    current_version = await get_token_version(payload["sub"])
    if int(claimed_version) != current_version:
        raise HTTPException(401, "Session expired. Please sign in again.")
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def get_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.tier != "admin":
        raise HTTPException(403, "Admin only")
    return current_user
