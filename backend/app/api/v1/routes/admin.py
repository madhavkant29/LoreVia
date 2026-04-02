from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.redis import get_redis
from app.api.deps.auth import get_admin
from app.models.user import User, UserRateLimitOverride
from app.models.book import Book
from app.models.character import Character
from app.models.intelligence import BookChunk, ChapterSummary
import uuid

router = APIRouter()


class RateLimitOverrideBody(BaseModel):
    search_per_hour: int | None = None
    summary_per_hour: int | None = None
    chat_per_day: int | None = None
    api_per_minute: int | None = None


@router.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db), _=Depends(get_admin)):
    users = (await db.execute(select(func.count()).select_from(User))).scalar()
    books = (await db.execute(select(func.count()).select_from(Book))).scalar()
    chars = (await db.execute(select(func.count()).select_from(Character))).scalar()
    chunks = (await db.execute(select(func.count()).select_from(BookChunk))).scalar()
    summaries = (await db.execute(select(func.count()).select_from(ChapterSummary))).scalar()
    r = await get_redis()
    mem = await r.info("memory")
    return {
        "users": users, "books": books, "characters": chars,
        "chunks_indexed": chunks, "summaries_cached": summaries,
        "redis_memory_mb": round(mem.get("used_memory", 0) / 1024 / 1024, 2),
    }


@router.get("/queue-depth")
async def queue_depth(_=Depends(get_admin)):
    r = await get_redis()
    return {
        "extraction": await r.llen("extraction"),
        "analysis": await r.llen("analysis"),
        "embedding": await r.llen("embedding"),
        "intelligence": await r.llen("intelligence"),
    }


@router.get("/rate-limits/{user_id}")
async def get_rate_limit_override(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    override = (
        await db.execute(
            select(UserRateLimitOverride).where(UserRateLimitOverride.user_id == user_id)
        )
    ).scalars().first()
    return {
        "user_id": str(user_id),
        "email": user.email,
        "override": {
            "search_per_hour": override.search_per_hour if override else None,
            "summary_per_hour": override.summary_per_hour if override else None,
            "chat_per_day": override.chat_per_day if override else None,
            "api_per_minute": override.api_per_minute if override else None,
        },
    }


@router.put("/rate-limits/{user_id}")
async def upsert_rate_limit_override(
    user_id: uuid.UUID,
    body: RateLimitOverrideBody,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    override = (
        await db.execute(
            select(UserRateLimitOverride).where(UserRateLimitOverride.user_id == user_id)
        )
    ).scalars().first()
    if not override:
        override = UserRateLimitOverride(user_id=user_id)
        db.add(override)

    override.search_per_hour = body.search_per_hour
    override.summary_per_hour = body.summary_per_hour
    override.chat_per_day = body.chat_per_day
    override.api_per_minute = body.api_per_minute
    await db.commit()
    return {"ok": True, "user_id": str(user_id)}
