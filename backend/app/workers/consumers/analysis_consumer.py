"""
Analysis consumer: summaries + plot tracking for one chapter.
"""

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from openai import AsyncOpenAI
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import (
    cache_del,
    cache_set,
    cache_set_if_absent,
    key_analysis_inflight,
    key_analysis_queued,
    key_chapter_summary,
)
from app.engine.analysis.plot_tracker import extract_plot_threads
from app.engine.analysis.summariser import derive_summary_modes_from_detailed, generate_summary
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, Notification, PlotThread
from app.models.user import User
from app.services.email_service import send_processing_complete_with_stats
from app.services.event_linking_service import link_summary_events
from app.utils.books.chapter_titles import (
    build_chapter_title_from_summary,
    chapter_title_is_placeholder,
)
from app.utils.characters.extraction import resolve_character_reference_from_roster
from app.utils.ingestion_utils import (
    ANALYSIS_INFLIGHT_TTL_SECONDS,
    build_analysis_chapter_state,
    elapsed_ms,
    is_book_hidden,
    is_llm_coordination_retry_error,
    is_llm_usage_limit_error,
    mark_book_processing_cancelled,
    merge_processing_pipeline,
)
from app.utils.logging.errors import public_error_message
from app.utils.notification_utils import collect_book_ready_stats, upsert_book_ready_notification
from app.utils.plot_thread_utils import (
    merge_plot_thread_status,
    normalize_plot_thread_status,
    normalize_plot_thread_title,
    normalize_plot_thread_type,
    normalize_related_characters,
    plot_thread_lookup_key,
)
from app.utils.world_building_utils import ingest_world_elements_from_chapter

log = logging.getLogger("lorevia.analysis")


async def analyse_chapter(
    chapter_id: str,
    chapter_text: str,
    chapter_title: str = "",
    queue_wait_ms: int | None = None,
    rebuild_run_id: str | None = None,
    manual_reprocess: bool = False,
) -> dict:
    async with AsyncSessionLocal() as db:
        db_load_started = time.perf_counter()
        chapter = await db.get(Chapter, uuid.UUID(chapter_id))
        if not chapter:
            return {"error": "chapter not found"}
        book = await db.get(Book, chapter.book_id)
        if book is None:
            return {"error": "book not found"}
        from app.services.editor_project_service import get_rebuild_run_id

        active_rebuild_run_id = get_rebuild_run_id(book)
        if rebuild_run_id is not None and active_rebuild_run_id != rebuild_run_id:
            log.info("Skipping stale rebuild analysis chapter_id=%s", chapter_id)
            return {"error": "stale_rebuild_run"}
        if (
            getattr(book, "is_editor_project", False)
            and not active_rebuild_run_id
            and not manual_reprocess
        ):
            log.info("Skipping stale editor-project analysis chapter_id=%s", chapter_id)
            return {"error": "stale_editor_project_run"}
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

        inflight_key = key_analysis_inflight(chapter_id)
        if not await cache_set_if_absent(
            inflight_key,
            {"chapter_id": chapter_id},
            ANALYSIS_INFLIGHT_TTL_SECONDS,
        ):
            return {"skipped": "analysis_inflight"}

        chapter.analysis_state = build_analysis_chapter_state(
            chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
            status="running",
        )
        await _refresh_book_analysis_pipeline(db, book)
        await db.commit()

        try:
            existing_modes = set(
                (
                    await db.execute(
                        select(ChapterSummary.mode).where(ChapterSummary.chapter_id == chapter.id)
                    )
                )
                .scalars()
                .all()
            )
            pending_modes = [
                mode for mode in ["short", "detailed", "key_points"] if mode not in existing_modes
            ]

            results: dict[str, str] = {}
            detailed_payload: dict[str, Any] | None = None
            summary_payloads: dict[str, dict[str, Any]] = {}

            llm_started = time.perf_counter()
            client = (
                AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
            )
            try:
                if "detailed" in pending_modes:
                    try:
                        summary_payload = await generate_summary(
                            chapter_text,
                            "detailed",
                            chapter_title,
                            openai_client=client,
                            user_id=book.user_id,
                            book_id=book.id,
                        )
                    except Exception as exc:
                        if is_llm_usage_limit_error(exc) or is_llm_coordination_retry_error(exc):
                            raise
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
                    user_id=book.user_id,
                    book_id=book.id,
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
                db.add(
                    ChapterSummary(
                        chapter_id=chapter.id,
                        mode=mode,
                        content=payload["content"],
                        key_events=payload.get("key_events"),
                        char_changes=payload.get("char_changes"),
                        clues=payload.get("clues"),
                        themes=payload.get("themes"),
                    )
                )
                await cache_set(
                    key_chapter_summary(chapter_id, mode),
                    payload,
                    settings.REDIS_TTL_SUMMARY,
                )
                results[mode] = "generated"
                if mode == "detailed":
                    detailed_payload = payload

            if "detailed" in pending_modes and "detailed" not in results:
                raise RuntimeError("detailed_summary_generation_failed")

            await _upsert_plot_threads(db, book, chapter, threads)

            if detailed_payload is not None:
                await link_summary_events(
                    db,
                    chapter=chapter,
                    key_events=cast(list[dict] | None, detailed_payload.get("key_events")),
                    char_changes=cast(list[dict] | None, detailed_payload.get("char_changes")),
                )
                if chapter_title_is_placeholder(chapter.title, chapter_number=chapter.number):
                    derived_title = build_chapter_title_from_summary(
                        cast(str | None, detailed_payload.get("content")),
                        key_events=cast(
                            list[dict[str, Any]] | None, detailed_payload.get("key_events")
                        ),
                    )
                    if derived_title:
                        chapter.title = derived_title

            await ingest_world_elements_from_chapter(
                db,
                book=book,
                chapter=chapter,
                chapter_text=chapter_text,
            )

            chapter.analysis_state = build_analysis_chapter_state(
                chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
                status="succeeded",
                generated_modes=list(results.keys()),
            )
            await _refresh_book_analysis_pipeline(db, book)
            from app.services.editor_project_service import complete_rebuild_if_ready

            await complete_rebuild_if_ready(db, book)

            ready_stats = await collect_book_ready_stats(db, book)
            prior_ready_state = False
            if ready_stats.analysis_complete:
                existing_ready_notification = (
                    await db.execute(
                        select(Notification).where(
                            Notification.book_id == book.id,
                            Notification.user_id == book.user_id,
                            Notification.kind == "book_ready",
                        )
                    )
                ).scalar_one_or_none()
                prior_ready_state = bool(
                    existing_ready_notification is not None
                    and isinstance(existing_ready_notification.data, dict)
                    and existing_ready_notification.data.get("analysis_complete")
                )
                await upsert_book_ready_notification(db, book, ready_stats)

            db_commit_started = time.perf_counter()
            await db.commit()
            from app.utils.advisor_utils import invalidate_advisor_caches_for_book

            await invalidate_advisor_caches_for_book(db, book_id=book.id)
            log.info(
                "analysis_timing stage=db_commit chapter_id=%s elapsed_ms=%s summaries=%s threads=%s",
                chapter_id,
                elapsed_ms(db_commit_started),
                len(results),
                len(threads),
            )
            if ready_stats.analysis_complete and not prior_ready_state:
                user = await db.get(User, book.user_id)
                if user and user.email:
                    await send_processing_complete_with_stats(
                        user.email,
                        book_title=book.title,
                        character_count=ready_stats.character_count,
                        relationship_count=ready_stats.relationship_count,
                        plot_thread_count=ready_stats.plot_thread_count,
                        continuity_issue_count=ready_stats.continuity_issue_count,
                    )
            if settings.DEBUG:
                log.info("analysed_chapter %s %s", chapter_id, results)
            return {"chapter_id": chapter_id, "summaries": results}
        except Exception as exc:
            try:
                await db.rollback()
            except Exception:
                pass
            try:
                fresh_chapter = await db.get(Chapter, chapter.id)
                if fresh_chapter is not None:
                    retry_later = is_llm_usage_limit_error(exc) or is_llm_coordination_retry_error(
                        exc
                    )
                    fresh_chapter.analysis_state = build_analysis_chapter_state(
                        fresh_chapter.analysis_state
                        if isinstance(fresh_chapter.analysis_state, dict)
                        else None,
                        status="queued" if retry_later else "failed",
                        last_error=None if retry_later else public_error_message(500),
                    )
                    fresh_book = await db.get(Book, fresh_chapter.book_id)
                    if fresh_book is not None:
                        await _refresh_book_analysis_pipeline(db, fresh_book)
                await db.commit()
            except Exception:
                try:
                    await db.rollback()
                except Exception:
                    pass
            raise
        finally:
            await cache_del(inflight_key)
            await cache_del(key_analysis_queued(chapter_id))


async def _upsert_plot_threads(
    db, book: Book, chapter: Chapter, threads: list[dict[str, Any]]
) -> None:
    character_rows = (
        (await db.execute(select(Character).where(Character.book_id == chapter.book_id)))
        .scalars()
        .all()
    )
    existing_threads = (
        (await db.execute(select(PlotThread).where(PlotThread.book_id == chapter.book_id)))
        .scalars()
        .all()
    )
    existing_by_key: dict[str, PlotThread] = {}
    for existing in existing_threads:
        key = plot_thread_lookup_key(existing.title)
        if not key:
            continue
        chosen = existing_by_key.get(key)
        if chosen is None:
            existing_by_key[key] = existing
            continue
        chosen_last = chosen.last_mentioned_at or chosen.introduced_at or 0
        existing_last = existing.last_mentioned_at or existing.introduced_at or 0
        if existing_last > chosen_last:
            existing_by_key[key] = existing

    candidate_threads: dict[str, dict[str, Any]] = {}
    for raw_thread in threads:
        title = normalize_plot_thread_title(raw_thread.get("title"))
        key = plot_thread_lookup_key(title)
        if not key:
            continue
        thread_context = " ".join(
            part
            for part in [
                title,
                str(raw_thread.get("description") or "").strip(),
            ]
            if part
        )
        resolved_character_names_raw: list[str] = []
        for item in raw_thread.get("characters_involved") or []:
            candidate = str(item).strip()
            if not candidate:
                continue
            resolved = resolve_character_reference_from_roster(
                character_rows,
                candidate,
                context_text=thread_context,
            )
            resolved_character_names_raw.append(
                resolved.name if resolved is not None else candidate
            )
        resolved_character_names = normalize_related_characters(resolved_character_names_raw)
        bucket = candidate_threads.setdefault(
            key,
            {
                "title": title,
                "description": str(raw_thread.get("description") or "").strip() or None,
                "type": normalize_plot_thread_type(raw_thread.get("type")),
                "status": normalize_plot_thread_status(
                    raw_thread.get("status"), default="introduced"
                ),
                "characters_involved": resolved_character_names,
                "importance": int(raw_thread.get("importance") or 5),
            },
        )
        if not bucket.get("description") and raw_thread.get("description"):
            bucket["description"] = str(raw_thread.get("description") or "").strip() or None
        if raw_thread.get("type"):
            bucket["type"] = normalize_plot_thread_type(raw_thread.get("type")) or bucket.get(
                "type"
            )
        bucket["status"] = merge_plot_thread_status(bucket.get("status"), raw_thread.get("status"))
        bucket["importance"] = max(
            int(bucket.get("importance") or 5), int(raw_thread.get("importance") or 5)
        )
        bucket["characters_involved"] = normalize_related_characters(
            [*(bucket.get("characters_involved") or []), *resolved_character_names]
        )

    for key, candidate in candidate_threads.items():
        thread = existing_by_key.get(key)
        if thread is None:
            db.add(
                PlotThread(
                    book_id=chapter.book_id,
                    title=candidate["title"],
                    description=candidate.get("description"),
                    thread_type=candidate.get("type"),
                    status=candidate.get("status", "introduced"),
                    introduced_at=chapter.number,
                    last_mentioned_at=chapter.number,
                    resolved_at=chapter.number
                    if candidate.get("status") in {"resolved", "abandoned"}
                    else None,
                    mention_count=1,
                    character_ids=candidate.get("characters_involved", []),
                    importance=candidate.get("importance", 5),
                )
            )
            continue

        if getattr(thread, "edited_by_author", False):
            continue

        thread.title = candidate["title"] or thread.title
        if candidate.get("description"):
            thread.description = candidate["description"]
        if candidate.get("type"):
            thread.thread_type = candidate["type"]
        thread.status = merge_plot_thread_status(thread.status, candidate.get("status"))
        thread.introduced_at = (
            min(value for value in [thread.introduced_at, chapter.number] if value is not None)
            if thread.introduced_at is not None
            else chapter.number
        )
        thread.last_mentioned_at = max(
            value
            for value in [thread.last_mentioned_at, thread.introduced_at, chapter.number]
            if value is not None
        )
        thread.mention_count = int(thread.mention_count or 0) + 1
        thread.importance = max(int(thread.importance or 5), int(candidate.get("importance") or 5))
        thread.character_ids = normalize_related_characters(
            [*(thread.character_ids or []), *(candidate.get("characters_involved") or [])]
        )
        if thread.status in {"resolved", "abandoned"}:
            thread.resolved_at = chapter.number
        elif thread.status == "contradicted":
            thread.resolved_at = None


async def _refresh_book_analysis_pipeline(db, book: Book) -> None:
    total_chapters = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Chapter)
                .where(Chapter.book_id == book.id, Chapter.word_count > 0)
            )
        ).scalar_one()
    )
    completed = int(
        (
            await db.execute(
                select(func.count(func.distinct(ChapterSummary.chapter_id)))
                .select_from(ChapterSummary)
                .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.word_count > 0,
                    ChapterSummary.mode == "detailed",
                )
            )
        ).scalar_one()
    )
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.analysis_state)
            .where(Chapter.book_id == book.id, Chapter.word_count > 0)
            .order_by(Chapter.number.asc())
        )
    ).all()
    failed_chapters = [
        int(number)
        for number, analysis_state in chapter_rows
        if isinstance(analysis_state, dict)
        and str(analysis_state.get("status") or "").strip() == "failed"
    ]
    queued_or_running = any(
        isinstance(analysis_state, dict)
        and str(analysis_state.get("status") or "").strip() in {"queued", "running"}
        for _, analysis_state in chapter_rows
    )
    if total_chapters > 0 and completed >= total_chapters:
        analysis_status = "succeeded"
    elif failed_chapters:
        analysis_status = "failed"
    elif queued_or_running or completed > 0:
        analysis_status = "running"
    else:
        analysis_status = "pending"
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = (
        workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {}
    )
    processing = merge_processing_pipeline(
        dict(processing),
        analysis={
            "status": analysis_status,
            "completed_chapters": completed,
            "total_chapters": total_chapters,
            "updated_at": datetime.now(UTC).isoformat(),
            "failed_chapters": failed_chapters,
        },
    )
    workspace["processing"] = processing
    book.writer_workspace = workspace
