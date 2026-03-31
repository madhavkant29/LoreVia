from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.config import effective_tier, settings
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.redis import bump_token_version, get_token_version, refresh_session_active, revoke_refresh_session, store_refresh_session
from app.models.user import User
from app.api.deps.auth import get_current_user
from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
import uuid

router = APIRouter()


class RegisterBody(BaseModel):
    email: EmailStr
    password: str

class LoginBody(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    tier: str
    reading_mode: str
    created_at: datetime


async def _mint_token_pair(user_id: str) -> TokenOut:
    version = await get_token_version(user_id)
    session_id = str(uuid.uuid4())
    await store_refresh_session(
        user_id,
        session_id,
        settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
    )
    return TokenOut(
        access_token=create_access_token(user_id, version),
        refresh_token=create_refresh_token(user_id, version, session_id),
    )


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(User).where(User.email == body.email))).scalar():
        raise HTTPException(400, "Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return await _mint_token_pair(str(user.id))


@router.post("/login", response_model=TokenOut)
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email))).scalar()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return await _mint_token_pair(str(user.id))


@router.post("/refresh", response_model=TokenOut)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")
    claimed_version = payload.get("ver")
    session_id = payload.get("sid")
    if claimed_version is None or not session_id:
        raise HTTPException(401, "Invalid refresh token")

    current_version = await get_token_version(payload["sub"])
    if int(claimed_version) != current_version:
        raise HTTPException(401, "Refresh token expired")
    if not await refresh_session_active(payload["sub"], session_id):
        raise HTTPException(401, "Refresh token expired")

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(401, "User not found")
    await revoke_refresh_session(payload["sub"], session_id)
    return await _mint_token_pair(str(user.id))


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    await bump_token_version(str(current_user.id))
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        tier=effective_tier(current_user.tier),
        reading_mode=current_user.reading_mode,
        created_at=current_user.created_at,
    )


@router.patch("/me/reading-mode")
async def set_reading_mode(
    mode: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if mode not in ("casual", "analyst", "speed"):
        raise HTTPException(400, "Invalid mode")
    current_user.reading_mode = mode
    await db.commit()
    return {"reading_mode": mode}
