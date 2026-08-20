from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.beta_read import BetaReadAssignment, BetaReadAssignmentState
from app.models.book import BookCollaborator
from app.models.intelligence import Notification
from app.models.progress import ReadingProgress
from app.models.user import User
from app.utils.beta_read_access_utils import (
    _reader_match_clause,
    sync_beta_read_access,
    sync_reader_identity_for_beta_reads,
)
from app.utils.beta_read_policy_utils import (
    ACTIVE_READER_STATES,
    apply_beta_submission_snapshot,
    apply_missed_beta_read_penalty,
    beta_read_rating_sentiment,
    ensure_timezone,
    normalize_beta_read_rating,
    penalty_warning_for_user,
    set_beta_assignment_state,
    utc_now,
)
from app.utils.beta_read_progress_utils import _assignment_progress_snapshot, _requirements_met
from app.utils.notification_utils import create_notification_once, make_notification_idempotency_key


async def expire_beta_assignment_if_due(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    now: datetime | None = None,
) -> bool:
    current = ensure_timezone(now)
    if (
        assignment.state not in ACTIVE_READER_STATES
        or ensure_timezone(assignment.expires_at) >= current
    ):
        return False

    set_beta_assignment_state(assignment, BetaReadAssignmentState.EXPIRED.value, now=current)
    set_beta_assignment_state(
        assignment,
        BetaReadAssignmentState.MISSED.value,
        now=current,
        missed_reason="deadline_expired",
    )
    penalty_applied = False
    collaborator = (
        await db.get(BookCollaborator, assignment.collaborator_id)
        if assignment.collaborator_id
        else None
    )
    sync_beta_read_access(assignment, collaborator)
    reader = await db.get(User, assignment.reader_user_id) if assignment.reader_user_id else None
    if reader is not None:
        if not assignment.counted_toward_missed_streak:
            apply_missed_beta_read_penalty(reader, now=current)
            assignment.counted_toward_missed_streak = True
            penalty_applied = True
        await create_notification_once(
            db,
            user_id=reader.id,
            book_id=assignment.book_id,
            kind="beta_read_deadline_missed",
            title="Beta read deadline missed",
            body="This beta read expired before completion, so no points were awarded.",
            data={
                "assignment_id": str(assignment.id),
                "counted_toward_missed_streak": assignment.counted_toward_missed_streak
                or penalty_applied,
                "penalty_status": reader.beta_read_penalty_status,
            },
            idempotency_key=make_notification_idempotency_key(
                "beta_read_deadline_missed",
                assignment.id,
            ),
        )
        warning = penalty_warning_for_user(reader)
        if warning:
            await create_notification_once(
                db,
                user_id=reader.id,
                book_id=assignment.book_id,
                kind="beta_read_penalty_warning",
                title="Beta read warning",
                body=warning,
                data={
                    "assignment_id": str(assignment.id),
                    "penalty_status": reader.beta_read_penalty_status,
                },
                idempotency_key=make_notification_idempotency_key(
                    "beta_read_penalty_warning",
                    assignment.id,
                ),
            )
    await create_notification_once(
        db,
        user_id=assignment.author_user_id,
        book_id=assignment.book_id,
        kind="beta_read_missed_author_notice",
        title="A beta read deadline passed",
        body="A beta reader missed the deadline for this assignment.",
        data={"assignment_id": str(assignment.id), "book_id": str(assignment.book_id)},
        idempotency_key=make_notification_idempotency_key(
            "beta_read_missed_author_notice",
            assignment.id,
        ),
    )
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
        assignment.first_opened_at is not None
        or float(snapshot["progress_pct"]) > 0
        or int(snapshot["comment_count"]) > 0
        or int(snapshot["feedback_item_count"]) > 0
    ):
        set_beta_assignment_state(
            assignment, BetaReadAssignmentState.IN_PROGRESS.value, now=current
        )
    requirements_met = _requirements_met(assignment, snapshot)
    if assignment.state == BetaReadAssignmentState.IN_PROGRESS.value and requirements_met:
        set_beta_assignment_state(
            assignment, BetaReadAssignmentState.READY_TO_SUBMIT.value, now=current
        )
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
        (
            await db.execute(
                select(BetaReadAssignment).where(
                    BetaReadAssignment.book_id == book_id,
                    _reader_match_clause(current_user),
                    BetaReadAssignment.state.in_(list(ACTIVE_READER_STATES)),
                )
            )
        )
        .scalars()
        .all()
    )
    for assignment in assignments:
        await sync_beta_assignment_progress(db, assignment=assignment, progress=progress, now=now)
    if assignments:
        await db.commit()


async def start_beta_read(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User | None,
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


async def submit_beta_read_feedback(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User | None,
    final_feedback: str,
    final_rating: float,
) -> BetaReadAssignment:
    now = utc_now()
    normalized_rating = normalize_beta_read_rating(final_rating)
    expired_now = await expire_beta_assignment_if_due(db, assignment=assignment, now=now)
    if expired_now and not settings.BETA_READ_ALLOW_LATE_FEEDBACK:
        await db.commit()
        raise HTTPException(
            409,
            "This beta read has already expired. Late feedback is no longer accepted for completion.",
        )
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
        raise HTTPException(
            409, "Finish the required reading and comments before submitting feedback."
        )
    if not _requirements_met(assignment, snapshot):
        raise HTTPException(
            409, "Finish the required reading and comments before submitting feedback."
        )
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
    collaborator = (
        await db.get(BookCollaborator, assignment.collaborator_id)
        if assignment.collaborator_id
        else None
    )
    sync_beta_read_access(assignment, collaborator)
    if assignment.reader_user_id is not None:
        db.add(
            Notification(
                user_id=assignment.reader_user_id,
                book_id=assignment.book_id,
                kind="beta_read_revoked",
                title="A beta read was revoked",
                body="This beta read is no longer available.",
                data={"assignment_id": str(assignment.id), "book_id": str(assignment.book_id)},
            )
        )
    await db.commit()
    await db.refresh(assignment)
    return assignment
