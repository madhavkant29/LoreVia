from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.models.beta_read import (
    BetaReadAssignment,
    BetaReadAssignmentState,
    BetaReadFeedbackItem,
    BetaReadFeedbackKind,
    BetaReadScopeKind,
)
from app.models.book import Book
from app.models.progress import ReadingProgress
from app.models.user import User

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
FEEDBACK_KINDS = {
    BetaReadFeedbackKind.CHAPTER_COMMENT.value,
    BetaReadFeedbackKind.SCENE_REACTION.value,
    BetaReadFeedbackKind.ANSWER.value,
    BetaReadFeedbackKind.CONFUSING.value,
    BetaReadFeedbackKind.BORING.value,
    BetaReadFeedbackKind.FAVORITE.value,
}
AUTHOR_FEEDBACK_ITEM_STATUSES = {
    "open",
    "resolved",
    "archived",
    "task_created",
}
RATED_ASSIGNMENT_STATES = {
    BetaReadAssignmentState.SUBMITTED.value,
    BetaReadAssignmentState.COMPLETED.value,
}
POSITIVE_RATING_MIN = 4.0
NEUTRAL_RATING_MIN = 2.5


@dataclass(slots=True)
class BetaAssignmentRenderContext:
    books_by_id: dict[uuid.UUID, Book]
    readers_by_id: dict[uuid.UUID, User]
    progress_by_pair: dict[tuple[uuid.UUID, uuid.UUID], ReadingProgress]
    rating_summary_by_book_id: dict[uuid.UUID, dict[str, Any]]
    question_count_by_assignment_id: dict[uuid.UUID, int]
    feedback_count_by_assignment_id: dict[uuid.UUID, int]
    answer_count_by_assignment_id: dict[uuid.UUID, int]
    note_comment_count_by_assignment_id: dict[uuid.UUID, int]
    chapter_comment_count_by_assignment_id: dict[uuid.UUID, int]


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
        raise HTTPException(
            400,
            "chapter_start and chapter_end are required for chapter-range and section beta reads.",
        )
    if chapter_start < 1 or chapter_end < 1 or chapter_end < chapter_start:
        raise HTTPException(400, "Invalid beta read chapter range.")
    if total_chapters and chapter_end > total_chapters:
        raise HTTPException(
            400, f"Chapter range cannot exceed the book's {total_chapters} chapters."
        )
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


def normalize_author_feedback_item_status(status: str) -> str:
    normalized = str(status or "").strip().lower().replace(" ", "_")
    if normalized not in AUTHOR_FEEDBACK_ITEM_STATUSES:
        raise HTTPException(400, "Invalid beta-read feedback status.")
    return normalized


def beta_feedback_item_author_metadata(item: BetaReadFeedbackItem) -> dict[str, Any]:
    metadata = dict(item.metadata_json or {})
    status = normalize_author_feedback_item_status(metadata.get("author_status") or "open")
    task_id = (
        str(metadata.get("author_task_id")).strip() or None
        if metadata.get("author_task_id") is not None
        else None
    )
    updated_at_raw = metadata.get("author_updated_at")
    updated_at = None
    if isinstance(updated_at_raw, str):
        try:
            updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
        except ValueError:
            updated_at = None
    return {
        "author_status": status,
        "author_task_id": task_id,
        "author_updated_at": updated_at,
    }


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


def apply_missed_beta_read_penalty(user: User, *, now: datetime | None = None) -> None:
    current = ensure_timezone(now)
    user.consecutive_missed_beta_reads = int(user.consecutive_missed_beta_reads or 0) + 1
    threshold = max(int(settings.BETA_READ_MISSED_PENALTY_THRESHOLD), 1)
    if user.consecutive_missed_beta_reads <= max(threshold - 2, 1):
        user.beta_read_penalty_status = PENALTY_STATUS_WARNING
        return
    if user.consecutive_missed_beta_reads < threshold:
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


def apply_beta_submission_snapshot(
    assignment: BetaReadAssignment, snapshot: dict[str, Any]
) -> None:
    assignment.submission_metadata = dict(snapshot)
    assignment.submitted_progress_pct = (
        float(snapshot["progress_pct"]) if snapshot.get("progress_pct") is not None else None
    )
    assignment.submitted_chapters_total = (
        int(snapshot["chapters_total"]) if snapshot.get("chapters_total") is not None else None
    )
    assignment.submitted_chapters_read_count = (
        int(snapshot["chapters_read_count"])
        if snapshot.get("chapters_read_count") is not None
        else None
    )
    assignment.submitted_comment_count = (
        int(snapshot["comment_count"]) if snapshot.get("comment_count") is not None else None
    )
    assignment.submitted_feedback_item_count = (
        int(snapshot["feedback_item_count"])
        if snapshot.get("feedback_item_count") is not None
        else None
    )
    assignment.submitted_answer_count = (
        int(snapshot["answer_count"]) if snapshot.get("answer_count") is not None else None
    )
    assignment.submitted_rating_sentiment = (
        str(snapshot["rating_sentiment"]).strip() or None
        if snapshot.get("rating_sentiment") is not None
        else None
    )
    assignment.submitted_before_deadline = (
        bool(snapshot["submitted_before_deadline"])
        if snapshot.get("submitted_before_deadline") is not None
        else None
    )
    assignment.late_feedback = bool(snapshot.get("late_feedback", False))


def submission_is_late(assignment: BetaReadAssignment, now: datetime | None = None) -> bool:
    current = ensure_timezone(now)
    return current > ensure_timezone(assignment.expires_at)


def assert_valid_beta_transition(current_state: str, next_state: str) -> None:
    allowed = VALID_STATE_TRANSITIONS.get(current_state, set())
    if next_state not in allowed:
        raise HTTPException(
            409, f"Cannot transition beta read from {current_state} to {next_state}."
        )


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
    if (
        assignment.state in ACTIVE_READER_STATES
        and ensure_timezone(assignment.expires_at) < current
    ):
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
    if (
        assignment.state == BetaReadAssignmentState.ACTIVE.value
        and ensure_timezone(assignment.starts_at) > current
    ):
        return "scheduled"
    return "active"


def beta_status_label(assignment: BetaReadAssignment, *, now: datetime | None = None) -> str:
    if assignment.state in ACTIVE_READER_STATES and submission_is_late(assignment, now):
        return "Expired"
    if assignment.state == BetaReadAssignmentState.ACTIVE.value:
        return (
            "Scheduled" if beta_view_bucket(assignment, now=now) == "scheduled" else "Not started"
        )
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
