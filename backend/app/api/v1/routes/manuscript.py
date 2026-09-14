from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.feature_flags import (
    require_cursor_page_apis_enabled,
    require_indexed_search_enabled,
)
from app.api.v1.routes import manuscript_annotations, manuscript_scene_history
from app.core.database import get_db
from app.models.book import Chapter, ChapterVersion, NovelScene
from app.schemas.books import (
    ChapterContentSaveBody,
    ChapterContentSaveOut,
    ChapterVersionDetailOut,
    ChapterVersionOut,
    ChapterVersionRestoreStatusOut,
    ManuscriptWorkspaceTreeOut,
    NovelSceneBody,
    NovelSceneOut,
    NovelScenePageOut,
    WorkspaceSearchBody,
    WorkspaceSearchPageOut,
    WorkspaceSearchResultOut,
)
from app.services.chapter_content_service import save_chapter_content
from app.utils.billing_utils import require_author_access
from app.utils.books.chapter_versions import (
    delete_chapter,
    get_chapter_version_content,
    list_chapter_versions,
    restore_chapter_version,
    snapshot_chapter_version,
)
from app.utils.books.collaboration_access import (
    assert_editor_project_not_rebuilding,
    collaboration_allows_chapter,
    collaboration_can_edit,
    get_book_with_collaboration_access,
)
from app.utils.books.scene_records import (
    delete_novel_scene,
    get_novel_scene,
    list_novel_scenes,
    list_novel_scenes_page,
    save_novel_scene,
)
from app.utils.books.workspace_search import (
    build_manuscript_workspace_tree,
    search_author_workspace,
    search_author_workspace_page,
)

router = APIRouter()
router.include_router(manuscript_annotations.router)
router.include_router(manuscript_scene_history.router)


@router.put(
    "/{book_id}/chapters/{chapter_number}/content",
    response_model=ChapterContentSaveOut,
)
async def put_chapter_content(
    book_id: uuid.UUID,
    chapter_number: int,
    body: ChapterContentSaveBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await save_chapter_content(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        current_user=current_user,
        body=body,
    )


@router.get("/{book_id}/workspace/tree", response_model=ManuscriptWorkspaceTreeOut)
async def get_manuscript_workspace_tree(
    book_id: uuid.UUID,
    include_scene_bodies: bool = Query(False),
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
        include_scene_bodies=include_scene_bodies,
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
        collaborator=collaborator,
        limit=body.limit,
    )


@router.post(
    "/{book_id}/workspace/search/page",
    response_model=WorkspaceSearchPageOut,
    dependencies=[
        Depends(require_cursor_page_apis_enabled),
        Depends(require_indexed_search_enabled),
    ],
)
async def search_workspace_page(
    book_id: uuid.UUID,
    body: WorkspaceSearchBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Cursor page for workspace search; keep the list route for legacy clients."""
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot search the author workspace.")
    if collaborator is None:
        require_author_access(current_user)
    return await search_author_workspace_page(
        db,
        book=book,
        user_id=current_user.id,
        query=body.query,
        scopes=body.scopes,
        case_sensitive=body.case_sensitive,
        whole_word=body.whole_word,
        regex=body.regex,
        filters=body.filters.model_dump(),
        collaborator=collaborator,
        limit=body.limit,
        cursor=body.cursor,
    )


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
    if (
        collaborator
        and chapter_number is not None
        and not collaboration_allows_chapter(collaborator, chapter_number)
    ):
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


@router.get(
    "/{book_id}/scenes/page",
    response_model=NovelScenePageOut,
    dependencies=[Depends(require_cursor_page_apis_enabled)],
)
async def get_novel_scenes_page(
    book_id: uuid.UUID,
    chapter_number: int | None = Query(None, ge=1),
    status: str | None = Query(None),
    query: str | None = Query(None),
    include_body: bool = Query(False),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1024),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if (
        collaborator
        and chapter_number is not None
        and not collaboration_allows_chapter(collaborator, chapter_number)
    ):
        raise HTTPException(403, "This share cannot access that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    return await list_novel_scenes_page(
        db,
        book=book,
        collaborator=collaborator,
        chapter_number=chapter_number,
        status=status,
        query=query,
        include_body=include_body,
        limit=limit,
        cursor=cursor,
    )


@router.get("/{book_id}/scenes/{scene_id}", response_model=NovelSceneOut)
async def get_novel_scene_detail(
    book_id: uuid.UUID,
    scene_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    return await get_novel_scene(db, book=book, scene_id=scene_id, collaborator=collaborator)


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
    if (
        collaborator
        and body.chapter_number is not None
        and not collaboration_allows_chapter(collaborator, body.chapter_number)
    ):
        raise HTTPException(403, "This share cannot create scenes for that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    assert_editor_project_not_rebuilding(book)
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
        metadata=body.metadata.model_dump()
        if hasattr(body.metadata, "model_dump")
        else body.metadata,
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
        if current_scene.chapter_number is not None and not collaboration_allows_chapter(
            collaborator, current_scene.chapter_number
        ):
            raise HTTPException(403, "This share cannot edit scenes from that chapter.")
        target_chapter_number = (
            body.chapter_number if body.chapter_number is not None else current_scene.chapter_number
        )
        if target_chapter_number is not None and not collaboration_allows_chapter(
            collaborator, target_chapter_number
        ):
            raise HTTPException(403, "This share cannot move scenes into that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    assert_editor_project_not_rebuilding(book)
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
        metadata=body.metadata.model_dump()
        if hasattr(body.metadata, "model_dump")
        else body.metadata,
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
        if scene.chapter_number is not None and not collaboration_allows_chapter(
            collaborator, scene.chapter_number
        ):
            raise HTTPException(403, "This share cannot remove scenes from that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    assert_editor_project_not_rebuilding(book)
    await delete_novel_scene(db, book=book, scene_id=scene_id)
    return Response(status_code=204)


@router.delete("/{book_id}/chapters/{chapter_number}", status_code=204)
async def remove_chapter(
    book_id: uuid.UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot remove that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    await delete_chapter(db, book=book, chapter_number=chapter_number)
    return Response(status_code=204)


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
    assert_editor_project_not_rebuilding(book)
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
    version = (
        await db.execute(
            select(ChapterVersion).where(
                ChapterVersion.book_id == book.id, ChapterVersion.id == version_id
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Chapter version not found")
    if collaborator is not None and not collaboration_allows_chapter(
        collaborator, version.chapter_number
    ):
        raise HTTPException(403, "This share cannot restore that chapter.")

    restored = await restore_chapter_version(db, book=book, version_id=version_id)

    version = await db.get(ChapterVersion, version_id)
    if version is None or version.book_id != book.id:
        raise HTTPException(404, "Chapter version not found")
    version.restore_status = "queued"
    version.restore_error = None
    version.restore_task_id = None
    version.restore_started_at = None
    version.restore_completed_at = None
    await db.commit()

    from app.services.task_execution_service import enqueue_extraction_execution

    execution = await enqueue_extraction_execution(
        db,
        book_id=book.id,
        user_id=book.user_id,
        chapter_id=version.chapter_id,
        chapter_number=int(restored["chapter_number"]),
        chapters_total=1,
        chapter_version_id=version_id,
        run_kind="chapter_restore",
    )
    version.restore_status = "queued"
    version.restore_task_id = str(execution.id)
    version.restore_started_at = None
    version.restore_completed_at = None
    await db.commit()

    versions = await list_chapter_versions(db, book, restored["chapter_number"], 12)
    scenes = await list_novel_scenes(
        db,
        book=book,
        collaborator=collaborator,
        chapter_number=restored["chapter_number"],
    )

    return {
        "status": "restore_queued",
        "task_id": str(execution.id),
        "chapter_number": restored["chapter_number"],
        "title": restored["title"],
        "text": restored["text"],
        "html": restored["html"],
        "versions": versions,
        "scenes": scenes,
    }


@router.get(
    "/{book_id}/chapter-versions/{version_id}/restore-status",
    response_model=ChapterVersionRestoreStatusOut,
)
async def get_chapter_version_restore_status(
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
    version = (
        await db.execute(
            select(ChapterVersion).where(
                ChapterVersion.book_id == book.id, ChapterVersion.id == version_id
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Chapter version not found")
    if collaborator is not None and not collaboration_allows_chapter(
        collaborator, version.chapter_number
    ):
        raise HTTPException(403, "This share cannot access that chapter history.")
    return ChapterVersionRestoreStatusOut(
        id=str(version.id),
        chapter_number=version.chapter_number,
        restore_status=version.restore_status,
        restore_error=version.restore_error,
        restore_task_id=version.restore_task_id,
        restore_started_at=version.restore_started_at,
        restore_completed_at=version.restore_completed_at,
    )
