from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.redis import get_redis
from app.api.deps.auth import get_admin
from app.models.user import User
from app.models.book import Book
from app.models.character import Character
from app.models.intelligence import BookChunk, ChapterSummary

router = APIRouter()


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
