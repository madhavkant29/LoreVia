from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.user import TrialEmailEvent, User
from app.services.email_service import send_trial_email
from app.utils.billing_utils import FREE_TIER, normalize_tier
from app.utils.trial_email_utils import FIRST_MANUSCRIPT_NUDGE, build_trial_email_schedule


async def schedule_trial_email_events(db: AsyncSession, user: User) -> None:
    schedule = build_trial_email_schedule(user.created_at)
    existing_types = {
        row[0]
        for row in (
            await db.execute(
                select(TrialEmailEvent.email_type).where(TrialEmailEvent.user_id == user.id)
            )
        ).all()
    }
    for email_type, scheduled_for in schedule.items():
        if email_type in existing_types:
            continue
        db.add(
            TrialEmailEvent(
                user_id=user.id,
                email_type=email_type,
                scheduled_for=scheduled_for,
                status="pending",
            )
        )


async def send_due_trial_emails(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> dict[str, int]:
    current = now or datetime.now(UTC)
    current = current if current.tzinfo else current.replace(tzinfo=UTC)
    stale_sending_rows = (
        await db.execute(
            select(TrialEmailEvent).where(
                TrialEmailEvent.status == "sending",
                TrialEmailEvent.updated_at < current - timedelta(minutes=30),
            )
        )
    ).scalars().all()
    for event in stale_sending_rows:
        event.status = "failed"
        event.last_error = "Previous send attempt did not finalize. Review delivery logs before retrying."

    due_rows = (
        await db.execute(
            select(TrialEmailEvent, User)
            .join(User, User.id == TrialEmailEvent.user_id)
            .where(
                TrialEmailEvent.status == "pending",
                TrialEmailEvent.scheduled_for <= current,
                User.email_verified_at.is_not(None),
            )
            .order_by(TrialEmailEvent.scheduled_for.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()

    sent_count = 0
    latest_due_by_user: dict[str, tuple[TrialEmailEvent, User]] = {}
    for event, user in due_rows:
        user_key = str(user.id)
        older = latest_due_by_user.get(user_key)
        if older is not None:
            older[0].status = "skipped"
            older[0].last_error = "Superseded by a later due trial email."
        latest_due_by_user[user_key] = (event, user)

    claimed_event_ids = []
    for event, user in latest_due_by_user.values():
        if normalize_tier(user.tier) != FREE_TIER:
            event.status = "skipped"
            event.last_error = "User upgraded before trial email was due."
            continue
        # Claim the event durably before calling the external email provider so
        # overlapping scheduler runs do not deliver the same logical email twice.
        event.status = "sending"
        event.last_error = None
        claimed_event_ids.append(event.id)

    await db.commit()

    if not claimed_event_ids:
        return {"sent": sent_count, "checked": len(due_rows)}

    claimed_events = (
        await db.execute(
            select(TrialEmailEvent, User)
            .join(User, User.id == TrialEmailEvent.user_id)
            .where(
                TrialEmailEvent.id.in_(claimed_event_ids),
            )
            .order_by(TrialEmailEvent.scheduled_for.asc())
        )
    ).all()

    for event, user in claimed_events:
        if event.email_type == FIRST_MANUSCRIPT_NUDGE:
            existing_book = (
                await db.execute(select(Book.id).where(Book.user_id == user.id).limit(1))
            ).scalar_one_or_none()
            if existing_book is not None:
                event.status = "skipped"
                event.last_error = "User already created a manuscript workspace before the nudge was due."
                await db.commit()
                continue
        delivered = await send_trial_email(user.email, event.email_type)
        if delivered:
            event.status = "sent"
            event.sent_at = current
            event.last_error = None
            sent_count += 1
        else:
            event.status = "failed"
            event.last_error = "Resend delivery failed."
        await db.commit()

    return {"sent": sent_count, "checked": len(due_rows)}
