from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.core.config import settings
from app.core.redis import get_token_version, store_refresh_session
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
import uuid


async def register_user(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    version = await get_token_version(str(user.id))
    session_id = str(uuid.uuid4())
    await store_refresh_session(str(user.id), session_id, settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60)
    return user, create_access_token(str(user.id), version), create_refresh_token(str(user.id), version, session_id)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar()
    if user and verify_password(password, user.password_hash):
        return user
    return None
