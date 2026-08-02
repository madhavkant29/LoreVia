import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book, Chapter
from app.models.intelligence import WorldBuildingDocument
from app.models.user import ProcessingUsageEvent
from app.utils.billing_utils import ARCHITECT_TIER, AUTHOR_TIER, billing_access_tier

RESERVED_STATUS = "reserved"
CONSUMED_STATUS = "consumed"
RELEASED_STATUS = "released"
COUNTED_STATUSES = (RESERVED_STATUS, CONSUMED_STATUS)


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


def allowances_enforced() -> bool:
    return settings.PROCESSING_ALLOWANCES_MODE.strip().lower() == "enforce"


def ensure_project_writable(book: object) -> None:
    if getattr(book, "archived_at", None) is not None:
        raise HTTPException(
            409, "Archived projects are read-only. Restore the project before making changes."
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
    active_manuscript_words = int(
        await db.scalar(
            select(func.coalesce(func.sum(Chapter.word_count), 0))
            .join(Book, Book.id == Chapter.book_id)
            .where(Book.user_id == user_id, Book.archived_at.is_(None))
        )
        or 0
    )
    active_world_words = int(
        await db.scalar(
            select(func.coalesce(func.sum(WorldBuildingDocument.word_count), 0))
            .join(Book, Book.id == WorldBuildingDocument.book_id)
            .where(
                Book.user_id == user_id,
                Book.archived_at.is_(None),
                WorldBuildingDocument.is_active.is_(True),
                WorldBuildingDocument.archived_at.is_(None),
            )
        )
        or 0
    )
    book_storage = int(
        await db.scalar(
            select(func.coalesce(func.sum(Book.source_size_bytes), 0)).where(
                Book.user_id == user_id
            )
        )
        or 0
    )
    world_storage = int(
        await db.scalar(
            select(func.coalesce(func.sum(WorldBuildingDocument.source_size_bytes), 0))
            .join(Book, Book.id == WorldBuildingDocument.book_id)
            .where(Book.user_id == user_id)
        )
        or 0
    )
    monthly_processed_words = int(
        await db.scalar(
            select(func.coalesce(func.sum(ProcessingUsageEvent.word_count), 0)).where(
                ProcessingUsageEvent.user_id == user_id,
                ProcessingUsageEvent.status.in_(COUNTED_STATUSES),
                ProcessingUsageEvent.reserved_at >= _month_start(now),
            )
        )
        or 0
    )
    active_limit, processed_limit, storage_limit = _tier_limits(user)
    return ProcessingAllowanceSummary(
        active_analyzed_words=active_manuscript_words + active_world_words,
        active_word_limit=active_limit,
        monthly_processed_words=monthly_processed_words,
        monthly_processed_word_limit=processed_limit,
        source_storage_bytes=book_storage + world_storage,
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
            403, "Active analyzed-word allowance exceeded. Archive a project or upgrade your plan."
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


async def consume_processing_reservation(
    db: AsyncSession, event_id: uuid.UUID, *, task_id: str | None = None
) -> None:
    event = await db.get(ProcessingUsageEvent, event_id)
    if event is None or event.status != RESERVED_STATUS:
        return
    event.status = CONSUMED_STATUS
    event.task_id = task_id or event.task_id
    event.consumed_at = datetime.now(UTC)


async def release_processing_reservation(db: AsyncSession, event_id: uuid.UUID) -> None:
    event = await db.get(ProcessingUsageEvent, event_id)
    if event is None or event.status != RESERVED_STATUS:
        return
    event.status = RELEASED_STATUS
    event.released_at = datetime.now(UTC)


async def release_stale_processing_reservations(
    db: AsyncSession,
    *,
    older_than: timedelta = timedelta(hours=1),
    limit: int = 500,
    now: datetime | None = None,
) -> int:
    """Release reservations whose dispatch or worker never reached consumption."""
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
    for event in events:
        event.status = RELEASED_STATUS
        event.released_at = current
    return len(events)
