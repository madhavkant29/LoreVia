"""
Analysis consumer: summaries + plot tracking for one chapter.
"""
import logging
import time
import uuid
from typing import Any, cast

from openai import AsyncOpenAI

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import cache_set, key_chapter_summary
from app.engine.analysis.plot_tracker import extract_plot_threads
from app.engine.analysis.summariser import derive_summary_modes_from_detailed, generate_summary
from app.models.book import Book, Chapter
from app.models.intelligence import ChapterSummary, PlotThread
from app.services.event_linking_service import link_summary_events
from app.utils.ingestion_utils import elapsed_ms
from app.utils.ingestion_utils import is_book_hidden, mark_book_processing_cancelled
from app.utils.world_building_utils import ingest_world_elements_from_chapter

log = logging.getLogger("lorevia.analysis")


async def analyse_chapter(
    chapter_id: str,
    chapter_text: str,
    chapter_title: str = "",
    queue_wait_ms: int | None = None,
) -> dict:
    async with AsyncSessionLocal() as db:
        db_load_started = time.perf_counter()
        chapter = await db.get(Chapter, uuid.UUID(chapter_id))
        if not chapter:
            return {"error": "chapter not found"}
        book = await db.get(Book, chapter.book_id)
        if book is None:
            return {"error": "book not found"}
        log.info(
            "analysis_timing stage=db_load chapter_id=%s elapsed_ms=%s",
            chapter_id,
            elapsed_ms(db_load_started),
        )
        log.info(
            "analysis_timing stage=queue_wait chapter_id=%s queue_wait_ms=%s",
            chapter_id,
            queue_wait_ms,
        )

        existing_modes = set(
            (
                await db.execute(
                    select(ChapterSummary.mode).where(ChapterSummary.chapter_id == chapter.id)
                )
            ).scalars().all()
        )
        pending_modes = [mode for mode in ["short", "detailed", "key_points"] if mode not in existing_modes]

        results = {}
        detailed_payload: dict[str, Any] | None = None
        summary_payloads: dict[str, dict[str, Any]] = {}

        llm_started = time.perf_counter()
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        try:
            if "detailed" in pending_modes:
                try:
                    summary_payload = await generate_summary(
                        chapter_text,
                        "detailed",
                        chapter_title,
                        openai_client=client,
                    )
                except Exception:
                    summary_payload = None
                if summary_payload is not None:
                    detailed_payload = cast(dict[str, Any], summary_payload)
                    summary_payloads["detailed"] = detailed_payload
            elif "short" in pending_modes or "key_points" in pending_modes:
                existing_detailed = (
                    await db.execute(
                        select(ChapterSummary).where(
                            ChapterSummary.chapter_id == chapter.id,
                            ChapterSummary.mode == "detailed",
                        )
                    )
                ).scalar_one_or_none()
                if existing_detailed is not None:
                    detailed_payload = {
                        "content": existing_detailed.content,
                        "key_events": existing_detailed.key_events,
                        "char_changes": existing_detailed.char_changes,
                        "clues": existing_detailed.clues,
                        "themes": existing_detailed.themes,
                    }

            if detailed_payload is not None:
                derived_payloads = derive_summary_modes_from_detailed(detailed_payload)
                for mode in ("short", "key_points"):
                    if mode in pending_modes:
                        summary_payloads[mode] = derived_payloads[mode]

            threads = await extract_plot_threads(
                chapter_text,
                chapter.number,
                openai_client=client,
            )
        finally:
            if client is not None:
                await client.close()

        log.info(
            "analysis_timing stage=llm chapter_id=%s elapsed_ms=%s pending_modes=%s",
            chapter_id,
            elapsed_ms(llm_started),
            pending_modes,
        )

        if await is_book_hidden(db, book.id):
            await mark_book_processing_cancelled(
                db,
                book,
                stage="analysis",
                queue_wait_ms=queue_wait_ms,
                chapter_number=chapter.number,
                chapter_title=chapter_title or chapter.title or "",
                last_error="Book was removed while processing.",
            )
            return {"skipped": "book_hidden"}

        for mode in pending_modes:
            payload = summary_payloads.get(mode)
            if payload is None:
                continue
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
            if mode == "detailed":
                detailed_payload = payload

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

        if detailed_payload is not None:
            await link_summary_events(
                db,
                chapter=chapter,
                key_events=cast(list[dict] | None, detailed_payload.get("key_events")),
                char_changes=cast(list[dict] | None, detailed_payload.get("char_changes")),
            )

        await ingest_world_elements_from_chapter(
            db,
            book=book,
            chapter=chapter,
            chapter_text=chapter_text,
        )

        db_commit_started = time.perf_counter()
        await db.commit()
        log.info(
            "analysis_timing stage=db_commit chapter_id=%s elapsed_ms=%s summaries=%s threads=%s",
            chapter_id,
            elapsed_ms(db_commit_started),
            len(results),
            len(threads),
        )
        if settings.DEBUG:
            log.info("analysed_chapter %s %s", chapter_id, results)
        return {"chapter_id": chapter_id, "summaries": results}
