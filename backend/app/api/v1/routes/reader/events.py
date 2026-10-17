import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.feature_flags import require_reader_events_v2_enabled
from app.core.database import get_db
from app.core.redis import (
    get_book_cache_version,
    get_reader_events_cache,
    get_reader_progress_cache_version,
    set_reader_events_cache,
)
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary
from app.models.progress import ReadingProgress
from app.schemas.books import BookEventsOut, CharacterEventOut, MajorEventOut
from app.schemas.reader import ReaderEventPageOut
from app.services.reader_event_service import (
    InvalidReaderEventCursor,
    list_reader_event_page,
)
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    get_book_with_collaboration_access,
)
from app.utils.reader_utils import summary_visible_chapter_set

router = APIRouter()


def _normalize_reader_major_event(
    chapter_number: int, chapter_title: str | None, event: dict, names_by_id: dict[str, str]
) -> dict:
    involved_ids = [
        str(item).strip() for item in (event.get("involved_characters") or []) if str(item).strip()
    ]
    return {
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "event_title": str(event.get("event_title") or event.get("event") or "").strip(),
        "description": str(event.get("description") or event.get("impact") or "").strip(),
        "importance": int(event.get("importance") or 5),
        "involved_characters": involved_ids or None,
        "involved_character_names": [names_by_id.get(item, item) for item in involved_ids] or None,
        "event_type": event.get("event_type"),
    }


def _normalize_reader_character_event(character: Character, event: dict) -> dict:
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


def _build_combined_events(
    major_events: list[MajorEventOut], character_events: list[CharacterEventOut]
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for e in major_events:
        events.append({"type": "major", **e.model_dump(mode="json")})
    for e in character_events:
        events.append({"type": "character", **e.model_dump(mode="json")})
    type_order = {"major": 0, "character": 1}
    events.sort(
        key=lambda item: (
            item.get("chapter_number", 0),
            type_order.get(str(item.get("type")), 9),
            item.get("event_title", "").lower()
            if item.get("type") == "major"
            else item.get("character_name", "").lower(),
        )
    )
    return events


def _paginated_events_response(
    events: list[dict[str, Any]], limit: int, offset: int
) -> dict[str, Any]:
    total = len(events)
    paged = events[offset : offset + limit]
    return {
        "items": paged,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


@router.get("/{book_id}/events")
async def get_reader_events(
    book_id: uuid.UUID,
    chapter: int | None = Query(None),
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    progress_result = await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
        )
    )
    progress = progress_result.scalar()
    read_set = set(progress.chapters_read or []) if progress else set()
    max_visible_chapter = chapter or (
        max(read_set) if read_set else (progress.current_chapter if progress else 1)
    )
    book_version = await get_book_cache_version(str(book_id))
    progress_version = await get_reader_progress_cache_version(str(book_id), str(current_user.id))
    cached = await get_reader_events_cache(
        str(book_id),
        str(current_user.id),
        int(max_visible_chapter),
        book_version,
        progress_version,
    )
    if cached is not None:
        cached_payload = BookEventsOut(**cached)
        all_events = _build_combined_events(
            cached_payload.major_events, cached_payload.character_events
        )
        return _paginated_events_response(all_events, limit, offset)

    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "detailed",
                Chapter.number <= max_visible_chapter,
            )
            .order_by(Chapter.number)
        )
    ).all()
    characters_result = await db.execute(select(Character).where(Character.book_id == book_id))
    characters = characters_result.scalars().all()
    names_by_id = {str(character.id): character.name for character in characters}

    major_events: list[MajorEventOut] = []
    for chapter_number, chapter_title, key_events in chapter_rows:
        for event in key_events or []:
            if isinstance(event, dict):
                major_events.append(
                    MajorEventOut(
                        **_normalize_reader_major_event(
                            chapter_number, chapter_title, event, names_by_id
                        )
                    )
                )

    character_events: list[CharacterEventOut] = []
    for character in characters:
        for event in character.growth_events or []:
            if (
                isinstance(event, dict)
                and int(event.get("chapter_number") or 0) <= max_visible_chapter
            ):
                character_events.append(
                    CharacterEventOut(**_normalize_reader_character_event(character, event))
                )

    payload = BookEventsOut(major_events=major_events, character_events=character_events)
    await set_reader_events_cache(
        str(book_id),
        str(current_user.id),
        int(max_visible_chapter),
        book_version,
        progress_version,
        payload.model_dump(mode="json"),
    )
    all_events = _build_combined_events(major_events, character_events)
    return _paginated_events_response(all_events, limit, offset)


@router.get(
    "/{book_id}/events/v2",
    response_model=ReaderEventPageOut,
    dependencies=[Depends(require_reader_events_v2_enabled)],
)
async def get_reader_events_v2(
    book_id: uuid.UUID,
    chapter: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Read materialized reader events with a stable keyset cursor.

    The v1 endpoint remains available while clients migrate; this path never
    loads chapter summaries or character JSON into Python to page the result.
    """

    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    progress = await db.scalar(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id,
            ReadingProgress.book_id == book_id,
        )
    )
    read_set = set(progress.chapters_read or []) if progress else set()
    max_visible_chapter = chapter or (
        max(read_set) if read_set else (progress.current_chapter if progress else 1)
    )
    try:
        return await list_reader_event_page(
            db,
            book_id=book.id,
            max_visible_chapter=int(max_visible_chapter),
            limit=limit,
            cursor=cursor,
        )
    except InvalidReaderEventCursor as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{book_id}/foreshadowing")
async def get_foreshadowing_highlights(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is None:
        require_author_access(current_user)

    read_set = await summary_visible_chapter_set(db, book, current_user, collaborator)
    if collaborator is not None:
        read_set = {
            chapter for chapter in read_set if collaboration_allows_chapter(collaborator, chapter)
        }
    if not read_set:
        return {"items": []}

    rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.clues)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                Chapter.number.in_(sorted(read_set)),
                ChapterSummary.mode == "detailed",
            )
            .order_by(Chapter.number)
        )
    ).all()

    items = []
    for number, title, clues in rows:
        for clue in clues or []:
            if isinstance(clue, dict) and clue.get("clue"):
                items.append(
                    {
                        "chapter_number": number,
                        "chapter_title": title,
                        "clue": clue.get("clue"),
                        "foreshadows": clue.get("foreshadows"),
                    }
                )
    if items:
        return {"items": items}

    return {"items": items}
