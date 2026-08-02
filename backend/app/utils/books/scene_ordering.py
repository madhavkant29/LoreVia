"""Focused book scene ordering workflows."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    Chapter,
    NovelScene,
)
from app.utils.books.scene_sync import (
    _ensure_syncable_chapter,
)


def normalize_scene_reorder_ids(scene_ids: list[str]) -> list[uuid.UUID]:
    normalized_ids: list[uuid.UUID] = []
    seen_ids: set[uuid.UUID] = set()

    for raw_scene_id in scene_ids:
        cleaned_scene_id = " ".join(str(raw_scene_id or "").split()).strip()
        if not cleaned_scene_id:
            raise HTTPException(400, "Scene order contains an empty scene ID.")
        try:
            parsed_scene_id = uuid.UUID(cleaned_scene_id)
        except ValueError as exc:
            raise HTTPException(400, f"Invalid scene ID: {cleaned_scene_id}") from exc
        if parsed_scene_id in seen_ids:
            raise HTTPException(400, "Scene order contains duplicate scene IDs.")
        seen_ids.add(parsed_scene_id)
        normalized_ids.append(parsed_scene_id)

    return normalized_ids


def _apply_sequential_scene_sort_order(scenes: Sequence[NovelScene]) -> None:
    for index, scene in enumerate(scenes, start=1):
        scene.sort_order = index


async def _list_chapter_novel_scene_rows(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    exclude_scene_id: uuid.UUID | None = None,
    lock: bool = False,
) -> list[NovelScene]:
    stmt = (
        select(NovelScene)
        .where(
            NovelScene.book_id == book_id,
            NovelScene.chapter_number == chapter_number,
        )
        .order_by(
            NovelScene.sort_order.asc(),
            NovelScene.created_at.asc(),
            NovelScene.id.asc(),
        )
    )
    if exclude_scene_id is not None:
        stmt = stmt.where(NovelScene.id != exclude_scene_id)
    if lock:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalars().all()


async def normalize_chapter_novel_scene_order(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    exclude_scene_id: uuid.UUID | None = None,
    lock: bool = False,
) -> list[NovelScene]:
    scenes = await _list_chapter_novel_scene_rows(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        exclude_scene_id=exclude_scene_id,
        lock=lock,
    )
    _apply_sequential_scene_sort_order(scenes)
    return scenes


async def _increment_chapter_structure_versions(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_numbers: Sequence[int | None],
) -> dict[int, int]:
    normalized_numbers = sorted(
        {
            int(chapter_number)
            for chapter_number in chapter_numbers
            if isinstance(chapter_number, int) and chapter_number > 0
        }
    )
    if not normalized_numbers:
        return {}

    chapters = (
        (
            await db.execute(
                select(Chapter).where(
                    Chapter.book_id == book_id,
                    Chapter.number.in_(normalized_numbers),
                )
            )
        )
        .scalars()
        .all()
    )

    versions_by_number: dict[int, int] = {}
    for chapter in chapters:
        chapter.structure_version = int(chapter.structure_version or 0) + 1
        versions_by_number[int(chapter.number)] = int(chapter.structure_version)
    return versions_by_number


async def replace_chapter_novel_scenes(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
    scenes: list[dict[str, Any]],
) -> None:
    await db.execute(
        delete(NovelScene).where(
            NovelScene.book_id == book.id,
            NovelScene.chapter_number == chapter_number,
        )
    )

    chapter, _chapter_created = await _ensure_syncable_chapter(
        db,
        book=book,
        chapter_number=chapter_number,
    )
    chapter_id = chapter.id
    for scene in scenes:
        db.add(
            NovelScene(
                book_id=book.id,
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                title=str(scene["title"]),
                description=cast(str | None, scene.get("description")),
                body=str(scene["body"]),
                html_body=cast(str | None, scene.get("html_body")),
                scene_metadata=cast(dict | None, scene.get("metadata")) or {},
                path=str(scene["path"]),
                status=str(scene.get("status") or "assigned"),
                sort_order=int(scene.get("sort_order") or 0),
                source=str(scene.get("source") or "chapter_sync"),
                origin_chapter_number=chapter_number,
            )
        )
    await _increment_chapter_structure_versions(
        db,
        book_id=book.id,
        chapter_numbers=[chapter_number],
    )
