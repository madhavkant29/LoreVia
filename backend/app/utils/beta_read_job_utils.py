from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_read import BetaReadAssignment, BetaReadAssignmentState
from app.models.book import BookCollaborator
from app.models.user import User
from app.schemas.beta_reads import BetaReadJobRunOut
from app.utils.beta_read_policy_utils import (
    ACTIVE_READER_STATES,
    beta_submission_snapshot,
    ensure_timezone,
    reset_missed_beta_read_penalty,
    set_beta_assignment_state,
    utc_now,
)
from app.utils.beta_read_access_utils import sync_beta_read_access
from app.utils.beta_read_lifecycle_utils import expire_beta_assignment_if_due
from app.utils.notification_utils import create_notification_once, make_notification_idempotency_key


async def award_submitted_beta_reads(
    db: AsyncSession,
    *,
    limit: int = 100,
) -> int:
    assignments = (
        (
            await db.execute(
                select(BetaReadAssignment)
                .where(BetaReadAssignment.state == BetaReadAssignmentState.SUBMITTED.value)
                .order_by(BetaReadAssignment.submitted_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    completed = 0
    for assignment in assignments:
        reader = (
            await db.get(User, assignment.reader_user_id) if assignment.reader_user_id else None
        )
        if reader is None:
            continue
        snapshot = beta_submission_snapshot(assignment)
        submitted_before_deadline = bool(snapshot.get("submitted_before_deadline"))
        requirements_met = (
            float(snapshot.get("progress_pct") or 0) >= float(assignment.required_progress_pct)
            and int(snapshot.get("comment_count") or 0) >= int(assignment.required_comment_count)
            and int(snapshot.get("feedback_item_count") or 0)
            >= int(assignment.required_feedback_item_count)
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
            collaborator = (
                await db.get(BookCollaborator, assignment.collaborator_id)
                if assignment.collaborator_id
                else None
            )
            sync_beta_read_access(assignment, collaborator)
            continue

        completed_at = utc_now()
        set_beta_assignment_state(
            assignment, BetaReadAssignmentState.COMPLETED.value, now=completed_at
        )
        reset_missed_beta_read_penalty(reader)
        await create_notification_once(
            db,
            user_id=reader.id,
            book_id=assignment.book_id,
            kind="beta_read_completed",
            title="Beta read completed",
            body="Thanks for submitting your beta read on time.",
            data={"assignment_id": str(assignment.id)},
            idempotency_key=make_notification_idempotency_key(
                "beta_read_completed",
                assignment.id,
            ),
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
        (
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
        )
        .scalars()
        .all()
    )
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
        (
            await db.execute(
                select(BetaReadAssignment)
                .where(BetaReadAssignment.state.in_(list(ACTIVE_READER_STATES)))
                .order_by(BetaReadAssignment.expires_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    sent = 0
    for assignment in assignments:
        if assignment.reader_user_id is None:
            continue
        hours_left = (ensure_timezone(assignment.expires_at) - now).total_seconds() / 3600
        reminder_window_hours: int | None = None
        if 23 <= hours_left <= 24 and assignment.reminder_24h_sent_at is None:
            assignment.reminder_24h_sent_at = now
            sent += 1
            body = "24 hours left. Complete before the deadline."
            reminder_window_hours = 24
        elif 5 <= hours_left <= 6 and assignment.reminder_6h_sent_at is None:
            assignment.reminder_6h_sent_at = now
            sent += 1
            body = "6 hours left. Finish the reading and feedback before the assignment closes."
            reminder_window_hours = 6
        else:
            continue
        await create_notification_once(
            db,
            user_id=assignment.reader_user_id,
            book_id=assignment.book_id,
            kind="beta_read_deadline_reminder",
            title="Beta read deadline reminder",
            body=body,
            data={
                "assignment_id": str(assignment.id),
                "expires_at": assignment.expires_at.isoformat(),
                "reminder_window_hours": reminder_window_hours,
            },
            idempotency_key=make_notification_idempotency_key(
                "beta_read_deadline_reminder",
                assignment.id,
                reminder_window_hours,
            ),
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
