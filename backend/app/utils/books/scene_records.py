"""Focused book scene records workflows."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book, upload_binary
from app.models.book import (
    Book,
    BookCollaborator,
    Chapter,
    NovelScene,
    SceneVersion,
)
from app.utils.books import (
    book_text,
    collaboration_access,
    manuscript,
    vault,
    writer_workspace,
)
from app.utils.books.chapter_titles import (
    _count_words,
)
from app.utils.books.chapter_versions import (
    snapshot_chapter_version,
)
from app.utils.books.scene_metadata import (
    build_novel_scene_path,
    extract_scene_metadata,
    normalize_scene_metadata,
)
from app.utils.books.scene_ordering import (
    _apply_sequential_scene_sort_order,
    _increment_chapter_structure_versions,
    _list_chapter_novel_scene_rows,
    normalize_chapter_novel_scene_order,
    normalize_scene_reorder_ids,
)
from app.utils.books.scene_serialization import (
    _scene_out,
    _scene_version_out,
)
from app.utils.books.scene_sync import (
    _ensure_syncable_chapter,
    sync_chapter_content_from_novel_scenes,
)
from app.utils.tag_utils import (
    ENTITY_TYPE_SCENE,
    get_custom_tags_for_entity,
    list_custom_tags_for_entity_ids,
)


async def list_novel_scenes(
    db: AsyncSession,
    *,
    book: Book,
    collaborator: BookCollaborator | None = None,
    chapter_number: int | None = None,
    status: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(NovelScene).where(NovelScene.book_id == book.id)
    if chapter_number is not None:
        stmt = stmt.where(NovelScene.chapter_number == chapter_number)
    if status:
        stmt = stmt.where(NovelScene.status == status)
    if query:
        like = f"%{' '.join(query.split()).strip()}%"
        stmt = stmt.where(
            NovelScene.title.ilike(like)
            | NovelScene.description.ilike(like)
            | NovelScene.body.ilike(like)
        )
    rows = list(
        (
            await db.execute(
                stmt.order_by(
                    NovelScene.chapter_number.is_(None),
                    NovelScene.chapter_number.asc(),
                    NovelScene.sort_order.asc(),
                    NovelScene.created_at.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    tags_by_scene = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_SCENE,
        entity_ids=[scene.id for scene in rows],
        book_id=book.id,
    )
    scenes = [_scene_out(scene, tags=tags_by_scene.get(scene.id, [])) for scene in rows]
    if collaborator is None:
        return scenes
    return [
        scene
        for scene in scenes
        if scene["chapter_number"] is not None
        and collaboration_access.collaboration_allows_chapter(
            collaborator, int(scene["chapter_number"])
        )
    ]


async def save_novel_scene(
    db: AsyncSession,
    *,
    book: Book,
    scene_id: uuid.UUID | None,
    title: str,
    description: str | None,
    body: str,
    html_body: str | None,
    chapter_number: int | None,
    status: str | None,
    sort_order: int | None,
    metadata: dict[str, Any] | None = None,
    path: str | None = None,
    skip_scene_version_snapshot: bool = False,
) -> dict[str, Any]:
    normalized_title = book_text._clean_text(title)
    if not normalized_title:
        raise HTTPException(400, "Scene title is required")
    normalized_body = (body or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized_body:
        raise HTTPException(400, "Scene body is required")
    normalized_description = book_text._clean_optional_text(description)
    normalized_metadata = normalize_scene_metadata(metadata, description=normalized_description)
    inferred_metadata = extract_scene_metadata(normalized_body, description=normalized_description)
    normalized_metadata = {**inferred_metadata, **normalized_metadata}
    normalized_chapter_number = (
        int(chapter_number) if isinstance(chapter_number, int) and chapter_number > 0 else None
    )
    normalized_status = "assigned" if normalized_chapter_number else "unassigned"
    if status in {"assigned", "unassigned", "archived"}:
        normalized_status = status
    chapter_id = None
    if normalized_chapter_number:
        chapter_id = (
            await db.execute(
                select(Chapter.id).where(
                    Chapter.book_id == book.id, Chapter.number == normalized_chapter_number
                )
            )
        ).scalar_one_or_none()
        if chapter_id is None:
            chapter, _chapter_created = await _ensure_syncable_chapter(
                db,
                book=book,
                chapter_number=normalized_chapter_number,
            )
            chapter_id = chapter.id

    scene = await db.get(NovelScene, scene_id) if scene_id else None
    if scene is not None and scene.book_id != book.id:
        raise HTTPException(404, "Scene not found")
    if (
        scene is not None
        and not skip_scene_version_snapshot
        and (
            scene.title != normalized_title
            or (scene.description or None) != normalized_description
            or scene.body != normalized_body
            or scene.chapter_number != normalized_chapter_number
        )
    ):
        await snapshot_scene_version(
            db,
            book,
            scene,
            note=f"Auto checkpoint before editing scene: {scene.title}",
            snapshot_kind="auto_checkpoint",
        )
    previous_body = scene.body if scene is not None else ""
    previous_title = scene.title if scene is not None else None
    previous_chapter_number = scene.chapter_number if scene is not None else None
    previous_sort_order = scene.sort_order if scene is not None else None
    snapshot_version_id: str | None = None
    snapshot_chapter_number = normalized_chapter_number or previous_chapter_number
    if isinstance(snapshot_chapter_number, int) and snapshot_chapter_number > 0:
        snapshot_chapter = (
            await db.execute(
                select(Chapter).where(
                    Chapter.book_id == book.id, Chapter.number == snapshot_chapter_number
                )
            )
        ).scalar_one_or_none()
        if snapshot_chapter is not None:
            snapshot = await snapshot_chapter_version(
                db,
                book,
                snapshot_chapter,
                note=f"Scene workspace snapshot for Chapter {snapshot_chapter_number}",
                snapshot_kind="scene_workspace",
            )
            snapshot_version_id = str(snapshot.id) if snapshot is not None else None

    initial_sort_order = int(sort_order) if isinstance(sort_order, int) and sort_order > 0 else 1
    base_path = (
        vault.normalize_vault_note_path(path)
        if path
        else build_novel_scene_path(
            chapter_number=normalized_chapter_number if normalized_status == "assigned" else None,
            sort_order=initial_sort_order,
            title=normalized_title,
        )
    )
    path = base_path
    suffix = 2
    while True:
        existing_path_scene = (
            await db.execute(
                select(NovelScene.id).where(
                    NovelScene.book_id == book.id,
                    NovelScene.path == path,
                )
            )
        ).scalar_one_or_none()
        if existing_path_scene is None or (scene is not None and existing_path_scene == scene.id):
            break
        if base_path.endswith(".md"):
            path = f"{base_path[:-3]}-{suffix}.md"
        else:
            path = f"{base_path}-{suffix}"
        suffix += 1
    if scene is None:
        scene = NovelScene(
            book_id=book.id,
            chapter_id=chapter_id,
            chapter_number=normalized_chapter_number,
            title=normalized_title,
            description=normalized_description,
            body=normalized_body,
            html_body=manuscript.clean_manuscript_html(html_body)
            if html_body
            else manuscript.manuscript_text_to_html(normalized_body),
            scene_metadata=normalized_metadata,
            path=path,
            status=normalized_status,
            sort_order=initial_sort_order,
            source="manual",
            origin_chapter_number=normalized_chapter_number,
        )
        db.add(scene)
        await db.flush()
    else:
        scene.chapter_id = chapter_id
        scene.chapter_number = normalized_chapter_number
        scene.title = normalized_title
        scene.description = normalized_description
        scene.body = normalized_body
        scene.html_body = (
            manuscript.clean_manuscript_html(html_body)
            if html_body
            else manuscript.manuscript_text_to_html(normalized_body)
        )
        scene.scene_metadata = normalized_metadata
        scene.path = path
        scene.status = normalized_status
        scene.sort_order = initial_sort_order if normalized_chapter_number is not None else 1
        await db.flush()

    touched_chapters: list[int | None] = []
    structure_changed = False
    requested_sort_order = (
        int(sort_order) if isinstance(sort_order, int) and sort_order > 0 else None
    )

    if normalized_chapter_number is not None:
        if scene_id is None or previous_chapter_number != normalized_chapter_number:
            requested_sort_order = None
        elif requested_sort_order is None and previous_sort_order is not None:
            requested_sort_order = previous_sort_order
        chapter_scenes = await _list_chapter_novel_scene_rows(
            db,
            book_id=book.id,
            chapter_number=normalized_chapter_number,
            exclude_scene_id=scene.id,
        )
        insert_position = (
            requested_sort_order if requested_sort_order is not None else len(chapter_scenes) + 1
        )
        insert_position = max(1, min(insert_position, len(chapter_scenes) + 1))
        chapter_scenes.insert(insert_position - 1, scene)
        _apply_sequential_scene_sort_order(chapter_scenes)
        touched_chapters.append(normalized_chapter_number)
        structure_changed = (
            scene_id is None
            or previous_chapter_number != normalized_chapter_number
            or (requested_sort_order is not None and requested_sort_order != previous_sort_order)
        )
    else:
        scene.sort_order = 1

    if previous_chapter_number is not None and previous_chapter_number != normalized_chapter_number:
        await normalize_chapter_novel_scene_order(
            db,
            book_id=book.id,
            chapter_number=previous_chapter_number,
        )
        touched_chapters.append(previous_chapter_number)
        structure_changed = True

    if structure_changed:
        await _increment_chapter_structure_versions(
            db,
            book_id=book.id,
            chapter_numbers=touched_chapters,
        )

    if scene_id is None:
        writer_workspace._append_recent_revision_edit(
            book,
            kind="scene",
            chapter_number=normalized_chapter_number,
            before_text="",
            after_text=normalized_body,
            scene_id=str(scene.id) if getattr(scene, "id", None) else None,
            scene_title=normalized_title,
            source_version_id=snapshot_version_id,
        )
    elif (
        previous_body != normalized_body
        or previous_title != normalized_title
        or previous_chapter_number != normalized_chapter_number
    ):
        writer_workspace._append_recent_revision_edit(
            book,
            kind="scene",
            chapter_number=normalized_chapter_number or previous_chapter_number,
            before_text=previous_body,
            after_text=normalized_body,
            scene_id=str(scene.id),
            scene_title=normalized_title,
            source_version_id=snapshot_version_id,
        )
    synced_chapters = sorted(
        {
            int(chapter_number)
            for chapter_number in [previous_chapter_number, normalized_chapter_number]
            if isinstance(chapter_number, int) and chapter_number > 0
        }
    )
    for synced_chapter_number in synced_chapters:
        await sync_chapter_content_from_novel_scenes(
            db,
            book=book,
            chapter_number=synced_chapter_number,
        )
    await db.commit()
    await db.refresh(scene)

    if not getattr(book, "is_editor_project", False):
        from app.services.task_execution_service import enqueue_extraction_execution

        for synced_chapter_number in synced_chapters:
            await enqueue_extraction_execution(
                db,
                book_id=book.id,
                user_id=book.user_id,
                chapter_id=None,
                chapter_number=synced_chapter_number,
                chapters_total=1,
                run_kind="scene_sync",
                identity_suffix=uuid.uuid4(),
            )

    return _scene_out(
        scene,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_SCENE,
            entity_id=scene.id,
            book_id=book.id,
        ),
    )


async def delete_novel_scene(
    db: AsyncSession,
    *,
    book: Book,
    scene_id: uuid.UUID,
) -> None:
    scene = (
        await db.execute(
            select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.id == scene_id)
        )
    ).scalar_one_or_none()
    if scene is None:
        raise HTTPException(404, "Scene not found")
    await snapshot_scene_version(
        db,
        book,
        scene,
        note=f"Auto checkpoint before deleting scene: {scene.title}",
        snapshot_kind="pre_delete",
    )
    snapshot_version_id: str | None = None
    if isinstance(scene.chapter_number, int) and scene.chapter_number > 0:
        chapter = (
            await db.execute(
                select(Chapter).where(
                    Chapter.book_id == book.id, Chapter.number == scene.chapter_number
                )
            )
        ).scalar_one_or_none()
        if chapter is not None:
            snapshot = await snapshot_chapter_version(
                db,
                book,
                chapter,
                note=f"Scene delete snapshot for Chapter {scene.chapter_number}",
                snapshot_kind="scene_workspace",
            )
            snapshot_version_id = str(snapshot.id) if snapshot is not None else None
    writer_workspace._append_recent_revision_edit(
        book,
        kind="scene_deleted",
        chapter_number=scene.chapter_number,
        before_text=scene.body,
        after_text="",
        scene_id=str(scene.id),
        scene_title=scene.title,
        source_version_id=snapshot_version_id,
    )
    removed_chapter_number = scene.chapter_number
    await db.delete(scene)
    if isinstance(removed_chapter_number, int) and removed_chapter_number > 0:
        await normalize_chapter_novel_scene_order(
            db,
            book_id=book.id,
            chapter_number=removed_chapter_number,
        )
        await _increment_chapter_structure_versions(
            db,
            book_id=book.id,
            chapter_numbers=[removed_chapter_number],
        )
        await sync_chapter_content_from_novel_scenes(
            db,
            book=book,
            chapter_number=removed_chapter_number,
        )
    await db.commit()

    if isinstance(removed_chapter_number, int) and removed_chapter_number > 0:
        if not getattr(book, "is_editor_project", False):
            from app.services.task_execution_service import enqueue_extraction_execution

            await enqueue_extraction_execution(
                db,
                book_id=book.id,
                user_id=book.user_id,
                chapter_id=None,
                chapter_number=removed_chapter_number,
                chapters_total=1,
                run_kind="scene_sync",
                identity_suffix=uuid.uuid4(),
            )


async def reorder_chapter_novel_scenes(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
    scene_ids: list[str],
    expected_structure_version: int,
) -> dict[str, Any]:
    normalized_scene_ids = normalize_scene_reorder_ids(scene_ids)
    chapter = (
        await db.execute(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.number == chapter_number)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(404, "Chapter not found")
    if int(chapter.structure_version or 0) != expected_structure_version:
        raise HTTPException(409, "Scene order changed elsewhere. Please refresh.")

    chapter_scenes = await _list_chapter_novel_scene_rows(
        db,
        book_id=book.id,
        chapter_number=chapter_number,
        lock=True,
    )
    chapter_scene_ids = [scene.id for scene in chapter_scenes]
    if len(normalized_scene_ids) != len(chapter_scene_ids):
        raise HTTPException(400, "Scene order must include every scene in the chapter.")
    if set(normalized_scene_ids) != set(chapter_scene_ids):
        raise HTTPException(400, "Scene order does not match the chapter scene set.")

    previous_order = [str(scene.id) for scene in chapter_scenes]
    scenes_by_id = {scene.id: scene for scene in chapter_scenes}
    reordered_scenes = [scenes_by_id[scene_id] for scene_id in normalized_scene_ids]
    _apply_sequential_scene_sort_order(reordered_scenes)
    for scene in reordered_scenes:
        scene.chapter_id = chapter.id
        scene.chapter_number = chapter.number
        scene.status = "assigned"

    await _increment_chapter_structure_versions(
        db,
        book_id=book.id,
        chapter_numbers=[chapter_number],
    )
    writer_workspace._append_recent_revision_edit(
        book,
        kind="scene_reordered",
        chapter_number=chapter_number,
        before_text="\n".join(previous_order),
        after_text="\n".join(str(scene.id) for scene in reordered_scenes),
    )
    await sync_chapter_content_from_novel_scenes(
        db,
        book=book,
        chapter_number=chapter_number,
    )
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise

    if not getattr(book, "is_editor_project", False):
        from app.services.task_execution_service import enqueue_extraction_execution

        await enqueue_extraction_execution(
            db,
            book_id=book.id,
            user_id=book.user_id,
            chapter_id=None,
            chapter_number=chapter_number,
            chapters_total=1,
            run_kind="scene_sync",
            identity_suffix=uuid.uuid4(),
        )

    return {
        "chapter_number": chapter_number,
        "structure_version": int(chapter.structure_version or 0),
        "scenes": [
            {
                "id": str(scene.id),
                "title": scene.title,
                "sort_order": scene.sort_order,
            }
            for scene in reordered_scenes
        ],
    }


async def snapshot_scene_version(
    db: AsyncSession,
    book: Book,
    scene: NovelScene,
    *,
    note: str,
    snapshot_kind: str = "manual",
    restored_from_version_id: uuid.UUID | None = None,
) -> SceneVersion | None:
    if not scene.title or not scene.body:
        return None

    version_key = await asyncio.to_thread(
        upload_binary,
        f"versions/{book.user_id}/{book.id}/scenes/{scene.id}/{uuid.uuid4()}.txt",
        manuscript.serialize_manuscript_content(scene.body, scene.html_body).encode("utf-8"),
        "text/plain; charset=utf-8",
    )
    version = SceneVersion(
        book_id=book.id,
        scene_id=scene.id,
        chapter_id=scene.chapter_id,
        chapter_number=scene.chapter_number,
        scene_title=scene.title,
        scene_description=scene.description,
        scene_path=scene.path,
        s3_key=version_key,
        word_count=_count_words(scene.body),
        note=note,
        snapshot_kind=snapshot_kind,
        restored_from_version_id=restored_from_version_id,
    )
    db.add(version)
    await db.flush()
    return version


async def list_scene_versions(
    db: AsyncSession,
    book: Book,
    scene_id: uuid.UUID,
    limit: int = 12,
) -> list[dict[str, Any]]:
    versions = (
        (
            await db.execute(
                select(SceneVersion)
                .where(SceneVersion.book_id == book.id, SceneVersion.scene_id == scene_id)
                .order_by(SceneVersion.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_scene_version_out(version) for version in versions]


async def get_scene_version_content(
    db: AsyncSession,
    *,
    book: Book,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = (
        await db.execute(
            select(SceneVersion).where(
                SceneVersion.book_id == book.id, SceneVersion.id == version_id
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Scene version not found")

    raw = await asyncio.to_thread(download_book, version.s3_key)
    stored = manuscript.deserialize_manuscript_content(raw)
    return {
        **_scene_version_out(version),
        "description": version.scene_description,
        "body": str(stored.get("text") or ""),
        "html_body": cast(str | None, stored.get("html")),
    }


async def restore_scene_version(
    db: AsyncSession,
    *,
    book: Book,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = (
        await db.execute(
            select(SceneVersion).where(
                SceneVersion.book_id == book.id, SceneVersion.id == version_id
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Scene version not found")

    current_scene = await db.get(NovelScene, version.scene_id) if version.scene_id else None
    if current_scene is not None and current_scene.book_id != book.id:
        current_scene = None
    if current_scene is not None:
        await snapshot_scene_version(
            db,
            book,
            current_scene,
            note=f"Checkpoint before restoring scene: {current_scene.title}",
            snapshot_kind="pre_restore",
            restored_from_version_id=version.id,
        )

    raw = await asyncio.to_thread(download_book, version.s3_key)
    stored = manuscript.deserialize_manuscript_content(raw)
    restored_scene = await save_novel_scene(
        db,
        book=book,
        scene_id=current_scene.id if current_scene is not None else None,
        title=version.scene_title,
        description=version.scene_description,
        body=str(stored.get("text") or ""),
        html_body=cast(str | None, stored.get("html")),
        chapter_number=version.chapter_number,
        status="assigned" if version.chapter_number else "unassigned",
        sort_order=current_scene.sort_order if current_scene is not None else None,
        metadata=None,
        path=version.scene_path,
        skip_scene_version_snapshot=True,
    )
    restored_scene_id = uuid.UUID(restored_scene["id"])
    versions = await list_scene_versions(db, book, restored_scene_id, 12)
    return {
        "scene": restored_scene,
        "versions": versions,
    }
