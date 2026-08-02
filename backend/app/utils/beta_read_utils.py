from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.beta_read import (
    BetaReadAssignment,
    BetaReadAssignmentState,
    BetaReadFeedbackItem,
    BetaReadFeedbackKind,
    BetaReadQuestion,
    BetaReadScopeKind,
)
from app.models.book import Book, Chapter
from app.models.intelligence import Notification
from app.models.user import User
from app.schemas.beta_reads import (
    BetaReadAssignmentCreateBody,
    BetaReadFeedbackItemCreateBody,
)
from app.utils.beta_read_access_utils import (
    _upsert_beta_read_collaborator,
)
from app.utils.beta_read_activity_utils import _beta_feedback_reader_display_name
from app.utils.beta_read_feedback_utils import (
    _clean_optional_feedback_text,
    _resolve_feedback_question,
    _resolve_feedback_scene,
    list_beta_read_questions,
)
from app.utils.beta_read_lifecycle_utils import (
    expire_beta_assignment_if_due,
    sync_beta_assignment_progress,
)
from app.utils.beta_read_policy_utils import (
    ACTIVE_READER_STATES,
    AUTHOR_FEEDBACK_ITEM_STATUSES,
    FEEDBACK_KINDS,
    NEUTRAL_RATING_MIN,
    PENALTY_STATUS_NONE,
    PENALTY_STATUS_PENALTY_REQUIRED,
    PENALTY_STATUS_STRONG_WARNING,
    PENALTY_STATUS_WARNING,
    POSITIVE_RATING_MIN,
    RATED_ASSIGNMENT_STATES,
    TERMINAL_STATES,
    VALID_STATE_TRANSITIONS,
    apply_beta_submission_snapshot,
    apply_missed_beta_read_penalty,
    assert_valid_beta_transition,
    assignment_scope_bounds,
    beta_feedback_item_author_metadata,
    beta_primary_action,
    beta_read_rating_sentiment,
    beta_submission_snapshot,
    ensure_timezone,
    normalize_author_feedback_item_status,
    normalize_beta_read_questions,
    normalize_beta_read_rating,
    normalize_feedback_kind,
    penalty_warning_for_user,
    reset_missed_beta_read_penalty,
    set_beta_assignment_state,
    utc_now,
    validate_beta_read_scope,
    validate_beta_read_window,
)
from app.utils.beta_read_progress_utils import (
    _assignment_progress_snapshot,
    _read_set_from_progress,
    _requirements_met,
)
from app.utils.books.collaboration import (
    normalize_collaboration_email,
)


async def book_beta_rating_summary(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[str, Any]:
    rating_values = (
        (
            await db.execute(
                select(BetaReadAssignment.final_rating).where(
                    BetaReadAssignment.book_id == book_id,
                    BetaReadAssignment.state.in_(list(RATED_ASSIGNMENT_STATES)),
                    BetaReadAssignment.final_rating.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    ratings = [float(value) for value in rating_values if value is not None]
    if not ratings:
        return {
            "average_rating": None,
            "rating_count": 0,
            "positive_rating_count": 0,
            "neutral_rating_count": 0,
            "negative_rating_count": 0,
        }
    positive = sum(1 for rating in ratings if beta_read_rating_sentiment(rating) == "positive")
    neutral = sum(1 for rating in ratings if beta_read_rating_sentiment(rating) == "neutral")
    negative = sum(1 for rating in ratings if beta_read_rating_sentiment(rating) == "negative")
    return {
        "average_rating": round(sum(ratings) / len(ratings), 2),
        "rating_count": len(ratings),
        "positive_rating_count": positive,
        "neutral_rating_count": neutral,
        "negative_rating_count": negative,
    }


async def create_beta_read_assignment(
    db: AsyncSession,
    *,
    book: Book,
    current_user: User,
    body: BetaReadAssignmentCreateBody,
) -> BetaReadAssignment:
    now = utc_now()
    window_days = validate_beta_read_window(body.window_days)
    starts_at = ensure_timezone(body.starts_at, default=now)
    scope_kind, chapter_start, chapter_end, section_label = validate_beta_read_scope(
        book,
        scope_kind=body.scope_kind,
        chapter_start=body.chapter_start,
        chapter_end=body.chapter_end,
        section_label=body.section_label,
    )
    reader_email = normalize_collaboration_email(body.reader_email)
    existing = (
        await db.execute(
            select(BetaReadAssignment.id).where(
                BetaReadAssignment.book_id == book.id,
                BetaReadAssignment.reader_email == reader_email,
                BetaReadAssignment.state.not_in(
                    list(TERMINAL_STATES | {BetaReadAssignmentState.EXPIRED.value})
                ),
            )
        )
    ).first()
    if existing:
        raise HTTPException(409, "This reader already has an active beta read for this book.")

    task_label = " ".join(body.task_label.split()).strip()
    if not task_label:
        raise HTTPException(400, "task_label is required.")
    author_questions = normalize_beta_read_questions(body.author_questions)

    reader_user = (
        await db.execute(select(User).where(User.email == reader_email))
    ).scalar_one_or_none()
    if reader_user is not None and settings.BETA_READ_PENALTY_ENABLED:
        penalty_type = str(settings.BETA_READ_PENALTY_TYPE or "warning").strip().lower()
        if (
            penalty_type == "temporary_beta_read_ban"
            and reader_user.beta_read_penalty_status == PENALTY_STATUS_PENALTY_REQUIRED
        ):
            raise HTTPException(409, "This reader is temporarily restricted from new beta reads.")

    collaborator = await _upsert_beta_read_collaborator(
        db,
        book=book,
        reader_email=reader_email,
        reader_user=reader_user,
        scope_kind=scope_kind,
        chapter_start=chapter_start,
        chapter_end=chapter_end,
    )
    assignment = BetaReadAssignment(
        book_id=book.id,
        author_user_id=current_user.id,
        reader_user_id=reader_user.id if reader_user else None,
        collaborator_id=collaborator.id,
        reader_email=reader_email,
        state=BetaReadAssignmentState.ACTIVE.value,
        scope_kind=scope_kind,
        task_label=task_label,
        section_label=section_label,
        chapter_start=chapter_start,
        chapter_end=chapter_end,
        window_days=window_days,
        required_progress_pct=int(body.required_progress_pct),
        required_comment_count=int(body.required_comment_count),
        required_feedback_item_count=int(body.required_feedback_item_count),
        require_final_feedback=bool(body.require_final_feedback),
        starts_at=starts_at,
        expires_at=starts_at + timedelta(days=window_days),
        access_granted_at=now,
        state_changed_at=now,
    )
    db.add(assignment)
    await db.flush()
    for prompt in author_questions:
        db.add(
            BetaReadQuestion(
                assignment_id=assignment.id,
                book_id=book.id,
                author_user_id=current_user.id,
                prompt=prompt,
            )
        )
    if reader_user is not None:
        db.add(
            Notification(
                user_id=reader_user.id,
                book_id=book.id,
                kind="beta_read_assigned",
                title=f"You were assigned a beta read for {book.title}",
                body="Complete before the deadline to finish this beta read cleanly.",
                data={
                    "assignment_id": str(assignment.id),
                    "book_id": str(book.id),
                    "book_title": book.title,
                    "task_label": assignment.task_label,
                    "question_count": len(author_questions),
                    "starts_at": assignment.starts_at.isoformat(),
                    "expires_at": assignment.expires_at.isoformat(),
                },
            )
        )
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def append_beta_read_questions(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    questions: list[str],
) -> list[BetaReadQuestion]:
    if assignment.state in TERMINAL_STATES | {BetaReadAssignmentState.EXPIRED.value}:
        raise HTTPException(409, "Questions can only be added to active beta reads.")
    existing_questions = await list_beta_read_questions(db, assignment_id=assignment.id)
    existing_keys = {question.prompt.lower() for question in existing_questions}
    cleaned = normalize_beta_read_questions(questions)
    new_questions: list[BetaReadQuestion] = []
    for prompt in cleaned:
        if prompt.lower() in existing_keys:
            continue
        question = BetaReadQuestion(
            assignment_id=assignment.id,
            book_id=assignment.book_id,
            author_user_id=assignment.author_user_id,
            prompt=prompt,
        )
        db.add(question)
        new_questions.append(question)
        existing_keys.add(prompt.lower())
    await db.commit()
    return await list_beta_read_questions(db, assignment_id=assignment.id)


async def add_beta_read_feedback_item(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User,
    body: BetaReadFeedbackItemCreateBody,
) -> BetaReadFeedbackItem:
    now = utc_now()
    if await expire_beta_assignment_if_due(db, assignment=assignment, now=now):
        await db.commit()
        raise HTTPException(409, "This beta read has expired.")
    if ensure_timezone(assignment.starts_at) > now:
        raise HTTPException(400, "This beta read has not started yet.")
    if assignment.state not in ACTIVE_READER_STATES:
        raise HTTPException(409, "Feedback can only be added to an active beta read.")

    kind = normalize_feedback_kind(body.kind)
    cleaned_body = _clean_optional_feedback_text(body.body, max_length=10000)
    anchor_text = _clean_optional_feedback_text(body.anchor_text, max_length=500)
    reaction = _clean_optional_feedback_text(body.reaction, max_length=64)
    scene = await _resolve_feedback_scene(db, assignment=assignment, scene_id=body.scene_id)
    question = await _resolve_feedback_question(
        db, assignment=assignment, question_id=body.question_id
    )

    book = await db.get(Book, assignment.book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    start, end = assignment_scope_bounds(assignment, int(book.total_chapters or 0))
    chapter_number = body.chapter_number
    if scene is not None and scene.chapter_number is not None:
        chapter_number = int(scene.chapter_number)
    if chapter_number is not None and not start <= int(chapter_number) <= end:
        raise HTTPException(403, "That chapter is outside this beta read scope.")

    if kind == BetaReadFeedbackKind.ANSWER.value:
        if question is None or not cleaned_body:
            raise HTTPException(400, "Question answers require a question_id and body.")
    elif kind == BetaReadFeedbackKind.CHAPTER_COMMENT.value:
        if chapter_number is None or not cleaned_body:
            raise HTTPException(400, "Chapter comments require a chapter_number and body.")
    elif kind == BetaReadFeedbackKind.SCENE_REACTION.value:
        if scene is None and chapter_number is None:
            raise HTTPException(400, "Scene reactions require a scene_id or chapter_number.")
        if not reaction and not cleaned_body:
            raise HTTPException(400, "Scene reactions require a reaction or body.")
    else:
        if chapter_number is None and scene is None:
            raise HTTPException(400, "Marked moments must reference a chapter or scene.")
        if not anchor_text and not cleaned_body:
            raise HTTPException(400, "Marked moments require anchor_text or body.")

    item = BetaReadFeedbackItem(
        assignment_id=assignment.id,
        book_id=assignment.book_id,
        author_user_id=assignment.author_user_id,
        reader_user_id=current_user.id,
        question_id=question.id if question else None,
        scene_id=scene.id if scene else None,
        kind=kind,
        chapter_number=int(chapter_number) if chapter_number is not None else None,
        reaction=reaction.lower().replace(" ", "_") if reaction else None,
        anchor_text=anchor_text,
        body=cleaned_body,
        metadata_json={},
    )
    db.add(item)
    await db.flush()
    await sync_beta_assignment_progress(db, assignment=assignment, now=now)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_beta_read_feedback_item(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    feedback_item_id: uuid.UUID,
    current_user: User,
) -> None:
    if assignment.state not in ACTIVE_READER_STATES:
        raise HTTPException(409, "Feedback can only be edited on an active beta read.")
    item = (
        await db.execute(
            select(BetaReadFeedbackItem).where(
                BetaReadFeedbackItem.id == feedback_item_id,
                BetaReadFeedbackItem.assignment_id == assignment.id,
                BetaReadFeedbackItem.reader_user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Beta-read feedback item not found.")
    await db.delete(item)
    await sync_beta_assignment_progress(db, assignment=assignment, now=utc_now())
    await db.commit()


async def update_beta_read_feedback_item_author_state(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    feedback_item_id: uuid.UUID,
    author_status: str,
    author_task_id: str | None,
) -> BetaReadFeedbackItem:
    item = (
        await db.execute(
            select(BetaReadFeedbackItem).where(
                BetaReadFeedbackItem.id == feedback_item_id,
                BetaReadFeedbackItem.assignment_id == assignment.id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(404, "Beta-read feedback item not found.")

    metadata = dict(item.metadata_json or {})
    normalized_status = normalize_author_feedback_item_status(author_status)
    cleaned_task_id = str(author_task_id).strip() if author_task_id is not None else ""
    metadata["author_status"] = normalized_status
    metadata["author_updated_at"] = utc_now().isoformat()
    if normalized_status == "task_created":
        if not cleaned_task_id:
            raise HTTPException(
                400, "author_task_id is required when marking feedback as task_created."
            )
        metadata["author_task_id"] = cleaned_task_id
    else:
        metadata["author_task_id"] = cleaned_task_id or None
    item.metadata_json = metadata
    await db.commit()
    await db.refresh(item)
    return item
