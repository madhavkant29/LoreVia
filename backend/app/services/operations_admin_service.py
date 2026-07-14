from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book
from app.models.operations import (
    AiQualityEvent,
    BookProcessingRun,
    RevenueLedgerEvent,
    SupportIncident,
    TaskExecution,
)
from app.models.user import LlmUsageEvent, User
from app.services.task_execution_service import (
    EXTRACTION_TASK_NAMES,
    dispatch_pending_analysis_tasks,
    dispatch_pending_embedding_tasks,
    dispatch_pending_extraction_tasks,
)


def serialize_task_execution(row: TaskExecution) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "task_name": row.task_name,
        "feature": row.feature,
        "status": row.status,
        "user_id": str(row.user_id) if row.user_id else None,
        "book_id": str(row.book_id) if row.book_id else None,
        "chapter_number": row.chapter_number,
        "attempt_count": row.attempt_count,
        "max_attempts": row.max_attempts,
        "error_category": row.error_category,
        "error_detail": row.error_detail,
        "queued_at": row.queued_at,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "created_at": row.created_at,
    }


async def list_task_executions(
    db: AsyncSession, *, status: str | None, limit: int, offset: int
) -> list[dict[str, Any]]:
    query = select(TaskExecution).order_by(TaskExecution.created_at.desc())
    if status:
        query = query.where(TaskExecution.status == status)
    rows = (await db.execute(query.limit(limit).offset(offset))).scalars().all()
    return [serialize_task_execution(row) for row in rows]


async def retry_terminal_execution(db: AsyncSession, execution_id: uuid.UUID) -> TaskExecution:
    row = await db.get(TaskExecution, execution_id, with_for_update=True)
    if row is None:
        raise LookupError("Task execution not found")
    if row.status != "failed_terminal":
        raise ValueError("Only terminal failures can be retried")
    supported_tasks = {
        *EXTRACTION_TASK_NAMES,
        "analysis_tasks.analyse_chapter",
        "embedding_tasks.update_character_embedding",
    }
    if row.task_name not in supported_tasks:
        raise ValueError("This task type does not support administrative retry")
    if (
        row.task_name == "embedding_tasks.update_character_embedding"
        and not (row.arguments_json or {}).get("character_id")
    ):
        raise ValueError("Embedding task is missing character identity")
    row.status = "pending_dispatch"
    row.completed_at = None
    row.error_category = None
    row.error_detail = None
    row.dismissed_at = None
    if row.processing_run_id:
        run = await db.get(BookProcessingRun, row.processing_run_id, with_for_update=True)
        if run is not None:
            run.status = "queued"
            run.completed_at = None
            run.pause_reason = None
            run.resume_blockers = []
    await db.commit()
    if row.task_name in EXTRACTION_TASK_NAMES:
        await dispatch_pending_extraction_tasks(db)
    elif row.task_name == "analysis_tasks.analyse_chapter":
        await dispatch_pending_analysis_tasks(db)
    elif row.task_name == "embedding_tasks.update_character_embedding":
        await dispatch_pending_embedding_tasks(db)
    return row


async def dismiss_terminal_execution(
    db: AsyncSession, execution_id: uuid.UUID, *, admin_user_id: uuid.UUID, reason: str
) -> TaskExecution:
    row = await db.get(TaskExecution, execution_id, with_for_update=True)
    if row is None:
        raise LookupError("Task execution not found")
    if row.status not in {"failed_terminal", "paused"}:
        raise ValueError("Only failed or paused executions can be dismissed")
    row.status = "dismissed"
    row.dismissed_at = datetime.now(UTC)
    row.dismissed_by_user_id = admin_user_id
    row.dismissal_reason = reason
    if row.processing_run_id:
        run = await db.get(BookProcessingRun, row.processing_run_id, with_for_update=True)
        if run is not None:
            run.status = "dismissed"
            run.completed_at = row.dismissed_at
    await db.commit()
    return row


async def operations_metrics(db: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    total = int(await db.scalar(select(func.count(TaskExecution.id))) or 0)
    failed = int(
        await db.scalar(
            select(func.count(TaskExecution.id)).where(TaskExecution.status == "failed_terminal")
        )
        or 0
    )
    oldest = await db.scalar(
        select(func.min(TaskExecution.created_at)).where(
            TaskExecution.status.in_(("pending_dispatch", "queued"))
        )
    )
    avg_duration = await db.scalar(
        select(
            func.avg(func.extract("epoch", TaskExecution.completed_at - TaskExecution.started_at))
        ).where(TaskExecution.completed_at.is_not(None), TaskExecution.started_at.is_not(None))
    )
    paused_runs = int(
        await db.scalar(
            select(func.count(BookProcessingRun.id)).where(BookProcessingRun.status == "paused")
        )
        or 0
    )
    queue_depth = int(
        await db.scalar(
            select(func.count(TaskExecution.id)).where(
                TaskExecution.status.in_(("pending_dispatch", "queued"))
            )
        )
        or 0
    )
    running = int(
        await db.scalar(
            select(func.count(TaskExecution.id)).where(TaskExecution.status == "running")
        )
        or 0
    )
    retry_count = int(
        await db.scalar(
            select(
                func.coalesce(
                    func.sum(func.greatest(TaskExecution.attempt_count - 1, 0)),
                    0,
                )
            )
        )
        or 0
    )
    task_rows = (
        await db.execute(
            select(
                TaskExecution.task_name,
                func.count(TaskExecution.id),
                func.sum(case((TaskExecution.status == "failed_terminal", 1), else_=0)),
                func.sum(func.greatest(TaskExecution.attempt_count - 1, 0)),
                func.avg(
                    func.extract(
                        "epoch", TaskExecution.completed_at - TaskExecution.started_at
                    )
                ),
            ).group_by(TaskExecution.task_name)
        )
    ).all()
    return {
        "total_executions": total,
        "terminal_failures": failed,
        "failure_rate": round(failed / total, 4) if total else 0,
        "oldest_job_age_seconds": int((now - oldest).total_seconds()) if oldest else 0,
        "average_task_duration_seconds": round(float(avg_duration or 0), 2),
        "paused_runs": paused_runs,
        "queue_depth": queue_depth,
        "running_executions": running,
        "retry_count": retry_count,
        "by_task": [
            {
                "task_name": task_name,
                "count": int(count or 0),
                "terminal_failures": int(task_failures or 0),
                "retries": int(retries or 0),
                "average_duration_seconds": round(float(task_duration or 0), 2),
            }
            for task_name, count, task_failures, retries, task_duration in task_rows
        ],
    }


async def quality_metrics(db: AsyncSession) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(AiQualityEvent.entity_type, AiQualityEvent.outcome, func.count(AiQualityEvent.id))
            .group_by(AiQualityEvent.entity_type, AiQualityEvent.outcome)
            .order_by(AiQualityEvent.entity_type, AiQualityEvent.outcome)
        )
    ).all()
    review_outcomes = {"accepted", "promoted", "merged", "rejected", "suppressed", "resolved"}
    reviewed = sum(int(count) for _, outcome, count in rows if outcome in review_outcomes)
    accepted = sum(
        int(count) for _, outcome, count in rows if outcome in {"accepted", "promoted", "merged"}
    )
    version_rows = (
        await db.execute(
            select(
                AiQualityEvent.model,
                AiQualityEvent.extractor_version,
                AiQualityEvent.outcome,
                func.count(AiQualityEvent.id),
            ).group_by(
                AiQualityEvent.model,
                AiQualityEvent.extractor_version,
                AiQualityEvent.outcome,
            )
        )
    ).all()
    support_incidents = int(await db.scalar(select(func.count(SupportIncident.id))) or 0)
    processed_manuscripts = int(
        await db.scalar(
            select(func.count(func.distinct(BookProcessingRun.book_id))).where(
                BookProcessingRun.status == "succeeded"
            )
        )
        or 0
    )
    reprocessing_runs = int(
        await db.scalar(
            select(func.count(BookProcessingRun.id)).where(
                BookProcessingRun.run_kind.notin_(("initial_ingestion", "legacy_recovery"))
            )
        )
        or 0
    )
    character_corrections = sum(
        int(count)
        for entity_type, outcome, count in rows
        if entity_type == "character" and outcome == "corrected_after_promotion"
    )
    relationship_corrections = sum(
        int(count)
        for entity_type, outcome, count in rows
        if entity_type == "relationship" and outcome == "corrected"
    )
    return {
        "label": "Review-confirmed precision proxy",
        "reviewed": reviewed,
        "accepted": accepted,
        "acceptance_rate": round(accepted / reviewed, 4) if reviewed else None,
        "character_corrections_after_promotion": character_corrections,
        "relationship_corrections": relationship_corrections,
        "reprocessing_runs": reprocessing_runs,
        "support_incidents": support_incidents,
        "support_incidents_per_processed_manuscript": round(
            support_incidents / processed_manuscripts, 4
        )
        if processed_manuscripts
        else None,
        "breakdown": [
            {"entity_type": entity_type, "outcome": outcome, "count": int(count)}
            for entity_type, outcome, count in rows
        ],
        "by_model_version": [
            {
                "model": model,
                "extractor_version": extractor_version,
                "outcome": outcome,
                "count": int(count),
            }
            for model, extractor_version, outcome, count in version_rows
        ],
    }


async def contribution_margin(db: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    revenue_rows = (await db.execute(select(RevenueLedgerEvent))).scalars().all()
    revenue_by_user: dict[uuid.UUID, float] = {}
    for row in revenue_rows:
        duration = max((row.service_period_end - row.service_period_start).total_seconds(), 1)
        elapsed = max(
            min((now - row.service_period_start).total_seconds(), duration),
            0,
        )
        recognized = float(row.net_amount) * elapsed / duration
        revenue_by_user[row.user_id] = revenue_by_user.get(row.user_id, 0) + recognized
    revenue = sum(revenue_by_user.values())

    def add_cost(target: dict[Any, float], key: Any, value: object) -> None:
        if key is not None:
            target[key] = target.get(key, 0.0) + float(value or 0)

    feature_costs: dict[str, float] = {}
    user_costs: dict[uuid.UUID, float] = {}
    book_costs: dict[uuid.UUID, float] = {}
    book_users: dict[uuid.UUID, uuid.UUID] = {}
    llm_rows = (
        await db.execute(
            select(
                LlmUsageEvent.feature,
                LlmUsageEvent.user_id,
                LlmUsageEvent.book_id,
                func.coalesce(func.sum(LlmUsageEvent.total_cost_usd), 0),
            ).group_by(
                LlmUsageEvent.feature,
                LlmUsageEvent.user_id,
                LlmUsageEvent.book_id,
            )
        )
    ).all()
    llm_cost = 0.0
    for feature, user_id, book_id, cost in llm_rows:
        value = float(cost or 0)
        llm_cost += value
        add_cost(feature_costs, str(feature or "unattributed"), value)
        add_cost(user_costs, user_id, value)
        add_cost(book_costs, book_id, value)

    task_rows = (
        await db.execute(
            select(
                TaskExecution.feature,
                TaskExecution.user_id,
                TaskExecution.book_id,
                func.coalesce(
                    func.sum(
                        func.extract(
                            "epoch", TaskExecution.completed_at - TaskExecution.started_at
                        )
                    ),
                    0,
                ),
            )
            .where(
                TaskExecution.completed_at.is_not(None),
                TaskExecution.started_at.is_not(None),
            )
            .group_by(TaskExecution.feature, TaskExecution.user_id, TaskExecution.book_id)
        )
    ).all()
    total_task_seconds = sum(float(seconds or 0) for *_, seconds in task_rows)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )
    month_seconds = max((next_month - month_start).total_seconds(), 1)
    elapsed_month_fraction = min(max((now - month_start).total_seconds(), 0), month_seconds) / month_seconds
    worker_cost = float(settings.MONTHLY_WORKER_INFRA_COST_USD) * elapsed_month_fraction
    if total_task_seconds:
        for feature, user_id, book_id, seconds in task_rows:
            allocated = worker_cost * float(seconds or 0) / total_task_seconds
            add_cost(feature_costs, str(feature or "unattributed"), allocated)
            add_cost(user_costs, user_id, allocated)
            add_cost(book_costs, book_id, allocated)
    else:
        add_cost(feature_costs, "unallocated_worker", worker_cost)

    storage_cost = 0.0
    days_in_month = month_seconds / 86_400
    books = (
        await db.execute(
            select(
                Book.id,
                Book.user_id,
                Book.source_size_bytes,
                Book.created_at,
                Book.archived_at,
            )
        )
    ).all()
    for book_id, user_id, source_size_bytes, created_at, archived_at in books:
        book_users[book_id] = user_id
        start = max(created_at, month_start)
        end = min(archived_at or now, now)
        gb_days = max((end - start).total_seconds(), 0) / 86_400
        gb_days *= int(source_size_bytes or 0) / (1024**3)
        cost = gb_days / days_in_month * float(settings.STORAGE_COST_PER_GB_MONTH_USD)
        storage_cost += cost
        add_cost(user_costs, user_id, cost)
        add_cost(book_costs, book_id, cost)
    add_cost(feature_costs, "source_storage", storage_cost)

    total_cost = llm_cost + storage_cost + worker_cost
    feature_base = sum(feature_costs.values())
    user_book_totals: dict[uuid.UUID, float] = {}
    for book_id, cost in book_costs.items():
        add_cost(user_book_totals, book_users.get(book_id), cost)
    relevant_user_ids = set(user_costs) | set(revenue_by_user)
    tier_rows = (
        (
            await db.execute(select(User.id, User.tier).where(User.id.in_(relevant_user_ids)))
        ).all()
        if relevant_user_ids
        else []
    )
    tiers = {user_id: tier for user_id, tier in tier_rows}
    return {
        "currency": "USD",
        "recognized_net_revenue": round(revenue, 6),
        "llm_cost": round(llm_cost, 6),
        "worker_cost": round(worker_cost, 6),
        "storage_cost": round(storage_cost, 6),
        "contribution_margin": round(revenue - total_cost, 6),
        "complete": bool(feature_base and revenue_rows),
        "allocation_basis": "direct LLM cost, worker task-seconds, and source-storage GB-days",
        "by_feature": [
            {
                "feature": feature,
                "direct_cost": round(cost, 6),
                "allocated_revenue": round(revenue * cost / feature_base, 6)
                if feature_base
                else 0,
            }
            for feature, cost in sorted(feature_costs.items(), key=lambda item: -item[1])
        ],
        "by_user": [
            {
                "user_id": str(user_id),
                "tier": tiers.get(user_id),
                "recognized_revenue": round(revenue_by_user.get(user_id, 0), 6),
                "direct_cost": round(user_costs.get(user_id, 0), 6),
                "contribution_margin": round(
                    revenue_by_user.get(user_id, 0) - user_costs.get(user_id, 0), 6
                ),
            }
            for user_id in sorted(relevant_user_ids, key=str)
        ],
        "by_book": [
            {
                "book_id": str(book_id),
                "user_id": str(book_users.get(book_id)) if book_users.get(book_id) else None,
                "direct_cost": round(cost, 6),
                "allocated_revenue": round(
                    revenue_by_user.get(book_users.get(book_id), 0)
                    * cost
                    / user_book_totals.get(book_users.get(book_id), 1),
                    6,
                )
                if user_book_totals.get(book_users.get(book_id), 0)
                else 0,
            }
            for book_id, cost in sorted(book_costs.items(), key=lambda item: -item[1])
        ],
    }
