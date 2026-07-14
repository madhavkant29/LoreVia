from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.book import ManuscriptAnnotation
from app.schemas.books import ManuscriptAnnotationBody, ManuscriptAnnotationOut
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_can_comment,
    get_book_with_collaboration_access,
)
from app.utils.books.notes import (
    delete_manuscript_annotation,
    list_manuscript_annotations,
    save_manuscript_annotation,
)

router = APIRouter()


@router.get("/{book_id}/annotations", response_model=list[ManuscriptAnnotationOut])
async def get_manuscript_annotations(
    book_id: uuid.UUID,
    chapter_number: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if (
        collaborator
        and chapter_number is not None
        and not collaboration_allows_chapter(collaborator, chapter_number)
    ):
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
    if (
        collaborator
        and target_chapter is not None
        and not collaboration_allows_chapter(collaborator, target_chapter)
    ):
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
