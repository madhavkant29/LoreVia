import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# â”€â”€â”€ Upload limits â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MAX_BOOK_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_COVER_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

_COVER_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG": ("png", "image/png"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),
}

BLEACH_EMPTY_TAGS: Any = frozenset()


from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.core.redis import (
    get_book_cache_version,
    get_writer_workspace_cache,
    mark_book_cache_dirty,
    set_writer_workspace_cache,
)
from app.models.book import (
    Book,
)
from app.models.character import (
    Character,
)
from app.schemas.books import (
    BookOverviewOut,
    ChapterConsistencyReport,
    ChapterVersionOut,
    EmotionalArcOverviewOut,
    PreWritingCheckOut,
    RevisionFindingDecisionBody,
    RevisionIntelligenceOut,
    StoryHealthOut,
    WriterWorkspaceBody,
    WriterWorkspaceOut,
)
from app.services.pipeline_state_service import (
    build_writer_workspace_response,
    build_writer_workspace_update,
    enqueue_processing_state_repair_if_needed,
)
from app.utils.billing_utils import require_author_access
from app.utils.books.access import book_cache_access_key
from app.utils.books.chapter_versions import (
    list_chapter_versions,
)
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_can_edit,
    collaboration_has_resource,
    get_book_with_collaboration_access,
)
from app.utils.books.consistency_reports import list_chapter_consistency_reports
from app.utils.books.notes import (
    get_owned_book,
)
from app.utils.books.overview import build_book_overview_payload
from app.utils.books.planning import (
    build_emotional_arc_payload,
    build_prewriting_check,
)
from app.utils.books.revision_decisions import (
    apply_revision_finding_decision,
)
from app.utils.books.revision_service import (
    build_revision_intelligence_payload,
)
from app.utils.books.story_health import build_story_health_payload

router = APIRouter()


@router.get("/{book_id}/overview", response_model=BookOverviewOut)
async def get_book_overview(
    book_id: uuid.UUID,
    include: str | None = Query(
        None,
        description="Comma-separated sub-objects: book, progress, chapter_list, summary_collection",
    ),
    fields: str | None = Query(None, description="Comma-separated fields for the book sub-object"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(
        db,
        book_id,
        current_user,
    )
    return await build_book_overview_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
        include=include,
        fields=fields,
    )


# â”€â”€â”€ Analysis & intelligence endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get("/{book_id}/pre-writing-check", response_model=PreWritingCheckOut)
async def get_prewriting_check(
    book_id: uuid.UUID,
    upcoming_chapter: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "reader_confusion_report"):
        raise HTTPException(403, "This share does not include the reader confusion report.")
    if collaborator is None:
        require_author_access(current_user)
    next_chapter = upcoming_chapter or ((book.total_chapters or 0) + 1)
    return await build_prewriting_check(db, book, next_chapter)


@router.get("/{book_id}/story-health", response_model=StoryHealthOut)
async def get_story_health(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "reader_confusion_report"):
        raise HTTPException(403, "This share does not include the reader confusion report.")
    if collaborator is None:
        require_author_access(current_user)
    return await build_story_health_payload(db, book)


@router.get("/{book_id}/revision-intelligence", response_model=RevisionIntelligenceOut)
async def get_revision_intelligence(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_has_resource(collaborator, "continuity_report"):
        raise HTTPException(403, "This share does not include revision intelligence.")
    if collaborator is None:
        require_author_access(current_user)
    return RevisionIntelligenceOut(**(await build_revision_intelligence_payload(db, book)))


@router.post(
    "/{book_id}/revision-findings/{finding_id}/decision", response_model=RevisionIntelligenceOut
)
async def decide_revision_finding(
    book_id: uuid.UUID,
    finding_id: str,
    body: RevisionFindingDecisionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    payload = await build_revision_intelligence_payload(db, book)
    findings = payload.get("priority_findings") or []
    finding = next((item for item in findings if str(item.get("id")) == finding_id), None)
    if finding is None:
        all_findings = [
            *payload.get("change_impacts", []),
            *payload.get("scene_advice", []),
            *payload.get("confusion_map", []),
            *payload.get("voice_alerts", []),
        ]
        finding = next((item for item in all_findings if str(item.get("id")) == finding_id), None)
    if finding is None:
        raise HTTPException(404, "Revision finding not found.")
    apply_revision_finding_decision(
        book,
        finding=finding,
        decision=body.decision,
        action=body.action,
        reason=body.reason,
    )
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    return RevisionIntelligenceOut(**(await build_revision_intelligence_payload(db, book)))


@router.get("/{book_id}/chapter-reports", response_model=list[ChapterConsistencyReport])
async def get_book_chapter_reports(
    book_id: uuid.UUID,
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "continuity_report"):
        raise HTTPException(403, "This share does not include the continuity report.")
    if collaborator is None:
        require_author_access(current_user)
    return await list_chapter_consistency_reports(db, book, limit)


@router.get("/{book_id}/chapter-versions", response_model=list[ChapterVersionOut])
async def get_book_chapter_versions(
    book_id: uuid.UUID,
    chapter_number: int = Query(..., ge=1),
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator and not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share cannot access that chapter history.")
    if collaborator is None:
        require_author_access(current_user)
    return await list_chapter_versions(db, book, chapter_number, limit)


# â”€â”€â”€ Writer workspace â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get("/{book_id}/writer-workspace", response_model=WriterWorkspaceOut)
async def get_writer_workspace(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    await enqueue_processing_state_repair_if_needed(book)
    cache_version = await get_book_cache_version(str(book.id))
    access_key = book_cache_access_key(current_user.id, collaborator)
    cached = await get_writer_workspace_cache(
        str(book.id), str(current_user.id), access_key, cache_version
    )
    if cached is not None:
        return WriterWorkspaceOut(**cached)
    payload = build_writer_workspace_response(book)
    await set_writer_workspace_cache(
        str(book.id),
        str(current_user.id),
        access_key,
        cache_version,
        payload.model_dump(mode="json"),
    )
    return payload


@router.put("/{book_id}/writer-workspace", response_model=WriterWorkspaceOut)
async def update_writer_workspace(
    book_id: uuid.UUID,
    body: WriterWorkspaceBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This share cannot edit the manuscript.")
    if collaborator is None:
        require_author_access(current_user)
    next_payload = build_writer_workspace_update(book, body.model_dump(exclude_none=True))
    book.writer_workspace = next_payload
    if body.reprocess is not None and body.reprocess.auto_reprocess_enabled is not None:
        from app.services.editor_project_service import update_reprocess_metadata

        update_reprocess_metadata(
            book, auto_reprocess_enabled=body.reprocess.auto_reprocess_enabled
        )
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    return build_writer_workspace_response(book)


# â”€â”€â”€ Emotional arc â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get("/{book_id}/emotional-arc", response_model=EmotionalArcOverviewOut)
async def get_emotional_arc(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(
        db,
        book_id,
        current_user.id,
        options=(selectinload(Book.characters),),
    )
    require_author_access(current_user)
    book_characters = getattr(book, "characters", None)
    if book_characters is None:
        result = await db.execute(
            select(Character)
            .where(Character.book_id == book_id)
            .order_by(Character.mention_count.desc().nullslast(), Character.name)
        )
        book_characters = result.scalars().all()
    characters = sorted(
        book_characters or [],
        key=lambda c: (c.mention_count or 0, c.name or ""),
        reverse=True,
    )
    return EmotionalArcOverviewOut(**build_emotional_arc_payload(characters))


# â”€â”€â”€ Book lifecycle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
