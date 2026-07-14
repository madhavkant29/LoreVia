from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis import (
    get_book_cache_version,
    get_series_cache_version,
    get_series_story_context_cache,
    get_story_context_cache,
    set_series_story_context_cache,
    set_story_context_cache,
)
from app.models.book import Book, Chapter, SeriesBook
from app.models.character import Character
from app.models.intelligence import ChapterSummary, PlotThread, WorldElement
from app.utils.advisor_story_context_format_utils import (
    format_major_event_lines,
    format_story_world_element_lines,
)


async def build_story_context(db: AsyncSession, book_id: uuid.UUID, total_ch: int) -> str:
    version = await get_book_cache_version(str(book_id))
    cached = await get_story_context_cache(str(book_id), version, int(total_ch or 0))
    if cached is not None:
        return cached
    lines: list[str] = [f"Total chapters processed: {total_ch}"]

    book_result = await db.execute(
        select(Book)
        .where(Book.id == book_id)
        .options(
            selectinload(Book.characters),
            selectinload(Book.plot_threads),
            selectinload(Book.world_elements),
        )
    )
    book = book_result.scalars().first()

    if book is not None and book.characters:
        sorted_chars = sorted(book.characters, key=lambda c: (c.first_chapter or 0, c.name or ""))[
            :20
        ]
        lines.append("\nCHARACTERS (extracted from manuscript):")
        for character in sorted_chars:
            role_str = f"[{character.role}]" if character.role else ""
            arc = (
                (character.arc_summary[:120] + "...")
                if character.arc_summary and len(character.arc_summary) > 120
                else (character.arc_summary or "")
            )
            tags = ", ".join((character.personality_tags or [])[:3])
            motives = "; ".join((character.motivations or [])[:2])
            growth = ""
            if isinstance(character.growth_events, list) and character.growth_events:
                latest_growth = next(
                    (
                        item
                        for item in reversed(character.growth_events)
                        if isinstance(item, dict) and (item.get("event") or item.get("event_title"))
                    ),
                    None,
                )
                if latest_growth:
                    growth_title = latest_growth.get("event") or latest_growth.get("event_title")
                    growth = f"Recent growth beat: {growth_title}."
            trait_bits: list[str] = []
            if isinstance(character.trait_state, dict):
                for trait_key in ("eyes", "hair", "build", "age_descriptor"):
                    raw = character.trait_state.get(trait_key)
                    value = (
                        raw.get("value")
                        if isinstance(raw, dict)
                        else (raw if isinstance(raw, str) else None)
                    )
                    if value:
                        trait_bits.append(f"{trait_key}={value}")
            traits_str = "; ".join(trait_bits[:3])
            lines.append(
                f"  • {character.name} {role_str} — first ch.{character.first_chapter}. "
                + (f"Arc: {arc} " if arc else "")
                + (f"Personality: {tags}. " if tags else "")
                + (f"Physical: {traits_str}. " if traits_str else "")
                + (f"Drives: {motives}. " if motives else "")
                + growth
            )

    if book is not None and book.plot_threads:
        sorted_threads = sorted(
            book.plot_threads,
            key=lambda thread: thread.importance or 5,
            reverse=True,
        )[:12]
        lines.append("\nPLOT THREADS (extracted from manuscript):")
        for thread in sorted_threads:
            desc = (
                (thread.description[:100] + "...")
                if thread.description and len(thread.description) > 100
                else (thread.description or "")
            )
            status_label = str(thread.status or "introduced").upper()
            lines.append(
                f"  • [{status_label}] {thread.title} (importance {thread.importance}/10, "
                f"introduced ch.{thread.introduced_at}). {desc}"
            )

    world_rows = (
        await db.execute(
            select(
                WorldElement.name,
                WorldElement.element_type,
                WorldElement.description,
                WorldElement.usage_count,
            )
            .where(WorldElement.book_id == book_id, WorldElement.source_scope == "worldbuilding")
            .order_by(WorldElement.usage_count.desc(), WorldElement.name.asc())
            .limit(10)
        )
    ).all()
    if world_rows:
        lines.append("\nWORLD REFERENCE CORPUS (author-supplied lore):")
        for name, element_type, description, _usage_count in world_rows:
            snippet = (
                (description[:120] + "...")
                if description and len(description) > 120
                else (description or "")
            )
            lines.append(f"  • {name} [{element_type}] {snippet}")

    event_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "detailed",
                ChapterSummary.key_events.isnot(None),
            )
            .order_by(Chapter.number.desc())
            .limit(8)
        )
    ).all()
    lines.extend(format_major_event_lines(event_rows))

    lines.extend(format_story_world_element_lines(book))

    theme_rows = (
        await db.execute(
            select(Chapter.number, ChapterSummary.themes)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "detailed",
                ChapterSummary.themes.isnot(None),
            )
            .order_by(Chapter.number.desc())
            .limit(8)
        )
    ).all()
    theme_lines: list[str] = []
    seen_themes: set[str] = set()
    for chapter_num, themes in theme_rows:
        if not isinstance(themes, list):
            continue
        for item in themes:
            if not isinstance(item, dict):
                continue
            name = " ".join(str(item.get("theme") or "").split()).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen_themes:
                continue
            seen_themes.add(key)
            signal = item.get("signal")
            depth = item.get("depth")
            evidence = " ".join(str(item.get("evidence") or "").split()).strip()
            theme_lines.append(
                f"  • {name} (chapter {chapter_num}"
                + (f", {signal}" if signal else "")
                + (f", {depth}" if depth else "")
                + f"). {evidence[:120]}"
            )
            if len(theme_lines) >= 10:
                break
        if len(theme_lines) >= 10:
            break
    if theme_lines:
        lines.append("\nTHEMES (including philosophical subtext):")
        lines.extend(theme_lines)

    payload = "\n".join(lines)
    await set_story_context_cache(str(book_id), version, int(total_ch or 0), payload)
    return payload


async def build_series_story_context(
    db: AsyncSession,
    book_ids: list[uuid.UUID],
    book_titles: dict[uuid.UUID, str],
    max_chars_per_book: int = 8,
    max_threads_per_book: int = 5,
) -> str:
    """Build a merged story context from multiple books for series-level queries."""
    series_key_parts = [
        f"{book_id}:{book_titles.get(book_id, str(book_id))}" for book_id in book_ids
    ]
    series_key = hashlib.sha256("||".join(series_key_parts).encode("utf-8")).hexdigest()
    version = 0
    for book_id in book_ids:
        version = max(version, await get_book_cache_version(str(book_id)))
        series_rows = (
            await db.execute(select(SeriesBook.series_id).where(SeriesBook.book_id == book_id))
        ).all()
        for row in series_rows:
            version = max(version, await get_series_cache_version(str(row.series_id)))
    cached = await get_series_story_context_cache(series_key, version)
    if cached is not None:
        return cached

    lines: list[str] = []

    for book_id in book_ids:
        title = book_titles.get(book_id, str(book_id))
        lines.append(f"\n=== Book: {title} ===")

        chars = (
            await db.execute(
                select(
                    Character.name,
                    Character.role,
                    Character.arc_summary,
                    Character.first_chapter,
                    Character.archetype,
                    Character.personality_tags,
                    Character.motivations,
                    Character.trait_state,
                )
                .where(Character.book_id == book_id)
                .order_by(Character.first_chapter)
                .limit(max_chars_per_book)
            )
        ).all()

        if chars:
            lines.append("Characters:")
            for character in chars:
                role_str = f"[{character.role}]" if character.role else ""
                arc = (
                    (character.arc_summary[:100] + "...")
                    if character.arc_summary and len(character.arc_summary) > 100
                    else (character.arc_summary or "")
                )
                tags = ", ".join((character.personality_tags or [])[:3])
                motives = "; ".join((character.motivations or [])[:2])
                lines.append(
                    f"  • {character.name} {role_str} — first ch.{character.first_chapter}. "
                    + (f"Arc: {arc} " if arc else "")
                    + (f"Personality: {tags}. " if tags else "")
                    + (f"Drives: {motives}." if motives else "")
                )

        threads = (
            await db.execute(
                select(
                    PlotThread.title,
                    PlotThread.status,
                    PlotThread.introduced_at,
                    PlotThread.description,
                )
                .where(PlotThread.book_id == book_id)
                .order_by(PlotThread.importance.desc())
                .limit(max_threads_per_book)
            )
        ).all()

        if threads:
            lines.append("Plot threads:")
            for thread in threads:
                desc = (
                    (thread.description[:80] + "...")
                    if thread.description and len(thread.description) > 80
                    else (thread.description or "")
                )
                lines.append(
                    f"  • [{thread.status}] {thread.title} (ch.{thread.introduced_at}). {desc}"
                )

    payload = "\n".join(lines)
    await set_series_story_context_cache(series_key, version, payload)
    return payload
