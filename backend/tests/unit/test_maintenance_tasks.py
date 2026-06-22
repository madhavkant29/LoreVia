from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.book import Book
from app.models.user import PaddleWebhookEvent, SubscriptionEvent, User
from app.workers.tasks.maintenance_tasks import (
    cleanup_expired_advisor_jobs_task,
    cleanup_expired_subscription_events_task,
    cleanup_expired_webhook_events_task,
    process_beta_reads_task,
    process_data_deletion_requests_task,
    refresh_public_rankings_task,
    repair_processing_books_task,
    send_due_trial_emails_task,
)


def _fake_run_worker_coro(coro):
    result = None
    exc = None

    def _target():
        nonlocal result, exc
        try:
            result = asyncio.run(coro)
        except Exception as e:
            exc = e

    thread = threading.Thread(target=_target)
    thread.start()
    thread.join()

    if exc:
        raise exc
    return result


def _mock_async_session_local(monkeypatch, db):
    class _SingleSessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *args):
            return False

    import app.core.database as database_module

    monkeypatch.setattr(database_module, "AsyncSessionLocal", _SingleSessionContext)
    monkeypatch.setattr(
        "app.workers.tasks.maintenance_tasks.run_worker_coro", _fake_run_worker_coro
    )


@pytest.mark.asyncio
async def test_cleanup_webhook_events(db, monkeypatch):
    now = datetime.now(UTC)

    old_processed = PaddleWebhookEvent(
        id=uuid.uuid4(),
        event_id="evt-old-processed-1",
        event_type="subscription.updated",
        processing_status="processed",
        processed_at=now - timedelta(days=120),
        first_received_at=now - timedelta(days=120),
    )
    recent_processed = PaddleWebhookEvent(
        id=uuid.uuid4(),
        event_id="evt-recent-processed-1",
        event_type="subscription.updated",
        processing_status="processed",
        processed_at=now - timedelta(days=30),
        first_received_at=now - timedelta(days=30),
    )
    pending = PaddleWebhookEvent(
        id=uuid.uuid4(),
        event_id="evt-pending-1",
        event_type="subscription.updated",
        processing_status="pending",
        first_received_at=now - timedelta(days=120),
    )
    processing = PaddleWebhookEvent(
        id=uuid.uuid4(),
        event_id="evt-processing-1",
        event_type="subscription.updated",
        processing_status="processing",
        first_received_at=now - timedelta(days=120),
    )

    db.add_all([old_processed, recent_processed, pending, processing])
    await db.commit()

    old_id = old_processed.id
    recent_id = recent_processed.id
    pending_id = pending.id
    processing_id = processing.id

    _mock_async_session_local(monkeypatch, db)

    result = cleanup_expired_webhook_events_task.run(batch_size=1000)
    assert result["deleted"] == 1

    remaining_count = await db.scalar(
        select(func.count())
        .select_from(PaddleWebhookEvent)
        .where(PaddleWebhookEvent.id.in_([old_id, recent_id, pending_id, processing_id]))
    )
    assert remaining_count == 3

    assert (
        await db.scalar(select(PaddleWebhookEvent).where(PaddleWebhookEvent.id == old_id)) is None
    )
    assert (
        await db.scalar(select(PaddleWebhookEvent).where(PaddleWebhookEvent.id == recent_id))
        is not None
    )
    assert (
        await db.scalar(select(PaddleWebhookEvent).where(PaddleWebhookEvent.id == pending_id))
        is not None
    )
    assert (
        await db.scalar(select(PaddleWebhookEvent).where(PaddleWebhookEvent.id == processing_id))
        is not None
    )


@pytest.mark.asyncio
async def test_cleanup_webhook_events_idempotent(db, monkeypatch):
    now = datetime.now(UTC)

    old = PaddleWebhookEvent(
        id=uuid.uuid4(),
        event_id="evt-old-2",
        event_type="subscription.updated",
        processing_status="processed",
        processed_at=now - timedelta(days=120),
        first_received_at=now - timedelta(days=120),
    )
    db.add(old)
    await db.commit()

    old_id = old.id

    _mock_async_session_local(monkeypatch, db)

    first = cleanup_expired_webhook_events_task.run(batch_size=1000)
    assert first["deleted"] >= 1

    second = cleanup_expired_webhook_events_task.run(batch_size=1000)
    assert second["deleted"] == 0

    assert (
        await db.scalar(select(PaddleWebhookEvent).where(PaddleWebhookEvent.id == old_id)) is None
    )


@pytest.mark.asyncio
async def test_cleanup_webhook_events_batched(db, monkeypatch):
    now = datetime.now(UTC)

    event_ids = []
    for i in range(5):
        eid = uuid.uuid4()
        event_ids.append(eid)
        db.add(
            PaddleWebhookEvent(
                id=eid,
                event_id=f"evt-batch-{i}",
                event_type="subscription.updated",
                processing_status="processed",
                processed_at=now - timedelta(days=120),
                first_received_at=now - timedelta(days=120),
            )
        )
    await db.commit()

    _mock_async_session_local(monkeypatch, db)

    result = cleanup_expired_webhook_events_task.run(batch_size=2)
    assert result["deleted"] >= 5

    for eid in event_ids:
        assert (
            await db.scalar(select(PaddleWebhookEvent).where(PaddleWebhookEvent.id == eid)) is None
        )


@pytest.mark.asyncio
async def test_cleanup_subscription_events(db, monkeypatch):
    now = datetime.now(UTC)

    user = User(
        email=f"sub-cleanup-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"subclean{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    old_event = SubscriptionEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        event_type="subscription.created",
        source="paddle",
        source_event_id=f"evt-old-{uuid.uuid4().hex}",
        occurred_at=now - timedelta(days=400),
        created_at=now - timedelta(days=400),
    )
    recent_event = SubscriptionEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        event_type="subscription.updated",
        source="paddle",
        source_event_id=f"evt-recent-{uuid.uuid4().hex}",
        occurred_at=now - timedelta(days=30),
        created_at=now - timedelta(days=30),
    )

    db.add_all([old_event, recent_event])
    await db.commit()

    old_id = old_event.id
    recent_id = recent_event.id

    _mock_async_session_local(monkeypatch, db)

    result = cleanup_expired_subscription_events_task.run(batch_size=1000)
    assert result["deleted"] == 1

    remaining_count = await db.scalar(
        select(func.count())
        .select_from(SubscriptionEvent)
        .where(SubscriptionEvent.id.in_([old_id, recent_id]))
    )
    assert remaining_count == 1

    assert await db.scalar(select(SubscriptionEvent).where(SubscriptionEvent.id == old_id)) is None
    assert (
        await db.scalar(select(SubscriptionEvent).where(SubscriptionEvent.id == recent_id))
        is not None
    )


@pytest.mark.asyncio
async def test_cleanup_subscription_events_idempotent(db, monkeypatch):
    now = datetime.now(UTC)

    user = User(
        email=f"sub-idem-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"subidem{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    old = SubscriptionEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        event_type="subscription.created",
        source="paddle",
        source_event_id=f"evt-idem-{uuid.uuid4().hex}",
        occurred_at=now - timedelta(days=400),
        created_at=now - timedelta(days=400),
    )
    db.add(old)
    await db.commit()

    old_id = old.id

    _mock_async_session_local(monkeypatch, db)

    first = cleanup_expired_subscription_events_task.run(batch_size=1000)
    assert first["deleted"] >= 1

    second = cleanup_expired_subscription_events_task.run(batch_size=1000)
    assert second["deleted"] == 0

    assert await db.scalar(select(SubscriptionEvent).where(SubscriptionEvent.id == old_id)) is None


@pytest.mark.asyncio
async def test_repair_processing_books_scan_uses_existing_book_columns(db, monkeypatch):
    user = User(
        email=f"repair-scan-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"repairscan{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    first_processing = Book(
        id=uuid.uuid4(),
        user_id=user.id,
        title="First Processing",
        format="txt",
        s3_key="books/first.txt",
        status="processing",
    )
    second_processing = Book(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Second Processing",
        format="txt",
        s3_key="books/second.txt",
        status="processing",
    )
    ready_book = Book(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Ready",
        format="txt",
        s3_key="books/ready.txt",
        status="ready",
    )
    db.add_all([first_processing, second_processing, ready_book])
    await db.commit()

    _mock_async_session_local(monkeypatch, db)

    result = repair_processing_books_task.run(limit=10)

    assert result["checked"] >= 2
    assert result["repaired"] >= 0
    assert result["requeued"] >= 0


@pytest.mark.asyncio
async def test_cron_lock_prevents_double_execution(monkeypatch):
    async def _fake_cache_set_if_absent_lock_held(key, value, ttl):
        return False

    async def _fake_cache_delete_if_owner(key, owner_token):
        return True

    monkeypatch.setattr(
        "app.core.redis.cache_set_if_absent",
        _fake_cache_set_if_absent_lock_held,
    )
    monkeypatch.setattr(
        "app.core.redis.cache_delete_if_owner",
        _fake_cache_delete_if_owner,
    )
    monkeypatch.setattr(
        "app.workers.tasks.maintenance_tasks.run_worker_coro",
        _fake_run_worker_coro,
    )

    result = send_due_trial_emails_task.run(limit=100)
    assert result["skipped"] == "cron_task_already_running"


@pytest.mark.asyncio
async def test_remaining_locked_maintenance_tasks_run_services(db, monkeypatch):
    _mock_async_session_local(monkeypatch, db)

    class BetaResult:
        def model_dump(self):
            return {"processed": 3}

    async def run_beta_reads(session, *, limit):
        assert session is db
        assert limit == 7
        return BetaResult()

    async def process_deletions(session, *, limit):
        assert session is db
        assert limit == 8
        return {"deleted": 2}

    async def rebuild_rankings(session):
        assert session is db
        return {"ranked": 11}

    monkeypatch.setattr("app.utils.beta_read_utils.run_beta_read_jobs", run_beta_reads)
    monkeypatch.setattr(
        "app.services.privacy_service.process_due_data_deletion_requests",
        process_deletions,
    )
    monkeypatch.setattr(
        "app.utils.public.ranking_service.rebuild_public_book_rankings_snapshot",
        rebuild_rankings,
    )

    assert process_beta_reads_task.run(limit=7) == {"processed": 3}
    assert process_data_deletion_requests_task.run(limit=8) == {"deleted": 2}
    assert refresh_public_rankings_task.run() == {"ranked": 11}


@pytest.mark.asyncio
async def test_cleanup_advisor_jobs_handles_limited_and_full_purges(db, monkeypatch):
    _mock_async_session_local(monkeypatch, db)
    scalar_values = iter([5, 0])
    original_scalar = db.scalar

    async def scalar(statement, *args, **kwargs):
        try:
            return next(scalar_values)
        except StopIteration:
            return await original_scalar(statement, *args, **kwargs)

    class IdResult:
        class Scalars:
            @staticmethod
            def all():
                return [uuid.uuid4(), uuid.uuid4()]

        @staticmethod
        def scalars():
            return IdResult.Scalars()

    original_execute = db.execute
    execute_calls = 0

    async def execute(statement, *args, **kwargs):
        nonlocal execute_calls
        execute_calls += 1
        if execute_calls == 1:
            return IdResult()
        return await original_execute(statement, *args, **kwargs)

    async def purge_jobs(session):
        return 4

    async def purge_suggestions(session):
        return 3

    monkeypatch.setattr(db, "scalar", scalar)
    monkeypatch.setattr(db, "execute", execute)
    monkeypatch.setattr("app.services.advisor_jobs_service.purge_expired_advisor_jobs", purge_jobs)
    monkeypatch.setattr(
        "app.services.advisor_suggestion_jobs_service.purge_expired_advisor_suggestion_jobs",
        purge_suggestions,
    )

    limited = cleanup_expired_advisor_jobs_task.run(limit=2)
    assert limited == {"deleted": 2, "suggestions_deleted": 3, "limited": True}

    full = cleanup_expired_advisor_jobs_task.run(limit=10)
    assert full == {"deleted": 4, "suggestions_deleted": 3, "limited": False}
