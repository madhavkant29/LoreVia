import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book, Chapter
from app.models.intelligence import WorldBuildingDocument
from app.models.operations import TaskExecution
from app.models.user import ProcessingUsageEvent
from app.utils.billing_utils import ARCHITECT_TIER, AUTHOR_TIER, billing_access_tier

RESERVED_STATUS = "reserved"
CONSUMED_STATUS = "consumed"
RELEASED_STATUS = "released"
COUNTED_STATUSES = (RESERVED_STATUS, CONSUMED_STATUS)
MANUAL_REPROCESS_USAGE_KIND = "manual_reprocess"
AUTO_FIRST_REPROCESS_USAGE_KIND = "auto_first_reprocess"


def manual_reprocess_source_prefix(rebuild_run_id: str) -> str:
    return f"manual:{rebuild_run_id}:"


def auto_first_reprocess_source_prefix(rebuild_run_id: str) -> str:
    return f"auto-first:{rebuild_run_id}:"


def reprocess_source_prefix(usage_kind: str, rebuild_run_id: str) -> str | None:
    if usage_kind == MANUAL_REPROCESS_USAGE_KIND:
        return manual_reprocess_source_prefix(rebuild_run_id)
    if usage_kind == AUTO_FIRST_REPROCESS_USAGE_KIND:
        return auto_first_reprocess_source_prefix(rebuild_run_id)
    return None


def manual_reprocess_run_id_from_source(source_id: str) -> str | None:
    parts = str(source_id or "").split(":", 2)
    if len(parts) != 3 or parts[0] != "manual" or not parts[1]:
        return None
    return parts[1]


def reprocess_run_id_from_source(source_id: str, usage_kind: str) -> str | None:
    if usage_kind == MANUAL_REPROCESS_USAGE_KIND:
        return manual_reprocess_run_id_from_source(source_id)
    if usage_kind != AUTO_FIRST_REPROCESS_USAGE_KIND:
        return None
    parts = str(source_id or "").split(":", 2)
    if len(parts) != 3 or parts[0] != "auto-first" or not parts[1]:
        return None
    return parts[1]


@dataclass(frozen=True)
class ProcessingAllowanceSummary:
    active_analyzed_words: int
    active_word_limit: int
    monthly_processed_words: int
    monthly_processed_word_limit: int
    source_storage_bytes: int
    source_storage_limit_bytes: int
    allowances_enforced: bool

    @property
    def active_words_remaining(self) -> int:
        return max(self.active_word_limit - self.active_analyzed_words, 0)

    @property
    def monthly_processed_words_remaining(self) -> int:
        return max(self.monthly_processed_word_limit - self.monthly_processed_words, 0)

    @property
    def source_storage_remaining_bytes(self) -> int:
        return max(self.source_storage_limit_bytes - self.source_storage_bytes, 0)


@dataclass(frozen=True)
class ProcessingReservationRequest:
    source_id: str
    word_count: int
    task_id: str | None = None


def allowances_enforced() -> bool:
    return settings.PROCESSING_ALLOWANCES_MODE.strip().lower() == "enforce"


def ensure_project_writable(book: object) -> None:
    if getattr(book, "archived_at", None) is not None:
        raise HTTPException(
            409,
            "Archived projects are read-only. Restore the project before making changes.",
        )


def _tier_limits(user: object) -> tuple[int, int, int]:
    tier = billing_access_tier(user)
    if tier == ARCHITECT_TIER:
        return (
            settings.ARCHITECT_ACTIVE_WORD_LIMIT,
            settings.ARCHITECT_MONTHLY_PROCESSED_WORD_LIMIT,
            settings.ARCHITECT_SOURCE_STORAGE_LIMIT_BYTES,
        )
    if tier == AUTHOR_TIER:
        return (
            settings.AUTHOR_ACTIVE_WORD_LIMIT,
            settings.AUTHOR_MONTHLY_PROCESSED_WORD_LIMIT,
            settings.AUTHOR_SOURCE_STORAGE_LIMIT_BYTES,
        )
    return (0, 0, 0)


def _month_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def summarize_processing_allowances(
    db: AsyncSession,
    user: object,
    *,
    now: datetime | None = None,
) -> ProcessingAllowanceSummary:
    user_id = getattr(user, "id")
    active_manuscript_words = (
        select(func.coalesce(func.sum(Chapter.word_count), 0))
        .join(Book, Book.id == Chapter.book_id)
        .where(Book.user_id == user_id, Book.archived_at.is_(None))
        .scalar_subquery()
    )
    active_world_words = (
        select(func.coalesce(func.sum(WorldBuildingDocument.word_count), 0))
        .join(Book, Book.id == WorldBuildingDocument.book_id)
        .where(
            Book.user_id == user_id,
            Book.archived_at.is_(None),
            WorldBuildingDocument.is_active.is_(True),
            WorldBuildingDocument.archived_at.is_(None),
        )
        .scalar_subquery()
    )
    book_storage = (
        select(func.coalesce(func.sum(Book.source_size_bytes), 0))
        .where(Book.user_id == user_id)
        .scalar_subquery()
    )
    world_storage = (
        select(func.coalesce(func.sum(WorldBuildingDocument.source_size_bytes), 0))
        .join(Book, Book.id == WorldBuildingDocument.book_id)
        .where(Book.user_id == user_id)
        .scalar_subquery()
    )
    monthly_processed_words = (
        select(func.coalesce(func.sum(ProcessingUsageEvent.word_count), 0))
        .where(
            ProcessingUsageEvent.user_id == user_id,
            ProcessingUsageEvent.status.in_(COUNTED_STATUSES),
            ProcessingUsageEvent.reserved_at >= _month_start(now),
        )
        .scalar_subquery()
    )
    row = (
        await db.execute(
            select(
                active_manuscript_words.label("active_manuscript_words"),
                active_world_words.label("active_world_words"),
                book_storage.label("book_storage"),
                world_storage.label("world_storage"),
                monthly_processed_words.label("monthly_processed_words"),
            )
        )
    ).one()
    active_limit, processed_limit, storage_limit = _tier_limits(user)
    return ProcessingAllowanceSummary(
        active_analyzed_words=int(row.active_manuscript_words or 0)
        + int(row.active_world_words or 0),
        active_word_limit=active_limit,
        monthly_processed_words=int(row.monthly_processed_words or 0),
        monthly_processed_word_limit=processed_limit,
        source_storage_bytes=int(row.book_storage or 0) + int(row.world_storage or 0),
        source_storage_limit_bytes=storage_limit,
        allowances_enforced=allowances_enforced(),
    )


async def ensure_source_storage_capacity(
    db: AsyncSession,
    user: object,
    requested_bytes: int,
    *,
    released_bytes: int = 0,
) -> ProcessingAllowanceSummary:
    summary = await summarize_processing_allowances(db, user)
    projected_bytes = max(int(requested_bytes or 0) - max(int(released_bytes or 0), 0), 0)
    if allowances_enforced() and projected_bytes > summary.source_storage_remaining_bytes:
        raise HTTPException(
            403,
            "Source storage allowance exceeded. Delete stored source files or upgrade your plan.",
        )
    return summary


async def ensure_active_word_capacity(
    db: AsyncSession, user: object, requested_words: int
) -> ProcessingAllowanceSummary:
    summary = await summarize_processing_allowances(db, user)
    if allowances_enforced() and requested_words > summary.active_words_remaining:
        raise HTTPException(
            403,
            "Active analyzed-word allowance exceeded. Archive a project or upgrade your plan.",
        )
    return summary


async def reserve_processing_words(
    db: AsyncSession,
    user: object,
    *,
    book_id: uuid.UUID | None,
    usage_kind: str,
    source_id: str,
    word_count: int,
    task_id: str | None = None,
) -> tuple[ProcessingUsageEvent, ProcessingAllowanceSummary]:
    user_id = getattr(user, "id")
    existing = (
        await db.execute(
            select(ProcessingUsageEvent).where(
                ProcessingUsageEvent.user_id == user_id,
                ProcessingUsageEvent.usage_kind == usage_kind,
                ProcessingUsageEvent.source_id == source_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.status in COUNTED_STATUSES:
        return existing, await summarize_processing_allowances(db, user)

    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(user_id)))))
    existing = (
        await db.execute(
            select(ProcessingUsageEvent)
            .where(
                ProcessingUsageEvent.user_id == user_id,
                ProcessingUsageEvent.usage_kind == usage_kind,
                ProcessingUsageEvent.source_id == source_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is not None and existing.status in COUNTED_STATUSES:
        return existing, await summarize_processing_allowances(db, user)

    summary = await summarize_processing_allowances(db, user)
    requested_words = max(int(word_count or 0), 0)
    if allowances_enforced() and requested_words > summary.monthly_processed_words_remaining:
        raise HTTPException(
            403,
            "Monthly processed-word allowance exceeded. Wait for the monthly reset or upgrade your plan.",
        )

    if existing is not None:
        event = existing
        event.book_id = book_id
        event.word_count = requested_words
        event.task_id = task_id
        event.status = RESERVED_STATUS
        event.reserved_at = datetime.now(UTC)
        event.consumed_at = None
        event.released_at = None
    else:
        event = ProcessingUsageEvent(
            user_id=user_id,
            book_id=book_id,
            usage_kind=usage_kind,
            source_id=source_id,
            word_count=requested_words,
            task_id=task_id,
            status=RESERVED_STATUS,
        )
        db.add(event)
    await db.flush()
    updated = ProcessingAllowanceSummary(
        active_analyzed_words=summary.active_analyzed_words,
        active_word_limit=summary.active_word_limit,
        monthly_processed_words=summary.monthly_processed_words + requested_words,
        monthly_processed_word_limit=summary.monthly_processed_word_limit,
        source_storage_bytes=summary.source_storage_bytes,
        source_storage_limit_bytes=summary.source_storage_limit_bytes,
        allowances_enforced=summary.allowances_enforced,
    )
    return event, updated


async def reserve_processing_word_batch(
    db: AsyncSession,
    user: object,
    *,
    book_id: uuid.UUID | None,
    usage_kind: str,
    requests: list[ProcessingReservationRequest],
) -> tuple[list[ProcessingUsageEvent], ProcessingAllowanceSummary]:
    """Atomically reserve a set of independently settleable processing charges."""
    user_id = getattr(user, "id")
    normalized_requests = [
        ProcessingReservationRequest(
            source_id=str(request.source_id),
            word_count=max(int(request.word_count or 0), 0),
            task_id=request.task_id,
        )
        for request in requests
        if max(int(request.word_count or 0), 0) > 0
    ]
    if not normalized_requests:
        return [], await summarize_processing_allowances(db, user)
    source_ids = [request.source_id for request in normalized_requests]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("Processing reservation source IDs must be unique within a batch")

    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(user_id)))))
    existing_events = list(
        (
            await db.execute(
                select(ProcessingUsageEvent)
                .where(
                    ProcessingUsageEvent.user_id == user_id,
                    ProcessingUsageEvent.usage_kind == usage_kind,
                    ProcessingUsageEvent.source_id.in_(source_ids),
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    existing_by_source = {event.source_id: event for event in existing_events}
    summary = await summarize_processing_allowances(db, user)
    requested_words = sum(
        request.word_count
        for request in normalized_requests
        if existing_by_source.get(request.source_id) is None
        or existing_by_source[request.source_id].status not in COUNTED_STATUSES
    )
    if allowances_enforced() and requested_words > summary.monthly_processed_words_remaining:
        raise HTTPException(
            403,
            "Monthly processed-word allowance exceeded. Wait for the monthly reset or upgrade your plan.",
        )

    now = datetime.now(UTC)
    events: list[ProcessingUsageEvent] = []
    for request in normalized_requests:
        event = existing_by_source.get(request.source_id)
        if event is None:
            event = ProcessingUsageEvent(
                user_id=user_id,
                book_id=book_id,
                usage_kind=usage_kind,
                source_id=request.source_id,
                word_count=request.word_count,
                task_id=request.task_id,
                status=RESERVED_STATUS,
            )
            db.add(event)
        elif event.status not in COUNTED_STATUSES:
            event.book_id = book_id
            event.word_count = request.word_count
            event.task_id = request.task_id
            event.status = RESERVED_STATUS
            event.reserved_at = now
            event.consumed_at = None
            event.released_at = None
        events.append(event)

    await db.flush()
    updated = ProcessingAllowanceSummary(
        active_analyzed_words=summary.active_analyzed_words,
        active_word_limit=summary.active_word_limit,
        monthly_processed_words=summary.monthly_processed_words + requested_words,
        monthly_processed_word_limit=summary.monthly_processed_word_limit,
        source_storage_bytes=summary.source_storage_bytes,
        source_storage_limit_bytes=summary.source_storage_limit_bytes,
        allowances_enforced=summary.allowances_enforced,
    )
    return events, updated


async def consume_processing_reservation(
    db: AsyncSession, event_id: uuid.UUID, *, task_id: str | None = None
) -> None:
    event = await db.get(ProcessingUsageEvent, event_id, with_for_update=True)
    if event is None or event.status != RESERVED_STATUS:
        return
    event.status = CONSUMED_STATUS
    event.task_id = task_id or event.task_id
    event.consumed_at = datetime.now(UTC)


async def release_processing_reservation(db: AsyncSession, event_id: uuid.UUID) -> None:
    event = await db.get(ProcessingUsageEvent, event_id, with_for_update=True)
    if event is None or event.status != RESERVED_STATUS:
        return
    event.status = RELEASED_STATUS
    event.released_at = datetime.now(UTC)


async def release_processing_reservations_for_source_prefix(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    usage_kind: str,
    source_prefix: str,
    now: datetime | None = None,
) -> int:
    """Release the unfinished reservations belonging to one processing run."""
    current = now or datetime.now(UTC)
    events = list(
        (
            await db.execute(
                select(ProcessingUsageEvent)
                .where(
                    ProcessingUsageEvent.user_id == user_id,
                    ProcessingUsageEvent.book_id == book_id,
                    ProcessingUsageEvent.usage_kind == usage_kind,
                    ProcessingUsageEvent.source_id.startswith(source_prefix),
                    ProcessingUsageEvent.status == RESERVED_STATUS,
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    for event in events:
        event.status = RELEASED_STATUS
        event.released_at = current
    return len(events)


async def _processing_reservation_task(
    db: AsyncSession, task_id: str | None
) -> TaskExecution | None:
    if not task_id:
        return None
    try:
        execution_id = uuid.UUID(str(task_id))
    except (TypeError, ValueError):
        execution_id = None
    if execution_id is not None:
        execution = await db.get(TaskExecution, execution_id)
        if execution is not None:
            return execution
    return (
        (
            await db.execute(
                select(TaskExecution).where(TaskExecution.celery_task_id == str(task_id))
            )
        )
        .scalars()
        .first()
    )


async def release_stale_processing_reservations(
    db: AsyncSession,
    *,
    older_than: timedelta = timedelta(hours=1),
    limit: int = 500,
    now: datetime | None = None,
) -> int:
    """Reconcile old reservations against their durable task outcome."""
    current = now or datetime.now(UTC)
    cutoff = current - older_than
    events = (
        (
            await db.execute(
                select(ProcessingUsageEvent)
                .where(
                    ProcessingUsageEvent.status == RESERVED_STATUS,
                    ProcessingUsageEvent.reserved_at < cutoff,
                )
                .order_by(ProcessingUsageEvent.reserved_at.asc())
                .limit(max(1, min(limit, 5000)))
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    released = 0
    for event in events:
        if event.status != RESERVED_STATUS:
            continue
        execution = await _processing_reservation_task(db, event.task_id)
        if execution is not None and execution.status in {
            "pending_dispatch",
            "queued",
            "running",
            "paused",
        }:
            continue
        if (
            execution is not None
            and execution.status == "succeeded"
            and execution.task_name == "extraction_tasks.process_chapter"
        ):
            event.status = CONSUMED_STATUS
            event.consumed_at = current
            continue
        rebuild_run_id = (
            reprocess_run_id_from_source(event.source_id, event.usage_kind)
            if execution is None and event.book_id is not None
            else None
        )
        source_prefix = (
            reprocess_source_prefix(event.usage_kind, rebuild_run_id) if rebuild_run_id else None
        )
        if rebuild_run_id and source_prefix and event.book_id is not None:
            released_for_run = await release_processing_reservations_for_source_prefix(
                db,
                user_id=event.user_id,
                book_id=event.book_id,
                usage_kind=event.usage_kind,
                source_prefix=source_prefix,
                now=current,
            )
            book = await db.get(Book, event.book_id, with_for_update=True)
            if book is not None:
                from app.services.editor_project_service import fail_rebuild_if_active

                await fail_rebuild_if_active(
                    db,
                    book,
                    expected_rebuild_run_id=rebuild_run_id,
                    error="Processing stopped before every chapter task could be created.",
                )
            released += released_for_run
            continue
        event.status = RELEASED_STATUS
        event.released_at = current
        released += 1
    return released
