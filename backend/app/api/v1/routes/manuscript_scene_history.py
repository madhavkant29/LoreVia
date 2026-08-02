from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.book import NovelScene
from app.schemas.books import (
    ChapterSceneOrderOut,
    ChapterSceneOrderUpdateBody,
    SceneVersionDetailOut,
    SceneVersionOut,
    SceneVersionRestoreOut,
)
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    assert_editor_project_not_rebuilding,
    collaboration_allows_chapter,
    collaboration_can_edit,
    get_book_with_collaboration_access,
)
from app.utils.books.manuscript import manuscript_text_to_html
from app.utils.books.scene_metadata import build_scene_chapter_import_text
from app.utils.books.scene_records import (
    get_scene_version_content,
    list_scene_versions,
    reorder_chapter_novel_scenes,
    restore_scene_version,
    snapshot_scene_version,
)

router = APIRouter()


@router.get("/{book_id}/scenes/{scene_id}/versions", response_model=list[SceneVersionOut])
async def get_novel_scene_versions(
    book_id: uuid.UUID,
    scene_id: uuid.UUID,
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    scene = (
        await db.execute(
            select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.id == scene_id)
        )
    ).scalar_one_or_none()
    if scene is None:
        raise HTTPException(404, "Scene not found")
    if (
        collaborator
        and scene.chapter_number is not None
        and not collaboration_allows_chapter(collaborator, scene.chapter_number)
    ):
        raise HTTPException(403, "This share cannot access that scene history.")
    if collaborator is None:
        require_author_access(current_user)
    return await list_scene_versions(db, book, scene_id, limit)


@router.post("/{book_id}/scenes/{scene_id}/snapshot", response_model=SceneVersionOut)
async def create_scene_snapshot(
    book_id: uuid.UUID,
    scene_id: uuid.UUID,
    note: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    scene = (
        await db.execute(
            select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.id == scene_id)
        )
    ).scalar_one_or_none()
    if scene is None:
        raise HTTPException(404, "Scene not found")
    if (
        collaborator
        and scene.chapter_number is not None
        and not collaboration_allows_chapter(collaborator, scene.chapter_number)
    ):
        raise HTTPException(403, "This share cannot snapshot that scene.")
    if collaborator is None:
        require_author_access(current_user)
    version = await snapshot_scene_version(
        db,
        book,
        scene,
        note=(note or f"Manual snapshot for scene: {scene.title}").strip(),
        snapshot_kind="manual",
    )
    if version is None:
        raise HTTPException(400, "Unable to snapshot scene")
    await db.commit()
    await db.refresh(version)
    return SceneVersionOut(
        **{
            "id": str(version.id),
            "scene_id": str(version.scene_id) if version.scene_id else None,
            "chapter_number": version.chapter_number,
            "scene_title": version.scene_title,
            "scene_path": version.scene_path,
            "word_count": version.word_count,
            "note": version.note,
            "snapshot_kind": version.snapshot_kind,
            "created_at": version.created_at,
        }
    )


@router.get("/{book_id}/scene-versions/{version_id}", response_model=SceneVersionDetailOut)
async def get_scene_version_detail(
    book_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    payload = await get_scene_version_content(db, book=book, version_id=version_id)
    if (
        collaborator
        and payload["chapter_number"] is not None
        and not collaboration_allows_chapter(collaborator, payload["chapter_number"])
    ):
        raise HTTPException(403, "This share cannot access that scene history.")
    return SceneVersionDetailOut(**payload)


@router.post(
    "/{book_id}/scene-versions/{version_id}/restore", response_model=SceneVersionRestoreOut
)
async def restore_saved_scene_version(
    book_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    assert_editor_project_not_rebuilding(book)
    if collaborator is not None:
        version_payload = await get_scene_version_content(db, book=book, version_id=version_id)
        if version_payload["chapter_number"] is not None and not collaboration_allows_chapter(
            collaborator, version_payload["chapter_number"]
        ):
            raise HTTPException(403, "This share cannot restore that scene.")
        if version_payload["scene_id"]:
            current_scene = await db.get(NovelScene, uuid.UUID(version_payload["scene_id"]))
            if (
                current_scene is not None
                and current_scene.book_id == book.id
                and current_scene.chapter_number is not None
                and not collaboration_allows_chapter(collaborator, current_scene.chapter_number)
            ):
                raise HTTPException(403, "This share cannot restore scenes from that chapter.")
    restored = await restore_scene_version(db, book=book, version_id=version_id)
    return SceneVersionRestoreOut(**restored)


@router.patch(
    "/{book_id}/chapters/{chapter_number}/scenes/order", response_model=ChapterSceneOrderOut
)
async def update_chapter_scene_order(
    book_id: uuid.UUID,
    chapter_number: int,
    body: ChapterSceneOrderUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot reorder scenes in that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    assert_editor_project_not_rebuilding(book)
    return await reorder_chapter_novel_scenes(
        db,
        book=book,
        chapter_number=chapter_number,
        scene_ids=body.scene_ids,
        expected_structure_version=body.expected_structure_version,
    )


@router.post("/{book_id}/scenes/{scene_id}/insert")
async def insert_scene_into_chapter(
    book_id: uuid.UUID,
    scene_id: uuid.UUID,
    chapter_number: int = Query(..., ge=1),
    position: str = Query("end", pattern="^(start|end)$"),
    include_metadata: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot insert into that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    assert_editor_project_not_rebuilding(book)
    scene = (
        await db.execute(
            select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.id == scene_id)
        )
    ).scalar_one_or_none()
    if scene is None:
        raise HTTPException(404, "Scene not found")
    scene_payload = {
        "title": scene.title,
        "description": scene.description,
        "body": scene.body,
        "metadata": scene.scene_metadata or {},
    }
    scene_number = scene.sort_order if scene.sort_order and scene.sort_order > 0 else 1
    formatted_body = build_scene_chapter_import_text(
        scene_payload,
        scene_number=scene_number,
        include_metadata=include_metadata,
    )
    return {
        "chapter_number": chapter_number,
        "position": position,
        "title": scene.title,
        "body": formatted_body,
        "html_body": manuscript_text_to_html(formatted_body),
        "scene_id": str(scene.id),
        "include_metadata": include_metadata,
    }
