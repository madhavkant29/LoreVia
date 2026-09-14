from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.book import Book
from app.models.operations import (
    AiQualityEvent,
    BookProcessingRun,
    RevenueLedgerEvent,
    SupportIncident,
    TaskExecution,
)
from app.models.user import LlmUsageEvent, ProcessingUsageEvent, User
from app.services.operations_admin_service import (
    contribution_margin,
    dismiss_terminal_execution,
    operations_metrics,
    quality_metrics,
    retry_terminal_execution,
)


async def _user_and_book(db):
    user = User(
        email=f"ops-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"ops{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Operations",
        format="txt",
        s3_key=f"books/{uuid.uuid4()}.txt",
        status="ready",
        source_size_bytes=1024**3,
    )
    db.add(book)
    await db.flush()
    return user, book


async def test_operations_quality_and_margin_metrics_include_control_plane_allocations(
    db,
):
    baseline_quality = await quality_metrics(db)
    user, book = await _user_and_book(db)
    now = datetime.now(UTC)
    book.created_at = now - timedelta(days=10)
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_retry",
        status="succeeded",
        chapters_total=1,
        chapters_completed=1,
    )
    db.add(run)
    await db.flush()
    db.add_all(
        [
            TaskExecution(
                identity_key=uuid.uuid4().hex,
                task_name="analysis_tasks.analyse_chapter",
                feature="analysis",
                processing_run_id=run.id,
                user_id=user.id,
                book_id=book.id,
                status="succeeded",
                attempt_count=2,
                started_at=now - timedelta(seconds=20),
                completed_at=now - timedelta(seconds=10),
            ),
            AiQualityEvent(
                user_id=user.id,
                actor_user_id=user.id,
                book_id=book.id,
                entity_type="character",
                entity_id="character-1",
                outcome="corrected_after_promotion",
                model="gpt-4o-mini",
                extractor_version="v1",
            ),
            SupportIncident(
                user_id=user.id,
                book_id=book.id,
                category="ai_accuracy",
                severity="medium",
                status="open",
                summary="Correction required",
                created_by_user_id=user.id,
            ),
            LlmUsageEvent(
                user_id=user.id,
                book_id=book.id,
                provider="openai",
                model="gpt-4o-mini",
                operation="chat",
                feature="analysis",
                status="succeeded",
                total_tokens=100,
                total_cost_usd=Decimal("0.01"),
            ),
            RevenueLedgerEvent(
                user_id=user.id,
                source_event_id=uuid.uuid4().hex,
                plan="author_monthly",
                billing_interval="monthly",
                currency="USD",
                gross_amount=Decimal("20"),
                fee_amount=Decimal("1"),
                net_amount=Decimal("19"),
                pricing_version="test",
                service_period_start=now - timedelta(days=15),
                service_period_end=now + timedelta(days=15),
            ),
        ]
    )
    await db.commit()

    operations = await operations_metrics(db)
    quality = await quality_metrics(db)
    margin = await contribution_margin(db)

    assert operations["retry_count"] == 1
    analysis_task = next(
        t for t in operations["by_task"] if t["task_name"] == "analysis_tasks.analyse_chapter"
    )
    assert analysis_task["average_duration_seconds"] == 10
    assert quality["character_corrections_after_promotion"] == 1
    assert quality["support_incidents"] == baseline_quality["support_incidents"] + 1
    assert quality["processed_manuscripts"] == baseline_quality["processed_manuscripts"] + 1
    assert quality["support_incidents_per_processed_manuscript"] == round(
        quality["support_incidents"] / quality["processed_manuscripts"],
        4,
    )
    assert any(
        row["extractor_version"] == "v1" and row["model"] == "gpt-4o-mini"
        for row in quality["by_model_version"]
    )
    assert margin["worker_cost"] > 0
    assert margin["storage_cost"] > 0
    book_margin = next(row for row in margin["by_book"] if row["book_id"] == str(book.id))
    assert book_margin["allocated_revenue"] > 0
    assert "task-seconds" in margin["allocation_basis"]


async def test_admin_retry_reopens_run_and_dismiss_closes_it(db, monkeypatch):
    user, book = await _user_and_book(db)
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_retry",
        status="failed_terminal",
        completed_at=datetime.now(UTC),
    )
    db.add(run)
    await db.flush()
    execution = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="extraction_tasks.process_book",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        status="failed_terminal",
        arguments_json={"book_id": str(book.id)},
    )
    db.add(execution)
    await db.commit()
    dispatch = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "app.services.operations_admin_service.dispatch_pending_extraction_tasks",
        dispatch,
    )

    await retry_terminal_execution(db, execution.id)
    await db.refresh(run)
    assert run.status == "queued"
    assert run.completed_at is None
    dispatch.assert_awaited_once()

    execution.status = "failed_terminal"
    run.status = "failed_terminal"
    await db.commit()
    await dismiss_terminal_execution(
        db,
        execution.id,
        admin_user_id=user.id,
        reason="Known invalid source",
    )
    await db.refresh(run)
    assert run.status == "dismissed"
    assert run.completed_at is not None


async def test_admin_dismiss_clears_active_rebuild_and_releases_reservations(db):
    user, book = await _user_and_book(db)
    rebuild_run_id = uuid.uuid4().hex
    book.status = "processing"
    book.writer_workspace = {
        "reprocess": {},
        "processing": {
            "status": "paused",
            "rebuild_run_id": rebuild_run_id,
        },
    }
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        status="paused",
        rebuild_run_id=rebuild_run_id,
    )
    db.add(run)
    await db.flush()
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=f"manual:{rebuild_run_id}:chapter-1",
        word_count=100,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    execution = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="extraction_tasks.process_chapter",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        rebuild_run_id=rebuild_run_id,
        status="paused",
        arguments_json={
            "book_id": str(book.id),
            "chapter_number": 1,
            "processing_reservation_id": str(reservation.id),
        },
    )
    db.add(execution)
    await db.flush()
    reservation.task_id = str(execution.id)
    await db.commit()

    await dismiss_terminal_execution(
        db,
        execution.id,
        admin_user_id=user.id,
        reason="Cancelled after review",
    )

    await db.refresh(book)
    await db.refresh(run)
    await db.refresh(reservation)
    assert reservation.status == "released"
    assert run.status == "dismissed"
    assert book.writer_workspace["processing"].get("rebuild_run_id") is None
    assert book.writer_workspace["processing"]["status"] == "failed"


async def test_admin_retry_re_reserves_released_chapter_charge(db, monkeypatch):
    user, book = await _user_and_book(db)
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind="chapter_reprocess",
        status="failed_terminal",
    )
    db.add(run)
    await db.flush()
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="chapter_reprocess",
        source_id=uuid.uuid4().hex,
        word_count=100,
        status="released",
        released_at=datetime.now(UTC),
    )
    db.add(reservation)
    await db.flush()
    execution = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="extraction_tasks.process_chapter",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        status="failed_terminal",
        arguments_json={
            "book_id": str(book.id),
            "chapter_number": 1,
            "processing_reservation_id": str(reservation.id),
        },
    )
    db.add(execution)
    await db.flush()
    reservation.task_id = str(execution.id)
    await db.commit()
    dispatch = AsyncMock(return_value=0)
    monkeypatch.setattr(
        "app.services.operations_admin_service.dispatch_pending_extraction_tasks",
        dispatch,
    )

    await retry_terminal_execution(db, execution.id)

    await db.refresh(reservation)
    assert reservation.status == "reserved"
    assert reservation.released_at is None
    assert reservation.task_id == str(execution.id)
    dispatch.assert_awaited_once()


async def test_admin_retry_rejects_individual_failed_rebuild_task(db):
    user, book = await _user_and_book(db)
    run = BookProcessingRun(
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        status="failed_terminal",
        rebuild_run_id=uuid.uuid4().hex,
    )
    db.add(run)
    await db.flush()
    execution = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="extraction_tasks.process_chapter",
        processing_run_id=run.id,
        user_id=user.id,
        book_id=book.id,
        rebuild_run_id=run.rebuild_run_id,
        status="failed_terminal",
        arguments_json={"book_id": str(book.id), "chapter_number": 1},
    )
    db.add(execution)
    await db.commit()

    with pytest.raises(ValueError, match="cannot be retried individually"):
        await retry_terminal_execution(db, execution.id)
