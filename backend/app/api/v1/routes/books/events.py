import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary
from app.models.progress import ReadingProgress
from app.schemas.books import BookEventsOut, CharacterEventOut, MajorEventOut
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import (
    get_owned_book,
)

router = APIRouter()


def _normalize_book_major_event(
    *,
    chapter_number: int,
    chapter_title: str | None,
    event: dict,
    character_names_by_id: dict[str, str],
) -> dict:
    involved_ids = [
        str(item).strip() for item in (event.get("involved_characters") or []) if str(item).strip()
    ]
    involved_names = [character_names_by_id.get(item, item) for item in involved_ids]
    return {
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "event_title": str(event.get("event_title") or event.get("event") or "").strip(),
        "description": str(event.get("description") or event.get("impact") or "").strip(),
        "importance": int(event.get("importance") or 5),
        "involved_characters": involved_ids or None,
        "involved_character_names": involved_names or None,
        "event_type": event.get("event_type"),
    }


def _normalize_book_character_event(*, character: Character, event: dict) -> dict:
    return {
        "character_id": str(character.id),
        "character_name": character.name,
        "chapter_number": int(event.get("chapter_number") or character.first_chapter),
        "event_title": str(event.get("event_title") or event.get("event") or "").strip(),
        "description": str(event.get("description") or event.get("impact") or "").strip(),
        "impact_score": int(event.get("impact_score") or event.get("importance") or 5),
        "role": event.get("role") or character.role,
        "accomplishments": [
            str(item).strip() for item in (event.get("accomplishments") or []) if str(item).strip()
        ],
        "growth_direction": str(event.get("growth_direction") or "neutral"),
        "growth_magnitude": int(event.get("growth_magnitude") or event.get("impact_score") or 0),
        "is_major": bool(event.get("is_major", False)),
    }


# ─── Book events ─────────────────────────────────────────────────────────────


@router.get("/{book_id}/events", response_model=BookEventsOut)
async def get_book_events(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id, ChapterSummary.mode == "detailed")
            .order_by(Chapter.number)
        )
    ).all()
    characters = (
        (
            await db.execute(
                select(Character).where(Character.book_id == book.id).order_by(Character.name)
            )
        )
        .scalars()
        .all()
    )
    character_names_by_id = {str(character.id): character.name for character in characters}

    major_events: list[dict] = []
    for chapter_number, chapter_title, key_events in chapter_rows:
        for event in key_events or []:
            if isinstance(event, dict):
                major_events.append(
                    _normalize_book_major_event(
                        chapter_number=chapter_number,
                        chapter_title=chapter_title,
                        event=event,
                        character_names_by_id=character_names_by_id,
                    )
                )

    character_events: list[dict] = []
    for character in characters:
        for event in character.growth_events or []:
            if isinstance(event, dict):
                character_events.append(
                    _normalize_book_character_event(character=character, event=event)
                )

    major_events.sort(key=lambda item: (item["chapter_number"], item["event_title"].lower()))
    character_events.sort(
        key=lambda item: (
            item["chapter_number"],
            item["character_name"].lower(),
            item["event_title"].lower(),
        )
    )
    return BookEventsOut(
        major_events=[MajorEventOut(**item) for item in major_events],
        character_events=[CharacterEventOut(**item) for item in character_events],
    )


@router.get("/{book_id}/events/reader", response_model=BookEventsOut)
async def get_reader_safe_book_events(
    book_id: uuid.UUID,
    chapter: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    progress_result = await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book.id
        )
    )
    progress = progress_result.scalar()
    max_visible_chapter = chapter or (progress.current_chapter if progress else 1)
    payload = await get_book_events(book_id=book_id, db=db, current_user=current_user)
    return BookEventsOut(
        major_events=[
            event for event in payload.major_events if event.chapter_number <= max_visible_chapter
        ],
        character_events=[
            event
            for event in payload.character_events
            if event.chapter_number <= max_visible_chapter
        ],
    )
