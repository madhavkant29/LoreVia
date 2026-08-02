from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_read import BetaReadAssignment, BetaReadFeedbackItem, BetaReadFeedbackKind
from app.models.book import Book, BookCollaborator, Chapter, ManuscriptAnnotation
from app.models.user import User
from app.schemas.books import CollaboratorActivityItemOut, CollaboratorActivityOut
from app.utils.beta_read_output_utils import (
    _build_beta_read_assignment_out_from_context,
    load_beta_assignment_render_context,
)
from app.utils.books.collaboration import serialize_book_collaborator


def _beta_feedback_reader_display_name(
    *,
    assignment: BetaReadAssignment,
    reader: User | None,
    collaborator: BookCollaborator | None,
) -> str:
    collaborator_name = (
        str(collaborator.display_name or "").strip() if collaborator is not None else ""
    )
    if collaborator_name:
        return collaborator_name
    username = str(reader.username or "").strip() if reader is not None else ""
    if username:
        return username
    reader_email = str(reader.email or "").strip() if reader is not None else ""
    if reader_email:
        return reader_email
    fallback_email = str(assignment.reader_email or "").strip()
    return fallback_email or "Beta reader"


def _beta_feedback_activity_title(item: BetaReadFeedbackItem) -> str:
    if item.kind == BetaReadFeedbackKind.CHAPTER_COMMENT.value:
        return "Left a chapter comment"
    if item.kind == BetaReadFeedbackKind.SCENE_REACTION.value:
        return "Left a scene reaction"
    if item.kind == BetaReadFeedbackKind.ANSWER.value:
        return "Answered an author question"
    if item.kind == BetaReadFeedbackKind.CONFUSING.value:
        return "Flagged a confusing moment"
    if item.kind == BetaReadFeedbackKind.BORING.value:
        return "Flagged a slow moment"
    if item.kind == BetaReadFeedbackKind.FAVORITE.value:
        return "Marked a favorite moment"
    return "Added beta feedback"


async def get_book_collaborator_activity(
    db: AsyncSession,
    *,
    book: Book,
    collaborator_id: uuid.UUID,
) -> CollaboratorActivityOut:
    collaborator = await db.get(BookCollaborator, collaborator_id)
    if collaborator is None or collaborator.book_id != book.id:
        raise HTTPException(404, "Collaborator not found.")

    assignments = (
        (
            await db.execute(
                select(BetaReadAssignment)
                .where(
                    BetaReadAssignment.book_id == book.id,
                    or_(
                        BetaReadAssignment.collaborator_id == collaborator.id,
                        BetaReadAssignment.reader_email == collaborator.email,
                    ),
                )
                .order_by(BetaReadAssignment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    context = (
        await load_beta_assignment_render_context(db, assignments=assignments)
        if assignments
        else None
    )
    assignment_payload = (
        [
            _build_beta_read_assignment_out_from_context(assignment, context=context)
            for assignment in assignments
        ]
        if context is not None
        else []
    )

    assignment_ids = [assignment.id for assignment in assignments]
    feedback_rows = (
        (
            await db.execute(
                select(BetaReadFeedbackItem, BetaReadAssignment)
                .join(
                    BetaReadAssignment, BetaReadAssignment.id == BetaReadFeedbackItem.assignment_id
                )
                .where(BetaReadFeedbackItem.assignment_id.in_(assignment_ids))
                .order_by(BetaReadFeedbackItem.created_at.desc())
            )
        ).all()
        if assignment_ids
        else []
    )
    annotations = (
        (
            await db.execute(
                select(ManuscriptAnnotation)
                .where(
                    ManuscriptAnnotation.book_id == book.id,
                    ManuscriptAnnotation.user_id == collaborator.invited_user_id,
                )
                .order_by(ManuscriptAnnotation.created_at.desc())
            )
        )
        .scalars()
        .all()
        if collaborator.invited_user_id is not None
        else []
    )

    chapter_numbers = {
        int(number)
        for number in [
            *[
                item.chapter_number
                for item, _assignment in feedback_rows
                if item.chapter_number is not None
            ],
            *[
                annotation.chapter_number
                for annotation in annotations
                if annotation.chapter_number is not None
            ],
        ]
        if number is not None
    }
    chapter_rows = (
        (
            await db.execute(
                select(Chapter.number, Chapter.title).where(
                    Chapter.book_id == book.id,
                    Chapter.number.in_(sorted(chapter_numbers)),
                )
            )
        ).all()
        if chapter_numbers
        else []
    )
    chapter_titles = {int(number): title for number, title in chapter_rows}

    items: list[CollaboratorActivityItemOut] = []
    for assignment in assignments:
        if assignment.first_opened_at is not None:
            items.append(
                CollaboratorActivityItemOut(
                    id=f"{assignment.id}:opened",
                    kind="beta_read_opened",
                    title="Opened beta read",
                    body=assignment.task_label,
                    assignment_id=str(assignment.id),
                    created_at=assignment.first_opened_at,
                )
            )
        if assignment.submitted_at is not None:
            items.append(
                CollaboratorActivityItemOut(
                    id=f"{assignment.id}:submitted",
                    kind="beta_read_submitted",
                    title="Submitted beta read",
                    body=assignment.final_feedback,
                    assignment_id=str(assignment.id),
                    created_at=assignment.submitted_at,
                )
            )
        if assignment.completed_at is not None:
            items.append(
                CollaboratorActivityItemOut(
                    id=f"{assignment.id}:completed",
                    kind="beta_read_completed",
                    title="Beta read completed",
                    body=assignment.task_label,
                    assignment_id=str(assignment.id),
                    created_at=assignment.completed_at,
                )
            )

    chapter_comment_count = 0
    for feedback_item, assignment in feedback_rows:
        if feedback_item.kind == BetaReadFeedbackKind.CHAPTER_COMMENT.value:
            chapter_comment_count += 1
        items.append(
            CollaboratorActivityItemOut(
                id=f"feedback:{feedback_item.id}",
                kind=feedback_item.kind,
                title=_beta_feedback_activity_title(feedback_item),
                body=feedback_item.body or feedback_item.anchor_text or feedback_item.reaction,
                chapter_number=feedback_item.chapter_number,
                chapter_title=chapter_titles.get(int(feedback_item.chapter_number))
                if feedback_item.chapter_number is not None
                else None,
                assignment_id=str(assignment.id),
                feedback_item_id=str(feedback_item.id),
                created_at=feedback_item.created_at,
            )
        )

    for annotation in annotations:
        items.append(
            CollaboratorActivityItemOut(
                id=f"annotation:{annotation.id}",
                kind="annotation",
                title="Left a manuscript annotation",
                body=annotation.comment,
                chapter_number=annotation.chapter_number,
                chapter_title=chapter_titles.get(int(annotation.chapter_number))
                if annotation.chapter_number is not None
                else None,
                annotation_id=str(annotation.id),
                created_at=annotation.created_at,
            )
        )

    items.sort(key=lambda item: item.created_at, reverse=True)
    return CollaboratorActivityOut(
        collaborator=serialize_book_collaborator(collaborator),
        assignments=assignment_payload,
        items=items,
        chapter_comment_count=chapter_comment_count,
        annotation_count=len(annotations),
        latest_activity_at=items[0].created_at if items else None,
    )
