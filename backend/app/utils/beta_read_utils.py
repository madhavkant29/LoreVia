from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.beta_read import (
    BetaReadAssignment,
    BetaReadFeedbackItem,
    BetaReadFeedbackKind,
    BetaReadAssignmentState,
    BetaReadQuestion,
    BetaReadScopeKind,
)
from app.models.book import Book, BookCollaborator, NovelScene
from app.models.intelligence import Notification
from app.models.progress import ReadingProgress
from app.models.user import User
from app.schemas.beta_reads import (
    BetaReadAssignmentCreateBody,
    BetaReadAssignmentDetailOut,
    BetaReadAssignmentOut,
    BetaReadFeedbackItemCreateBody,
    BetaReadFeedbackItemOut,
    BetaReadFeedbackSummaryOut,
    BetaReadJobRunOut,
    BetaReadQuestionOut,
)
from app.utils.book_utils import (
    apply_collaboration_permissions,
    apply_collaboration_scope,
    normalize_collaboration_email,
    normalize_collaboration_permissions,
    normalize_collaboration_scope,
)
from app.services.monetization_service import grant_points, grant_review_feedback_points
from app.utils.monetization_utils import POINT_SOURCE_BETA_READ_AUTHOR_REWARD

ACTIVE_READER_STATES = {
    BetaReadAssignmentState.ACTIVE.value,
    BetaReadAssignmentState.IN_PROGRESS.value,
    BetaReadAssignmentState.READY_TO_SUBMIT.value,
}
READER_VISIBLE_STATES = ACTIVE_READER_STATES | {
    BetaReadAssignmentState.SUBMITTED.value,
    BetaReadAssignmentState.COMPLETED.value,
    BetaReadAssignmentState.EXPIRED.value,
    BetaReadAssignmentState.MISSED.value,
    BetaReadAssignmentState.REVOKED.value,
    BetaReadAssignmentState.DISQUALIFIED.value,
}
TERMINAL_STATES = {
    BetaReadAssignmentState.COMPLETED.value,
    BetaReadAssignmentState.MISSED.value,
    BetaReadAssignmentState.REVOKED.value,
    BetaReadAssignmentState.DISQUALIFIED.value,
}
VALID_STATE_TRANSITIONS = {
    BetaReadAssignmentState.ACTIVE.value: {
        BetaReadAssignmentState.IN_PROGRESS.value,
        BetaReadAssignmentState.EXPIRED.value,
        BetaReadAssignmentState.REVOKED.value,
    },
    BetaReadAssignmentState.IN_PROGRESS.value: {
        BetaReadAssignmentState.READY_TO_SUBMIT.value,
        BetaReadAssignmentState.EXPIRED.value,
        BetaReadAssignmentState.REVOKED.value,
    },
    BetaReadAssignmentState.READY_TO_SUBMIT.value: {
        BetaReadAssignmentState.SUBMITTED.value,
        BetaReadAssignmentState.EXPIRED.value,
        BetaReadAssignmentState.REVOKED.value,
    },
    BetaReadAssignmentState.SUBMITTED.value: {
        BetaReadAssignmentState.COMPLETED.value,
        BetaReadAssignmentState.DISQUALIFIED.value,
    },
    BetaReadAssignmentState.EXPIRED.value: {
        BetaReadAssignmentState.MISSED.value,
    },
}
PENALTY_STATUS_NONE = "none"
PENALTY_STATUS_WARNING = "warning"
PENALTY_STATUS_STRONG_WARNING = "strong_warning"
PENALTY_STATUS_PENALTY_REQUIRED = "penalty_required"
POINT_SOURCE_BETA_READ = "beta_read_completed"
FEEDBACK_KINDS = {
    BetaReadFeedbackKind.CHAPTER_COMMENT.value,
    BetaReadFeedbackKind.SCENE_REACTION.value,
    BetaReadFeedbackKind.ANSWER.value,
    BetaReadFeedbackKind.CONFUSING.value,
    BetaReadFeedbackKind.BORING.value,
    BetaReadFeedbackKind.FAVORITE.value,
}
RATED_ASSIGNMENT_STATES = {
    BetaReadAssignmentState.SUBMITTED.value,
    BetaReadAssignmentState.COMPLETED.value,
}
POSITIVE_RATING_MIN = 4.0
NEUTRAL_RATING_MIN = 2.5


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_timezone(value: datetime | None, *, default: datetime | None = None) -> datetime:
    resolved = value or default or utc_now()
    return resolved if resolved.tzinfo else resolved.replace(tzinfo=UTC)


def validate_beta_read_window(window_days: int) -> int:
    if window_days < settings.BETA_READ_MIN_WINDOW_DAYS:
        raise HTTPException(
            400,
            f"Beta read window must be at least {settings.BETA_READ_MIN_WINDOW_DAYS} days.",
        )
    if window_days > settings.BETA_READ_MAX_WINDOW_DAYS:
        raise HTTPException(
            400,
            f"Beta read window must be at most {settings.BETA_READ_MAX_WINDOW_DAYS} days.",
        )
    return int(window_days)


def validate_beta_read_scope(
    book: Book,
    *,
    scope_kind: str,
    chapter_start: int | None,
    chapter_end: int | None,
    section_label: str | None,
) -> tuple[str, int | None, int | None, str | None]:
    normalized_kind = str(scope_kind or "").strip().lower() or BetaReadScopeKind.FULL_BOOK.value
    if normalized_kind not in {
        BetaReadScopeKind.FULL_BOOK.value,
        BetaReadScopeKind.CHAPTER_RANGE.value,
        BetaReadScopeKind.SECTION.value,
    }:
        raise HTTPException(400, "Invalid beta read scope.")

    total_chapters = int(book.total_chapters or 0)
    if normalized_kind == BetaReadScopeKind.FULL_BOOK.value:
        return normalized_kind, None, None, None

    if chapter_start is None or chapter_end is None:
        raise HTTPException(400, "chapter_start and chapter_end are required for chapter-range and section beta reads.")
    if chapter_start < 1 or chapter_end < 1 or chapter_end < chapter_start:
        raise HTTPException(400, "Invalid beta read chapter range.")
    if total_chapters and chapter_end > total_chapters:
        raise HTTPException(400, f"Chapter range cannot exceed the book's {total_chapters} chapters.")
    if normalized_kind == BetaReadScopeKind.SECTION.value:
        cleaned_section_label = " ".join(str(section_label or "").split()).strip()
        if not cleaned_section_label:
            raise HTTPException(400, "section_label is required when scope_kind is section.")
        return normalized_kind, int(chapter_start), int(chapter_end), cleaned_section_label
    return normalized_kind, int(chapter_start), int(chapter_end), None


def assignment_scope_bounds(assignment: BetaReadAssignment, total_chapters: int) -> tuple[int, int]:
    if assignment.scope_kind == BetaReadScopeKind.FULL_BOOK.value:
        if total_chapters <= 0:
            return 1, 1
        return 1, total_chapters
    start = int(assignment.chapter_start or 1)
    end = int(assignment.chapter_end or max(total_chapters, start))
    if total_chapters > 0:
        end = min(end, total_chapters)
    return start, max(start, end)


def normalize_beta_read_questions(questions: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in questions or []:
        prompt = " ".join(str(raw or "").split()).strip()
        if not prompt:
            continue
        if len(prompt) > 300:
            raise HTTPException(400, "Author questions must be 300 characters or fewer.")
        dedupe_key = prompt.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        cleaned.append(prompt)
    if len(cleaned) > 12:
        raise HTTPException(400, "Beta reads can include at most 12 author questions.")
    return cleaned


def normalize_feedback_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower().replace(" ", "_")
    if normalized not in FEEDBACK_KINDS:
        raise HTTPException(400, "Invalid beta-read feedback kind.")
    return normalized


def normalize_beta_read_rating(value: float | int | None) -> float:
    try:
        rating = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "final_rating must be a number between 1 and 5.") from exc
    if rating < 1 or rating > 5:
        raise HTTPException(400, "final_rating must be between 1 and 5.")
    scaled = rating * 2
    if abs(scaled - round(scaled)) > 1e-9:
        raise HTTPException(400, "final_rating must use 0.5 increments.")
    return round(scaled) / 2


def beta_read_rating_sentiment(rating: float | None) -> str | None:
    if rating is None:
        return None
    if rating >= POSITIVE_RATING_MIN:
        return "positive"
    if rating >= NEUTRAL_RATING_MIN:
        return "neutral"
    return "negative"


def beta_submission_snapshot(assignment: BetaReadAssignment) -> dict[str, Any]:
    snapshot = dict(assignment.submission_metadata or {})
    if assignment.submitted_progress_pct is not None:
        snapshot["progress_pct"] = float(assignment.submitted_progress_pct)
    if assignment.submitted_chapters_total is not None:
        snapshot["chapters_total"] = int(assignment.submitted_chapters_total)
    if assignment.submitted_chapters_read_count is not None:
        snapshot["chapters_read_count"] = int(assignment.submitted_chapters_read_count)
    if assignment.submitted_comment_count is not None:
        snapshot["comment_count"] = int(assignment.submitted_comment_count)
    if assignment.submitted_feedback_item_count is not None:
        snapshot["feedback_item_count"] = int(assignment.submitted_feedback_item_count)
    if assignment.submitted_answer_count is not None:
        snapshot["answer_count"] = int(assignment.submitted_answer_count)
    if assignment.final_rating is not None:
        snapshot["final_rating"] = float(assignment.final_rating)
    if assignment.submitted_rating_sentiment:
        snapshot["rating_sentiment"] = assignment.submitted_rating_sentiment
    if assignment.submitted_before_deadline is not None:
        snapshot["submitted_before_deadline"] = bool(assignment.submitted_before_deadline)
    snapshot["late_feedback"] = bool(assignment.late_feedback)
    return snapshot


def apply_beta_submission_snapshot(assignment: BetaReadAssignment, snapshot: dict[str, Any]) -> None:
    assignment.submission_metadata = dict(snapshot)
    assignment.submitted_progress_pct = float(snapshot["progress_pct"]) if snapshot.get("progress_pct") is not None else None
    assignment.submitted_chapters_total = int(snapshot["chapters_total"]) if snapshot.get("chapters_total") is not None else None
    assignment.submitted_chapters_read_count = int(snapshot["chapters_read_count"]) if snapshot.get("chapters_read_count") is not None else None
    assignment.submitted_comment_count = int(snapshot["comment_count"]) if snapshot.get("comment_count") is not None else None
    assignment.submitted_feedback_item_count = int(snapshot["feedback_item_count"]) if snapshot.get("feedback_item_count") is not None else None
    assignment.submitted_answer_count = int(snapshot["answer_count"]) if snapshot.get("answer_count") is not None else None
    assignment.submitted_rating_sentiment = (
        str(snapshot["rating_sentiment"]).strip() or None if snapshot.get("rating_sentiment") is not None else None
    )
    assignment.submitted_before_deadline = (
        bool(snapshot["submitted_before_deadline"]) if snapshot.get("submitted_before_deadline") is not None else None
    )
    assignment.late_feedback = bool(snapshot.get("late_feedback", False))


async def book_beta_rating_summary(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[str, Any]:
    rating_values = (
        await db.execute(
            select(BetaReadAssignment.final_rating).where(
                BetaReadAssignment.book_id == book_id,
                BetaReadAssignment.state.in_(list(RATED_ASSIGNMENT_STATES)),
                BetaReadAssignment.final_rating.is_not(None),
            )
        )
    ).scalars().all()
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


def beta_read_reward_multiplier(average_rating: float | None) -> float:
    if average_rating is None:
        return 1.0
    if average_rating >= 4.5:
        return 1.5
    if average_rating >= 4.0:
        return 1.3
    if average_rating >= 3.5:
        return 1.15
    return 1.0


def compute_beta_read_reward_points(base_points: int, average_rating: float | None) -> int:
    base = max(int(base_points or 0), 0)
    if base <= 0:
        return 0
    boosted = int(round(base * beta_read_reward_multiplier(average_rating)))
    return max(base, boosted)


def submission_is_late(assignment: BetaReadAssignment, now: datetime | None = None) -> bool:
    current = ensure_timezone(now)
    return current > ensure_timezone(assignment.expires_at)


def assert_valid_beta_transition(current_state: str, next_state: str) -> None:
    allowed = VALID_STATE_TRANSITIONS.get(current_state, set())
    if next_state not in allowed:
        raise HTTPException(409, f"Cannot transition beta read from {current_state} to {next_state}.")


def set_beta_assignment_state(
    assignment: BetaReadAssignment,
    next_state: str,
    *,
    now: datetime | None = None,
    missed_reason: str | None = None,
    revoked_reason: str | None = None,
    disqualified_reason: str | None = None,
) -> None:
    current = ensure_timezone(now)
    assert_valid_beta_transition(assignment.state, next_state)
    assignment.state = next_state
    assignment.state_changed_at = current
    if next_state == BetaReadAssignmentState.EXPIRED.value:
        assignment.missed_reason = "deadline_expired"
    if next_state == BetaReadAssignmentState.MISSED.value and missed_reason:
        assignment.missed_reason = missed_reason
    if next_state == BetaReadAssignmentState.REVOKED.value:
        assignment.revoked_at = current
        assignment.revoked_reason = revoked_reason or "revoked_by_author"
    if next_state == BetaReadAssignmentState.DISQUALIFIED.value:
        assignment.disqualified_at = current
        assignment.disqualified_reason = disqualified_reason or "submission_ineligible"
    if next_state == BetaReadAssignmentState.COMPLETED.value:
        assignment.completed_at = current


def beta_view_bucket(assignment: BetaReadAssignment, *, now: datetime | None = None) -> str:
    current = ensure_timezone(now)
    if assignment.state in ACTIVE_READER_STATES and ensure_timezone(assignment.expires_at) < current:
        return "missed"
    if assignment.state == BetaReadAssignmentState.COMPLETED.value:
        return "completed"
    if assignment.state in {
        BetaReadAssignmentState.MISSED.value,
        BetaReadAssignmentState.EXPIRED.value,
        BetaReadAssignmentState.REVOKED.value,
        BetaReadAssignmentState.DISQUALIFIED.value,
    }:
        return "missed"
    if assignment.state == BetaReadAssignmentState.SUBMITTED.value:
        return "completed"
    if assignment.state == BetaReadAssignmentState.ACTIVE.value and ensure_timezone(assignment.starts_at) > current:
        return "scheduled"
    return "active"


def beta_status_label(assignment: BetaReadAssignment, *, now: datetime | None = None) -> str:
    if assignment.state in ACTIVE_READER_STATES and submission_is_late(assignment, now):
        return "Expired"
    if assignment.state == BetaReadAssignmentState.ACTIVE.value:
        return "Scheduled" if beta_view_bucket(assignment, now=now) == "scheduled" else "Not started"
    if assignment.state == BetaReadAssignmentState.IN_PROGRESS.value:
        return "In progress"
    if assignment.state == BetaReadAssignmentState.READY_TO_SUBMIT.value:
        return "Ready to submit"
    if assignment.state == BetaReadAssignmentState.SUBMITTED.value:
        return "Submitted"
    if assignment.state == BetaReadAssignmentState.COMPLETED.value:
        return "Completed"
    if assignment.state == BetaReadAssignmentState.REVOKED.value:
        return "Revoked"
    if assignment.state == BetaReadAssignmentState.DISQUALIFIED.value:
        return "Disqualified"
    if assignment.state == BetaReadAssignmentState.EXPIRED.value:
        return "Expired"
    if assignment.state == BetaReadAssignmentState.MISSED.value:
        return "Missed"
    return assignment.state.replace("_", " ").title()


def beta_primary_action(assignment: BetaReadAssignment, *, now: datetime | None = None) -> str:
    bucket = beta_view_bucket(assignment, now=now)
    if bucket == "missed" and assignment.state in ACTIVE_READER_STATES:
        return "View"
    if bucket == "scheduled":
        return "View"
    if assignment.state == BetaReadAssignmentState.ACTIVE.value:
        return "Start"
    if assignment.state == BetaReadAssignmentState.IN_PROGRESS.value:
        return "Continue"
    if assignment.state == BetaReadAssignmentState.READY_TO_SUBMIT.value:
        return "Submit feedback"
    if assignment.state in {
        BetaReadAssignmentState.SUBMITTED.value,
        BetaReadAssignmentState.COMPLETED.value,
        BetaReadAssignmentState.MISSED.value,
        BetaReadAssignmentState.EXPIRED.value,
        BetaReadAssignmentState.REVOKED.value,
        BetaReadAssignmentState.DISQUALIFIED.value,
    }:
        return "View"
    return "View"


def penalty_warning_for_user(user: User) -> str | None:
    count = int(user.consecutive_missed_beta_reads or 0)
    threshold = max(int(settings.BETA_READ_MISSED_PENALTY_THRESHOLD), 1)
    if count <= 0:
        return None
    if count == 1:
        return "You missed 1 beta read in a row. Complete the next one before the deadline to keep your streak healthy."
    if count == 2:
        return "You missed 2 beta reads in a row. One more missed deadline may trigger a beta-read penalty review."
    if count >= threshold:
        return "You reached the missed beta-read threshold. New beta-read assignments may be reviewed or restricted."
    return None


def _reader_match_clause(current_user: User):
    email = normalize_collaboration_email(current_user.email)
    return or_(
        BetaReadAssignment.reader_user_id == current_user.id,
        BetaReadAssignment.reader_email == email,
    )


async def sync_reader_identity_for_beta_reads(db: AsyncSession, current_user: User) -> None:
    email = normalize_collaboration_email(current_user.email)
    assignments = (
        await db.execute(
            select(BetaReadAssignment).where(
                BetaReadAssignment.reader_user_id.is_(None),
                BetaReadAssignment.reader_email == email,
            )
        )
    ).scalars().all()
    changed = False
    for assignment in assignments:
        assignment.reader_user_id = current_user.id
        changed = True
    if changed:
        await db.flush()


async def get_beta_assignment_for_author(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
    author_user_id: uuid.UUID,
) -> BetaReadAssignment:
    assignment = (
        await db.execute(
            select(BetaReadAssignment).where(
                BetaReadAssignment.id == assignment_id,
                BetaReadAssignment.author_user_id == author_user_id,
            )
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(404, "Beta read assignment not found.")
    return assignment


async def get_beta_assignment_for_reader(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
    current_user: User,
) -> BetaReadAssignment:
    await sync_reader_identity_for_beta_reads(db, current_user)
    assignment = (
        await db.execute(
            select(BetaReadAssignment).where(
                BetaReadAssignment.id == assignment_id,
                _reader_match_clause(current_user),
            )
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(404, "Beta read assignment not found.")
    return assignment


async def list_beta_read_questions(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
) -> list[BetaReadQuestion]:
    return (
        await db.execute(
            select(BetaReadQuestion)
            .where(BetaReadQuestion.assignment_id == assignment_id)
            .order_by(BetaReadQuestion.created_at.asc())
        )
    ).scalars().all()


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
    answer_counts = {str(question_id): int(count or 0) for question_id, count in answer_rows if question_id is not None}
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
        await db.execute(
            select(BetaReadFeedbackItem)
            .where(BetaReadFeedbackItem.assignment_id == assignment_id)
            .order_by(BetaReadFeedbackItem.created_at.asc())
        )
    ).scalars().all()
    if not items:
        return []

    question_ids = {item.question_id for item in items if item.question_id is not None}
    scene_ids = {item.scene_id for item in items if item.scene_id is not None}
    questions = {}
    if question_ids:
        question_rows = (
            await db.execute(select(BetaReadQuestion).where(BetaReadQuestion.id.in_(list(question_ids))))
        ).scalars().all()
        questions = {question.id: question for question in question_rows}
    scenes = {}
    if scene_ids:
        scene_rows = (
            await db.execute(select(NovelScene).where(NovelScene.id.in_(list(scene_ids))))
        ).scalars().all()
        scenes = {scene.id: scene for scene in scene_rows}

    return [
        BetaReadFeedbackItemOut(
            id=str(item.id),
            kind=item.kind,
            chapter_number=item.chapter_number,
            scene_id=str(item.scene_id) if item.scene_id else None,
            scene_title=scenes.get(item.scene_id).title if item.scene_id in scenes else None,
            question_id=str(item.question_id) if item.question_id else None,
            question_prompt=questions.get(item.question_id).prompt if item.question_id in questions else None,
            reaction=item.reaction,
            anchor_text=item.anchor_text,
            body=item.body,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


async def _upsert_beta_read_collaborator(
    db: AsyncSession,
    *,
    book: Book,
    reader_email: str,
    reader_user: User | None,
    scope_kind: str,
    chapter_start: int | None,
    chapter_end: int | None,
) -> BookCollaborator:
    normalized_email = normalize_collaboration_email(reader_email)
    collaborator = (
        await db.execute(
            select(BookCollaborator).where(
                BookCollaborator.book_id == book.id,
                BookCollaborator.email == normalized_email,
            )
        )
    ).scalar_one_or_none()
    if collaborator is None:
        collaborator = BookCollaborator(book_id=book.id, email=normalized_email)
        db.add(collaborator)

    scope = normalize_collaboration_scope(
        {
            "chapter_start": chapter_start if scope_kind != BetaReadScopeKind.FULL_BOOK.value else None,
            "chapter_end": chapter_end if scope_kind != BetaReadScopeKind.FULL_BOOK.value else None,
            "character_bible": False,
            "continuity_report": False,
            "reader_confusion_report": False,
        }
    )
    permissions = normalize_collaboration_permissions(
        {
            "can_edit_manuscript": False,
            "can_view_story_bible": False,
            "can_run_ai_scans": False,
            "can_export": False,
            "can_comment": True,
            "can_view_selected_chapters_only": scope_kind != BetaReadScopeKind.FULL_BOOK.value,
        },
        role="beta_reader",
        scope=scope,
    )
    collaborator.display_name = collaborator.display_name or "Beta Reader"
    collaborator.invited_user_id = reader_user.id if reader_user else collaborator.invited_user_id
    collaborator.role = "beta_reader"
    apply_collaboration_scope(collaborator, scope)
    apply_collaboration_permissions(
        collaborator,
        permissions,
        role="beta_reader",
        scope=scope,
    )
    collaborator.invite_status = "active"
    await db.flush()
    return collaborator


def sync_beta_read_access(assignment: BetaReadAssignment, collaborator: BookCollaborator | None) -> None:
    if collaborator is None:
        return
    if assignment.state in {
        BetaReadAssignmentState.REVOKED.value,
        BetaReadAssignmentState.DISQUALIFIED.value,
    }:
        collaborator.invite_status = "revoked"
        return
    if (
        assignment.state == BetaReadAssignmentState.MISSED.value
        and assignment.missed_reason != "deadline_expired"
    ):
        collaborator.invite_status = "revoked"
        return
    if (
        assignment.state == BetaReadAssignmentState.MISSED.value
        and assignment.missed_reason == "deadline_expired"
        and not settings.BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY
    ):
        collaborator.invite_status = "revoked"
        return
    if assignment.state == BetaReadAssignmentState.EXPIRED.value and not settings.BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY:
        collaborator.invite_status = "revoked"


async def expire_beta_assignment_if_due(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    now: datetime | None = None,
) -> bool:
    current = ensure_timezone(now)
    if assignment.state not in ACTIVE_READER_STATES or ensure_timezone(assignment.expires_at) >= current:
        return False

    set_beta_assignment_state(assignment, BetaReadAssignmentState.EXPIRED.value, now=current)
    set_beta_assignment_state(
        assignment,
        BetaReadAssignmentState.MISSED.value,
        now=current,
        missed_reason="deadline_expired",
    )
    assignment.counted_toward_missed_streak = True
    collaborator = await db.get(BookCollaborator, assignment.collaborator_id) if assignment.collaborator_id else None
    sync_beta_read_access(assignment, collaborator)
    reader = await db.get(User, assignment.reader_user_id) if assignment.reader_user_id else None
    if reader is not None:
        apply_missed_beta_read_penalty(reader, now=current)
        db.add(
            Notification(
                user_id=reader.id,
                book_id=assignment.book_id,
                kind="beta_read_deadline_missed",
                title="Beta read deadline missed",
                body="This beta read expired before completion, so no points were awarded.",
                data={
                    "assignment_id": str(assignment.id),
                    "counted_toward_missed_streak": True,
                    "penalty_status": reader.beta_read_penalty_status,
                },
            )
        )
        warning = penalty_warning_for_user(reader)
        if warning:
            db.add(
                Notification(
                    user_id=reader.id,
                    book_id=assignment.book_id,
                    kind="beta_read_penalty_warning",
                    title="Beta read warning",
                    body=warning,
                    data={"assignment_id": str(assignment.id), "penalty_status": reader.beta_read_penalty_status},
                )
            )
    db.add(
        Notification(
            user_id=assignment.author_user_id,
            book_id=assignment.book_id,
            kind="beta_read_missed_author_notice",
            title="A beta read deadline passed",
            body="A beta reader missed the deadline for this assignment.",
            data={"assignment_id": str(assignment.id), "book_id": str(assignment.book_id)},
        )
    )
    return True


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
                BetaReadAssignment.state.not_in(list(TERMINAL_STATES | {BetaReadAssignmentState.EXPIRED.value})),
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
        if penalty_type == "temporary_beta_read_ban" and reader_user.beta_read_penalty_status == PENALTY_STATUS_PENALTY_REQUIRED:
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
        reward_points=int(body.reward_points),
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
                body="Complete before the deadline to earn points.",
                data={
                    "assignment_id": str(assignment.id),
                    "book_id": str(book.id),
                    "book_title": book.title,
                    "task_label": assignment.task_label,
                    "reward_points": assignment.reward_points,
                    "question_count": len(author_questions),
                    "starts_at": assignment.starts_at.isoformat(),
                    "expires_at": assignment.expires_at.isoformat(),
                },
            )
        )
    await db.commit()
    await db.refresh(assignment)
    return assignment


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
                select(func.count(BetaReadQuestion.id)).where(BetaReadQuestion.assignment_id == assignment.id)
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
        from app.models.book import BookNote

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


async def sync_beta_assignment_progress(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    progress: ReadingProgress | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = ensure_timezone(now)
    snapshot = await _assignment_progress_snapshot(db, assignment=assignment, progress=progress)
    if assignment.state == BetaReadAssignmentState.ACTIVE.value and (
        assignment.first_opened_at is not None or float(snapshot["progress_pct"]) > 0
        or int(snapshot["comment_count"]) > 0
        or int(snapshot["feedback_item_count"]) > 0
    ):
        set_beta_assignment_state(assignment, BetaReadAssignmentState.IN_PROGRESS.value, now=current)
    requirements_met = _requirements_met(assignment, snapshot)
    if assignment.state == BetaReadAssignmentState.IN_PROGRESS.value and requirements_met:
        set_beta_assignment_state(assignment, BetaReadAssignmentState.READY_TO_SUBMIT.value, now=current)
    return snapshot


async def sync_beta_assignments_for_reader_book(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    current_user: User,
    now: datetime | None = None,
) -> None:
    await sync_reader_identity_for_beta_reads(db, current_user)
    progress = (
        await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.book_id == book_id,
                ReadingProgress.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    assignments = (
        await db.execute(
            select(BetaReadAssignment).where(
                BetaReadAssignment.book_id == book_id,
                _reader_match_clause(current_user),
                BetaReadAssignment.state.in_(list(ACTIVE_READER_STATES)),
            )
        )
    ).scalars().all()
    for assignment in assignments:
        await sync_beta_assignment_progress(db, assignment=assignment, progress=progress, now=now)
    if assignments:
        await db.commit()


def _clean_optional_feedback_text(value: str | None, *, max_length: int) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        raise HTTPException(400, f"Feedback text must be {max_length} characters or fewer.")
    return cleaned


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
    question = await _resolve_feedback_question(db, assignment=assignment, question_id=body.question_id)

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


async def build_beta_read_assignment_out(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User | None = None,
    reader_user: User | None = None,
) -> BetaReadAssignmentOut:
    now = utc_now()
    book = await db.get(Book, assignment.book_id)
    if book is None:
        raise HTTPException(404, "Book not found")
    resolved_reader = reader_user
    if resolved_reader is None and assignment.reader_user_id is not None:
        resolved_reader = await db.get(User, assignment.reader_user_id)
    progress = None
    if assignment.reader_user_id is not None:
        progress = (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.book_id == assignment.book_id,
                    ReadingProgress.user_id == assignment.reader_user_id,
                )
            )
        ).scalar_one_or_none()
    snapshot = await _assignment_progress_snapshot(db, assignment=assignment, progress=progress)
    rating_summary = await book_beta_rating_summary(db, book_id=assignment.book_id)
    requirements_met = _requirements_met(assignment, snapshot)
    effective_user = resolved_reader or current_user
    consecutive_missed = int(effective_user.consecutive_missed_beta_reads or 0) if effective_user is not None else 0
    penalty_status = str(effective_user.beta_read_penalty_status or PENALTY_STATUS_NONE) if effective_user is not None else PENALTY_STATUS_NONE
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
        reward_points=assignment.reward_points,
        projected_reward_points=compute_beta_read_reward_points(
            assignment.reward_points,
            rating_summary["average_rating"],
        ),
        awarded_points=assignment.awarded_points,
        required_progress_pct=assignment.required_progress_pct,
        required_comment_count=assignment.required_comment_count,
        required_feedback_item_count=assignment.required_feedback_item_count,
        require_final_feedback=assignment.require_final_feedback,
        starts_at=assignment.starts_at,
        expires_at=assignment.expires_at,
        access_granted_at=assignment.access_granted_at,
        submitted_at=assignment.submitted_at,
        completed_at=assignment.completed_at,
        awarded_at=assignment.awarded_at,
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
        penalty_warning=penalty_warning_for_user(effective_user) if effective_user is not None else None,
        final_rating=float(assignment.final_rating) if assignment.final_rating is not None else None,
        rating_sentiment=beta_read_rating_sentiment(float(assignment.final_rating)) if assignment.final_rating is not None else None,
        book_average_rating=rating_summary["average_rating"],
        book_rating_count=int(rating_summary["rating_count"]),
    )


async def build_beta_read_assignment_detail_out(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User | None = None,
    reader_user: User | None = None,
) -> BetaReadAssignmentDetailOut:
    assignment_out = await build_beta_read_assignment_out(
        db,
        assignment=assignment,
        current_user=current_user,
        reader_user=reader_user,
    )
    return BetaReadAssignmentDetailOut(
        assignment=assignment_out,
        author_questions=await _serialize_beta_read_questions(db, assignment_id=assignment.id),
        feedback_items=await _serialize_beta_read_feedback_items(db, assignment_id=assignment.id),
        feedback_summary=await beta_feedback_summary(db, assignment_id=assignment.id),
    )


async def list_reader_beta_read_assignments(
    db: AsyncSession,
    *,
    current_user: User,
    bucket: str | None = None,
    upcoming_only: bool = False,
) -> list[BetaReadAssignmentOut]:
    await sync_reader_identity_for_beta_reads(db, current_user)
    now = utc_now()
    assignments = (
        await db.execute(
            select(BetaReadAssignment)
            .where(_reader_match_clause(current_user), BetaReadAssignment.state.in_(list(READER_VISIBLE_STATES)))
            .order_by(BetaReadAssignment.expires_at.asc(), BetaReadAssignment.created_at.desc())
        )
    ).scalars().all()
    changed = False
    items: list[BetaReadAssignmentOut] = []
    for assignment in assignments:
        changed = await expire_beta_assignment_if_due(db, assignment=assignment, now=now) or changed
        item = await build_beta_read_assignment_out(db, assignment=assignment, current_user=current_user)
        if upcoming_only and item.view_bucket not in {"active", "scheduled"}:
            continue
        if bucket and item.view_bucket != bucket:
            continue
        items.append(item)
    if changed:
        await db.commit()
    return items


async def list_book_beta_read_assignments(
    db: AsyncSession,
    *,
    book: Book,
    author_user_id: uuid.UUID,
) -> list[BetaReadAssignmentOut]:
    now = utc_now()
    assignments = (
        await db.execute(
            select(BetaReadAssignment)
            .where(
                BetaReadAssignment.book_id == book.id,
                BetaReadAssignment.author_user_id == author_user_id,
            )
            .order_by(BetaReadAssignment.created_at.desc())
        )
    ).scalars().all()
    changed = False
    items: list[BetaReadAssignmentOut] = []
    for assignment in assignments:
        changed = await expire_beta_assignment_if_due(db, assignment=assignment, now=now) or changed
        reader_user = await db.get(User, assignment.reader_user_id) if assignment.reader_user_id else None
        items.append(await build_beta_read_assignment_out(db, assignment=assignment, reader_user=reader_user))
    if changed:
        await db.commit()
    return items


async def start_beta_read(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User,
) -> BetaReadAssignment:
    now = utc_now()
    if await expire_beta_assignment_if_due(db, assignment=assignment, now=now):
        await db.commit()
        raise HTTPException(409, "This beta read has expired.")
    if ensure_timezone(assignment.starts_at) > now:
        raise HTTPException(400, "This beta read has not started yet.")
    if assignment.state not in ACTIVE_READER_STATES:
        raise HTTPException(409, "This beta read cannot be started.")
    if assignment.state == BetaReadAssignmentState.ACTIVE.value:
        set_beta_assignment_state(assignment, BetaReadAssignmentState.IN_PROGRESS.value, now=now)
    if assignment.first_opened_at is None:
        assignment.first_opened_at = now
    db.add(
        Notification(
            user_id=assignment.author_user_id,
            book_id=assignment.book_id,
            kind="beta_read_started",
            title="A beta reader started reading",
            body="Your beta reader opened the assigned draft.",
            data={"assignment_id": str(assignment.id), "book_id": str(assignment.book_id)},
        )
    )
    await db.commit()
    await db.refresh(assignment)
    return assignment


def apply_missed_beta_read_penalty(user: User, *, now: datetime | None = None) -> None:
    current = ensure_timezone(now)
    user.consecutive_missed_beta_reads = int(user.consecutive_missed_beta_reads or 0) + 1
    threshold = max(int(settings.BETA_READ_MISSED_PENALTY_THRESHOLD), 1)
    if user.consecutive_missed_beta_reads <= 1:
        user.beta_read_penalty_status = PENALTY_STATUS_WARNING
        return
    if user.consecutive_missed_beta_reads == 2:
        user.beta_read_penalty_status = PENALTY_STATUS_STRONG_WARNING
        return

    user.beta_read_penalty_status = PENALTY_STATUS_PENALTY_REQUIRED
    user.beta_read_penalty_required_at = current
    # Monetary fines are intentionally not auto-applied here. We only record
    # reviewable state unless a separate, explicit billing flow is wired.


def reset_missed_beta_read_penalty(user: User) -> None:
    user.consecutive_missed_beta_reads = 0
    user.beta_read_penalty_status = PENALTY_STATUS_NONE
    user.beta_read_penalty_required_at = None


async def submit_beta_read_feedback(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User,
    final_feedback: str,
    final_rating: float,
) -> BetaReadAssignment:
    now = utc_now()
    normalized_rating = normalize_beta_read_rating(final_rating)
    expired_now = await expire_beta_assignment_if_due(db, assignment=assignment, now=now)
    if expired_now and not settings.BETA_READ_ALLOW_LATE_FEEDBACK:
        await db.commit()
        raise HTTPException(409, "This beta read has already expired. Late feedback does not award points.")
    await sync_beta_assignment_progress(db, assignment=assignment, now=now)
    if expired_now:
        assignment.final_feedback = final_feedback.strip()
        assignment.final_rating = normalized_rating
        assignment.submitted_at = now
        apply_beta_submission_snapshot(
            assignment,
            {
                "late_feedback": True,
                "final_rating": normalized_rating,
                "rating_sentiment": beta_read_rating_sentiment(normalized_rating),
                "submitted_before_deadline": False,
            },
        )
        await db.commit()
        await db.refresh(assignment)
        return assignment
    if assignment.state == BetaReadAssignmentState.ACTIVE.value:
        set_beta_assignment_state(assignment, BetaReadAssignmentState.IN_PROGRESS.value, now=now)
    snapshot = await sync_beta_assignment_progress(db, assignment=assignment, now=now)
    if assignment.state != BetaReadAssignmentState.READY_TO_SUBMIT.value:
        raise HTTPException(409, "Finish the required reading and comments before submitting feedback.")
    if not _requirements_met(assignment, snapshot):
        raise HTTPException(409, "Finish the required reading and comments before submitting feedback.")
    set_beta_assignment_state(assignment, BetaReadAssignmentState.SUBMITTED.value, now=now)
    assignment.final_feedback = final_feedback.strip()
    assignment.final_rating = normalized_rating
    assignment.submitted_at = now
    apply_beta_submission_snapshot(
        assignment,
        {
            "progress_pct": snapshot["progress_pct"],
            "chapters_total": snapshot["chapters_total"],
            "chapters_read_count": snapshot["chapters_read_count"],
            "comment_count": snapshot["comment_count"],
            "feedback_item_count": snapshot["feedback_item_count"],
            "answer_count": snapshot["answer_count"],
            "final_rating": normalized_rating,
            "rating_sentiment": beta_read_rating_sentiment(normalized_rating),
            "submitted_before_deadline": now <= ensure_timezone(assignment.expires_at),
            "late_feedback": False,
        },
    )
    db.add(
        Notification(
            user_id=assignment.author_user_id,
            book_id=assignment.book_id,
            kind="beta_read_feedback_submitted",
            title="Beta read feedback submitted",
            body="Your beta reader submitted their feedback.",
            data={"assignment_id": str(assignment.id), "book_id": str(assignment.book_id)},
        )
    )
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def revoke_beta_read_assignment(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    reason: str | None = None,
) -> BetaReadAssignment:
    if assignment.state not in ACTIVE_READER_STATES:
        raise HTTPException(409, "Only active beta reads can be revoked.")
    set_beta_assignment_state(
        assignment,
        BetaReadAssignmentState.REVOKED.value,
        now=utc_now(),
        revoked_reason=reason or "revoked_by_author",
    )
    collaborator = await db.get(BookCollaborator, assignment.collaborator_id) if assignment.collaborator_id else None
    sync_beta_read_access(assignment, collaborator)
    if assignment.reader_user_id is not None:
        db.add(
            Notification(
                user_id=assignment.reader_user_id,
                book_id=assignment.book_id,
                kind="beta_read_revoked",
                title="A beta read was revoked",
                body="This beta read is no longer available for points.",
                data={"assignment_id": str(assignment.id), "book_id": str(assignment.book_id)},
            )
        )
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def award_submitted_beta_reads(
    db: AsyncSession,
    *,
    limit: int = 100,
) -> int:
    assignments = (
        await db.execute(
            select(BetaReadAssignment)
            .where(BetaReadAssignment.state == BetaReadAssignmentState.SUBMITTED.value)
            .order_by(BetaReadAssignment.submitted_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    completed = 0
    for assignment in assignments:
        reader = await db.get(User, assignment.reader_user_id) if assignment.reader_user_id else None
        if reader is None:
            continue
        snapshot = beta_submission_snapshot(assignment)
        submitted_before_deadline = bool(snapshot.get("submitted_before_deadline"))
        requirements_met = (
            float(snapshot.get("progress_pct") or 0) >= float(assignment.required_progress_pct)
            and int(snapshot.get("comment_count") or 0) >= int(assignment.required_comment_count)
            and int(snapshot.get("feedback_item_count") or 0) >= int(assignment.required_feedback_item_count)
            and assignment.final_rating is not None
            and (
                not assignment.require_final_feedback
                or bool(str(assignment.final_feedback or "").strip())
            )
        )
        if not submitted_before_deadline or not requirements_met:
            set_beta_assignment_state(
                assignment,
                BetaReadAssignmentState.DISQUALIFIED.value,
                now=utc_now(),
                disqualified_reason="deadline_or_requirement_failed",
            )
            collaborator = await db.get(BookCollaborator, assignment.collaborator_id) if assignment.collaborator_id else None
            sync_beta_read_access(assignment, collaborator)
            continue

        rating_summary = await book_beta_rating_summary(db, book_id=assignment.book_id)
        awarded_points = compute_beta_read_reward_points(
            assignment.reward_points,
            rating_summary["average_rating"],
        )
        await grant_points(
            db,
            reader.id,
            awarded_points,
            POINT_SOURCE_BETA_READ,
            source_id=str(assignment.id),
            metadata={
                "book_id": str(assignment.book_id),
                "task_label": assignment.task_label,
                "submitted_at": assignment.submitted_at.isoformat() if assignment.submitted_at else None,
                "average_rating": rating_summary["average_rating"],
                "final_rating": assignment.final_rating,
            },
        )
        assignment.awarded_points = awarded_points
        assignment.awarded_at = utc_now()
        set_beta_assignment_state(assignment, BetaReadAssignmentState.COMPLETED.value, now=assignment.awarded_at)
        reset_missed_beta_read_penalty(reader)
        if assignment.final_rating is not None and beta_read_rating_sentiment(float(assignment.final_rating)) == "positive":
            await grant_points(
                db,
                assignment.author_user_id,
                max(int(settings.POSITIVE_BETA_REVIEW_REWARD_POINTS), 0),
                POINT_SOURCE_BETA_READ_AUTHOR_REWARD,
                source_id=str(assignment.id),
                metadata={
                    "book_id": str(assignment.book_id),
                    "reader_user_id": str(reader.id),
                    "final_rating": assignment.final_rating,
                },
            )
        db.add(
            Notification(
                user_id=reader.id,
                book_id=assignment.book_id,
                kind="beta_read_points_awarded",
                title="Beta read points awarded",
                body=f"You earned {awarded_points} points for completing this beta read on time.",
                data={"assignment_id": str(assignment.id), "points": awarded_points},
            )
        )
        completed += 1
    return completed


async def expire_due_beta_reads(
    db: AsyncSession,
    *,
    limit: int = 100,
) -> tuple[int, int]:
    now = utc_now()
    assignments = (
        await db.execute(
            select(BetaReadAssignment)
            .where(
                BetaReadAssignment.state.in_(list(ACTIVE_READER_STATES)),
                BetaReadAssignment.expires_at < now,
            )
            .order_by(BetaReadAssignment.expires_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    expired_count = 0
    missed_count = 0
    for assignment in assignments:
        if await expire_beta_assignment_if_due(db, assignment=assignment, now=now):
            expired_count += 1
            missed_count += 1
    return expired_count, missed_count


async def send_beta_read_reminders(
    db: AsyncSession,
    *,
    limit: int = 100,
) -> int:
    now = utc_now()
    assignments = (
        await db.execute(
            select(BetaReadAssignment)
            .where(BetaReadAssignment.state.in_(list(ACTIVE_READER_STATES)))
            .order_by(BetaReadAssignment.expires_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    sent = 0
    for assignment in assignments:
        if assignment.reader_user_id is None:
            continue
        hours_left = (ensure_timezone(assignment.expires_at) - now).total_seconds() / 3600
        if 23 <= hours_left <= 24 and assignment.reminder_24h_sent_at is None:
            assignment.reminder_24h_sent_at = now
            sent += 1
            body = "24 hours left. Complete before the deadline to earn points."
        elif 5 <= hours_left <= 6 and assignment.reminder_6h_sent_at is None:
            assignment.reminder_6h_sent_at = now
            sent += 1
            body = "6 hours left. Finish the reading and feedback to keep the points."
        else:
            continue
        db.add(
            Notification(
                user_id=assignment.reader_user_id,
                book_id=assignment.book_id,
                kind="beta_read_deadline_reminder",
                title="Beta read deadline reminder",
                body=body,
                data={"assignment_id": str(assignment.id), "expires_at": assignment.expires_at.isoformat()},
            )
        )
    return sent


async def run_beta_read_jobs(
    db: AsyncSession,
    *,
    limit: int = 100,
) -> BetaReadJobRunOut:
    reminders_sent = await send_beta_read_reminders(db, limit=limit)
    expired_count, missed_count = await expire_due_beta_reads(db, limit=limit)
    completed_count = await award_submitted_beta_reads(db, limit=limit)
    await db.commit()
    return BetaReadJobRunOut(
        reminders_sent=reminders_sent,
        expired_count=expired_count,
        missed_count=missed_count,
        completed_count=completed_count,
    )
