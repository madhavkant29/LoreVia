from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

import bleach  # type: ignore[import-untyped]
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, BookCollaborator, BookNote, Chapter, NovelScene
from app.models.character import Character
from app.models.intelligence import PlotThread, WorldNote
from app.models.tag import CustomTag
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_can_comment,
    collaboration_can_edit,
)

BLEACH_EMPTY_TAGS: Any = frozenset()
MAX_TAGS_PER_ENTITY = 25
MAX_TAG_LENGTH = 64

ENTITY_TYPE_CHAPTER = "chapter"
ENTITY_TYPE_SCENE = "scene"
ENTITY_TYPE_CHARACTER = "character"
ENTITY_TYPE_NOTE = "note"
ENTITY_TYPE_PLOT_THREAD = "plot_thread"
ENTITY_TYPE_WORLD_NOTE = "world_note"

PUBLIC_ENTITY_TYPES = {
    ENTITY_TYPE_CHAPTER,
    ENTITY_TYPE_SCENE,
    ENTITY_TYPE_CHARACTER,
    ENTITY_TYPE_NOTE,
    "comment",
    ENTITY_TYPE_PLOT_THREAD,
    ENTITY_TYPE_WORLD_NOTE,
}
CANONICAL_ENTITY_TYPES = {
    ENTITY_TYPE_CHAPTER: ENTITY_TYPE_CHAPTER,
    ENTITY_TYPE_SCENE: ENTITY_TYPE_SCENE,
    ENTITY_TYPE_CHARACTER: ENTITY_TYPE_CHARACTER,
    ENTITY_TYPE_NOTE: ENTITY_TYPE_NOTE,
    "comment": ENTITY_TYPE_NOTE,
    ENTITY_TYPE_PLOT_THREAD: ENTITY_TYPE_PLOT_THREAD,
    ENTITY_TYPE_WORLD_NOTE: ENTITY_TYPE_WORLD_NOTE,
}


def normalize_custom_tags(values: Iterable[object] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in values or []:
        cleaned = " ".join(str(raw or "").replace("_", " ").split()).strip().lower()
        cleaned = str(bleach.clean(cleaned, tags=BLEACH_EMPTY_TAGS, strip=True))
        if not cleaned:
            continue
        if len(cleaned) > MAX_TAG_LENGTH:
            raise HTTPException(400, f"Tags must be {MAX_TAG_LENGTH} characters or fewer.")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    if len(normalized) > MAX_TAGS_PER_ENTITY:
        raise HTTPException(400, f"No more than {MAX_TAGS_PER_ENTITY} tags are allowed per item.")
    return normalized


def normalize_public_entity_type(value: str) -> str:
    normalized = " ".join(str(value or "").split()).strip().lower().replace("-", "_")
    if normalized not in PUBLIC_ENTITY_TYPES:
        raise HTTPException(400, "Unsupported tag target.")
    return normalized


def canonical_entity_type(value: str) -> str:
    return CANONICAL_ENTITY_TYPES[normalize_public_entity_type(value)]


async def list_custom_tags_for_entity_ids(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_ids: Iterable[uuid.UUID],
    book_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, list[str]]:
    ids = list(dict.fromkeys(entity_ids))
    if not ids:
        return {}
    stmt = select(CustomTag).where(
        CustomTag.entity_type == canonical_entity_type(entity_type),
        CustomTag.entity_id.in_(ids),
    )
    if book_id is not None:
        stmt = stmt.where(CustomTag.book_id == book_id)
    rows = (
        (await db.execute(stmt.order_by(CustomTag.tag_name.asc(), CustomTag.created_at.asc())))
        .scalars()
        .all()
    )
    mapping: dict[uuid.UUID, list[str]] = {entity_id: [] for entity_id in ids}
    for row in rows:
        mapping.setdefault(row.entity_id, []).append(row.tag_name)
    return mapping


async def get_custom_tags_for_entity(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    book_id: uuid.UUID | None = None,
) -> list[str]:
    mapping = await list_custom_tags_for_entity_ids(
        db,
        entity_type=entity_type,
        entity_ids=[entity_id],
        book_id=book_id,
    )
    return mapping.get(entity_id, [])


async def replace_custom_tags_for_entity(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    tags: Iterable[object] | None,
) -> list[str]:
    normalized = normalize_custom_tags(tags)
    resolved_entity_type = canonical_entity_type(entity_type)
    await db.execute(
        delete(CustomTag).where(
            CustomTag.book_id == book_id,
            CustomTag.entity_type == resolved_entity_type,
            CustomTag.entity_id == entity_id,
        )
    )
    for tag_name in normalized:
        db.add(
            CustomTag(
                book_id=book_id,
                created_by_user_id=created_by_user_id,
                entity_type=resolved_entity_type,
                entity_id=entity_id,
                tag_name=tag_name,
            )
        )
    await db.flush()
    return normalized


async def resolve_tag_target(
    db: AsyncSession,
    *,
    book: Book,
    entity_type: str,
    entity_id: str | None,
    chapter_number: int | None = None,
) -> tuple[str, uuid.UUID, int | None]:
    public_type = normalize_public_entity_type(entity_type)
    resolved_type = CANONICAL_ENTITY_TYPES[public_type]
    parsed_id = _parse_optional_uuid(entity_id)

    if resolved_type == ENTITY_TYPE_CHAPTER:
        chapter = None
        if parsed_id is not None:
            chapter = await db.get(Chapter, parsed_id)
            if chapter and chapter.book_id != book.id:
                chapter = None
        elif chapter_number is not None:
            chapter = (
                await db.execute(
                    select(Chapter).where(
                        Chapter.book_id == book.id, Chapter.number == chapter_number
                    )
                )
            ).scalar_one_or_none()
        if chapter is None:
            raise HTTPException(404, "Chapter not found")
        return resolved_type, chapter.id, chapter.number

    if parsed_id is None:
        raise HTTPException(400, "Entity id is required")

    model_map = {
        ENTITY_TYPE_SCENE: NovelScene,
        ENTITY_TYPE_CHARACTER: Character,
        ENTITY_TYPE_NOTE: BookNote,
        ENTITY_TYPE_PLOT_THREAD: PlotThread,
        ENTITY_TYPE_WORLD_NOTE: WorldNote,
    }
    model = model_map.get(resolved_type)
    record = await db.get(model, parsed_id) if model else None
    if record is None or getattr(record, "book_id", None) != book.id:
        raise HTTPException(404, "Tag target not found")
    target_chapter = getattr(record, "chapter_number", None)
    return resolved_type, parsed_id, target_chapter if isinstance(target_chapter, int) else None


def can_manage_tag_target(
    *,
    collaborator: BookCollaborator | None,
    public_entity_type: str,
    target_chapter_number: int | None,
    target_owner_user_id: uuid.UUID | None,
    current_user_id: uuid.UUID,
) -> bool:
    if collaborator is None:
        return True

    normalized_public_type = normalize_public_entity_type(public_entity_type)
    if normalized_public_type in {
        ENTITY_TYPE_CHAPTER,
        ENTITY_TYPE_SCENE,
        ENTITY_TYPE_CHARACTER,
        ENTITY_TYPE_PLOT_THREAD,
        ENTITY_TYPE_WORLD_NOTE,
    }:
        if not collaboration_can_edit(collaborator):
            return False
        if target_chapter_number is not None and not collaboration_allows_chapter(
            collaborator, target_chapter_number
        ):
            return False
        return True

    if normalized_public_type in {ENTITY_TYPE_NOTE, "comment"}:
        if not collaboration_can_comment(collaborator):
            return False
        if target_chapter_number is not None and not collaboration_allows_chapter(
            collaborator, target_chapter_number
        ):
            return False
        return target_owner_user_id is None or target_owner_user_id == current_user_id

    return False


def _parse_optional_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise HTTPException(400, "Invalid entity id") from exc
