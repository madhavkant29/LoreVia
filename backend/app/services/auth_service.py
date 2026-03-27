from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token


async def register_user(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, create_access_token(str(user.id)), create_refresh_token(str(user.id))


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar()
    if user and verify_password(password, user.password_hash):
        return user
    return None
