from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import cache_del, cache_set_if_absent, mark_book_cache_dirty
from app.models.book import Chapter
from app.models.operations import BookProcessingRun, TaskDispatchOutbox, TaskExecution
from app.services.book_freeze_service import load_persisted_freeze_cutoff
from app.services.processing_pause_service import (
    parse_processing_blocker,
    parse_processing_resume_at,
    processing_rebuild_is_current,
    release_execution_processing_reservation,
    settle_terminal_processing_failure,
    write_book_pause_state,
)
from app.utils.exception_boundaries import BEST_EFFORT_CLEANUP_EXCEPTIONS

ACTIVE_EXECUTION_STATUSES = ("queued", "running")
TERMINAL_EXECUTION_STATUSES = ("succeeded", "failed_terminal", "dismissed")
DISPATCHABLE_EXECUTION_STATUSES = ("pending_dispatch", "queued")
OUTBOX_READY_STATUSES = ("pending", "publish_failed")
EXECUTION_LEASE_SECONDS = 30 * 60
OUTBOX_LEASE_SECONDS = 5 * 60
EXTRACTION_TASK_NAMES = (
    "extraction_tasks.process_book",
    "extraction_tasks.process_chapter",
    "extraction_tasks.repair_chapter_payload",
)
BOOK_SERIAL_EXTRACTION_TASK_NAMES = (
    "extraction_tasks.process_chapter",
    "extraction_tasks.repair_chapter_payload",
)
TASK_PUBLISH_EXCEPTIONS = (
    KombuOperationalError,
    RuntimeError,
    ValueError,
    KeyError,
    TypeError,
    SQLAlchemyError,
)

log = logging.getLogger("lorevia.task_execution")


async def _set_task_execution_cache_lease_best_effort(
    execution_id: uuid.UUID,
    celery_task_id: str,
) -> None:
    try:
        await cache_set_if_absent(
            f"task_execution_lease:{execution_id}",
            celery_task_id,
            EXECUTION_LEASE_SECONDS,
        )
    except BEST_EFFORT_CLEANUP_EXCEPTIONS:
        log.warning(
            "task_execution_cache_lease_set_failed execution_id=%s",
            execution_id,
            exc_info=True,
        )


async def _clear_task_execution_cache_lease_best_effort(
    execution_id: uuid.UUID,
) -> None:
    try:
        await cache_del(f"task_execution_lease:{execution_id}")
    except BEST_EFFORT_CLEANUP_EXCEPTIONS:
        log.warning(
            "task_execution_cache_lease_delete_failed execution_id=%s",
            execution_id,
            exc_info=True,
        )


def task_identity(
    task_name: str,
    *,
    processing_run_id: object | None,
    book_id: object | None,
    chapter_id: object | None = None,
    chapter_number: int | None = None,
    chapter_version_id: object | None = None,
    entity_id: object | None = None,
    rebuild_run_id: str | None = None,
    pipeline_version: str | None = None,
) -> str:
    payload = "|".join(
        str(value or "")
        for value in (
            task_name,
            processing_run_id,
            book_id,
            chapter_id or chapter_number,
            chapter_version_id,
            entity_id,
            rebuild_run_id,
            pipeline_version or settings.PROCESSING_PIPELINE_VERSION,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sanitize_task_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "book_id",
        "chapter_id",
        "chapter_number",
        "chapter_version_id",
        "rebuild_run_id",
        "manual_reprocess",
        "processing_run_id",
        "processing_reservation_id",
        "character_id",
        "reason",
    }
    return {key: value for key, value in arguments.items() if key in allowed}


def _safe_outbox_payload(execution: TaskExecution) -> dict[str, Any]:
    arguments = sanitize_task_arguments(dict(execution.arguments_json or {}))
    payload: dict[str, Any] = {
        "execution_id": str(execution.id),
        "task_name": execution.task_name,
    }
    for key in (
        "book_id",
        "chapter_id",
        "chapter_version_id",
        "rebuild_run_id",
        "processing_run_id",
        "processing_reservation_id",
        "character_id",
    ):
        value = arguments.get(key)
        if value is not None:
            payload[key] = str(value)
    if execution.book_id is not None:
        payload["book_id"] = str(execution.book_id)
    if execution.chapter_id is not None:
        payload["chapter_id"] = str(execution.chapter_id)
    if execution.chapter_version_id is not None:
        payload["chapter_version_id"] = str(execution.chapter_version_id)
    if execution.rebuild_run_id:
        payload["rebuild_run_id"] = execution.rebuild_run_id
    if execution.chapter_number is not None:
        payload["chapter_number"] = int(execution.chapter_number)
    if "manual_reprocess" in arguments:
        payload["manual_reprocess"] = bool(arguments.get("manual_reprocess"))
    return payload


def _bounded_error_detail(error: BaseException | str) -> str:
    return str(error)[:4000]


async def ensure_task_dispatch_outbox(
    db: AsyncSession,
    execution: TaskExecution,
    *,
    queue: str,
) -> TaskDispatchOutbox:
    existing = (
        await db.execute(
            select(TaskDispatchOutbox)
            .where(TaskDispatchOutbox.execution_id == execution.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is None:
        row = TaskDispatchOutbox(
            execution_id=execution.id,
            task_name=execution.task_name,
            queue=queue,
            payload_json=_safe_outbox_payload(execution),
            status="pending",
        )
        db.add(row)
        await db.flush()
        return row

    existing.task_name = execution.task_name
    existing.queue = queue
    existing.payload_json = _safe_outbox_payload(execution)
    if execution.status not in TERMINAL_EXECUTION_STATUSES:
        existing.status = "pending"
        existing.available_at = datetime.now(UTC)
        existing.lease_until = None
        existing.published_at = None
    return existing


def _outbox_backoff_seconds(attempts: int) -> int:
    return min(300, max(5, 2 ** min(attempts, 8)))


async def get_or_create_processing_run(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    run_kind: str = "initial_ingestion",
    rebuild_run_id: str | None = None,
    chapters_total: int = 0,
    reuse_active: bool = True,
) -> BookProcessingRun:
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"processing_run:{book_id}"))))
    if reuse_active:
        active_conditions = [
            BookProcessingRun.book_id == book_id,
            BookProcessingRun.status.in_(("queued", "running", "paused")),
        ]
        if rebuild_run_id is not None:
            active_conditions.append(BookProcessingRun.rebuild_run_id == rebuild_run_id)
        active = (
            (
                await db.execute(
                    select(BookProcessingRun)
                    .where(*active_conditions)
                    .order_by(BookProcessingRun.created_at.desc())
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if active is not None:
            active.chapters_total = max(active.chapters_total, chapters_total)
            return active
    run = BookProcessingRun(
        user_id=user_id,
        book_id=book_id,
        run_kind=run_kind,
        status="queued",
        rebuild_run_id=rebuild_run_id,
        chapters_total=max(chapters_total, 0),
        pipeline_version=settings.PROCESSING_PIPELINE_VERSION,
    )
    db.add(run)
    await db.flush()
    return run


async def ensure_task_execution(
    db: AsyncSession,
    *,
    task_name: str,
    processing_run: BookProcessingRun,
    chapter_id: uuid.UUID | None = None,
    chapter_number: int | None = None,
    chapter_version_id: uuid.UUID | None = None,
    rebuild_run_id: str | None = None,
    arguments: dict[str, Any] | None = None,
    feature: str = "processing",
    identity_suffix: object | None = None,
) -> TaskExecution:
    identity = task_identity(
        task_name,
        processing_run_id=processing_run.id,
        book_id=processing_run.book_id,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
        chapter_version_id=chapter_version_id,
        entity_id=identity_suffix or (arguments or {}).get("character_id"),
        rebuild_run_id=rebuild_run_id,
        pipeline_version=processing_run.pipeline_version,
    )
    existing = (
        await db.execute(select(TaskExecution).where(TaskExecution.identity_key == identity))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    execution = TaskExecution(
        identity_key=identity,
        task_name=task_name,
        feature=feature,
        processing_run_id=processing_run.id,
        user_id=processing_run.user_id,
        book_id=processing_run.book_id,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
        chapter_version_id=chapter_version_id,
        rebuild_run_id=rebuild_run_id,
        arguments_json=sanitize_task_arguments(arguments or {}),
    )
    db.add(execution)
    await db.flush()
    return execution


async def claim_task_execution(db: AsyncSession, execution_id: str, celery_task_id: str) -> bool:
    execution = await db.get(TaskExecution, uuid.UUID(execution_id), with_for_update=True)
    if execution is None or execution.status not in ACTIVE_EXECUTION_STATUSES:
        return False
    now = datetime.now(UTC)
    if execution.status == "running" and execution.locked_until and execution.locked_until > now:
        return False
    cutoff = await load_persisted_freeze_cutoff(db)
    if cutoff is not None and execution.created_at is not None and execution.created_at < cutoff:
        # Deployment transition gate: work created before the one-time legacy
        # cutoff is dismissed before any provider call. Already-delivered Celery
        # messages therefore become no-ops instead of spending tokens.
        execution.status = "dismissed"
        execution.error_category = "legacy_cutoff"
        execution.error_detail = (
            "Held by the one-time legacy freeze cutoff before any provider call."
        )
        execution.completed_at = now
        execution.locked_until = None
        await db.execute(
            update(TaskDispatchOutbox)
            .where(
                TaskDispatchOutbox.execution_id == execution.id,
                TaskDispatchOutbox.status.in_(("pending", "publishing", "publish_failed")),
            )
            .values(status="cancelled", lease_until=None, last_error="legacy_cutoff")
        )
        await release_execution_processing_reservation(db, execution)
        await db.commit()
        await _clear_task_execution_cache_lease_best_effort(execution.id)
        log.warning(
            "legacy_cutoff_execution_dismissed execution_id=%s book_id=%s",
            execution.id,
            execution.book_id,
        )
        return False
    if execution.attempt_count >= execution.max_attempts:
        execution.status = "failed_terminal"
        execution.error_category = "attempt_exhausted"
        execution.error_detail = "Task attempt budget exhausted before worker claim."
        execution.completed_at = now
        execution.locked_until = None
        await settle_terminal_processing_failure(
            db,
            execution,
            error=execution.error_detail,
            completed_at=now,
        )
        await db.commit()
        await _clear_task_execution_cache_lease_best_effort(execution.id)
        return False
    execution.status = "running"
    execution.celery_task_id = celery_task_id
    execution.attempt_count += 1
    execution.started_at = execution.started_at or now
    execution.locked_until = now + timedelta(seconds=EXECUTION_LEASE_SECONDS)
    await db.commit()
    await _set_task_execution_cache_lease_best_effort(execution.id, celery_task_id)
    import sentry_sdk

    sentry_sdk.set_tag("processing_run_id", str(execution.processing_run_id))
    sentry_sdk.set_tag("task_execution_id", str(execution.id))
    return True


async def complete_task_execution(db: AsyncSession, execution_id: str) -> None:
    execution = await db.get(TaskExecution, uuid.UUID(execution_id), with_for_update=True)
    if execution is None:
        return
    if execution.status in TERMINAL_EXECUTION_STATUSES:
        await db.commit()
        await _clear_task_execution_cache_lease_best_effort(execution.id)
        return
    now = datetime.now(UTC)
    if not await processing_rebuild_is_current(db, execution):
        execution.status = "dismissed"
        execution.error_category = "stale_rebuild"
        execution.error_detail = "The rebuild ended before this task completed."
        execution.completed_at = now
        execution.locked_until = None
        await release_execution_processing_reservation(db, execution)
        run = (
            await db.get(BookProcessingRun, execution.processing_run_id, with_for_update=True)
            if execution.processing_run_id
            else None
        )
        if run is not None and run.status not in {
            "failed_terminal",
            "dismissed",
            "succeeded",
        }:
            run.status = "dismissed"
            run.completed_at = now
        await db.commit()
        await _clear_task_execution_cache_lease_best_effort(execution.id)
        return
    if execution.task_name == "extraction_tasks.process_chapter" and execution.chapter_id:
        chapter = await db.get(Chapter, execution.chapter_id)
        if chapter is None or not chapter.processed:
            execution.status = "failed_terminal"
            execution.error_category = "extraction_incomplete"
            execution.error_detail = (
                "Chapter extraction returned without persisting a successful chapter result."
            )
            execution.completed_at = now
            execution.locked_until = None
            await settle_terminal_processing_failure(
                db,
                execution,
                error=execution.error_detail,
                completed_at=now,
            )
            await db.commit()
            await _clear_task_execution_cache_lease_best_effort(execution.id)
            return
    execution.status = "succeeded"
    execution.completed_at = now
    execution.locked_until = None
    execution.error_category = None
    execution.error_detail = None
    refresh_revision_digest = False
    if execution.task_name == "extraction_tasks.process_chapter" and execution.processing_run_id:
        from app.models.user import ProcessingUsageEvent
        from app.services.processing_allowance_service import (
            consume_processing_reservation,
        )

        reservation_id = (execution.arguments_json or {}).get("processing_reservation_id")
        reservation = (
            await db.get(ProcessingUsageEvent, uuid.UUID(str(reservation_id)))
            if reservation_id
            else (
                await db.execute(
                    select(ProcessingUsageEvent).where(
                        ProcessingUsageEvent.usage_kind == "initial_ingestion_chapter",
                        ProcessingUsageEvent.source_id
                        == f"{execution.processing_run_id}:{execution.chapter_number}",
                    )
                )
            ).scalar_one_or_none()
        )
        if reservation is not None:
            await consume_processing_reservation(
                db, reservation.id, task_id=execution.celery_task_id
            )
        run = (
            await db.get(BookProcessingRun, execution.processing_run_id, with_for_update=True)
            if execution.processing_run_id
            else None
        )
        if run is not None:
            completed = await db.scalar(
                select(func.count(TaskExecution.id)).where(
                    TaskExecution.processing_run_id == run.id,
                    TaskExecution.task_name == "extraction_tasks.process_chapter",
                    TaskExecution.status == "succeeded",
                )
            )
            run.chapters_completed = int(completed or 0)
            if run.status in {"queued", "running"}:
                run.status = "running"
                run.pause_reason = None
                run.resume_blockers = []
    elif execution.task_name == "analysis_tasks.analyse_chapter" and execution.processing_run_id:
        run = await db.get(BookProcessingRun, execution.processing_run_id, with_for_update=True)
        if run is not None:
            completed_analysis = int(
                await db.scalar(
                    select(func.count(TaskExecution.id)).where(
                        TaskExecution.processing_run_id == run.id,
                        TaskExecution.task_name == "analysis_tasks.analyse_chapter",
                        TaskExecution.status == "succeeded",
                    )
                )
                or 0
            )
            if run.chapters_total > 0 and completed_analysis >= run.chapters_total:
                run.status = "succeeded"
                run.completed_at = datetime.now(UTC)
                run.pause_reason = None
                run.resume_blockers = []
                refresh_revision_digest = True
    elif (
        execution.task_name == "extraction_tasks.repair_chapter_payload"
        and execution.processing_run_id
    ):
        run = await db.get(BookProcessingRun, execution.processing_run_id, with_for_update=True)
        if run is not None and run.run_kind == "source_recovery":
            run.chapters_completed = 1
            run.status = "succeeded"
            run.completed_at = datetime.now(UTC)
            run.pause_reason = None
            run.resume_blockers = []
    await db.commit()
    await _clear_task_execution_cache_lease_best_effort(execution.id)
    if refresh_revision_digest and execution.user_id and execution.book_id:
        from app.services.notification_service import enqueue_revision_digest_refresh

        await mark_book_cache_dirty(str(execution.book_id))
        await enqueue_revision_digest_refresh(
            user_id=execution.user_id,
            book_id=execution.book_id,
        )


async def pause_task_execution(
    db: AsyncSession, execution_id: str, *, reason: str, blocker: dict[str, Any]
) -> None:
    execution = await db.get(TaskExecution, uuid.UUID(execution_id), with_for_update=True)
    if execution is None:
        return
    if execution.status in TERMINAL_EXECUTION_STATUSES:
        await db.commit()
        await _clear_task_execution_cache_lease_best_effort(execution.id)
        return
    if not await processing_rebuild_is_current(db, execution):
        execution.status = "dismissed"
        execution.error_category = "stale_rebuild"
        execution.error_detail = "The rebuild was cancelled before this task could pause."
        execution.completed_at = datetime.now(UTC)
        execution.locked_until = None
        await release_execution_processing_reservation(db, execution)
        run = await db.get(BookProcessingRun, execution.processing_run_id, with_for_update=True)
        if run is not None and run.status not in {
            "failed_terminal",
            "dismissed",
            "succeeded",
        }:
            run.status = "dismissed"
            run.completed_at = execution.completed_at
        await db.commit()
        await _clear_task_execution_cache_lease_best_effort(execution.id)
        return
    execution.status = "paused"
    execution.error_category = reason
    execution.error_detail = json.dumps(blocker, default=str)[:4000]
    execution.locked_until = None
    run = (
        await db.get(BookProcessingRun, execution.processing_run_id, with_for_update=True)
        if execution.processing_run_id
        else None
    )
    if run is not None:
        run.status = "paused"
        run.pause_reason = reason
        run.resume_blockers = [blocker]
        run.next_chapter_number = execution.chapter_number
        run.paused_at = datetime.now(UTC)
        await write_book_pause_state(db, run, blocker=blocker)
    await db.commit()
    await _clear_task_execution_cache_lease_best_effort(execution.id)


async def resume_temporary_capacity_pauses(
    db: AsyncSession,
    *,
    limit: int = 20,
    min_age_seconds: int = 60,
    now: datetime | None = None,
) -> int:
    """Return eligible LLM capacity and token-window pauses to durable dispatch."""

    current = now or datetime.now(UTC)
    cutoff = current - timedelta(seconds=max(1, min_age_seconds))
    effective_limit = max(1, min(int(limit or 20), 20))
    executions = list(
        (
            await db.execute(
                select(TaskExecution)
                .where(
                    TaskExecution.status == "paused",
                    TaskExecution.error_category.in_(
                        ("llm_capacity", "llm_token_limit", "llm_budget")
                    ),
                )
                .order_by(TaskExecution.updated_at, TaskExecution.created_at)
                .with_for_update(skip_locked=True)
                .limit(effective_limit * 5)
            )
        )
        .scalars()
        .all()
    )
    resumed = 0
    affected_run_ids: set[uuid.UUID] = set()
    resumed_user_ids: set[uuid.UUID] = set()
    circuit_open_by_model: dict[str, bool] = {}
    if executions:
        from app.services.llm_circuit_breaker_service import provider_circuit_is_open

        provider_models = {
            (
                settings.OPENAI_EMBED_MODEL
                if row.task_name == "embedding_tasks.update_character_embedding"
                else settings.OPENAI_EXTRACT_MODEL
            )
            for row in executions
        }
        for provider_model in provider_models:
            circuit_open_by_model[provider_model] = await provider_circuit_is_open(
                provider="openai",
                model=provider_model,
            )
    for execution in executions:
        if resumed >= effective_limit or execution.user_id in resumed_user_ids:
            continue
        if not await processing_rebuild_is_current(db, execution):
            execution.status = "dismissed"
            execution.error_category = "stale_rebuild"
            execution.error_detail = "The rebuild ended before automatic resumption."
            execution.completed_at = current
            execution.locked_until = None
            await release_execution_processing_reservation(db, execution)
            run = (
                await db.get(
                    BookProcessingRun,
                    execution.processing_run_id,
                    with_for_update=True,
                )
                if execution.processing_run_id
                else None
            )
            if run is not None and run.status not in {
                "failed_terminal",
                "dismissed",
                "succeeded",
            }:
                run.status = "dismissed"
                run.completed_at = current
            continue
        provider_model = (
            settings.OPENAI_EMBED_MODEL
            if execution.task_name == "embedding_tasks.update_character_embedding"
            else settings.OPENAI_EXTRACT_MODEL
        )
        if circuit_open_by_model.get(provider_model, False):
            continue
        blocker = parse_processing_blocker(execution.error_detail)
        if execution.error_category == "llm_capacity":
            cooldowns = (60, 180, 600)
            cooldown_index = min(max(int(execution.attempt_count or 1) - 1, 0), 2)
            deterministic_jitter = int(execution.id.int % 31)
            eligible_at = execution.updated_at + timedelta(
                seconds=cooldowns[cooldown_index] + deterministic_jitter
            )
            if execution.updated_at > cutoff or eligible_at > current:
                continue
        else:
            next_resume_at = parse_processing_resume_at(blocker.get("next_resume_at"))
            if not blocker.get("auto_resume") or next_resume_at is None:
                continue
            if next_resume_at > current:
                continue
        run = (
            await db.get(
                BookProcessingRun,
                execution.processing_run_id,
                with_for_update=True,
            )
            if execution.processing_run_id
            else None
        )
        if execution.attempt_count >= execution.max_attempts:
            execution.status = "failed_terminal"
            execution.error_category = "attempt_exhausted"
            execution.error_detail = "Temporary LLM capacity remained unavailable."
            execution.completed_at = current
            await settle_terminal_processing_failure(
                db,
                execution,
                error="Automatic processing retries were exhausted.",
                completed_at=current,
            )
            resumed_user_ids.add(execution.user_id)
            continue

        execution.status = "pending_dispatch"
        execution.celery_task_id = None
        execution.queued_at = None
        execution.locked_until = None
        execution.error_category = None
        execution.error_detail = None
        resumed_user_ids.add(execution.user_id)
        if run is not None:
            affected_run_ids.add(run.id)
        resumed += 1
    for run_id in affected_run_ids:
        run = await db.get(BookProcessingRun, run_id, with_for_update=True)
        if run is None:
            continue
        remaining_paused = (
            (
                await db.execute(
                    select(TaskExecution)
                    .where(
                        TaskExecution.processing_run_id == run.id,
                        TaskExecution.status == "paused",
                    )
                    .order_by(TaskExecution.updated_at, TaskExecution.created_at)
                )
            )
            .scalars()
            .first()
        )
        if remaining_paused is not None:
            remaining_blocker = parse_processing_blocker(remaining_paused.error_detail)
            run.status = "paused"
            run.pause_reason = remaining_paused.error_category
            run.resume_blockers = [remaining_blocker]
            await write_book_pause_state(db, run, blocker=remaining_blocker)
            continue
        run.status = "queued"
        run.pause_reason = None
        run.resume_blockers = []
        run.paused_at = None
        await write_book_pause_state(db, run, blocker=None)
    await db.commit()
    return resumed


async def fail_task_execution(
    db: AsyncSession,
    execution_id: str,
    *,
    error: BaseException,
    terminal: bool,
    category: str = "unknown",
) -> None:
    execution = await db.get(TaskExecution, uuid.UUID(execution_id), with_for_update=True)
    if execution is None:
        return
    if execution.status in TERMINAL_EXECUTION_STATUSES:
        await db.commit()
        await _clear_task_execution_cache_lease_best_effort(execution.id)
        return
    now = datetime.now(UTC)
    terminal = terminal or execution.attempt_count >= execution.max_attempts
    execution.status = "failed_terminal" if terminal else "queued"
    execution.error_category = category
    execution.error_detail = str(error)[:4000]
    execution.first_failed_at = execution.first_failed_at or now
    execution.last_failed_at = now
    execution.locked_until = None
    if terminal:
        execution.completed_at = now
        await settle_terminal_processing_failure(
            db,
            execution,
            error=execution.error_detail,
            completed_at=now,
        )
    await db.commit()
    await _clear_task_execution_cache_lease_best_effort(execution.id)


async def reconcile_stale_task_dispatch_outbox(db: AsyncSession, *, limit: int = 500) -> int:
    now = datetime.now(UTC)
    rows = (
        (
            await db.execute(
                select(TaskDispatchOutbox)
                .where(
                    TaskDispatchOutbox.status == "publishing",
                    TaskDispatchOutbox.lease_until < now,
                )
                .order_by(TaskDispatchOutbox.lease_until)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    reconciled = 0
    for row in rows:
        execution = await db.get(TaskExecution, row.execution_id, with_for_update=True)
        if execution is None or execution.status in TERMINAL_EXECUTION_STATUSES:
            row.status = "cancelled"
            row.lease_until = None
        elif execution.status == "running":
            row.status = "published"
            row.published_at = row.published_at or now
            row.lease_until = None
        else:
            row.status = "pending"
            row.available_at = now
            row.lease_until = None
        reconciled += 1
    return reconciled


def _publish_outbox_task(row: TaskDispatchOutbox) -> None:
    payload = dict(row.payload_json or {})
    execution_id = str(row.execution_id)
    if row.task_name == "extraction_tasks.process_book":
        from app.workers.tasks.extraction_tasks import process_book_task

        process_book_task.apply_async(
            args=[str(payload["book_id"])],
            kwargs={"execution_id": execution_id},
            queue=row.queue,
            task_id=execution_id,
        )
        return
    if row.task_name == "extraction_tasks.process_chapter":
        from app.workers.tasks.extraction_tasks import process_chapter_task

        process_chapter_task.apply_async(
            args=[str(payload["book_id"]), int(payload.get("chapter_number") or 0)],
            kwargs={
                "chapter_version_id": payload.get("chapter_version_id"),
                "rebuild_run_id": payload.get("rebuild_run_id"),
                "manual_reprocess": bool(payload.get("manual_reprocess")),
                "execution_id": execution_id,
            },
            queue=row.queue,
            task_id=execution_id,
        )
        return
    if row.task_name == "extraction_tasks.repair_chapter_payload":
        from app.workers.tasks.extraction_tasks import repair_chapter_payload_task

        repair_chapter_payload_task.apply_async(
            args=[str(payload["book_id"]), int(payload.get("chapter_number") or 0)],
            kwargs={"execution_id": execution_id},
            queue=row.queue,
            task_id=execution_id,
        )
        return
    if row.task_name == "analysis_tasks.analyse_chapter":
        from app.workers.tasks.analysis_tasks import analyse_chapter_task

        analyse_chapter_task.apply_async(
            args=[str(payload["chapter_id"]), str(payload["book_id"])],
            kwargs={
                "is_reprocessing": True,
                "rebuild_run_id": payload.get("rebuild_run_id"),
                "manual_reprocess": bool(payload.get("manual_reprocess")),
                "execution_id": execution_id,
            },
            queue=row.queue,
            task_id=execution_id,
        )
        return
    if row.task_name == "embedding_tasks.update_character_embedding":
        from app.workers.tasks.embedding_tasks import update_character_embedding_task

        character_id = payload.get("character_id")
        if not character_id:
            raise ValueError("Embedding task is missing character identity")
        update_character_embedding_task.apply_async(
            args=[str(character_id)],
            kwargs={"execution_id": execution_id},
            queue=row.queue,
            task_id=execution_id,
        )
        return
    raise ValueError(f"Unsupported task dispatch outbox task {row.task_name}")


async def publish_task_dispatch_outbox(
    db: AsyncSession,
    *,
    queues: tuple[str, ...],
    limit: int = 100,
) -> int:
    await reconcile_stale_task_dispatch_outbox(db, limit=limit)
    now = datetime.now(UTC)
    cutoff = await load_persisted_freeze_cutoff(db)
    rows = (
        (
            await db.execute(
                select(TaskDispatchOutbox)
                .where(
                    TaskDispatchOutbox.queue.in_(queues),
                    TaskDispatchOutbox.status.in_(OUTBOX_READY_STATUSES),
                    TaskDispatchOutbox.available_at <= now,
                )
                .order_by(TaskDispatchOutbox.available_at, TaskDispatchOutbox.created_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        await db.commit()
        return 0

    for row in rows:
        row.status = "publishing"
        row.lease_until = now + timedelta(seconds=OUTBOX_LEASE_SECONDS)
        row.attempts += 1
        row.last_error = None
    await db.commit()

    published = 0
    for row in rows:
        try:
            execution = await db.get(TaskExecution, row.execution_id, with_for_update=True)
            if execution is None or execution.status in TERMINAL_EXECUTION_STATUSES:
                fresh = await db.get(TaskDispatchOutbox, row.id, with_for_update=True)
                if fresh is not None:
                    fresh.status = "cancelled"
                    fresh.lease_until = None
                await db.commit()
                continue
            if (
                cutoff is not None
                and execution.created_at is not None
                and execution.created_at < cutoff
            ):
                # Never publish pre-cutoff (legacy) work; the one-time freeze
                # owns it and it must not spend provider tokens.
                fresh = await db.get(TaskDispatchOutbox, row.id, with_for_update=True)
                if fresh is not None:
                    fresh.status = "cancelled"
                    fresh.lease_until = None
                    fresh.last_error = "legacy_cutoff"
                await db.commit()
                continue
            _publish_outbox_task(row)
            fresh = await db.get(TaskDispatchOutbox, row.id, with_for_update=True)
            execution.status = "queued"
            execution.celery_task_id = str(execution.id)
            execution.queued_at = execution.queued_at or datetime.now(UTC)
            if fresh is not None:
                fresh.status = "published"
                fresh.published_at = datetime.now(UTC)
                fresh.lease_until = None
                fresh.last_error = None
            await db.commit()
            published += 1
        except TASK_PUBLISH_EXCEPTIONS as exc:
            failed = await db.get(TaskDispatchOutbox, row.id, with_for_update=True)
            execution = await db.get(TaskExecution, row.execution_id, with_for_update=True)
            if failed is not None:
                failed.status = "publish_failed"
                failed.lease_until = None
                failed.available_at = datetime.now(UTC) + timedelta(
                    seconds=_outbox_backoff_seconds(failed.attempts)
                )
                failed.last_error = _bounded_error_detail(exc)
            if execution is not None and execution.status == "queued":
                execution.status = "pending_dispatch"
                execution.celery_task_id = None
                execution.queued_at = None
                execution.error_category = "dispatch"
                execution.error_detail = _bounded_error_detail(exc)
            await db.commit()
            log.exception("task_publish_failed execution_id=%s", row.execution_id)
    return published


async def dispatch_pending_extraction_tasks(db: AsyncSession) -> int:
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext("task_dispatch:extraction"))))
    cutoff = await load_persisted_freeze_cutoff(db)
    candidate_statement = (
        select(TaskExecution)
        .where(
            TaskExecution.task_name.in_(EXTRACTION_TASK_NAMES),
            TaskExecution.status == "pending_dispatch",
        )
        .order_by(TaskExecution.created_at, TaskExecution.chapter_number)
        .with_for_update(skip_locked=True)
        .limit(100)
    )
    if cutoff is not None:
        # Legacy executions stay pending_dispatch until the one-time freeze
        # dismisses them; they must not occupy dispatch slots or be published.
        candidate_statement = candidate_statement.where(TaskExecution.created_at >= cutoff)
    candidates = (await db.execute(candidate_statement)).scalars().all()
    if not candidates:
        await db.commit()
        return 0
    waiting_users = {row.user_id for row in candidates if row.user_id is not None}
    per_user_limit = 1 if len(waiting_users) > 1 else settings.EXTRACTION_WORKER_CONCURRENCY
    active_rows = (
        await db.execute(
            select(TaskExecution.user_id, func.count(TaskExecution.id))
            .where(
                TaskExecution.task_name.in_(EXTRACTION_TASK_NAMES),
                TaskExecution.status.in_(ACTIVE_EXECUTION_STATUSES),
            )
            .group_by(TaskExecution.user_id)
        )
    ).all()
    active = {user_id: int(count) for user_id, count in active_rows}
    active_book_ids = set(
        (
            await db.execute(
                select(TaskExecution.book_id).where(
                    TaskExecution.task_name.in_(BOOK_SERIAL_EXTRACTION_TASK_NAMES),
                    TaskExecution.status.in_(ACTIVE_EXECUTION_STATUSES),
                    TaskExecution.book_id.isnot(None),
                )
            )
        )
        .scalars()
        .all()
    )
    pending_book_heads_statement = (
        select(
            TaskExecution.book_id,
            func.min(TaskExecution.chapter_number),
        )
        .where(
            TaskExecution.task_name.in_(BOOK_SERIAL_EXTRACTION_TASK_NAMES),
            TaskExecution.status == "pending_dispatch",
            TaskExecution.book_id.isnot(None),
            TaskExecution.chapter_number.isnot(None),
        )
        .group_by(TaskExecution.book_id)
    )
    if cutoff is not None:
        pending_book_heads_statement = pending_book_heads_statement.where(
            TaskExecution.created_at >= cutoff
        )
    pending_book_heads = {
        book_id: int(chapter_number)
        for book_id, chapter_number in (await db.execute(pending_book_heads_statement)).all()
    }
    available_slots = max(
        int(settings.EXTRACTION_WORKER_CONCURRENCY) - sum(active.values()),
        0,
    )
    if available_slots == 0:
        await db.commit()
        return 0
    selected: list[TaskExecution] = []
    for row in candidates:
        if active.get(row.user_id, 0) >= per_user_limit:
            continue
        if row.task_name in BOOK_SERIAL_EXTRACTION_TASK_NAMES and row.book_id in active_book_ids:
            continue
        if (
            row.task_name in BOOK_SERIAL_EXTRACTION_TASK_NAMES
            and row.book_id is not None
            and row.chapter_number is not None
            and row.chapter_number != pending_book_heads.get(row.book_id)
        ):
            continue
        active[row.user_id] = active.get(row.user_id, 0) + 1
        if row.task_name in BOOK_SERIAL_EXTRACTION_TASK_NAMES and row.book_id is not None:
            active_book_ids.add(row.book_id)
        selected.append(row)
        if len(selected) >= available_slots:
            break
    from app.models.user import User
    from app.utils.queue_utils import queue_for_user

    user_ids = {row.user_id for row in selected if row.user_id is not None}
    users = (
        (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        if user_ids
        else []
    )
    users_by_id = {user.id: user for user in users}

    now = datetime.now(UTC)
    for row in selected:
        row.status = "queued"
        row.celery_task_id = str(row.id)
        row.queued_at = now
        queue = (
            queue_for_user(users_by_id[row.user_id], "extraction")
            if row.user_id in users_by_id
            else "extraction"
        )
        await ensure_task_dispatch_outbox(db, row, queue=queue)
    await db.commit()

    return await publish_task_dispatch_outbox(
        db, queues=("extraction", "extraction_priority"), limit=len(selected)
    )


async def enqueue_extraction_execution(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_id: uuid.UUID | None,
    chapter_number: int,
    chapters_total: int,
    chapter_version_id: uuid.UUID | None = None,
    rebuild_run_id: str | None = None,
    manual_reprocess: bool = False,
    processing_reservation_id: uuid.UUID | None = None,
    run_kind: str = "chapter_reprocess",
    identity_suffix: object | None = None,
) -> TaskExecution:
    run = await get_or_create_processing_run(
        db,
        user_id=user_id,
        book_id=book_id,
        run_kind=run_kind,
        rebuild_run_id=rebuild_run_id,
        chapters_total=chapters_total,
    )
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
        chapter_version_id=chapter_version_id,
        rebuild_run_id=rebuild_run_id,
        arguments={
            "book_id": str(book_id),
            "chapter_number": chapter_number,
            "chapter_version_id": (str(chapter_version_id) if chapter_version_id else None),
            "processing_run_id": str(run.id),
            "processing_reservation_id": (
                str(processing_reservation_id) if processing_reservation_id else None
            ),
            "manual_reprocess": manual_reprocess,
        },
        identity_suffix=identity_suffix or processing_reservation_id,
    )
    if processing_reservation_id is not None:
        from app.models.user import ProcessingUsageEvent

        reservation = await db.get(
            ProcessingUsageEvent,
            processing_reservation_id,
            with_for_update=True,
        )
        if reservation is None:
            raise RuntimeError(f"processing_reservation_missing:{processing_reservation_id}")
        reservation.task_id = str(execution.id)
        await db.flush()
    await db.commit()
    await dispatch_pending_extraction_tasks(db)
    return execution


async def enqueue_extraction_execution_batch(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    chapters: list[tuple[uuid.UUID, int]],
    chapters_total: int,
    rebuild_run_id: str | None = None,
    manual_reprocess: bool = False,
    run_kind: str = "chapter_reprocess",
) -> list[TaskExecution]:
    if not chapters:
        return []
    run = await get_or_create_processing_run(
        db,
        user_id=user_id,
        book_id=book_id,
        run_kind=run_kind,
        rebuild_run_id=rebuild_run_id,
        chapters_total=chapters_total,
    )
    executions: list[TaskExecution] = []
    for chapter_id, chapter_number in chapters:
        execution = await ensure_task_execution(
            db,
            task_name="extraction_tasks.process_chapter",
            processing_run=run,
            chapter_id=chapter_id,
            chapter_number=chapter_number,
            rebuild_run_id=rebuild_run_id,
            arguments={
                "book_id": str(book_id),
                "chapter_number": chapter_number,
                "processing_run_id": str(run.id),
                "manual_reprocess": manual_reprocess,
            },
        )
        executions.append(execution)
    await db.commit()
    await dispatch_pending_extraction_tasks(db)
    return executions


async def enqueue_chapter_repair_execution(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_id: uuid.UUID | None,
    chapter_number: int,
    chapters_total: int,
    reason: str = "source_integrity_mismatch",
) -> TaskExecution:
    run = await get_or_create_processing_run(
        db,
        user_id=user_id,
        book_id=book_id,
        run_kind="source_recovery",
        chapters_total=1,
        reuse_active=False,
    )
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.repair_chapter_payload",
        processing_run=run,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
        arguments={
            "book_id": str(book_id),
            "chapter_id": str(chapter_id) if chapter_id else None,
            "chapter_number": chapter_number,
            "processing_run_id": str(run.id),
            "reason": reason,
        },
        feature="source_recovery",
    )
    if execution.status not in TERMINAL_EXECUTION_STATUSES + ACTIVE_EXECUTION_STATUSES:
        execution.status = "pending_dispatch"
    await db.commit()
    await dispatch_pending_extraction_tasks(db)
    return execution


async def enqueue_analysis_execution(
    db: AsyncSession,
    *,
    chapter_id: uuid.UUID,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_number: int,
    chapters_total: int,
    manual_reprocess: bool = False,
    rebuild_run_id: str | None = None,
) -> TaskExecution:
    run = await get_or_create_processing_run(
        db,
        user_id=user_id,
        book_id=book_id,
        run_kind="analysis_recovery",
        rebuild_run_id=rebuild_run_id,
        chapters_total=chapters_total,
    )
    execution = await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=run,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
        rebuild_run_id=rebuild_run_id,
        arguments={
            "chapter_id": str(chapter_id),
            "book_id": str(book_id),
            "manual_reprocess": manual_reprocess,
        },
        feature="analysis",
    )
    await db.commit()
    await dispatch_pending_analysis_tasks(db)
    return execution


async def dispatch_pending_analysis_tasks(db: AsyncSession) -> int:
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext("task_dispatch:analysis"))))
    active_count = int(
        await db.scalar(
            select(func.count(TaskExecution.id)).where(
                TaskExecution.task_name == "analysis_tasks.analyse_chapter",
                TaskExecution.status.in_(ACTIVE_EXECUTION_STATUSES),
            )
        )
        or 0
    )
    available_slots = max(int(settings.ANALYSIS_WORKER_CONCURRENCY) - active_count, 0)
    if available_slots == 0:
        await db.commit()
        return 0
    cutoff = await load_persisted_freeze_cutoff(db)
    analysis_statement = (
        select(TaskExecution)
        .where(
            TaskExecution.task_name == "analysis_tasks.analyse_chapter",
            TaskExecution.status == "pending_dispatch",
        )
        .order_by(TaskExecution.created_at, TaskExecution.chapter_number)
        .with_for_update(skip_locked=True)
        .limit(available_slots)
    )
    if cutoff is not None:
        analysis_statement = analysis_statement.where(TaskExecution.created_at >= cutoff)
    candidates = (await db.execute(analysis_statement)).scalars().all()
    if not candidates:
        await db.commit()
        return 0
    from app.models.user import User
    from app.utils.queue_utils import queue_for_user

    user_ids = {row.user_id for row in candidates if row.user_id is not None}
    users = (
        (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        if user_ids
        else []
    )
    users_by_id = {user.id: user for user in users}
    now = datetime.now(UTC)
    for row in candidates:
        row.status = "queued"
        row.celery_task_id = str(row.id)
        row.queued_at = now
        queue = (
            queue_for_user(users_by_id[row.user_id], "analysis")
            if row.user_id in users_by_id
            else "analysis"
        )
        await ensure_task_dispatch_outbox(db, row, queue=queue)
    await db.commit()

    return await publish_task_dispatch_outbox(
        db, queues=("analysis", "analysis_priority"), limit=len(candidates)
    )


async def dispatch_pending_embedding_tasks(db: AsyncSession) -> int:
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext("task_dispatch:embedding"))))
    active_count = int(
        await db.scalar(
            select(func.count(TaskExecution.id)).where(
                TaskExecution.task_name == "embedding_tasks.update_character_embedding",
                TaskExecution.status.in_(ACTIVE_EXECUTION_STATUSES),
            )
        )
        or 0
    )
    available_slots = max(int(settings.EMBEDDING_WORKER_CONCURRENCY) - active_count, 0)
    if available_slots == 0:
        await db.commit()
        return 0
    cutoff = await load_persisted_freeze_cutoff(db)
    embedding_statement = (
        select(TaskExecution)
        .where(
            TaskExecution.task_name == "embedding_tasks.update_character_embedding",
            TaskExecution.status == "pending_dispatch",
        )
        .order_by(TaskExecution.created_at)
        .with_for_update(skip_locked=True)
        .limit(available_slots)
    )
    if cutoff is not None:
        embedding_statement = embedding_statement.where(TaskExecution.created_at >= cutoff)
    candidates = (await db.execute(embedding_statement)).scalars().all()
    if not candidates:
        await db.commit()
        return 0
    now = datetime.now(UTC)
    for row in candidates:
        row.status = "queued"
        row.celery_task_id = str(row.id)
        row.queued_at = now
        await ensure_task_dispatch_outbox(db, row, queue="embedding")
    await db.commit()

    return await publish_task_dispatch_outbox(db, queues=("embedding",), limit=len(candidates))


async def release_stale_task_leases(db: AsyncSession, *, limit: int = 500) -> int:
    now = datetime.now(UTC)
    rows = (
        (
            await db.execute(
                select(TaskExecution)
                .where(TaskExecution.status == "running", TaskExecution.locked_until < now)
                .order_by(TaskExecution.locked_until)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        if row.attempt_count >= row.max_attempts:
            row.status = "failed_terminal"
            row.completed_at = now
            row.error_category = "attempt_exhausted"
            row.error_detail = "Task attempt budget exhausted after stale worker lease."
            await settle_terminal_processing_failure(
                db,
                row,
                error=row.error_detail,
                completed_at=now,
            )
        else:
            row.status = "pending_dispatch"
        row.locked_until = None
        row.celery_task_id = None
        await _clear_task_execution_cache_lease_best_effort(row.id)
    return len(rows)
