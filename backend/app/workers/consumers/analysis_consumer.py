"""
Analysis consumer: summaries + plot tracking for one chapter.
"""
import uuid
import asyncio
from app.core.database import AsyncSessionLocal
from app.core.redis import cache_set, key_chapter_summary
from app.core.config import settings
from app.models.book import Chapter
from app.models.intelligence import ChapterSummary, PlotThread
from app.engine.analysis.summariser import generate_summary
from app.engine.analysis.plot_tracker import extract_plot_threads
from sqlalchemy import select
import logging

log = logging.getLogger("lorevia.analysis")


async def analyse_chapter(chapter_id: str, chapter_text: str, chapter_title: str = "") -> dict:
    async with AsyncSessionLocal() as db:
        chapter = await db.get(Chapter, uuid.UUID(chapter_id))
        if not chapter:
            return {"error": "chapter not found"}

        results = {}
        for mode in ["short", "detailed", "key_points"]:
            # Check if summary already exists
            existing = (await db.execute(
                select(ChapterSummary).where(
                    ChapterSummary.chapter_id == chapter.id,
                    ChapterSummary.mode == mode,
                )
            )).scalar()
            if existing:
                continue

            summary_data = await generate_summary(chapter_text, mode, chapter_title)
            row = ChapterSummary(
                chapter_id=chapter.id,
                mode=mode,
                content=summary_data["content"],
                key_events=summary_data.get("key_events"),
                char_changes=summary_data.get("char_changes"),
                clues=summary_data.get("clues"),
            )
            db.add(row)
            await db.flush()

            # Cache it
            await cache_set(
                key_chapter_summary(chapter_id, mode),
                summary_data,
                settings.REDIS_TTL_SUMMARY,
            )
            results[mode] = "generated"

        # Extract plot threads
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
        log.info(f"Analysed chapter {chapter_id}: {results}")
        return {"chapter_id": chapter_id, "summaries": results}
