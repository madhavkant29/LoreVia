from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.book import Chapter, NovelScene
from app.schemas.books import (
    ChapterVersionDetailOut,
    ChapterVersionOut,
    ManuscriptWorkspaceTreeOut,
    NovelSceneBody,
    NovelSceneOut,
)
from app.utils.book_utils import (
    build_manuscript_workspace_tree,
    build_scene_chapter_import_text,
    delete_novel_scene,
    extract_novel_scene_candidates,
    get_chapter_version_content,
    get_owned_book,
    list_chapter_versions,
    list_novel_scenes,
    replace_chapter_novel_scenes,
    restore_chapter_version,
    save_novel_scene,
    snapshot_chapter_version,
    manuscript_text_to_html,
)
from app.utils.billing_utils import require_author_access
from app.workers.consumers.extraction_consumer import _process_chapter

router = APIRouter()


@router.get("/{book_id}/workspace/tree", response_model=ManuscriptWorkspaceTreeOut)
async def get_manuscript_workspace_tree(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await build_manuscript_workspace_tree(db, book=book, user_id=current_user.id)


@router.get("/{book_id}/scenes", response_model=list[NovelSceneOut])
async def get_novel_scenes(
    book_id: uuid.UUID,
    chapter_number: int | None = Query(None, ge=1),
    status: str | None = Query(None),
    query: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await list_novel_scenes(
        db,
        book=book,
        chapter_number=chapter_number,
        status=status,
        query=query,
    )


@router.post("/{book_id}/scenes", response_model=NovelSceneOut)
async def create_novel_scene(
    book_id: uuid.UUID,
    body: NovelSceneBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await save_novel_scene(
        db,
        book=book,
        scene_id=None,
        title=body.title,
        description=body.description,
        body=body.body,
        html_body=body.html_body,
        chapter_number=body.chapter_number,
        status=body.status,
        sort_order=body.sort_order,
        metadata=body.metadata,
        path=body.path,
    )


@router.put("/{book_id}/scenes/{scene_id}", response_model=NovelSceneOut)
async def update_novel_scene(
    book_id: uuid.UUID,
    scene_id: uuid.UUID,
    body: NovelSceneBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await save_novel_scene(
        db,
        book=book,
        scene_id=scene_id,
        title=body.title,
        description=body.description,
        body=body.body,
        html_body=body.html_body,
        chapter_number=body.chapter_number,
        status=body.status,
        sort_order=body.sort_order,
        metadata=body.metadata,
        path=body.path,
    )


@router.delete("/{book_id}/scenes/{scene_id}", status_code=204)
async def remove_novel_scene(
    book_id: uuid.UUID,
    scene_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await delete_novel_scene(db, book=book, scene_id=scene_id)
    return Response(status_code=204)


@router.post("/{book_id}/chapters/{chapter_number}/snapshot", response_model=ChapterVersionOut)
async def create_chapter_snapshot(
    book_id: uuid.UUID,
    chapter_number: int,
    note: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(404, "Chapter not found")
    version = await snapshot_chapter_version(
        db,
        book,
        chapter,
        note=(note or f"Manual snapshot for Chapter {chapter_number}").strip(),
        snapshot_kind="manual",
    )
    if version is None:
        raise HTTPException(400, "Unable to snapshot chapter")
    await db.commit()
    await db.refresh(version)
    return ChapterVersionOut(
        id=str(version.id),
        chapter_number=version.chapter_number,
        title=version.title,
        word_count=version.word_count,
        note=version.note,
        snapshot_kind=version.snapshot_kind,
        created_at=version.created_at,
    )


@router.get("/{book_id}/chapter-versions/{version_id}", response_model=ChapterVersionDetailOut)
async def get_chapter_version_detail(
    book_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    payload = await get_chapter_version_content(db, book=book, version_id=version_id)
    return ChapterVersionDetailOut(**payload)


@router.post("/{book_id}/chapter-versions/{version_id}/restore")
async def restore_saved_chapter_version(
    book_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    restored = await restore_chapter_version(db, book=book, version_id=version_id)
    await _process_chapter(
        db,
        book,
        {
            "number": restored["chapter_number"],
            "title": restored["title"],
            "text": restored["text"],
            "html": restored["html"],
            "description": None,
            "images": [],
        },
    )
    if book.work_type != "screenplay":
        extracted_scenes = extract_novel_scene_candidates(
            text=restored["text"],
            chapter_number=restored["chapter_number"],
            source="extracted",
        )
        await replace_chapter_novel_scenes(
            db,
            book=book,
            chapter_number=restored["chapter_number"],
            scenes=extracted_scenes,
        )
    versions = await list_chapter_versions(db, book, restored["chapter_number"], 12)
    scenes = await list_novel_scenes(db, book=book, chapter_number=restored["chapter_number"])
    return {
        "chapter_number": restored["chapter_number"],
        "title": restored["title"],
        "text": restored["text"],
        "html": restored["html"],
        "versions": versions,
        "scenes": scenes,
    }


@router.post("/{book_id}/scenes/{scene_id}/insert")
async def insert_scene_into_chapter(
    book_id: uuid.UUID,
    scene_id: uuid.UUID,
    chapter_number: int = Query(..., ge=1),
    position: str = Query("end", pattern="^(start|end)$"),
    include_metadata: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
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
