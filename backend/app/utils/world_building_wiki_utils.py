from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter, SeriesBook
from app.models.character import Character
from app.models.intelligence import ChapterSummary, WikiEntry, WorldElement
from app.utils.world_building_serialization_utils import map_element_to_wiki_type
from app.utils.world_building_story_utils import collect_story_elements


async def generate_wiki_from_manuscript(db: AsyncSession, book: Book) -> list[WikiEntry]:
    elements = await collect_story_elements(db, book)
    summaries = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id, ChapterSummary.mode == "detailed")
            .order_by(Chapter.number.asc())
        )
    ).all()
    characters = (
        await db.execute(select(Character.id, Character.name).where(Character.book_id == book.id))
    ).all()
    character_ids = [str(character_id) for character_id, _ in characters[:5]]

    existing = (
        (await db.execute(select(WikiEntry).where(WikiEntry.book_id == book.id))).scalars().all()
    )
    by_name = {entry.name.strip().lower(): entry for entry in existing if entry.name}
    touched: list[WikiEntry] = []

    for element in elements:
        key = element.name.strip().lower()
        if not key:
            continue
        metadata = element.analysis_metadata or {}
        entry = by_name.get(key)
        description = (
            element.description or ""
        ).strip() or f"{element.name} appears in the manuscript and has not been summarized yet."
        if entry is None:
            entry = WikiEntry(
                book_id=book.id,
                entry_type=map_element_to_wiki_type(element.element_type),
                name=element.name.strip(),
                description=description,
                first_mention=int(metadata.get("chapter_number") or 0) or None,
                related_char_ids=character_ids or None,
            )
            db.add(entry)
            by_name[key] = entry
        else:
            entry.entry_type = map_element_to_wiki_type(element.element_type)
            entry.description = (
                description
                if len(description) >= len(entry.description or "")
                else entry.description
            )
            entry.first_mention = entry.first_mention or (
                int(metadata.get("chapter_number") or 0) or None
            )
            entry.related_char_ids = entry.related_char_ids or (character_ids or None)
        touched.append(entry)

    for chapter_number, chapter_title, key_events in summaries:
        if not isinstance(key_events, list):
            continue
        for event in key_events[:3]:
            if not isinstance(event, dict):
                continue
            name = " ".join(
                str(event.get("event_title") or event.get("event") or "").split()
            ).strip()
            if not name:
                continue
            key = name.lower()
            entry = by_name.get(key)
            description = " ".join(
                str(event.get("description") or event.get("impact") or "").split()
            ).strip() or (
                f"{name} is tracked as a chapter event in {chapter_title or f'chapter {chapter_number}'}."
            )
            if entry is None:
                entry = WikiEntry(
                    book_id=book.id,
                    entry_type="event",
                    name=name,
                    description=description,
                    first_mention=chapter_number,
                    related_char_ids=character_ids or None,
                )
                db.add(entry)
                by_name[key] = entry
            else:
                entry.entry_type = entry.entry_type or "event"
                entry.description = (
                    description
                    if len(description) >= len(entry.description or "")
                    else entry.description
                )
                entry.first_mention = entry.first_mention or chapter_number
            touched.append(entry)

    await db.flush()
    return sorted(touched, key=lambda item: (item.entry_type, item.name.lower()))


def build_world_context(elements: list[WorldElement]) -> str:
    lines: list[str] = []
    for element in elements[:40]:
        scope = "world" if element.source_scope == "worldbuilding" else "story"
        lines.append(
            f"- {element.name} [{element.element_type} · {scope}] usage={element.usage_count}: "
            f"{(element.description or 'No description.')[:180]}"
        )
    return "\n".join(lines)


async def build_series_world_context(db: AsyncSession, series_id: uuid.UUID) -> str:
    book_ids = list(
        (await db.execute(select(SeriesBook.book_id).where(SeriesBook.series_id == series_id)))
        .scalars()
        .all()
    )
    if not book_ids:
        return ""
    elements = list(
        (await db.execute(select(WorldElement).where(WorldElement.book_id.in_(book_ids))))
        .scalars()
        .all()
    )
    return build_world_context(elements)
