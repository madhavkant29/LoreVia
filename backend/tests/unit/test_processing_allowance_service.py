import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.models.user import ProcessingUsageEvent, User
from app.services.processing_allowance_service import (
    RELEASED_STATUS,
    ensure_project_writable,
    release_stale_processing_reservations,
    reserve_processing_words,
    summarize_processing_allowances,
)


def test_archived_projects_are_read_only() -> None:
    ensure_project_writable(SimpleNamespace(archived_at=None))
    try:
        ensure_project_writable(SimpleNamespace(archived_at=datetime.now(UTC)))
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("archived project should be read-only")


async def _user(db) -> User:
    user = User(
        email=f"allowance-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"allowance{uuid.uuid4().hex[:8]}",
        password_hash="fake",
    )
    db.add(user)
    await db.flush()
    return user


async def test_processing_reservation_is_idempotent_and_counted(db) -> None:
    user = await _user(db)
    event, first_summary = await reserve_processing_words(
        db,
        user,
        book_id=None,
        usage_kind="test",
        source_id="same-source",
        word_count=750,
    )
    duplicate, second_summary = await reserve_processing_words(
        db,
        user,
        book_id=None,
        usage_kind="test",
        source_id="same-source",
        word_count=750,
    )
    assert duplicate.id == event.id
    assert first_summary.monthly_processed_words == 750
    assert second_summary.monthly_processed_words == 750


async def test_stale_reservations_are_released(db) -> None:
    user = await _user(db)
    event = ProcessingUsageEvent(
        user_id=user.id,
        usage_kind="test",
        source_id="stale-source",
        word_count=500,
        status="reserved",
        reserved_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db.add(event)
    await db.flush()
    released = await release_stale_processing_reservations(db, older_than=timedelta(hours=1))
    await db.flush()
    assert released == 1
    assert event.status == RELEASED_STATUS
    assert (await summarize_processing_allowances(db, user)).monthly_processed_words == 0


async def test_concurrent_reservations_cannot_exceed_limit(db, monkeypatch) -> None:
    user = await _user(db)
    await db.commit()
    monkeypatch.setattr(settings, "PROCESSING_ALLOWANCES_MODE", "enforce")
    monkeypatch.setattr(settings, "AUTHOR_MONTHLY_PROCESSED_WORD_LIMIT", 1000)
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)

    async def reserve(source_id: str):
        async with sessions() as session:
            local_user = await session.get(User, user.id)
            try:
                await reserve_processing_words(
                    session,
                    local_user,
                    book_id=None,
                    usage_kind="concurrent-test",
                    source_id=source_id,
                    word_count=750,
                )
                await session.commit()
                return "reserved"
            except HTTPException:
                await session.rollback()
                return "blocked"

    results = await asyncio.gather(reserve("concurrent-a"), reserve("concurrent-b"))
    assert sorted(results) == ["blocked", "reserved"]
    counted = await db.scalar(
        select(func.coalesce(func.sum(ProcessingUsageEvent.word_count), 0)).where(
            ProcessingUsageEvent.user_id == user.id,
            ProcessingUsageEvent.status.in_(("reserved", "consumed")),
        )
    )
    assert int(counted or 0) == 750
