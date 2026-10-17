"""Persistence and keyset reads for reader-safe generated events."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, ReaderEvent
from app.services.data_generation_service import current_generation_id

MAJOR_EVENT_SORT_ORDER = 0
CHARACTER_EVENT_SORT_ORDER = 1


class InvalidReaderEventCursor(ValueError):
    """Raised when a reader-event page cursor cannot be safely reused."""


@dataclass(frozen=True)
class ReaderEventCursor:
    chapter_number: int
    sort_order: int
    sort_label: str
    event_id: uuid.UUID


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [cleaned for item in value if (cleaned := _clean_text(item))]


def _event_source_key(event_type: str, chapter_id: uuid.UUID, payload: dict[str, Any]) -> str:
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    return f"{event_type}:{chapter_id}:{digest}"


def _major_event_payload(chapter: Chapter, event: dict[str, Any]) -> dict[str, Any]:
    chapter_number = _bounded_int(
        event.get("chapter_number"),
        default=int(chapter.number),
        minimum=0,
        maximum=1_000_000,
    )
    title = _clean_text(event.get("event_title") or event.get("event"))
    return {
        "chapter_number": chapter_number,
        "chapter_title": chapter.title,
        "event_title": title or f"Chapter {chapter_number} event",
        "description": _clean_text(event.get("description") or event.get("impact")),
        "importance": _bounded_int(event.get("importance"), default=5, minimum=1, maximum=10),
        "involved_characters": _clean_string_list(event.get("involved_characters")) or None,
        "involved_character_names": _clean_string_list(event.get("involved_character_names"))
        or None,
        "event_type": _clean_text(event.get("event_type")) or None,
    }


def _character_event_payload(chapter: Chapter, event: dict[str, Any]) -> dict[str, Any]:
    chapter_number = _bounded_int(
        event.get("chapter_number"),
        default=int(chapter.number),
        minimum=0,
        maximum=1_000_000,
    )
    title = _clean_text(event.get("event_title") or event.get("event"))
    impact_score = _bounded_int(
        event.get("impact_score", event.get("importance")),
        default=5,
        minimum=1,
        maximum=10,
    )
    return {
        "character_id": _clean_text(event.get("character_id")) or None,
        "character_name": _clean_text(event.get("character_name")) or None,
        "chapter_number": chapter_number,
        "chapter_title": chapter.title,
        "event_title": title or f"Chapter {chapter_number} event",
        "description": _clean_text(event.get("description") or event.get("impact")),
        "impact_score": impact_score,
        "role": _clean_text(event.get("role")) or None,
        "accomplishments": _clean_string_list(event.get("accomplishments")),
        "growth_direction": _clean_text(event.get("growth_direction")) or "neutral",
        "growth_magnitude": _bounded_int(
            event.get("growth_magnitude"),
            default=impact_score,
            minimum=0,
            maximum=10,
        ),
        "is_major": bool(event.get("is_major", False)),
    }


def _character_id_from_payload(payload: dict[str, Any]) -> uuid.UUID | None:
    raw_id = payload.get("character_id")
    if not raw_id:
        return None
    try:
        return uuid.UUID(str(raw_id))
    except (TypeError, ValueError):
        return None


def _reader_event_values(
    *,
    chapter: Chapter,
    event_type: str,
    payload: dict[str, Any],
    generation_id: uuid.UUID | None,
) -> dict[str, Any]:
    sort_order = MAJOR_EVENT_SORT_ORDER if event_type == "major" else CHARACTER_EVENT_SORT_ORDER
    return {
        "book_id": chapter.book_id,
        "chapter_id": chapter.id,
        "generation_id": generation_id,
        "character_id": _character_id_from_payload(payload),
        "event_type": event_type,
        "chapter_number": int(payload["chapter_number"]),
        "chapter_title": payload.get("chapter_title"),
        "sort_order": sort_order,
        "sort_label": _clean_text(payload.get("event_title")).casefold(),
        "payload": payload,
    }


async def sync_reader_events_for_chapter(
    db: AsyncSession,
    *,
    chapter: Chapter,
    major_events: list[dict[str, Any]],
    character_events: list[dict[str, Any]],
) -> list[ReaderEvent]:
    """Upsert one generation's events for a chapter after summary persistence.

    New rows are staged before obsolete rows are deleted, so a failed summary
    transaction leaves the previous materialization intact.
    """

    generation_id = current_generation_id()
    existing_stmt = select(ReaderEvent).where(ReaderEvent.chapter_id == chapter.id)
    if generation_id is None:
        existing_stmt = existing_stmt.where(ReaderEvent.generation_id.is_(None))
    else:
        existing_stmt = existing_stmt.where(ReaderEvent.generation_id == generation_id)
    existing_by_source = {
        row.source_key: row for row in (await db.execute(existing_stmt)).scalars().all()
    }

    normalized: list[tuple[str, dict[str, Any]]] = []
    normalized.extend(
        ("major", _major_event_payload(chapter, event))
        for event in major_events
        if isinstance(event, dict)
    )
    normalized.extend(
        ("character", _character_event_payload(chapter, event))
        for event in character_events
        if isinstance(event, dict)
    )

    persisted: list[ReaderEvent] = []
    retained_source_keys: set[str] = set()
    for event_type, payload in normalized:
        source_key = _event_source_key(event_type, chapter.id, payload)
        if source_key in retained_source_keys:
            continue
        retained_source_keys.add(source_key)
        values = _reader_event_values(
            chapter=chapter,
            event_type=event_type,
            payload=payload,
            generation_id=generation_id,
        )
        row = existing_by_source.pop(source_key, None)
        if row is None:
            row = ReaderEvent(source_key=source_key, **values)
            db.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        persisted.append(row)

    for obsolete in existing_by_source.values():
        await db.delete(obsolete)

    await db.flush()
    return persisted


def _encode_reader_event_cursor(
    *, book_id: uuid.UUID, max_visible_chapter: int, event: ReaderEvent
) -> str:
    payload = {
        "book_id": str(book_id),
        "max_visible_chapter": int(max_visible_chapter),
        "chapter_number": int(event.chapter_number),
        "sort_order": int(event.sort_order),
        "sort_label": str(event.sort_label),
        "event_id": str(event.id),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_reader_event_cursor(
    cursor: str | None, *, book_id: uuid.UUID, max_visible_chapter: int
) -> ReaderEventCursor | None:
    if not cursor:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(f"{cursor}{padding}").decode("utf-8"))
        if payload.get("book_id") != str(book_id) or int(payload.get("max_visible_chapter")) != int(
            max_visible_chapter
        ):
            raise InvalidReaderEventCursor("Reader event cursor does not match this request")
        return ReaderEventCursor(
            chapter_number=int(payload["chapter_number"]),
            sort_order=int(payload["sort_order"]),
            sort_label=str(payload["sort_label"]),
            event_id=uuid.UUID(str(payload["event_id"])),
        )
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, binascii.Error) as exc:
        if isinstance(exc, InvalidReaderEventCursor):
            raise
        raise InvalidReaderEventCursor("Invalid reader event cursor") from exc


def serialize_reader_event(event: ReaderEvent) -> dict[str, Any]:
    payload = dict(event.payload or {})
    return {"id": str(event.id), "type": event.event_type, **payload}


async def list_reader_event_page(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    max_visible_chapter: int,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    """Read a bounded cursor page without loading source summaries or JSON blobs."""

    normalized_limit = max(1, min(int(limit), 100))
    decoded_cursor = _decode_reader_event_cursor(
        cursor,
        book_id=book_id,
        max_visible_chapter=max_visible_chapter,
    )
    predicates = [
        ReaderEvent.book_id == book_id,
        ReaderEvent.chapter_number <= int(max_visible_chapter),
    ]
    if decoded_cursor is not None:
        predicates.append(
            or_(
                ReaderEvent.chapter_number > decoded_cursor.chapter_number,
                and_(
                    ReaderEvent.chapter_number == decoded_cursor.chapter_number,
                    ReaderEvent.sort_order > decoded_cursor.sort_order,
                ),
                and_(
                    ReaderEvent.chapter_number == decoded_cursor.chapter_number,
                    ReaderEvent.sort_order == decoded_cursor.sort_order,
                    ReaderEvent.sort_label > decoded_cursor.sort_label,
                ),
                and_(
                    ReaderEvent.chapter_number == decoded_cursor.chapter_number,
                    ReaderEvent.sort_order == decoded_cursor.sort_order,
                    ReaderEvent.sort_label == decoded_cursor.sort_label,
                    ReaderEvent.id > decoded_cursor.event_id,
                ),
            )
        )
    rows = list(
        (
            await db.execute(
                select(ReaderEvent)
                .where(*predicates)
                .order_by(
                    ReaderEvent.chapter_number.asc(),
                    ReaderEvent.sort_order.asc(),
                    ReaderEvent.sort_label.asc(),
                    ReaderEvent.id.asc(),
                )
                .limit(normalized_limit + 1)
            )
        )
        .scalars()
        .all()
    )
    has_more = len(rows) > normalized_limit
    page_rows = rows[:normalized_limit]
    return {
        "items": [serialize_reader_event(event) for event in page_rows],
        "next_cursor": (
            _encode_reader_event_cursor(
                book_id=book_id,
                max_visible_chapter=max_visible_chapter,
                event=page_rows[-1],
            )
            if has_more and page_rows
            else None
        ),
        "has_more": has_more,
    }


async def backfill_reader_events_for_book(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    after_chapter_number: int = 0,
    after_chapter_id: uuid.UUID | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Materialize one bounded chapter batch from existing summary/growth data.

    This is intentionally a worker-facing operation rather than a migration:
    it is resumable, keeps transactions bounded, and can be retried without
    reading manuscript storage or calling an LLM.
    """

    bounded_limit = max(1, min(int(limit), 100))
    after_conditions = [Chapter.number > int(after_chapter_number)]
    if after_chapter_id is not None:
        after_conditions.append(
            and_(
                Chapter.number == int(after_chapter_number),
                Chapter.id > after_chapter_id,
            )
        )
    chapter_rows = list(
        (
            await db.execute(
                select(Chapter)
                .where(Chapter.book_id == book_id, or_(*after_conditions))
                .order_by(Chapter.number.asc(), Chapter.id.asc())
                .limit(bounded_limit + 1)
            )
        )
        .scalars()
        .all()
    )
    has_more = len(chapter_rows) > bounded_limit
    chapters = chapter_rows[:bounded_limit]
    if not chapters:
        return {
            "processed_chapters": 0,
            "materialized_events": 0,
            "next_cursor": None,
            "has_more": False,
        }

    chapter_ids = [chapter.id for chapter in chapters]
    summary_events = {
        chapter_id: key_events
        for chapter_id, key_events in (
            await db.execute(
                select(ChapterSummary.chapter_id, ChapterSummary.key_events).where(
                    ChapterSummary.chapter_id.in_(chapter_ids),
                    ChapterSummary.mode == "detailed",
                )
            )
        ).all()
    }
    characters = list(
        (await db.execute(select(Character).where(Character.book_id == book_id))).scalars().all()
    )
    growth_events_by_chapter: dict[int, list[dict[str, Any]]] = {}
    for character in characters:
        for event in character.growth_events or []:
            if not isinstance(event, dict):
                continue
            chapter_number = _bounded_int(
                event.get("chapter_number"), default=0, minimum=0, maximum=1_000_000
            )
            if chapter_number <= 0:
                continue
            growth_events_by_chapter.setdefault(chapter_number, []).append(
                {
                    "character_id": str(character.id),
                    "character_name": character.name,
                    **event,
                }
            )

    materialized_events = 0
    for chapter in chapters:
        raw_major_events = summary_events.get(chapter.id)
        major_events = (
            [event for event in raw_major_events if isinstance(event, dict)]
            if isinstance(raw_major_events, list)
            else []
        )
        persisted = await sync_reader_events_for_chapter(
            db,
            chapter=chapter,
            major_events=major_events,
            character_events=growth_events_by_chapter.get(int(chapter.number), []),
        )
        materialized_events += len(persisted)

    last_chapter = chapters[-1]
    return {
        "processed_chapters": len(chapters),
        "materialized_events": materialized_events,
        "next_cursor": (
            {
                "chapter_number": int(last_chapter.number),
                "chapter_id": str(last_chapter.id),
            }
            if has_more
            else None
        ),
        "has_more": has_more,
    }
