from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.models.book import Book
from app.models.user import TrialEmailEvent, User
from app.services.trial_email_service import send_due_trial_emails
from app.utils.trial_email_utils import FIRST_MANUSCRIPT_NUDGE


@pytest.mark.asyncio
async def test_send_due_trial_emails_is_idempotent_for_sent_events(db, monkeypatch):
    await db.execute(delete(TrialEmailEvent))
    await db.commit()

    user = User(
        email="trial-idempotent@lorevia.test",
        username="trial-idempotent",
        password_hash="hashed",
        tier="free",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    due_at = datetime.now(UTC) - timedelta(minutes=5)
    event = TrialEmailEvent(
        user_id=user.id,
        email_type="trial_nudge",
        scheduled_for=due_at,
        status="pending",
    )
    db.add(event)
    await db.commit()

    deliveries: list[tuple[str, str]] = []

    async def fake_send(email: str, email_type: str) -> bool:
        deliveries.append((email, email_type))
        return True

    monkeypatch.setattr("app.services.trial_email_service.send_trial_email", fake_send)

    first = await send_due_trial_emails(db, now=datetime.now(UTC), limit=10)
    second = await send_due_trial_emails(db, now=datetime.now(UTC), limit=10)

    refreshed = (
        await db.execute(select(TrialEmailEvent).where(TrialEmailEvent.id == event.id))
    ).scalar_one()

    assert first == {"sent": 1, "checked": 1}
    assert second == {"sent": 0, "checked": 0}
    assert deliveries == [(user.email, "trial_nudge")]
    assert refreshed.status == "sent"
    assert refreshed.sent_at is not None


@pytest.mark.asyncio
async def test_send_due_trial_emails_marks_stale_sending_events_failed_without_resending(
    db, monkeypatch
):
    await db.execute(delete(TrialEmailEvent))
    await db.commit()

    user = User(
        email="trial-stale@lorevia.test",
        username="trial-stale",
        password_hash="hashed",
        tier="free",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    stale_time = datetime.now(UTC) - timedelta(hours=2)
    event = TrialEmailEvent(
        user_id=user.id,
        email_type="trial_nudge",
        scheduled_for=stale_time,
        sent_at=None,
        status="sending",
        updated_at=stale_time,
    )
    db.add(event)
    await db.commit()

    deliveries: list[tuple[str, str]] = []

    async def fake_send(email: str, email_type: str) -> bool:
        deliveries.append((email, email_type))
        return True

    monkeypatch.setattr("app.services.trial_email_service.send_trial_email", fake_send)

    result = await send_due_trial_emails(db, now=datetime.now(UTC), limit=10)
    refreshed = (
        await db.execute(select(TrialEmailEvent).where(TrialEmailEvent.id == event.id))
    ).scalar_one()

    assert result == {"sent": 0, "checked": 0}
    assert deliveries == []
    assert refreshed.status == "failed"
    assert "did not finalize" in str(refreshed.last_error or "")


@pytest.mark.asyncio
async def test_send_due_trial_emails_skips_first_manuscript_nudge_after_user_uploads_book(
    db, monkeypatch
):
    await db.execute(delete(TrialEmailEvent))
    await db.commit()

    user = User(
        email="trial-uploaded@lorevia.test",
        username="trial-uploaded",
        password_hash="hashed",
        tier="free",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    db.add(
        Book(
            user_id=user.id,
            title="Existing Project",
            format="manual",
            work_type="novel",
            s3_key="books/existing.txt",
            status="ready",
            mode="author",
        )
    )
    db.add(
        TrialEmailEvent(
            user_id=user.id,
            email_type=FIRST_MANUSCRIPT_NUDGE,
            scheduled_for=datetime.now(UTC) - timedelta(minutes=5),
            status="pending",
        )
    )
    await db.commit()

    deliveries: list[tuple[str, str]] = []

    async def fake_send(email: str, email_type: str) -> bool:
        deliveries.append((email, email_type))
        return True

    monkeypatch.setattr("app.services.trial_email_service.send_trial_email", fake_send)

    result = await send_due_trial_emails(db, now=datetime.now(UTC), limit=10)
    event = (
        await db.execute(select(TrialEmailEvent).where(TrialEmailEvent.user_id == user.id))
    ).scalar_one()

    assert result == {"sent": 0, "checked": 1}
    assert deliveries == []
    assert event.status == "skipped"
    assert "already created a manuscript workspace" in str(event.last_error or "")
