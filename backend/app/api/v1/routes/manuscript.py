from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.book import Chapter, ChapterVersion, ManuscriptAnnotation, NovelScene
from app.schemas.books import (
    ChapterSceneOrderOut,
    ChapterSceneOrderUpdateBody,
    ChapterVersionDetailOut,
    ChapterVersionOut,
    ManuscriptAnnotationBody,
    ManuscriptAnnotationOut,
    ManuscriptWorkspaceTreeOut,
    NovelSceneBody,
    NovelSceneOut,
    SceneVersionDetailOut,
    SceneVersionOut,
    SceneVersionRestoreOut,
    WorkspaceSearchBody,
    WorkspaceSearchResultOut,
)
from app.utils.book_utils import (
    build_manuscript_workspace_tree,
    build_scene_chapter_import_text,
    collaboration_allows_chapter,
    collaboration_can_comment,
    collaboration_can_edit,
    delete_manuscript_annotation,
    delete_novel_scene,
    extract_novel_scene_candidates,
    get_chapter_version_content,
    get_scene_version_content,
    get_book_with_collaboration_access,
    list_manuscript_annotations,
    list_chapter_versions,
    list_novel_scenes,
    list_scene_versions,
    reorder_chapter_novel_scenes,
    replace_chapter_novel_scenes,
    restore_chapter_version,
    restore_scene_version,
    save_manuscript_annotation,
    save_novel_scene,
    search_author_workspace,
    snapshot_chapter_version,
    snapshot_scene_version,
    manuscript_text_to_html,
    sync_chapter_content_from_novel_scenes,
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
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    return await build_manuscript_workspace_tree(
        db,
        book=book,
        user_id=current_user.id,
        collaborator=collaborator,
    )


@router.post("/{book_id}/workspace/search", response_model=list[WorkspaceSearchResultOut])
async def search_workspace(
    book_id: uuid.UUID,
    body: WorkspaceSearchBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot search the author workspace.")
    if collaborator is None:
        require_author_access(current_user)
    return await search_author_workspace(
        db,
        book=book,
        user_id=current_user.id,
        query=body.query,
        scopes=body.scopes,
        case_sensitive=body.case_sensitive,
        whole_word=body.whole_word,
        regex=body.regex,
        filters=body.filters.model_dump(),
    )


@router.get("/{book_id}/annotations", response_model=list[ManuscriptAnnotationOut])
async def get_manuscript_annotations(
    book_id: uuid.UUID,
    chapter_number: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot view manuscript comments.")
    if collaborator and chapter_number is not None and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot access that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    return await list_manuscript_annotations(
        db,
        book=book,
        actor=current_user,
        collaborator=collaborator,
        chapter_number=chapter_number,
    )


@router.post("/{book_id}/annotations", response_model=ManuscriptAnnotationOut)
async def upsert_manuscript_annotation(
    book_id: uuid.UUID,
    body: ManuscriptAnnotationBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot leave manuscript comments.")
    target_chapter = body.chapter_number
    if collaborator and body.annotation_id:
        try:
            existing_annotation_id = uuid.UUID(body.annotation_id)
        except ValueError as exc:
            raise HTTPException(400, "Invalid annotation id") from exc
        existing = (
            await db.execute(
                select(ManuscriptAnnotation).where(
                    ManuscriptAnnotation.book_id == book.id,
                    ManuscriptAnnotation.id == existing_annotation_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            raise HTTPException(404, "Annotation not found")
        target_chapter = target_chapter if target_chapter is not None else existing.chapter_number
    if collaborator and target_chapter is not None and not collaboration_allows_chapter(collaborator, target_chapter):
        raise HTTPException(403, "This share cannot comment on that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    return await save_manuscript_annotation(
        db,
        book=book,
        actor=current_user,
        annotation_id=body.annotation_id,
        chapter_number=body.chapter_number,
        category=body.category,
        status=body.status,
        visibility=body.visibility,
        quote=body.quote,
        comment=body.comment,
        anchor_context_before=body.anchor_context_before,
        anchor_context_after=body.anchor_context_after,
        start_offset=body.start_offset,
        end_offset=body.end_offset,
    )


@router.delete("/{book_id}/annotations/{annotation_id}", status_code=204)
async def remove_manuscript_annotation(
    book_id: uuid.UUID,
    annotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot remove manuscript comments.")
    if collaborator is not None:
        annotation = await db.get(ManuscriptAnnotation, annotation_id)
        if annotation is None or annotation.book_id != book.id:
            raise HTTPException(404, "Annotation not found")
        if not collaboration_allows_chapter(collaborator, annotation.chapter_number):
            raise HTTPException(403, "This share cannot remove comments from that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    await delete_manuscript_annotation(
        db,
        book=book,
        actor=current_user,
        annotation_id=annotation_id,
    )
    return Response(status_code=204)


@router.get("/{book_id}/scenes", response_model=list[NovelSceneOut])
async def get_novel_scenes(
    book_id: uuid.UUID,
    chapter_number: int | None = Query(None, ge=1),
    status: str | None = Query(None),
    query: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and chapter_number is not None and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot access that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    return await list_novel_scenes(
        db,
        book=book,
        collaborator=collaborator,
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
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and body.chapter_number is not None and not collaboration_allows_chapter(collaborator, body.chapter_number):
        raise HTTPException(403, "This share cannot create scenes for that chapter.")
    if collaborator is None:
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
        metadata=body.metadata.model_dump() if hasattr(body.metadata, "model_dump") else body.metadata,
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
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator:
        current_scene = (
            await db.execute(
                select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.id == scene_id)
            )
        ).scalar_one_or_none()
        if current_scene is None:
            raise HTTPException(404, "Scene not found")
        target_chapter_number = body.chapter_number if body.chapter_number is not None else current_scene.chapter_number
        if target_chapter_number is not None and not collaboration_allows_chapter(collaborator, target_chapter_number):
            raise HTTPException(403, "This share cannot move scenes into that chapter.")
    if collaborator is None:
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
        metadata=body.metadata.model_dump() if hasattr(body.metadata, "model_dump") else body.metadata,
        path=body.path,
    )


@router.delete("/{book_id}/scenes/{scene_id}", status_code=204)
async def remove_novel_scene(
    book_id: uuid.UUID,
    scene_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator:
        scene = (
            await db.execute(
                select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.id == scene_id)
            )
        ).scalar_one_or_none()
        if scene is None:
            raise HTTPException(404, "Scene not found")
        if scene.chapter_number is not None and not collaboration_allows_chapter(collaborator, scene.chapter_number):
            raise HTTPException(403, "This share cannot remove scenes from that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    await delete_novel_scene(db, book=book, scene_id=scene_id)
    return Response(status_code=204)


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
    if collaborator and scene.chapter_number is not None and not collaboration_allows_chapter(collaborator, scene.chapter_number):
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
    if collaborator and scene.chapter_number is not None and not collaboration_allows_chapter(collaborator, scene.chapter_number):
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
    return SceneVersionOut(**{
        "id": str(version.id),
        "scene_id": str(version.scene_id) if version.scene_id else None,
        "chapter_number": version.chapter_number,
        "scene_title": version.scene_title,
        "scene_path": version.scene_path,
        "word_count": version.word_count,
        "note": version.note,
        "snapshot_kind": version.snapshot_kind,
        "created_at": version.created_at,
    })


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
    if collaborator and payload["chapter_number"] is not None and not collaboration_allows_chapter(collaborator, payload["chapter_number"]):
        raise HTTPException(403, "This share cannot access that scene history.")
    return SceneVersionDetailOut(**payload)


@router.post("/{book_id}/scene-versions/{version_id}/restore", response_model=SceneVersionRestoreOut)
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
    if collaborator is not None:
        version_payload = await get_scene_version_content(db, book=book, version_id=version_id)
        if version_payload["chapter_number"] is not None and not collaboration_allows_chapter(collaborator, version_payload["chapter_number"]):
            raise HTTPException(403, "This share cannot restore that scene.")
    restored = await restore_scene_version(db, book=book, version_id=version_id)
    return SceneVersionRestoreOut(**restored)


@router.patch("/{book_id}/chapters/{chapter_number}/scenes/order", response_model=ChapterSceneOrderOut)
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
    return await reorder_chapter_novel_scenes(
        db,
        book=book,
        chapter_number=chapter_number,
        scene_ids=body.scene_ids,
        expected_structure_version=body.expected_structure_version,
    )


@router.post("/{book_id}/chapters/{chapter_number}/snapshot", response_model=ChapterVersionOut)
async def create_chapter_snapshot(
    book_id: uuid.UUID,
    chapter_number: int,
    note: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot snapshot that chapter.")
    if collaborator is None:
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
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    payload = await get_chapter_version_content(db, book=book, version_id=version_id)
    if collaborator and not collaboration_allows_chapter(collaborator, payload["chapter_number"]):
        raise HTTPException(403, "This share cannot access that chapter history.")
    return ChapterVersionDetailOut(**payload)


@router.post("/{book_id}/chapter-versions/{version_id}/restore")
async def restore_saved_chapter_version(
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
    if collaborator is not None:
        version = (
            await db.execute(
                select(ChapterVersion).where(ChapterVersion.book_id == book.id, ChapterVersion.id == version_id)
            )
        ).scalar_one_or_none()
        if version is None:
            raise HTTPException(404, "Chapter version not found")
        if not collaboration_allows_chapter(collaborator, version.chapter_number):
            raise HTTPException(403, "This share cannot restore that chapter.")
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
            source="chapter_sync",
        )
        await replace_chapter_novel_scenes(
            db,
            book=book,
            chapter_number=restored["chapter_number"],
            scenes=extracted_scenes,
        )
        await sync_chapter_content_from_novel_scenes(
            db,
            book=book,
            chapter_number=restored["chapter_number"],
        )
    versions = await list_chapter_versions(db, book, restored["chapter_number"], 12)
    scenes = await list_novel_scenes(
        db,
        book=book,
        collaborator=collaborator,
        chapter_number=restored["chapter_number"],
    )
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
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot insert into that chapter.")
    if collaborator is None:
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
