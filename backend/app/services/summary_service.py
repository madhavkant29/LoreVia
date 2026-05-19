"""
Summary service - thin wrapper around cached analysis state.
Called by the reader route for summary retrieval without request-time LLM work.
"""
import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import cache_get, cache_set, key_chapter_summary
from app.models.book import Chapter
from app.models.intelligence import ChapterSummary


async def get_or_generate_summary(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter_num: int,
    mode: str,
) -> dict | None:
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_num)
        )
    ).scalar()
    if not chapter:
        return None

    cached = await cache_get(key_chapter_summary(str(chapter.id), mode))
    if cached:
        payload = cast(dict[str, Any], cached)
        return {
            "status": "ready",
            "content": payload.get("content"),
            "key_events": payload.get("key_events"),
            "char_changes": payload.get("char_changes"),
            "clues": payload.get("clues"),
            "diagnostics": {"source": "cache"},
        }

    row = (
        await db.execute(
            select(ChapterSummary).where(
                ChapterSummary.chapter_id == chapter.id,
                ChapterSummary.mode == mode,
            )
        )
    ).scalar()
    if row:
        data = {
            "content": row.content,
            "key_events": row.key_events,
            "char_changes": row.char_changes,
            "clues": row.clues,
        }
        await cache_set(key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY)
        return {"status": "ready", **data, "diagnostics": {"source": "database"}}

    analysis_state = chapter.analysis_state if isinstance(chapter.analysis_state, dict) else {}
    status = str(analysis_state.get("status") or "pending").strip() or "pending"
    return {
        "status": "failed" if status == "failed" else "pending",
        "content": None,
        "key_events": [],
        "char_changes": [],
        "clues": [],
        "diagnostics": {
            "analysis_status": status,
            "generated_modes": list(analysis_state.get("generated_modes") or []),
            "last_error": analysis_state.get("last_error"),
        },
    }
