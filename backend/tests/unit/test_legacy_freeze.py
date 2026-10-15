"""Tests for the one-time global legacy freeze script and cutoff persistence."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.user import AdminAuditEvent, User
from app.services import book_freeze_service
from app.services.book_freeze_service import (
    ACTION_CUTOFF_RECORDED,
    FROZEN_USER_MESSAGE,
    is_book_frozen,
    load_persisted_freeze_cutoff,
    parse_freeze_cutoff,
    record_freeze_cutoff,
)
from scripts import freeze_legacy_manuscripts as legacy_script


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
    monkeypatch.setattr(legacy_script, "AsyncSessionLocal", lambda: _SessionCtx(db))
    return db


@pytest.fixture(autouse=True)
async def _clear_cutoff_marker(db: AsyncSession):
    """The legacy cutoff marker is global; keep tests independent."""
    await db.execute(
        delete(AdminAuditEvent).where(AdminAuditEvent.action_type == ACTION_CUTOFF_RECORDED)
    )
    await db.commit()
    yield


async def _create_user(db: AsyncSession) -> User:
    user = User(
        email=f"legacy-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"legacy{uuid.uuid4().hex[:8]}",
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
    status: str,
    age_days: float,
    editor_project: bool = False,
) -> Book:
    created_at = datetime.now(UTC) - timedelta(days=age_days)
    book = Book(
        user_id=user.id,
        title=f"Legacy {status}",
        format="txt",
        work_type="novel",
        s3_key=f"books/{user.id}/{uuid.uuid4()}/manuscript.txt",
        status=status,
        mode="author",
        language="en",
        source_kind="single_upload",
        total_chapters=3,
        is_editor_project=editor_project,
        created_at=created_at,
        writer_workspace={
            "processing": {
                "status": "failed" if status == "failed" else "processing",
                "stage": "queued",
                "started_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
            }
        },
    )
    db.add(book)
    await db.flush()
    return book


def test_parse_freeze_cutoff_handles_iso_strings_and_naive_values():
    assert parse_freeze_cutoff("2026-10-15T00:00:00Z") == datetime(2026, 10, 15, tzinfo=UTC)
    naive = parse_freeze_cutoff("2026-10-15T00:00:00")
    assert naive is not None and naive.tzinfo is UTC
    assert parse_freeze_cutoff("") is None
    assert parse_freeze_cutoff("not-a-date") is None
    assert parse_freeze_cutoff(None) is None
    aware = datetime(2026, 1, 2, tzinfo=UTC)
    assert parse_freeze_cutoff(aware) == aware


@pytest.mark.asyncio
async def test_record_freeze_cutoff_is_write_once(db: AsyncSession):
    cutoff = datetime(2026, 10, 1, tzinfo=UTC)
    assert await load_persisted_freeze_cutoff(db) is None
    assert await record_freeze_cutoff(db, cutoff=cutoff) is True
    assert await load_persisted_freeze_cutoff(db) == cutoff
    assert await record_freeze_cutoff(db, cutoff=datetime(2026, 11, 1, tzinfo=UTC)) is False
    assert await load_persisted_freeze_cutoff(db) == cutoff
    markers = (
        (
            await db.execute(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.action_type == ACTION_CUTOFF_RECORDED
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(markers) == 1


@pytest.mark.asyncio
async def test_dry_run_lists_legacy_books_without_modifying_anything(
    db: AsyncSession, capsys: pytest.CaptureFixture[str]
):
    user = await _create_user(db)
    legacy_pending = await _create_book(db, user=user, status="pending", age_days=10)
    legacy_failed = await _create_book(db, user=user, status="failed", age_days=20)
    legacy_editor = await _create_book(db, user=user, status="processing", age_days=30, editor_project=True)
    ready = await _create_book(db, user=user, status="ready", age_days=10)
    post_cutoff = await _create_book(db, user=user, status="processing", age_days=-0.05)
    await db.commit()

    result = await legacy_script.run(legacy_script.parse_args(["--json"]))
    summary = _summary_from_output(capsys)

    assert result == 0
    assert summary["applied"] is False
    assert summary["cutoff_will_be_persisted"] is True
    candidate_ids = {item["book_id"] for item in summary["results"]}
    assert str(legacy_pending.id) in candidate_ids
    assert str(legacy_failed.id) in candidate_ids
    assert str(legacy_editor.id) in candidate_ids
    assert str(ready.id) not in candidate_ids
    assert str(post_cutoff.id) not in candidate_ids
    # Nothing changed and no cutoff was persisted by a dry run.
    await db.refresh(legacy_pending)
    assert legacy_pending.status == "pending"
    assert is_book_frozen(legacy_pending) is False
    assert await load_persisted_freeze_cutoff(db) is None


@pytest.mark.asyncio
async def test_execute_freezes_all_legacy_books_and_persists_cutoff(db: AsyncSession):
    user = await _create_user(db)
    legacy_pending = await _create_book(db, user=user, status="pending", age_days=10)
    legacy_failed = await _create_book(db, user=user, status="failed", age_days=20)
    legacy_editor = await _create_book(db, user=user, status="failed", age_days=30, editor_project=True)
    post_cutoff = await _create_book(db, user=user, status="processing", age_days=-0.05)
    await db.commit()

    result = await legacy_script.run(
        legacy_script.parse_args(["--execute", "--confirm", legacy_script.CONFIRMATION_PHRASE])
    )

    assert result == 0
    for book in (legacy_pending, legacy_failed, legacy_editor):
        await db.refresh(book)
        assert book.status == "failed"
        assert is_book_frozen(book) is True
        assert book.writer_workspace["processing"]["last_error"] == FROZEN_USER_MESSAGE
    await db.refresh(post_cutoff)
    assert is_book_frozen(post_cutoff) is False
    assert await load_persisted_freeze_cutoff(db) is not None

    # A newly uploaded (post-cutoff) book must never be affected, even later.
    fresh = await _create_book(db, user=user, status="processing", age_days=0)
    await db.commit()
    await legacy_script.run(
        legacy_script.parse_args(["--execute", "--confirm", legacy_script.CONFIRMATION_PHRASE])
    )
    await db.refresh(fresh)
    assert is_book_frozen(fresh) is False
    assert fresh.status == "processing"


@pytest.mark.asyncio
async def test_execute_is_idempotent_on_repeat_runs(db: AsyncSession):
    user = await _create_user(db)
    legacy = await _create_book(db, user=user, status="pending", age_days=10)
    await db.commit()

    first = await legacy_script.run(
        legacy_script.parse_args(["--execute", "--confirm", legacy_script.CONFIRMATION_PHRASE])
    )
    digest_after_first = dict((await db.get(Book, legacy.id)).writer_workspace["processing"])

    second = await legacy_script.run(
        legacy_script.parse_args(["--execute", "--confirm", legacy_script.CONFIRMATION_PHRASE])
    )

    assert first == 0 and second == 0
    await db.refresh(legacy)
    processing = legacy.writer_workspace["processing"]
    assert processing["frozen_at"] == digest_after_first["frozen_at"]
    assert is_book_frozen(legacy) is True
    # Only one freeze audit event exists for the book.
    freeze_events = (
        (
            await db.execute(
                select(AdminAuditEvent).where(
                    AdminAuditEvent.target_book_id == legacy.id,
                    AdminAuditEvent.action_type == book_freeze_service.ACTION_FREEZE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(freeze_events) == 1


@pytest.mark.asyncio
async def test_conflicting_explicit_cutoff_is_refused(db: AsyncSession):
    user = await _create_user(db)
    await _create_book(db, user=user, status="pending", age_days=10)
    await db.commit()

    recorded = await legacy_script.run(legacy_script.parse_args(["--record-cutoff", "--execute", "--confirm", legacy_script.CONFIRMATION_PHRASE]))
    assert recorded == 0
    persisted = await load_persisted_freeze_cutoff(db)
    assert persisted is not None

    with pytest.raises(SystemExit):
        await legacy_script.run(
            legacy_script.parse_args(["--cutoff", "2000-01-01T00:00:00Z"])
        )


@pytest.mark.asyncio
async def test_record_cutoff_requires_execute_and_touches_no_book(db: AsyncSession):
    user = await _create_user(db)
    legacy = await _create_book(db, user=user, status="pending", age_days=10)
    await db.commit()

    refused = await legacy_script.run(legacy_script.parse_args(["--record-cutoff"]))
    assert refused == 2
    await db.refresh(legacy)
    assert is_book_frozen(legacy) is False
    assert await load_persisted_freeze_cutoff(db) is None

    recorded = await legacy_script.run(
        legacy_script.parse_args(
            ["--record-cutoff", "--execute", "--confirm", legacy_script.CONFIRMATION_PHRASE]
        )
    )
    assert recorded == 0
    await db.refresh(legacy)
    assert is_book_frozen(legacy) is False
    assert await load_persisted_freeze_cutoff(db) is not None


@pytest.mark.asyncio
async def test_unfreeze_requires_book_id_and_releases_only_that_book(db: AsyncSession):
    user = await _create_user(db)
    first = await _create_book(db, user=user, status="pending", age_days=10)
    second = await _create_book(db, user=user, status="pending", age_days=10)
    await db.commit()
    await legacy_script.run(
        legacy_script.parse_args(["--execute", "--confirm", legacy_script.CONFIRMATION_PHRASE])
    )
    await db.refresh(first)
    await db.refresh(second)
    assert is_book_frozen(first) and is_book_frozen(second)

    refused = await legacy_script.run(legacy_script.parse_args(["--unfreeze"]))
    assert refused == 2

    released = await legacy_script.run(
        legacy_script.parse_args(
            [
                "--unfreeze",
                "--book-id",
                str(first.id),
                "--execute",
                "--confirm",
                legacy_script.CONFIRMATION_PHRASE,
            ]
        )
    )
    assert released == 0
    await db.refresh(first)
    await db.refresh(second)
    assert is_book_frozen(first) is False
    assert is_book_frozen(second) is True
    assert "retry_extraction" in first.writer_workspace["processing"]["retry_actions"]
    # The unfreeze never enqueues work.
    from app.models.operations import TaskExecution

    pending = (
        (
            await db.execute(
                select(TaskExecution).where(
                    TaskExecution.book_id == first.id,
                    TaskExecution.status.in_(("pending_dispatch", "queued", "running")),
                )
            )
        )
        .scalars()
        .all()
    )
    assert pending == []


@pytest.mark.asyncio
async def test_explicit_book_id_cannot_bypass_the_cutoff(
    db: AsyncSession, capsys: pytest.CaptureFixture[str]
):
    user = await _create_user(db)
    recent = await _create_book(db, user=user, status="processing", age_days=0)
    await db.commit()

    result = await legacy_script.run(
        legacy_script.parse_args(
            [
                "--book-id",
                str(recent.id),
                "--cutoff",
                (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                "--json",
                "--execute",
                "--confirm",
                legacy_script.CONFIRMATION_PHRASE,
            ]
        )
    )
    summary = _summary_from_output(capsys)

    assert result == 0
    await db.refresh(recent)
    assert is_book_frozen(recent) is False
    assert summary["results"][0]["action"] == "skipped_after_cutoff"


@pytest.mark.asyncio
async def test_freeze_skips_books_processing_after_cutoff(
    db: AsyncSession, capsys: pytest.CaptureFixture[str]
):
    user = await _create_user(db)
    book = await _create_book(db, user=user, status="processing", age_days=10)
    workspace = dict(book.writer_workspace)
    workspace["processing"] = {
        **workspace["processing"],
        "started_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    book.writer_workspace = workspace
    await db.commit()

    result = await legacy_script.run(
        legacy_script.parse_args(
            [
                "--book-id",
                str(book.id),
                "--cutoff",
                (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                "--json",
                "--execute",
                "--confirm",
                legacy_script.CONFIRMATION_PHRASE,
            ]
        )
    )
    summary = _summary_from_output(capsys)

    assert result == 0
    await db.refresh(book)
    assert is_book_frozen(book) is False
    assert book.status == "processing"
    assert summary["results"][0]["action"] == "skipped_processing_after_cutoff"
