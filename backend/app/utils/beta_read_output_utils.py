from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_read import (
    BetaReadAssignment,
    BetaReadAssignmentState,
    BetaReadFeedbackItem,
    BetaReadFeedbackKind,
    BetaReadQuestion,
    BetaReadScopeKind,
)
from app.models.book import Book, BookNote
from app.models.progress import ReadingProgress
from app.models.user import User
from app.schemas.beta_reads import BetaReadAssignmentOut
from app.utils.beta_read_policy_utils import (
    PENALTY_STATUS_NONE,
    RATED_ASSIGNMENT_STATES,
    BetaAssignmentRenderContext,
    assignment_scope_bounds,
    beta_primary_action,
    beta_read_rating_sentiment,
    beta_status_label,
    beta_view_bucket,
    penalty_warning_for_user,
    submission_is_late,
    utc_now,
)
from app.utils.beta_read_progress_utils import (
    _assignment_progress_snapshot_from_context,
    _requirements_met,
)


async def load_beta_assignment_render_context(
    db: AsyncSession,
    *,
    assignments: Sequence[BetaReadAssignment],
) -> BetaAssignmentRenderContext:
    assignment_list = list(assignments)
    if not assignment_list:
        return BetaAssignmentRenderContext(
            books_by_id={},
            readers_by_id={},
            progress_by_pair={},
            rating_summary_by_book_id={},
            question_count_by_assignment_id={},
            feedback_count_by_assignment_id={},
            answer_count_by_assignment_id={},
            note_comment_count_by_assignment_id={},
            chapter_comment_count_by_assignment_id={},
        )

    assignment_ids = [assignment.id for assignment in assignment_list]
    book_ids = list({assignment.book_id for assignment in assignment_list})
    reader_ids = list(
        {
            assignment.reader_user_id
            for assignment in assignment_list
            if assignment.reader_user_id is not None
        }
    )

    books = (
        (await db.execute(select(Book).where(Book.id.in_(book_ids)))).scalars().all()
        if book_ids
        else []
    )
    readers = (
        (await db.execute(select(User).where(User.id.in_(reader_ids)))).scalars().all()
        if reader_ids
        else []
    )
    progress_rows = (
        (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.book_id.in_(book_ids),
                    ReadingProgress.user_id.in_(reader_ids),
                )
            )
        )
        .scalars()
        .all()
        if book_ids and reader_ids
        else []
    )
    rating_rows = (
        (
            await db.execute(
                select(BetaReadAssignment.book_id, BetaReadAssignment.final_rating).where(
                    BetaReadAssignment.book_id.in_(book_ids),
                    BetaReadAssignment.state.in_(list(RATED_ASSIGNMENT_STATES)),
                    BetaReadAssignment.final_rating.is_not(None),
                )
            )
        ).all()
        if book_ids
        else []
    )
    question_count_rows = (
        await db.execute(
            select(BetaReadQuestion.assignment_id, func.count(BetaReadQuestion.id))
            .where(BetaReadQuestion.assignment_id.in_(assignment_ids))
            .group_by(BetaReadQuestion.assignment_id)
        )
    ).all()
    feedback_count_rows = (
        await db.execute(
            select(BetaReadFeedbackItem.assignment_id, func.count(BetaReadFeedbackItem.id))
            .where(BetaReadFeedbackItem.assignment_id.in_(assignment_ids))
            .group_by(BetaReadFeedbackItem.assignment_id)
        )
    ).all()
    answer_count_rows = (
        await db.execute(
            select(BetaReadFeedbackItem.assignment_id, func.count(BetaReadFeedbackItem.id))
            .where(
                BetaReadFeedbackItem.assignment_id.in_(assignment_ids),
                BetaReadFeedbackItem.kind == BetaReadFeedbackKind.ANSWER.value,
            )
            .group_by(BetaReadFeedbackItem.assignment_id)
        )
    ).all()
    note_rows = (
        (
            await db.execute(
                select(BookNote.book_id, BookNote.user_id, BookNote.chapter_number).where(
                    BookNote.book_id.in_(book_ids),
                    BookNote.user_id.in_(reader_ids),
                )
            )
        ).all()
        if book_ids and reader_ids
        else []
    )
    chapter_comment_rows = (
        await db.execute(
            select(
                BetaReadFeedbackItem.assignment_id,
                BetaReadFeedbackItem.chapter_number,
            ).where(
                BetaReadFeedbackItem.assignment_id.in_(assignment_ids),
                BetaReadFeedbackItem.kind == BetaReadFeedbackKind.CHAPTER_COMMENT.value,
            )
        )
    ).all()

    ratings_by_book_id: dict[uuid.UUID, list[float]] = {}
    for book_id, final_rating in rating_rows:
        if final_rating is None:
            continue
        ratings_by_book_id.setdefault(book_id, []).append(float(final_rating))
    rating_summary_by_book_id = {
        book_id: {
            "average_rating": round(sum(ratings) / len(ratings), 2),
            "rating_count": len(ratings),
            "positive_rating_count": sum(
                1 for rating in ratings if beta_read_rating_sentiment(rating) == "positive"
            ),
            "neutral_rating_count": sum(
                1 for rating in ratings if beta_read_rating_sentiment(rating) == "neutral"
            ),
            "negative_rating_count": sum(
                1 for rating in ratings if beta_read_rating_sentiment(rating) == "negative"
            ),
        }
        for book_id, ratings in ratings_by_book_id.items()
    }
    note_rows_by_pair: dict[tuple[uuid.UUID, uuid.UUID], list[int | None]] = {}
    for book_id, user_id, chapter_number in note_rows:
        note_rows_by_pair.setdefault((book_id, user_id), []).append(chapter_number)

    chapter_comment_count_by_assignment_id: dict[uuid.UUID, int] = {}
    chapter_comment_rows_by_assignment_id: dict[uuid.UUID, list[int | None]] = {}
    for assignment_id, chapter_number in chapter_comment_rows:
        chapter_comment_rows_by_assignment_id.setdefault(assignment_id, []).append(chapter_number)

    books_by_id = {book.id: book for book in books}
    note_comment_count_by_assignment_id: dict[uuid.UUID, int] = {}
    for assignment in assignment_list:
        if assignment.reader_user_id is None:
            note_comment_count_by_assignment_id[assignment.id] = 0
            chapter_comment_count_by_assignment_id[assignment.id] = 0
            continue
        book = books_by_id.get(assignment.book_id)
        start, end = assignment_scope_bounds(
            assignment, int((book.total_chapters if book is not None else 0) or 0)
        )
        note_comment_count = 0
        for chapter_number in note_rows_by_pair.get(
            (assignment.book_id, assignment.reader_user_id), []
        ):
            if assignment.scope_kind == BetaReadScopeKind.FULL_BOOK.value:
                note_comment_count += 1
            elif chapter_number is None or start <= int(chapter_number) <= end:
                note_comment_count += 1
        note_comment_count_by_assignment_id[assignment.id] = note_comment_count

        comment_count = 0
        for chapter_number in chapter_comment_rows_by_assignment_id.get(assignment.id, []):
            if assignment.scope_kind == BetaReadScopeKind.FULL_BOOK.value:
                comment_count += 1
            elif chapter_number is None or start <= int(chapter_number) <= end:
                comment_count += 1
        chapter_comment_count_by_assignment_id[assignment.id] = comment_count

    return BetaAssignmentRenderContext(
        books_by_id=books_by_id,
        readers_by_id={reader.id: reader for reader in readers},
        progress_by_pair={
            (progress.book_id, progress.user_id): progress for progress in progress_rows
        },
        rating_summary_by_book_id=rating_summary_by_book_id,
        question_count_by_assignment_id={
            assignment_id: int(count or 0) for assignment_id, count in question_count_rows
        },
        feedback_count_by_assignment_id={
            assignment_id: int(count or 0) for assignment_id, count in feedback_count_rows
        },
        answer_count_by_assignment_id={
            assignment_id: int(count or 0) for assignment_id, count in answer_count_rows
        },
        note_comment_count_by_assignment_id=note_comment_count_by_assignment_id,
        chapter_comment_count_by_assignment_id=chapter_comment_count_by_assignment_id,
    )


def _build_beta_read_assignment_out_from_context(
    assignment: BetaReadAssignment,
    *,
    context: BetaAssignmentRenderContext,
    current_user: User | None = None,
    reader_user: User | None = None,
) -> BetaReadAssignmentOut:
    now = utc_now()
    book = context.books_by_id.get(assignment.book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    rating_summary = context.rating_summary_by_book_id.get(
        assignment.book_id,
        {
            "average_rating": None,
            "rating_count": 0,
            "positive_rating_count": 0,
            "neutral_rating_count": 0,
            "negative_rating_count": 0,
        },
    )
    resolved_reader = reader_user
    if resolved_reader is None and assignment.reader_user_id is not None:
        resolved_reader = context.readers_by_id.get(assignment.reader_user_id)
    progress = (
        context.progress_by_pair.get((assignment.book_id, assignment.reader_user_id))
        if assignment.reader_user_id is not None
        else None
    )
    snapshot = _assignment_progress_snapshot_from_context(
        assignment,
        book=book,
        progress=progress,
        question_count=context.question_count_by_assignment_id.get(assignment.id, 0),
        feedback_item_count=context.feedback_count_by_assignment_id.get(assignment.id, 0),
        answer_count=context.answer_count_by_assignment_id.get(assignment.id, 0),
        note_comment_count=context.note_comment_count_by_assignment_id.get(assignment.id, 0),
        chapter_comment_count=context.chapter_comment_count_by_assignment_id.get(assignment.id, 0),
    )
    requirements_met = _requirements_met(assignment, snapshot)
    effective_user = resolved_reader or current_user
    consecutive_missed = (
        int(effective_user.consecutive_missed_beta_reads or 0) if effective_user is not None else 0
    )
    penalty_status = (
        str(effective_user.beta_read_penalty_status or PENALTY_STATUS_NONE)
        if effective_user is not None
        else PENALTY_STATUS_NONE
    )
    bucket = beta_view_bucket(assignment, now=now)
    primary_action = beta_primary_action(assignment, now=now)
    if assignment.state == BetaReadAssignmentState.READY_TO_SUBMIT.value and not requirements_met:
        primary_action = "Continue"
    return BetaReadAssignmentOut(
        id=str(assignment.id),
        book_id=str(assignment.book_id),
        author_user_id=str(assignment.author_user_id),
        reader_user_id=str(assignment.reader_user_id) if assignment.reader_user_id else None,
        reader_email=assignment.reader_email,
        collaborator_id=str(assignment.collaborator_id) if assignment.collaborator_id else None,
        state=assignment.state,
        view_bucket=bucket,
        task_label=assignment.task_label,
        scope_kind=assignment.scope_kind,
        section_label=assignment.section_label,
        chapter_start=assignment.chapter_start,
        chapter_end=assignment.chapter_end,
        window_days=assignment.window_days,
        required_progress_pct=assignment.required_progress_pct,
        required_comment_count=assignment.required_comment_count,
        required_feedback_item_count=assignment.required_feedback_item_count,
        require_final_feedback=assignment.require_final_feedback,
        starts_at=assignment.starts_at,
        expires_at=assignment.expires_at,
        access_granted_at=assignment.access_granted_at,
        submitted_at=assignment.submitted_at,
        completed_at=assignment.completed_at,
        first_opened_at=assignment.first_opened_at,
        missed_reason=assignment.missed_reason,
        counted_toward_missed_streak=assignment.counted_toward_missed_streak,
        revoked_at=assignment.revoked_at,
        revoked_reason=assignment.revoked_reason,
        disqualified_at=assignment.disqualified_at,
        disqualified_reason=assignment.disqualified_reason,
        book_title=book.title,
        author_name=book.author or "Unknown author",
        book_route_title=book.title,
        progress_pct=float(snapshot["progress_pct"]),
        chapters_total=int(snapshot["chapters_total"]),
        chapters_read_count=int(snapshot["chapters_read_count"]),
        comment_count=int(snapshot["comment_count"]),
        feedback_item_count=int(snapshot["feedback_item_count"]),
        question_count=int(snapshot["question_count"]),
        answered_question_count=int(snapshot["answer_count"]),
        current_chapter=int(snapshot["current_chapter"]),
        status_label=beta_status_label(assignment, now=now),
        primary_action=primary_action,
        submission_allowed=(
            assignment.state == BetaReadAssignmentState.READY_TO_SUBMIT.value
            and requirements_met
            and not submission_is_late(assignment, now)
        ),
        is_overdue=submission_is_late(assignment, now),
        consecutive_missed_beta_reads=consecutive_missed,
        penalty_status=penalty_status,
        penalty_warning=penalty_warning_for_user(effective_user)
        if effective_user is not None
        else None,
        final_rating=float(assignment.final_rating)
        if assignment.final_rating is not None
        else None,
        rating_sentiment=beta_read_rating_sentiment(float(assignment.final_rating))
        if assignment.final_rating is not None
        else None,
        book_average_rating=rating_summary["average_rating"],
        book_rating_count=rating_summary["rating_count"],
    )
