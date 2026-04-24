"""
Summary service — thin wrapper around the analysis engine + cache.
Called by the reader route for on-demand summary generation.
"""
import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import cache_get, cache_set, key_chapter_summary
from app.core.storage import download_book
from app.engine.analysis.summariser import generate_summary
from app.models.book import Chapter
from app.models.intelligence import ChapterSummary
from app.utils.book_utils import deserialize_manuscript_content


async def get_or_generate_summary(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter_num: int,
    mode: str,
) -> dict | None:
    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        return None

    # 1. Redis cache
    cached = await cache_get(key_chapter_summary(str(chapter.id), mode))
    if cached:
        return cast(dict[str, Any], cached)

    # 2. DB
    row = (await db.execute(
        select(ChapterSummary).where(
            ChapterSummary.chapter_id == chapter.id,
            ChapterSummary.mode == mode,
        )
    )).scalar()
    if row:
        data = {"content": row.content, "key_events": row.key_events,
                "char_changes": row.char_changes, "clues": row.clues}
        await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
        return data

    # 3. Generate (fallback — normally done by worker)
    if not chapter.s3_key:
        return None
    raw = download_book(chapter.s3_key)
    text = str(deserialize_manuscript_content(raw).get("text") or "")
    data = await generate_summary(text, mode, chapter.title or "")

    row = ChapterSummary(
        chapter_id=chapter.id, mode=mode, content=data["content"],
        key_events=data.get("key_events"), char_changes=data.get("char_changes"),
        clues=data.get("clues"),
    )
    db.add(row)
    await db.commit()
    await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
    return data
