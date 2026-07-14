from __future__ import annotations

from datetime import UTC

from app.utils.exception_boundaries import FATAL_TASK_BOUNDARY_EXCEPTIONS
from app.utils.worker_async_utils import run_worker_coro
from app.workers.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="maintenance_tasks.maintain_task_executions",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def maintain_task_executions_task(self, *, limit: int = 500):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.services.task_execution_service import (
            dispatch_pending_analysis_tasks,
            dispatch_pending_embedding_tasks,
            dispatch_pending_extraction_tasks,
            reconcile_stale_task_dispatch_outbox,
            release_stale_task_leases,
        )

        async with AsyncSessionLocal() as db:
            released = await release_stale_task_leases(db, limit=limit)
            reconciled_outbox = await reconcile_stale_task_dispatch_outbox(db, limit=limit)
            await db.commit()
            extraction_dispatched = await dispatch_pending_extraction_tasks(db)
            analysis_dispatched = await dispatch_pending_analysis_tasks(db)
            embedding_dispatched = await dispatch_pending_embedding_tasks(db)
            from app.services.llm_control_service import rehydrate_llm_coordination_state

            llm_coordination = await rehydrate_llm_coordination_state()
            return {
                "released": released,
                "reconciled_outbox": reconciled_outbox,
                "extraction_dispatched": extraction_dispatched,
                "analysis_dispatched": analysis_dispatched,
                "embedding_dispatched": embedding_dispatched,
                "dispatched": (
                    extraction_dispatched + analysis_dispatched + embedding_dispatched
                ),
                "llm_coordination": llm_coordination,
            }

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.release_stale_processing_reservations",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def release_stale_processing_reservations_task(self, *, limit: int = 500):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.services.processing_allowance_service import release_stale_processing_reservations

        async with AsyncSessionLocal() as db:
            released = await release_stale_processing_reservations(db, limit=limit)
            await db.commit()
            return {"released": released}

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.repair_processing_books",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def repair_processing_books_task(self, *, book_id: str | None = None, limit: int = 50):
    async def _run():
        import uuid

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.models.book import Book
        from app.services.editor_project_service import repair_stale_editor_processing_state
        from app.services.pipeline_state_service import (
            repair_stale_completed_processing_state,
            requeue_stalled_book_processing_if_needed,
        )

        lock_scope = book_id or "scan"
        lock_key = key_cron_lock(f"maintenance_tasks.repair_processing_books:{lock_scope}")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=300):
            return {"skipped": "repair_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                if book_id:
                    try:
                        target_id = uuid.UUID(book_id)
                    except ValueError:
                        return {"repaired": 0, "invalid_book_id": book_id}
                    books = [
                        book
                        for book in [
                            await db.get(
                                Book,
                                target_id,
                                options=(selectinload(Book.chapters),),
                            )
                        ]
                        if book is not None
                    ]
                else:
                    books = (
                        (
                            await db.execute(
                                select(Book)
                                .where(Book.status == "processing")
                                .order_by(Book.created_at.asc(), Book.id.asc())
                                .limit(limit)
                            )
                        )
                        .scalars()
                        .all()
                    )

                repaired = 0
                requeued = 0
                for book in books:
                    if book.status != "processing":
                        continue
                    if await requeue_stalled_book_processing_if_needed(db, book=book):
                        requeued += 1
                    if await repair_stale_completed_processing_state(db, book):
                        repaired += 1
                    if await repair_stale_editor_processing_state(db, book):
                        repaired += 1
                await db.commit()
                return {"checked": len(books), "repaired": repaired, "requeued": requeued}
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.send_due_trial_emails",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def send_due_trial_emails_task(self, *, limit: int = 100):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.trial_email_service import send_due_trial_emails

        lock_key = key_cron_lock("maintenance_tasks.send_due_trial_emails")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=600):
            return {"skipped": "cron_task_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                result = await send_due_trial_emails(db, limit=limit)
                await db.commit()
                return result
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.process_beta_reads",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def process_beta_reads_task(self, *, limit: int = 100):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.utils.beta_read_job_utils import run_beta_read_jobs

        lock_key = key_cron_lock("maintenance_tasks.process_beta_reads")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=900):
            return {"skipped": "cron_task_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                result = await run_beta_read_jobs(db, limit=limit)
                await db.commit()
                return result.model_dump()
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.process_data_deletion_requests",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def process_data_deletion_requests_task(self, *, limit: int = 50):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.privacy_service import process_due_data_deletion_requests

        lock_key = key_cron_lock("maintenance_tasks.process_data_deletion_requests")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=900):
            return {"skipped": "cron_task_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                return await process_due_data_deletion_requests(db, limit=limit)
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.cleanup_expired_advisor_jobs",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def cleanup_expired_advisor_jobs_task(self, *, limit: int = 1000):
    async def _run():
        from sqlalchemy import delete, func, select

        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.models.intelligence import AdvisorJob, AdvisorSuggestionJob
        from app.services.advisor_jobs_service import purge_expired_advisor_jobs
        from app.services.advisor_suggestion_jobs_service import (
            purge_expired_advisor_suggestion_jobs,
        )

        lock_key = key_cron_lock("maintenance_tasks.cleanup_expired_advisor_jobs")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=600):
            return {"skipped": "cron_task_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                expired_count = await db.scalar(
                    select(func.count())
                    .select_from(AdvisorJob)
                    .where(AdvisorJob.expires_at.is_not(None), AdvisorJob.expires_at < func.now())
                )
                if int(expired_count or 0) > limit:
                    rows = (
                        (
                            await db.execute(
                                select(AdvisorJob.id)
                                .where(
                                    AdvisorJob.expires_at.is_not(None),
                                    AdvisorJob.expires_at < func.now(),
                                )
                                .order_by(AdvisorJob.expires_at.asc())
                                .limit(limit)
                            )
                        )
                        .scalars()
                        .all()
                    )
                    if rows:
                        await db.execute(delete(AdvisorJob).where(AdvisorJob.id.in_(list(rows))))
                        await db.commit()
                    suggestions_deleted = await purge_expired_advisor_suggestion_jobs(db)
                    return {
                        "deleted": len(rows),
                        "suggestions_deleted": suggestions_deleted,
                        "limited": True,
                    }
                deleted = await purge_expired_advisor_jobs(db)
                suggestions_deleted = await purge_expired_advisor_suggestion_jobs(db)
                return {
                    "deleted": deleted,
                    "suggestions_deleted": suggestions_deleted,
                    "limited": False,
                }
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.cleanup_expired_webhook_events",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def cleanup_expired_webhook_events_task(self, *, batch_size: int = 1000):
    async def _run():
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import delete, select

        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.models.user import PaddleWebhookEvent

        lock_key = key_cron_lock("maintenance_tasks.cleanup_expired_webhook_events")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=600):
            return {"skipped": "cron_task_already_running"}

        try:
            cutoff = datetime.now(UTC) - timedelta(days=90)
            total_deleted = 0

            async with AsyncSessionLocal() as db:
                while True:
                    ids_result = await db.execute(
                        select(PaddleWebhookEvent.id)
                        .where(
                            PaddleWebhookEvent.processing_status == "processed",
                            PaddleWebhookEvent.processed_at.is_not(None),
                            PaddleWebhookEvent.processed_at < cutoff,
                        )
                        .limit(batch_size)
                    )
                    ids = ids_result.scalars().all()
                    if not ids:
                        break
                    await db.execute(
                        delete(PaddleWebhookEvent).where(PaddleWebhookEvent.id.in_(list(ids)))
                    )
                    await db.commit()
                    total_deleted += len(ids)

                return {"deleted": total_deleted}
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.cleanup_expired_subscription_events",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def cleanup_expired_subscription_events_task(self, *, batch_size: int = 1000):
    async def _run():
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import delete, select

        from app.core.database import AsyncSessionLocal
        from app.models.user import SubscriptionEvent

        cutoff = datetime.now(UTC) - timedelta(days=365)
        total_deleted = 0

        async with AsyncSessionLocal() as db:
            while True:
                ids_result = await db.execute(
                    select(SubscriptionEvent.id)
                    .where(SubscriptionEvent.created_at < cutoff)
                    .limit(batch_size)
                )
                ids = ids_result.scalars().all()
                if not ids:
                    break
                await db.execute(
                    delete(SubscriptionEvent).where(SubscriptionEvent.id.in_(list(ids)))
                )
                await db.commit()
                total_deleted += len(ids)

            return {"deleted": total_deleted}

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.refresh_public_rankings",
    queue="intelligence",
    max_retries=2,
    ignore_result=True,
)
def refresh_public_rankings_task(self):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.utils.public.ranking_service import rebuild_public_book_rankings_snapshot

        lock_key = key_cron_lock("maintenance_tasks.refresh_public_rankings")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=900):
            return {"skipped": "cron_task_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                result = await rebuild_public_book_rankings_snapshot(db)
                await db.commit()
                return result
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(exc=exc)
