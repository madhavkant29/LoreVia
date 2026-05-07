import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.models.user import TrialEmailEvent, User
from app.services.email_service import send_trial_email
from app.services.monetization_service import expire_due_points
from app.utils.billing_utils import FREE_TIER, normalize_tier
from app.workers.celery_app import celery_app


def _run_coro(coro):
    async def _wrapped():
        from app.core.database import engine

        await engine.dispose()
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


@celery_app.task(bind=True, name="lifecycle_tasks.send_due_trial_emails", queue="lifecycle", max_retries=3)
def send_due_trial_emails_task(self, limit: int = 100):
    async def _run():
        from app.core.database import AsyncSessionLocal

        now = datetime.now(UTC)
        sent_count = 0
        async with AsyncSessionLocal() as db:
            due_rows = (
                await db.execute(
                    select(TrialEmailEvent, User)
                    .join(User, User.id == TrialEmailEvent.user_id)
                    .where(
                        TrialEmailEvent.status == "pending",
                        TrialEmailEvent.scheduled_for <= now,
                        User.email_verified_at.is_not(None),
                    )
                    .order_by(TrialEmailEvent.scheduled_for.asc())
                    .limit(limit)
                )
            ).all()
            latest_due_by_user: dict[str, tuple[TrialEmailEvent, User]] = {}
            for event, user in due_rows:
                user_key = str(user.id)
                older = latest_due_by_user.get(user_key)
                if older is not None:
                    older[0].status = "skipped"
                    older[0].last_error = "Superseded by a later due trial email."
                latest_due_by_user[user_key] = (event, user)

            for event, user in latest_due_by_user.values():
                if normalize_tier(user.tier) != FREE_TIER:
                    event.status = "skipped"
                    event.last_error = "User upgraded before trial email was due."
                    continue
                delivered = await send_trial_email(user.email, event.email_type)
                if delivered:
                    event.status = "sent"
                    event.sent_at = now
                    event.last_error = None
                    sent_count += 1
                else:
                    event.status = "failed"
                    event.last_error = "Resend delivery failed."
            await db.commit()
        return {"sent": sent_count, "checked": len(due_rows)}

    try:
        return _run_coro(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="lifecycle_tasks.expire_due_points", queue="lifecycle", max_retries=3)
def expire_due_points_task(self, limit: int = 250):
    async def _run():
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            expired = await expire_due_points(db, limit=limit)
            await db.commit()
            return {"expired": expired}

    try:
        return _run_coro(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
