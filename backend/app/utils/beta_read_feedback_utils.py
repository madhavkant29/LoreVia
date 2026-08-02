from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_read import (
    BetaReadAssignment,
    BetaReadFeedbackItem,
    BetaReadFeedbackKind,
    BetaReadQuestion,
)
from app.models.book import Book, BookCollaborator, NovelScene
from app.models.user import User
from app.schemas.beta_reads import (
    BetaReadFeedbackItemOut,
    BetaReadFeedbackSummaryOut,
    BetaReadQuestionOut,
)
from app.schemas.books import ChapterBetaFeedbackOut
from app.utils.beta_read_activity_utils import _beta_feedback_reader_display_name
from app.utils.beta_read_policy_utils import (
    assignment_scope_bounds,
    beta_feedback_item_author_metadata,
)


def _clean_optional_feedback_text(value: str | None, *, max_length: int) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        raise HTTPException(400, f"Feedback text must be {max_length} characters or fewer.")
    return cleaned


async def _resolve_feedback_scene(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    scene_id: str | None,
) -> NovelScene | None:
    if not scene_id:
        return None
    try:
        parsed_scene_id = uuid.UUID(scene_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid scene_id.") from exc
    scene = await db.get(NovelScene, parsed_scene_id)
    if scene is None or scene.book_id != assignment.book_id:
        raise HTTPException(404, "Scene not found for this beta read.")
    book = await db.get(Book, assignment.book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    start, end = assignment_scope_bounds(assignment, int(book.total_chapters or 0))
    if scene.chapter_number is not None and not start <= int(scene.chapter_number) <= end:
        raise HTTPException(403, "That scene is outside this beta read scope.")
    return scene


async def _resolve_feedback_question(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    question_id: str | None,
) -> BetaReadQuestion | None:
    if not question_id:
        return None
    try:
        parsed_question_id = uuid.UUID(question_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid question_id.") from exc
    question = await db.get(BetaReadQuestion, parsed_question_id)
    if question is None or question.assignment_id != assignment.id:
        raise HTTPException(404, "Beta-read question not found.")
    return question


async def list_beta_read_questions(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
) -> list[BetaReadQuestion]:
    return (
        (
            await db.execute(
                select(BetaReadQuestion)
                .where(BetaReadQuestion.assignment_id == assignment_id)
                .order_by(BetaReadQuestion.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


async def beta_feedback_summary(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
) -> BetaReadFeedbackSummaryOut:
    rows = (
        await db.execute(
            select(BetaReadFeedbackItem.kind, func.count(BetaReadFeedbackItem.id))
            .where(BetaReadFeedbackItem.assignment_id == assignment_id)
            .group_by(BetaReadFeedbackItem.kind)
        )
    ).all()
    counts = {str(kind): int(count or 0) for kind, count in rows}
    return BetaReadFeedbackSummaryOut(
        feedback_item_count=sum(counts.values()),
        chapter_comment_count=counts.get(BetaReadFeedbackKind.CHAPTER_COMMENT.value, 0),
        scene_reaction_count=counts.get(BetaReadFeedbackKind.SCENE_REACTION.value, 0),
        answer_count=counts.get(BetaReadFeedbackKind.ANSWER.value, 0),
        confusing_count=counts.get(BetaReadFeedbackKind.CONFUSING.value, 0),
        boring_count=counts.get(BetaReadFeedbackKind.BORING.value, 0),
        favorite_count=counts.get(BetaReadFeedbackKind.FAVORITE.value, 0),
    )


async def _serialize_beta_read_questions(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
) -> list[BetaReadQuestionOut]:
    questions = await list_beta_read_questions(db, assignment_id=assignment_id)
    answer_rows = (
        await db.execute(
            select(BetaReadFeedbackItem.question_id, func.count(BetaReadFeedbackItem.id))
            .where(
                BetaReadFeedbackItem.assignment_id == assignment_id,
                BetaReadFeedbackItem.kind == BetaReadFeedbackKind.ANSWER.value,
                BetaReadFeedbackItem.question_id.is_not(None),
            )
            .group_by(BetaReadFeedbackItem.question_id)
        )
    ).all()
    answer_counts = {
        str(question_id): int(count or 0)
        for question_id, count in answer_rows
        if question_id is not None
    }
    return [
        BetaReadQuestionOut(
            id=str(question.id),
            prompt=question.prompt,
            created_at=question.created_at,
            answer_count=answer_counts.get(str(question.id), 0),
        )
        for question in questions
    ]


async def _serialize_beta_read_feedback_items(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
) -> list[BetaReadFeedbackItemOut]:
    items = (
        (
            await db.execute(
                select(BetaReadFeedbackItem)
                .where(BetaReadFeedbackItem.assignment_id == assignment_id)
                .order_by(BetaReadFeedbackItem.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    if not items:
        return []

    question_ids = {item.question_id for item in items if item.question_id is not None}
    scene_ids = {item.scene_id for item in items if item.scene_id is not None}
    questions = {}
    if question_ids:
        question_rows = (
            (
                await db.execute(
                    select(BetaReadQuestion).where(BetaReadQuestion.id.in_(list(question_ids)))
                )
            )
            .scalars()
            .all()
        )
        questions = {question.id: question for question in question_rows}
    scenes = {}
    if scene_ids:
        scene_rows = (
            (await db.execute(select(NovelScene).where(NovelScene.id.in_(list(scene_ids)))))
            .scalars()
            .all()
        )
        scenes = {scene.id: scene for scene in scene_rows}

    serialized_items: list[BetaReadFeedbackItemOut] = []
    for item in items:
        author_metadata = beta_feedback_item_author_metadata(item)
        serialized_items.append(
            BetaReadFeedbackItemOut(
                id=str(item.id),
                kind=item.kind,
                chapter_number=item.chapter_number,
                scene_id=str(item.scene_id) if item.scene_id else None,
                scene_title=scenes.get(item.scene_id).title if item.scene_id in scenes else None,
                question_id=str(item.question_id) if item.question_id else None,
                question_prompt=questions.get(item.question_id).prompt
                if item.question_id in questions
                else None,
                reaction=item.reaction,
                anchor_text=item.anchor_text,
                body=item.body,
                author_status=author_metadata["author_status"],
                author_task_id=author_metadata["author_task_id"],
                author_updated_at=author_metadata["author_updated_at"],
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return serialized_items


async def list_chapter_beta_feedback(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    current_user: User,
    collaborator: BookCollaborator | None,
) -> list[ChapterBetaFeedbackOut]:
    query = (
        select(BetaReadFeedbackItem, BetaReadAssignment)
        .join(BetaReadAssignment, BetaReadAssignment.id == BetaReadFeedbackItem.assignment_id)
        .where(
            BetaReadFeedbackItem.book_id == book_id,
            BetaReadFeedbackItem.kind == BetaReadFeedbackKind.CHAPTER_COMMENT.value,
            BetaReadFeedbackItem.chapter_number == chapter_number,
        )
        .order_by(BetaReadFeedbackItem.created_at.asc())
    )
    rows = (await db.execute(query)).all()
    if not rows:
        return []

    reader_ids = {
        assignment.reader_user_id
        for _item, assignment in rows
        if assignment.reader_user_id is not None
    }
    collaborator_ids = {
        assignment.collaborator_id
        for _item, assignment in rows
        if assignment.collaborator_id is not None
    }
    readers = (
        (await db.execute(select(User).where(User.id.in_(list(reader_ids))))).scalars().all()
        if reader_ids
        else []
    )
    collaborators = (
        (
            await db.execute(
                select(BookCollaborator).where(BookCollaborator.id.in_(list(collaborator_ids)))
            )
        )
        .scalars()
        .all()
        if collaborator_ids
        else []
    )
    readers_by_id = {reader.id: reader for reader in readers}
    collaborators_by_id = {entry.id: entry for entry in collaborators}

    payload: list[ChapterBetaFeedbackOut] = []
    for item, assignment in rows:
        author_metadata = beta_feedback_item_author_metadata(item)
        reader = (
            readers_by_id.get(assignment.reader_user_id)
            if assignment.reader_user_id is not None
            else None
        )
        collaborator_row = (
            collaborators_by_id.get(assignment.collaborator_id)
            if assignment.collaborator_id is not None
            else None
        )
        payload.append(
            ChapterBetaFeedbackOut(
                id=str(item.id),
                assignment_id=str(assignment.id),
                collaborator_id=str(assignment.collaborator_id)
                if assignment.collaborator_id
                else None,
                reader_user_id=str(assignment.reader_user_id)
                if assignment.reader_user_id
                else None,
                reader_email=assignment.reader_email,
                reader_display_name=_beta_feedback_reader_display_name(
                    assignment=assignment,
                    reader=reader,
                    collaborator=collaborator_row,
                ),
                task_label=assignment.task_label,
                kind=item.kind,
                chapter_number=item.chapter_number,
                anchor_text=item.anchor_text,
                body=item.body,
                author_status=author_metadata["author_status"],
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return payload
