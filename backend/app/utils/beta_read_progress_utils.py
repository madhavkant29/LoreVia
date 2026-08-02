from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_read import (
    BetaReadAssignment,
    BetaReadFeedbackItem,
    BetaReadFeedbackKind,
    BetaReadQuestion,
    BetaReadScopeKind,
)
from app.models.book import Book, BookNote
from app.models.progress import ReadingProgress
from app.utils.beta_read_policy_utils import assignment_scope_bounds


def _read_set_from_progress(progress: ReadingProgress | None) -> set[int]:
    if progress is None:
        return set()
    chapters = set(progress.chapters_read or [])
    if chapters:
        return chapters
    current_chapter = int(progress.current_chapter or 0)
    if current_chapter > 0:
        return set(range(1, current_chapter + 1))
    return set()


async def _assignment_progress_snapshot(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    progress: ReadingProgress | None = None,
) -> dict[str, Any]:
    book = await db.get(Book, assignment.book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    if progress is None and assignment.reader_user_id is not None:
        progress = (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.book_id == assignment.book_id,
                    ReadingProgress.user_id == assignment.reader_user_id,
                )
            )
        ).scalar_one_or_none()
    start, end = assignment_scope_bounds(assignment, int(book.total_chapters or 0))
    total = max(end - start + 1, 1)
    read_set = _read_set_from_progress(progress)
    read_count = len([chapter for chapter in read_set if start <= chapter <= end])
    progress_pct = round((read_count / total) * 100, 1) if total else 0.0
    question_count = int(
        (
            await db.execute(
                select(func.count(BetaReadQuestion.id)).where(
                    BetaReadQuestion.assignment_id == assignment.id
                )
            )
        ).scalar_one()
        or 0
    )
    feedback_item_count = int(
        (
            await db.execute(
                select(func.count(BetaReadFeedbackItem.id)).where(
                    BetaReadFeedbackItem.assignment_id == assignment.id,
                )
            )
        ).scalar_one()
        or 0
    )
    answer_count = int(
        (
            await db.execute(
                select(func.count(BetaReadFeedbackItem.id)).where(
                    BetaReadFeedbackItem.assignment_id == assignment.id,
                    BetaReadFeedbackItem.kind == BetaReadFeedbackKind.ANSWER.value,
                )
            )
        ).scalar_one()
        or 0
    )
    if assignment.reader_user_id is not None:
        note_query = select(func.count(BookNote.id)).where(
            BookNote.book_id == assignment.book_id,
            BookNote.user_id == assignment.reader_user_id,
        )
        if assignment.scope_kind != BetaReadScopeKind.FULL_BOOK.value:
            note_query = note_query.where(
                or_(
                    BookNote.chapter_number.is_(None),
                    and_(BookNote.chapter_number >= start, BookNote.chapter_number <= end),
                )
            )
        note_comment_count = int((await db.execute(note_query)).scalar_one() or 0)
        feedback_scope_clause = []
        if assignment.scope_kind != BetaReadScopeKind.FULL_BOOK.value:
            feedback_scope_clause.append(
                or_(
                    BetaReadFeedbackItem.chapter_number.is_(None),
                    and_(
                        BetaReadFeedbackItem.chapter_number >= start,
                        BetaReadFeedbackItem.chapter_number <= end,
                    ),
                )
            )
        chapter_comment_count = int(
            (
                await db.execute(
                    select(func.count(BetaReadFeedbackItem.id)).where(
                        BetaReadFeedbackItem.assignment_id == assignment.id,
                        BetaReadFeedbackItem.kind == BetaReadFeedbackKind.CHAPTER_COMMENT.value,
                        *feedback_scope_clause,
                    )
                )
            ).scalar_one()
            or 0
        )
        comment_count = note_comment_count + chapter_comment_count
    else:
        comment_count = 0
    current_chapter = int(progress.current_chapter or start) if progress is not None else start
    return {
        "book": book,
        "chapters_total": total,
        "chapters_read_count": read_count,
        "progress_pct": progress_pct,
        "comment_count": comment_count,
        "feedback_item_count": feedback_item_count,
        "answer_count": answer_count,
        "question_count": question_count,
        "current_chapter": max(start, current_chapter),
        "chapter_start": start,
        "chapter_end": end,
    }


def _requirements_met(assignment: BetaReadAssignment, snapshot: dict[str, Any]) -> bool:
    if float(snapshot["progress_pct"]) < float(assignment.required_progress_pct):
        return False
    if int(snapshot["comment_count"]) < int(assignment.required_comment_count):
        return False
    if int(snapshot["feedback_item_count"]) < int(assignment.required_feedback_item_count):
        return False
    return True


def _assignment_progress_snapshot_from_context(
    assignment: BetaReadAssignment,
    *,
    book: Book,
    progress: ReadingProgress | None,
    question_count: int,
    feedback_item_count: int,
    answer_count: int,
    note_comment_count: int,
    chapter_comment_count: int,
) -> dict[str, Any]:
    start, end = assignment_scope_bounds(assignment, int(book.total_chapters or 0))
    total = max(end - start + 1, 1)
    read_set = _read_set_from_progress(progress)
    read_count = len([chapter for chapter in read_set if start <= chapter <= end])
    progress_pct = round((read_count / total) * 100, 1) if total else 0.0
    comment_count = int(note_comment_count) + int(chapter_comment_count)
    current_chapter = int(progress.current_chapter or start) if progress is not None else start
    return {
        "book": book,
        "chapters_total": total,
        "chapters_read_count": read_count,
        "progress_pct": progress_pct,
        "comment_count": comment_count,
        "feedback_item_count": int(feedback_item_count),
        "answer_count": int(answer_count),
        "question_count": int(question_count),
        "current_chapter": max(start, current_chapter),
        "chapter_start": start,
        "chapter_end": end,
    }
