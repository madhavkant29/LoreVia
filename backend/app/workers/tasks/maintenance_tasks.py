from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

from app.utils.exception_boundaries import FATAL_TASK_BOUNDARY_EXCEPTIONS
from app.utils.retry_utils import NON_LLM_MAX_RETRIES, exponential_backoff_seconds
from app.utils.worker_async_utils import run_worker_coro
from app.workers.celery_app import celery_app

log = logging.getLogger("lorevia.maintenance")


@celery_app.task(
    name="maintenance_tasks.resume_voice_chapter_reviews",
    queue="maintenance",
    ignore_result=True,
)
def resume_voice_chapter_reviews_task(*, limit: int = 50):
    """Recover paused, abandoned, and stranded chapter reviews from their checkpoints."""

    async def find_ready() -> list[str]:
        from datetime import UTC, datetime, timedelta

        from app.core.database import AsyncSessionLocal
        from app.services.voice_chapter_review_jobs_service import (
            voice_chapter_resume_candidates,
        )

        now = datetime.now(UTC)
        ready: list[str] = []
        async with AsyncSessionLocal() as db:
            rows = (
                (
                    await db.execute(
                        voice_chapter_resume_candidates(now, limit=limit).with_for_update(
                            skip_locked=True
                        )
                    )
                )
                .scalars()
                .all()
            )
            for job in rows:
                state = dict(job.result_json or {})
                updated = job.updated_at or now
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=UTC)
                if job.status == "paused":
                    raw_resume = state.get("next_resume_at")
                    if not raw_resume or datetime.fromisoformat(raw_resume) > now:
                        continue
                elif job.status == "queued" and now - updated < timedelta(minutes=5):
                    continue
                elif job.status == "running" and now - updated < timedelta(minutes=25):
                    continue
                job.status = "queued"
                job.updated_at = now
                ready.append(str(job.id))
            await db.commit()
        return ready

    from app.utils.worker_async_utils import run_worker_coro
    from app.workers.tasks.voice_chapter_tasks import review_voice_chapter_task

    for job_id in run_worker_coro(find_ready()):
        try:
            review_voice_chapter_task.apply_async(
                task_id=str(uuid.uuid4()), kwargs={"job_id": job_id}
            )
        except Exception:
            log.exception("voice_chapter_resume_enqueue_failed job_id=%s", job_id)


@celery_app.task(
    bind=True,
    name="maintenance_tasks.reconcile_upload_intents",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def reconcile_upload_intents_task(self, *, limit: int = 250):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.upload_intent_service import reconcile_stale_upload_intents

        lock_key = key_cron_lock("maintenance_tasks.reconcile_upload_intents")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=900):
            return {"skipped": "upload_intent_reconciliation_already_running"}
        try:
            async with AsyncSessionLocal() as db:
                return await reconcile_stale_upload_intents(db, limit=limit)
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.cleanup_inactive_generations",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def cleanup_inactive_generations_task(self, *, limit: int = 100):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.data_generation_service import cleanup_inactive_generations

        lock_key = key_cron_lock("maintenance_tasks.cleanup_inactive_generations")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=900):
            return {"skipped": "generation_cleanup_already_running"}
        try:
            async with AsyncSessionLocal() as db:
                deleted = await cleanup_inactive_generations(db, limit=limit)
                return {"deleted": deleted}
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.backfill_reader_events",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def backfill_reader_events_task(
    self,
    *,
    book_id: str,
    after_chapter_number: int = 0,
    after_chapter_id: str | None = None,
    limit: int = 50,
):
    """Resume a bounded ReaderEvent materialization for one book."""

    async def _run():
        import uuid

        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.reader_event_service import backfill_reader_events_for_book

        try:
            parsed_book_id = uuid.UUID(book_id)
            parsed_chapter_id = uuid.UUID(after_chapter_id) if after_chapter_id else None
        except ValueError:
            return {"skipped": "invalid_reader_event_backfill_cursor"}

        lock_key = key_cron_lock(f"maintenance_tasks.backfill_reader_events:{parsed_book_id}")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=900):
            return {"skipped": "reader_event_backfill_already_running"}
        try:
            async with AsyncSessionLocal() as db:
                result = await backfill_reader_events_for_book(
                    db,
                    book_id=parsed_book_id,
                    after_chapter_number=after_chapter_number,
                    after_chapter_id=parsed_chapter_id,
                    limit=limit,
                )
                await db.commit()
            next_cursor = result.get("next_cursor")
            if isinstance(next_cursor, dict):
                self.apply_async(
                    kwargs={
                        "book_id": str(parsed_book_id),
                        "after_chapter_number": int(next_cursor["chapter_number"]),
                        "after_chapter_id": str(next_cursor["chapter_id"]),
                        "limit": min(max(int(limit), 1), 100),
                    },
                    countdown=1,
                )
            return result
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.maintain_task_executions",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def maintain_task_executions_task(self, *, limit: int = 500):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.manuscript_export_service import (
            dispatch_pending_manuscript_export_jobs,
        )
        from app.services.manuscript_import_job_service import (
            dispatch_pending_manuscript_import_jobs,
        )
        from app.services.task_execution_service import (
            dispatch_pending_analysis_tasks,
            dispatch_pending_embedding_tasks,
            dispatch_pending_extraction_tasks,
            reconcile_stale_task_dispatch_outbox,
            release_stale_task_leases,
            resume_temporary_capacity_pauses,
        )

        lock_key = key_cron_lock("maintenance_tasks.maintain_task_executions")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=120):
            return {"skipped": "maintenance_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                timings_ms: dict[str, float] = {}
                step_started = time.perf_counter()
                released = await release_stale_task_leases(db, limit=limit)
                timings_ms["release_stale_leases"] = round(
                    (time.perf_counter() - step_started) * 1000, 2
                )
                step_started = time.perf_counter()
                reconciled_outbox = await reconcile_stale_task_dispatch_outbox(db, limit=limit)
                timings_ms["reconcile_outbox"] = round(
                    (time.perf_counter() - step_started) * 1000, 2
                )
                step_started = time.perf_counter()
                resumed_capacity_pauses = await resume_temporary_capacity_pauses(
                    db,
                    limit=limit,
                )
                timings_ms["resume_capacity_pauses"] = round(
                    (time.perf_counter() - step_started) * 1000, 2
                )
                step_started = time.perf_counter()
                extraction_dispatched = await dispatch_pending_extraction_tasks(db)
                timings_ms["dispatch_extraction"] = round(
                    (time.perf_counter() - step_started) * 1000, 2
                )
                step_started = time.perf_counter()
                analysis_dispatched = await dispatch_pending_analysis_tasks(db)
                timings_ms["dispatch_analysis"] = round(
                    (time.perf_counter() - step_started) * 1000, 2
                )
                step_started = time.perf_counter()
                embedding_dispatched = await dispatch_pending_embedding_tasks(db)
                timings_ms["dispatch_embedding"] = round(
                    (time.perf_counter() - step_started) * 1000, 2
                )
                step_started = time.perf_counter()
                manuscript_imports_dispatched = await dispatch_pending_manuscript_import_jobs(
                    db,
                    limit=min(limit, 100),
                )
                timings_ms["dispatch_manuscript_imports"] = round(
                    (time.perf_counter() - step_started) * 1000,
                    2,
                )
                step_started = time.perf_counter()
                manuscript_exports_dispatched = await dispatch_pending_manuscript_export_jobs(
                    db,
                    limit=min(limit, 100),
                )
                timings_ms["dispatch_manuscript_exports"] = round(
                    (time.perf_counter() - step_started) * 1000,
                    2,
                )
                from app.services.llm_control_service import (
                    rehydrate_llm_coordination_state,
                    settle_stale_llm_reservations,
                    summarize_monthly_processing_cost_efficiency,
                )

                stale_llm_reservations = await settle_stale_llm_reservations(
                    limit=limit,
                )
                llm_coordination = await rehydrate_llm_coordination_state()
                processing_cost_efficiency = None
                if datetime.now(UTC).minute == 0:
                    processing_cost_efficiency = await summarize_monthly_processing_cost_efficiency(
                        db
                    )
                return {
                    "released": released,
                    "reconciled_outbox": reconciled_outbox,
                    "resumed_capacity_pauses": resumed_capacity_pauses,
                    "extraction_dispatched": extraction_dispatched,
                    "analysis_dispatched": analysis_dispatched,
                    "embedding_dispatched": embedding_dispatched,
                    "manuscript_imports_dispatched": manuscript_imports_dispatched,
                    "manuscript_exports_dispatched": manuscript_exports_dispatched,
                    "dispatched": (
                        extraction_dispatched + analysis_dispatched + embedding_dispatched
                    ),
                    "llm_coordination": llm_coordination,
                    "stale_llm_reservations": stale_llm_reservations,
                    "processing_cost_efficiency": (
                        {
                            "p95_cost_per_100k_words_usd": (
                                processing_cost_efficiency.p95_cost_per_100k_words_usd
                            ),
                            "total_processing_cost_usd": (
                                processing_cost_efficiency.total_processing_cost_usd
                            ),
                            "total_processed_words": (
                                processing_cost_efficiency.total_processed_words
                            ),
                            "sampled_users": processing_cost_efficiency.sampled_users,
                            "exceeds_acceptance_threshold": (
                                processing_cost_efficiency.exceeds_acceptance_threshold
                            ),
                            "resets_at": processing_cost_efficiency.resets_at.isoformat(),
                        }
                        if processing_cost_efficiency is not None
                        else None
                    ),
                    "timings_ms": timings_ms,
                }
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.release_stale_processing_reservations",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
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
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.repair_processing_books",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def repair_processing_books_task(self, *, book_id: str | None = None, limit: int = 50):
    async def _run():
        import uuid

        from sqlalchemy import and_, or_, select
        from sqlalchemy.orm import selectinload

        from app.core.database import AsyncSessionLocal
        from app.core.redis import (
            cache_del,
            cache_delete_if_owner,
            cache_get,
            cache_set,
            cache_set_if_absent,
            key_cron_lock,
            key_maintenance_cursor,
        )
        from app.models.book import Book
        from app.services.book_freeze_service import (
            book_created_before_cutoff,
            load_persisted_freeze_cutoff,
        )
        from app.services.editor_project_service import repair_stale_editor_processing_state
        from app.services.pipeline_state_service import (
            book_processing_has_blocking_failure,
            repair_stale_completed_processing_state,
            requeue_stalled_book_processing_if_needed,
        )

        lock_scope = book_id or "scan"
        lock_key = key_cron_lock(f"maintenance_tasks.repair_processing_books:{lock_scope}")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=300):
            return {"skipped": "repair_already_running"}

        try:
            started_at = time.perf_counter()
            async with AsyncSessionLocal() as db:
                wrapped_cursor = False
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
                    cursor_key = key_maintenance_cursor("repair_processing_books")
                    cursor = await cache_get(cursor_key)
                    statement = (
                        select(Book)
                        .where(Book.status == "processing")
                        .options(selectinload(Book.chapters))
                        .order_by(Book.created_at.asc(), Book.id.asc())
                        .limit(limit)
                    )
                    if isinstance(cursor, dict):
                        try:
                            cursor_created_at = datetime.fromisoformat(str(cursor["created_at"]))
                            cursor_id = uuid.UUID(str(cursor["book_id"]))
                            statement = statement.where(
                                or_(
                                    Book.created_at > cursor_created_at,
                                    and_(
                                        Book.created_at == cursor_created_at,
                                        Book.id > cursor_id,
                                    ),
                                )
                            )
                        except (KeyError, TypeError, ValueError):
                            await cache_del(cursor_key)
                            cursor = None
                    books = list((await db.execute(statement)).scalars().all())
                    if not books and cursor is not None:
                        wrapped_cursor = True
                        await cache_del(cursor_key)
                        books = list(
                            (
                                await db.execute(
                                    select(Book)
                                    .where(Book.status == "processing")
                                    .options(selectinload(Book.chapters))
                                    .order_by(Book.created_at.asc(), Book.id.asc())
                                    .limit(limit)
                                )
                            )
                            .scalars()
                            .all()
                        )
                    if books:
                        last_book = books[-1]
                        await cache_set(
                            cursor_key,
                            {
                                "created_at": last_book.created_at.isoformat(),
                                "book_id": str(last_book.id),
                            },
                            ttl=24 * 60 * 60,
                        )

                repaired = 0
                requeued = 0
                legacy_freeze_cutoff = await load_persisted_freeze_cutoff(db)
                held_for_legacy_freeze = 0
                for book in books:
                    if book.status != "processing":
                        continue
                    book_requeued = await requeue_stalled_book_processing_if_needed(
                        db,
                        book=book,
                        chapters=list(book.chapters),
                    )
                    if book_requeued:
                        requeued += 1
                    book_repaired = await repair_stale_completed_processing_state(db, book)
                    if book_repaired:
                        repaired += 1
                    if await repair_stale_editor_processing_state(db, book):
                        book_repaired = True
                        repaired += 1
                    if (
                        not book_requeued
                        and not book_repaired
                        and book.status == "processing"
                        and book_processing_has_blocking_failure(book)
                    ):
                        if book_created_before_cutoff(book, legacy_freeze_cutoff):
                            # The cutoff deliberately holds these books until
                            # the one-time freeze. Repeating an error on every
                            # sweep cannot recover or unblock them.
                            held_for_legacy_freeze += 1
                            continue
                        # Alertable signal: a book cannot finish on its own and
                        # the repair sweep cannot resolve it. Operators can find
                        # it by book_id without reading manuscript contents.
                        log.error(
                            "book_processing_stuck book_id=%s user_id=%s",
                            book.id,
                            book.user_id,
                        )
                await db.commit()
                return {
                    "checked": len(books),
                    "repaired": repaired,
                    "requeued": requeued,
                    "held_for_legacy_freeze": held_for_legacy_freeze,
                    "wrapped_cursor": wrapped_cursor,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                }
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.refresh_revision_digest_notification",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def refresh_revision_digest_notification_task(
    self,
    *,
    user_id: str,
    book_id: str,
    owner_token: str,
):
    async def _run():
        import uuid

        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, key_revision_digest_refresh
        from app.services.notification_service import refresh_revision_digest_for_book

        lock_key = key_revision_digest_refresh(book_id)
        try:
            async with AsyncSessionLocal() as db:
                changed = await refresh_revision_digest_for_book(db, uuid.UUID(book_id))
                return {"book_id": book_id, "user_id": user_id, "changed": changed}
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.send_due_trial_emails",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
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
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.send_due_subscription_emails",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def send_due_subscription_emails_task(self, *, limit: int = 100):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.subscription_email_service import send_due_subscription_emails

        lock_key = key_cron_lock("maintenance_tasks.send_due_subscription_emails")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=600):
            return {"skipped": "cron_task_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                result = await send_due_subscription_emails(db, limit=limit)
                await db.commit()
                return result
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.reconcile_paddle_subscriptions",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def reconcile_paddle_subscriptions_task(self, *, limit: int = 25):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.subscription_reconciliation_service import (
            reconcile_stale_subscriptions,
        )

        lock_key = key_cron_lock("maintenance_tasks.reconcile_paddle_subscriptions")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=1800):
            return {"skipped": "cron_task_already_running"}

        try:
            async with AsyncSessionLocal() as db:
                result = await reconcile_stale_subscriptions(db, limit=limit)
                await db.commit()
                return result
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.process_beta_reads",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
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
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.process_data_deletion_requests",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
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
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.backfill_public_assets",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def backfill_public_assets_task(self, *, limit: int = 10):
    async def _run():
        import uuid

        from app.core.database import AsyncSessionLocal
        from app.core.redis import (
            cache_del,
            cache_delete_if_owner,
            cache_get,
            cache_set,
            cache_set_if_absent,
            key_cron_lock,
            key_maintenance_cursor,
        )
        from app.services.public_asset_service import backfill_public_book_assets_page

        lock_key = key_cron_lock("maintenance_tasks.backfill_public_assets")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=1800):
            return {"skipped": "backfill_already_running"}
        cursor_key = key_maintenance_cursor("public_asset_backfill")
        try:
            raw_cursor = await cache_get(cursor_key)
            try:
                after_book_id = uuid.UUID(str(raw_cursor)) if raw_cursor else None
            except ValueError:
                after_book_id = None
            async with AsyncSessionLocal() as db:
                published, next_cursor = await backfill_public_book_assets_page(
                    db,
                    after_book_id=after_book_id,
                    limit=limit,
                )
            if next_cursor:
                await cache_set(cursor_key, next_cursor, ttl=7 * 24 * 60 * 60)
            else:
                await cache_del(cursor_key)
            return {"published": published, "next_cursor": next_cursor}
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.cleanup_expired_manuscript_exports",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def cleanup_expired_manuscript_exports_task(self, *, limit: int = 250):
    async def _run():
        from app.core.database import AsyncSessionLocal
        from app.core.redis import cache_delete_if_owner, cache_set_if_absent, key_cron_lock
        from app.services.manuscript_export_service import cleanup_expired_manuscript_export_jobs

        lock_key = key_cron_lock("maintenance_tasks.cleanup_expired_manuscript_exports")
        owner_token = self.request.id or "unknown"
        if not await cache_set_if_absent(lock_key, owner_token, ttl=600):
            return {"skipped": "cleanup_already_running"}
        try:
            async with AsyncSessionLocal() as db:
                deleted = await cleanup_expired_manuscript_export_jobs(db, limit=limit)
                return {"expired": deleted}
        finally:
            await cache_delete_if_owner(lock_key, owner_token)

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.cleanup_expired_advisor_jobs",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
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
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.cleanup_expired_webhook_events",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
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
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.cleanup_expired_subscription_events",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
    ignore_result=True,
)
def cleanup_expired_subscription_events_task(self, *, batch_size: int = 1000):
    async def _run():
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import delete, select

        from app.core.database import AsyncSessionLocal
        from app.models.user import SubscriptionEmailEvent, SubscriptionEvent

        cutoff = datetime.now(UTC) - timedelta(days=365)
        total_deleted = 0
        email_events_deleted = 0

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

            while True:
                email_ids_result = await db.execute(
                    select(SubscriptionEmailEvent.id)
                    .where(SubscriptionEmailEvent.created_at < cutoff)
                    .limit(batch_size)
                )
                email_ids = email_ids_result.scalars().all()
                if not email_ids:
                    break
                await db.execute(
                    delete(SubscriptionEmailEvent).where(
                        SubscriptionEmailEvent.id.in_(list(email_ids))
                    )
                )
                await db.commit()
                email_events_deleted += len(email_ids)

            return {
                "deleted": total_deleted,
                "email_events_deleted": email_events_deleted,
            }

    try:
        return run_worker_coro(_run())
    except FATAL_TASK_BOUNDARY_EXCEPTIONS as exc:
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )


@celery_app.task(
    bind=True,
    name="maintenance_tasks.refresh_public_rankings",
    queue="maintenance",
    max_retries=NON_LLM_MAX_RETRIES,
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
        raise self.retry(
            exc=exc,
            countdown=exponential_backoff_seconds(self.request.retries),
        )
