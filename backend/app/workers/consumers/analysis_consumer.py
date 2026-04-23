"""
Analysis consumer: summaries + plot tracking for one chapter.
"""
import asyncio
import logging
import uuid
from typing import Any, cast

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import cache_set, key_chapter_summary
from app.engine.analysis.plot_tracker import extract_plot_threads
from app.engine.analysis.summariser import generate_summary
from app.models.book import Chapter
from app.models.intelligence import ChapterSummary, PlotThread

log = logging.getLogger("lorevia.analysis")


async def analyse_chapter(chapter_id: str, chapter_text: str, chapter_title: str = "") -> dict:
    async with AsyncSessionLocal() as db:
        chapter = await db.get(Chapter, uuid.UUID(chapter_id))
        if not chapter:
            return {"error": "chapter not found"}

        existing_modes = set(
            (
                await db.execute(
                    select(ChapterSummary.mode).where(ChapterSummary.chapter_id == chapter.id)
                )
            ).scalars().all()
        )
        pending_modes = [mode for mode in ["short", "detailed", "key_points"] if mode not in existing_modes]

        summary_payloads = await asyncio.gather(
            *(generate_summary(chapter_text, mode, chapter_title) for mode in pending_modes),
            return_exceptions=True,
        )
        results = {}
        for mode, summary_data in zip(pending_modes, summary_payloads):
            if isinstance(summary_data, Exception):
                continue
            payload = cast(dict[str, Any], summary_data)
            row = ChapterSummary(
                chapter_id=chapter.id,
                mode=mode,
                content=payload["content"],
                key_events=payload.get("key_events"),
                char_changes=payload.get("char_changes"),
                clues=payload.get("clues"),
                themes=payload.get("themes"),
            )
            db.add(row)
            await cache_set(
                key_chapter_summary(chapter_id, mode),
                payload,
                settings.REDIS_TTL_SUMMARY,
            )
            results[mode] = "generated"

        threads = await extract_plot_threads(chapter_text, chapter.number)
        for t in threads:
            thread = PlotThread(
                book_id=chapter.book_id,
                title=t["title"],
                description=t.get("description"),
                thread_type=t.get("type"),
                status=t.get("status", "introduced"),
                introduced_at=chapter.number,
                character_ids=t.get("characters_involved", []),
                importance=t.get("importance", 5),
            )
            db.add(thread)

        await db.commit()
        if settings.DEBUG:
            log.info("analysed_chapter %s %s", chapter_id, results)
        return {"chapter_id": chapter_id, "summaries": results}
