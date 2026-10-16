"""Tests for the fail-closed legacy rollback hold script."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.operations import TaskDispatchOutbox, TaskExecution
from app.models.user import AdminAuditEvent, User
from app.services.book_freeze_service import (
    ACTION_CUTOFF_RECORDED,
    freeze_book_processing,
    is_book_frozen,
    record_freeze_cutoff,
)
from scripts import legacy_rollback_hold as hold_script


def _summary_from_output(capsys: pytest.CaptureFixture[str]) -> dict:
    return json.loads(capsys.readouterr().out)


class _SessionCtx:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False


@pytest.fixture(autouse=True)
def _use_test_session(monkeypatch, db: AsyncSession):
    monkeypatch.setattr(hold_script, "AsyncSessionLocal", lambda: _SessionCtx(db))
    return db


@pytest.fixture(autouse=True)
async def _clear_cutoff_marker(db: AsyncSession):
    await db.execute(
        delete(AdminAuditEvent).where(AdminAuditEvent.action_type == ACTION_CUTOFF_RECORDED)
    )
    await db.commit()
    yield
    await db.execute(
        delete(AdminAuditEvent).where(AdminAuditEvent.action_type == ACTION_CUTOFF_RECORDED)
    )
    await db.commit()


async def _create_user(db: AsyncSession) -> User:
    user = User(
        email=f"rollback-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"rollback{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    return user


async def _create_book(
    db: AsyncSession,
    *,
    user: User,
    status: str = "processing",
    age_days: float = 10,
    hidden: bool = False,
) -> Book:
    created_at = datetime.now(UTC) - timedelta(days=age_days)
    book = Book(
        user_id=user.id,
        title=f"Rollback {status}",
        format="txt",
        work_type="novel",
        s3_key=f"books/{user.id}/{uuid.uuid4()}/manuscript.txt",
        status=status,
        mode="author",
        language="en",
        source_kind="single_upload",
        total_chapters=1,
        created_at=created_at,
        hidden_at=created_at if hidden else None,
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "queued",
                "started_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
            }
        },
    )
    db.add(book)
    await db.flush()
    return book


async def _create_execution(
    db: AsyncSession,
    book: Book,
    *,
    status: str = "pending_dispatch",
    created_at: datetime | None = None,
) -> TaskExecution:
    execution = TaskExecution(
        identity_key=uuid.uuid4().hex,
        task_name="extraction_tasks.process_book",
        user_id=book.user_id,
        book_id=book.id,
        status=status,
        created_at=created_at or datetime.now(UTC),
    )
    db.add(execution)
    await db.flush()
    return execution


async def _create_outbox(db: AsyncSession, execution: TaskExecution) -> TaskDispatchOutbox:
    row = TaskDispatchOutbox(
        execution_id=execution.id,
        task_name=execution.task_name,
        queue="extraction",
        payload_json={"execution_id": str(execution.id)},
        status="pending",
        available_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db.add(row)
    await db.flush()
    return row


@pytest.mark.asyncio
async def test_dry_run_changes_nothing(db: AsyncSession, capsys: pytest.CaptureFixture[str]):
    user = await _create_user(db)
    legacy = await _create_book(db, user=user)
    execution = await _create_execution(db, legacy)
    outbox = await _create_outbox(db, execution)
    await db.commit()

    result = await hold_script.run(hold_script.parse_args(["--json"]))
    summary = _summary_from_output(capsys)

    assert result == 0
    assert summary["applied"] is False
    await db.refresh(legacy)
    await db.refresh(execution)
    await db.refresh(outbox)
    assert legacy.hidden_at is None
    assert execution.status == "pending_dispatch"
    assert outbox.status == "pending"
    assert "rollback_hold" not in legacy.writer_workspace["processing"]


@pytest.mark.asyncio
async def test_refuses_execute_without_confirmation(db: AsyncSession):
    user = await _create_user(db)
    legacy = await _create_book(db, user=user)
    await db.commit()

    result = await hold_script.run(hold_script.parse_args(["--execute"]))
    assert result == 2
    await db.refresh(legacy)
    assert legacy.hidden_at is None


@pytest.mark.asyncio
async def test_hold_hides_books_and_cancels_held_work(db: AsyncSession):
    user = await _create_user(db)
    legacy = await _create_book(db, user=user)
    execution = await _create_execution(db, legacy, status="queued")
    outbox = await _create_outbox(db, execution)
    post_cutoff = await _create_book(db, user=user, age_days=0)
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))
    await db.commit()

    result = await hold_script.run(
        hold_script.parse_args(
            [
                "--book-id",
                str(legacy.id),
                "--execute",
                "--confirm",
                hold_script.CONFIRMATION_PHRASE,
            ]
        )
    )

    assert result == 0
    await db.refresh(legacy)
    await db.refresh(execution)
    await db.refresh(outbox)
    await db.refresh(post_cutoff)
    assert legacy.hidden_at is not None
    marker = legacy.writer_workspace["processing"]["rollback_hold"]
    assert marker["reason"] == "code_rollback_fail_closed"
    assert marker["previous_hidden_at"] is None
    assert execution.status == "dismissed"
    assert execution.error_category == "rollback_hold"
    assert outbox.status == "cancelled"
    assert outbox.last_error == "rollback_hold"
    assert post_cutoff.hidden_at is None
    assert "rollback_hold" not in post_cutoff.writer_workspace["processing"]


@pytest.mark.asyncio
async def test_hold_records_frozen_books_and_is_idempotent(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_book(db, user=user, status="failed")
    await db.commit()
    await freeze_book_processing(db, book_id=book.id)
    await db.refresh(book)
    assert is_book_frozen(book) is True

    first = await hold_script.run(
        hold_script.parse_args(
            [
                "--book-id",
                str(book.id),
                "--execute",
                "--confirm",
                hold_script.CONFIRMATION_PHRASE,
            ]
        )
    )
    second = await hold_script.run(
        hold_script.parse_args(
            [
                "--book-id",
                str(book.id),
                "--execute",
                "--confirm",
                hold_script.CONFIRMATION_PHRASE,
            ]
        )
    )

    assert first == 0 and second == 0
    await db.refresh(book)
    assert book.hidden_at is not None
    assert "rollback_hold" in book.writer_workspace["processing"]


@pytest.mark.asyncio
async def test_release_restores_previous_hidden_state_only_for_marked_books(
    db: AsyncSession,
):
    user = await _create_user(db)
    previously_hidden_at = datetime.now(UTC) - timedelta(days=3)
    hidden_book = await _create_book(db, user=user, hidden=True)
    hidden_book.hidden_at = previously_hidden_at
    visible_book = await _create_book(db, user=user)
    untouched = await _create_book(db, user=user, hidden=True)
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))
    await db.commit()

    await hold_script.run(
        hold_script.parse_args(
            [
                "--book-id",
                str(hidden_book.id),
                "--book-id",
                str(visible_book.id),
                "--execute",
                "--confirm",
                hold_script.CONFIRMATION_PHRASE,
            ]
        )
    )
    await db.refresh(hidden_book)
    await db.refresh(visible_book)
    assert hidden_book.hidden_at != previously_hidden_at

    result = await hold_script.run(
        hold_script.parse_args(
            ["--release", "--execute", "--confirm", hold_script.CONFIRMATION_PHRASE]
        )
    )

    assert result == 0
    await db.refresh(hidden_book)
    await db.refresh(visible_book)
    await db.refresh(untouched)
    restored = hidden_book.hidden_at
    if restored is not None and restored.tzinfo is None:
        restored = restored.replace(tzinfo=UTC)
    assert restored == previously_hidden_at
    assert visible_book.hidden_at is None
    assert "rollback_hold" not in visible_book.writer_workspace["processing"]
    # A book hidden for unrelated reasons is never unhidden by release.
    assert untouched.hidden_at is not None


@pytest.mark.asyncio
async def test_release_skips_books_without_a_marker(db: AsyncSession):
    user = await _create_user(db)
    book = await _create_book(db, user=user)
    await record_freeze_cutoff(db, cutoff=datetime.now(UTC) - timedelta(minutes=1))
    await db.commit()

    await hold_script.run(
        hold_script.parse_args(
            [
                "--book-id",
                str(book.id),
                "--execute",
                "--confirm",
                hold_script.CONFIRMATION_PHRASE,
            ]
        )
    )
    await db.refresh(book)
    book.writer_workspace = {
        "processing": {
            key: value
            for key, value in book.writer_workspace["processing"].items()
            if key != "rollback_hold"
        }
    }
    hidden_before_release = book.hidden_at
    await db.commit()

    result = await hold_script.run(
        hold_script.parse_args(
            ["--release", "--execute", "--confirm", hold_script.CONFIRMATION_PHRASE]
        )
    )

    assert result == 0
    await db.refresh(book)
    assert book.hidden_at == hidden_before_release


@pytest.mark.asyncio
async def test_executions_left_terminal_after_hold(db: AsyncSession):
    user = await _create_user(db)
    legacy = await _create_book(db, user=user)
    await db.commit()
    await freeze_book_processing(db, book_id=legacy.id)
    await db.refresh(legacy)

    result = await hold_script.run(
        hold_script.parse_args(
            [
                "--book-id",
                str(legacy.id),
                "--execute",
                "--confirm",
                hold_script.CONFIRMATION_PHRASE,
            ]
        )
    )
    assert result == 0

    non_terminal = (
        (
            await db.execute(
                select(TaskExecution).where(
                    TaskExecution.book_id == legacy.id,
                    TaskExecution.status.in_(("pending_dispatch", "queued", "running", "paused")),
                )
            )
        )
        .scalars()
        .all()
    )
    assert non_terminal == []
