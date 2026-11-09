"""
Summary service - thin wrapper around cached analysis state.
Called by the reader route for summary retrieval without request-time LLM work.
"""

import uuid
from collections.abc import Collection, Mapping
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import cache_get, cache_set, key_chapter_summary
from app.models.book import Chapter
from app.models.intelligence import ChapterSummary
from app.utils.processing_error_utils import friendly_processing_error

SUMMARY_MODES = ("short", "detailed", "key_points")
PERSISTED_SUMMARY_MODES = (*SUMMARY_MODES, "editorial_note")


def summary_modes_to_generate(
    existing_modes: Collection[str],
    *,
    force_regenerate: bool = False,
) -> list[str]:
    if force_regenerate:
        return list(SUMMARY_MODES)
    missing_modes = [mode for mode in SUMMARY_MODES if mode not in existing_modes]
    if "detailed" in existing_modes and "editorial_note" not in existing_modes:
        missing_modes.append("detailed")
    return missing_modes


async def persist_chapter_summary_payloads(
    db: AsyncSession,
    *,
    chapter_id: uuid.UUID,
    payloads: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Replace generated summary modes without deleting the last good rows first."""
    requested_modes = [mode for mode in PERSISTED_SUMMARY_MODES if mode in payloads]
    if not requested_modes:
        return []

    existing_rows = (
        (
            await db.execute(
                select(ChapterSummary)
                .where(
                    ChapterSummary.chapter_id == chapter_id,
                    ChapterSummary.mode.in_(requested_modes),
                )
                .order_by(ChapterSummary.created_at, ChapterSummary.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    rows_by_mode: dict[str, list[ChapterSummary]] = {}
    for row in existing_rows:
        rows_by_mode.setdefault(row.mode, []).append(row)

    persisted_modes: list[str] = []
    for mode in requested_modes:
        payload = payloads[mode]
        content = str(payload.get("content") or "").strip()
        if not content:
            continue
        mode_rows = rows_by_mode.get(mode, [])
        if mode_rows:
            summary = mode_rows[0]
            for duplicate in mode_rows[1:]:
                await db.delete(duplicate)
        else:
            summary = ChapterSummary(chapter_id=chapter_id, mode=mode, content=content)
            db.add(summary)
        summary.content = content
        summary.key_events = payload.get("key_events")
        summary.char_changes = payload.get("char_changes")
        summary.clues = payload.get("clues")
        summary.themes = cast(list[dict] | None, payload.get("themes"))
        persisted_modes.append(mode)

    await db.flush()
    return persisted_modes


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
        await cache_set(
            key_chapter_summary(str(chapter.id), mode), data, settings.REDIS_TTL_SUMMARY
        )
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
            "last_error": (
                friendly_processing_error(str(analysis_state["last_error"]))
                if analysis_state.get("last_error")
                else None
            ),
        },
    }
