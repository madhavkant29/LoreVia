from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter, Series, SeriesBook
from app.models.intelligence import WorldAnalysisState, WorldSourceObservation
from app.models.user import User
from app.services.world_analysis_state_service import (
    build_book_world_input_fingerprint,
    build_series_world_input_fingerprint,
    content_sha256,
    mark_book_world_analysis_running,
    mark_book_world_analysis_stale,
    mark_world_analysis_failed,
    publish_book_world_analysis,
    record_world_source_observations,
    snapshot_freshness,
)


async def _book(db, *, email: str = "world-state@example.com") -> tuple[User, Book]:
    user = User(email=email, password_hash="hashed")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="The Persisted World",
        format="pdf",
        s3_key="books/persisted-world.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    return user, book


def test_content_sha256_is_stable_for_text_and_bytes():
    assert content_sha256("same source") == content_sha256(b"same source")
    assert len(content_sha256("same source")) == 64
    assert content_sha256("same source") != content_sha256("changed source")


@pytest.mark.asyncio
async def test_book_fingerprint_changes_when_persisted_chapter_version_changes(db):
    _, book = await _book(db)
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Threshold",
        s3_key="chapters/persisted-world/1.json",
        content_version=1,
    )
    db.add(chapter)
    await db.flush()

    before = await build_book_world_input_fingerprint(db, book.id)
    chapter.content_version = 2
    await db.flush()
    after = await build_book_world_input_fingerprint(db, book.id)

    assert before != after


@pytest.mark.asyncio
async def test_publish_and_stale_keep_last_completed_snapshot_readable(db):
    _, book = await _book(db)
    state = await publish_book_world_analysis(
        db,
        book_id=book.id,
        mode="gap_detection",
        payload={"priority_gaps": [{"id": "gap-1"}], "world_elements": []},
    )
    ready = snapshot_freshness(state, input_fingerprint=state.input_fingerprint or "")

    assert ready["status"] == "ready"
    assert ready["is_stale"] is False
    assert ready["has_snapshot"] is True
    assert state.payload["gap_analysis"]["priority_gaps"][0]["id"] == "gap-1"

    state.completed_at = datetime.now(UTC) - timedelta(seconds=1)
    await mark_book_world_analysis_stale(db, book_id=book.id, refresh_job_id="world-refresh-1")
    stale = snapshot_freshness(state, input_fingerprint=state.input_fingerprint or "")

    assert stale["status"] == "ready"
    assert stale["is_stale"] is True
    assert stale["has_snapshot"] is True
    assert stale["refresh_job_id"] == "world-refresh-1"


@pytest.mark.asyncio
async def test_source_observation_replacement_deletes_removed_and_empty_candidates(db):
    _, book = await _book(db)
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Observations",
        s3_key="chapters/persisted-world/observations.json",
    )
    db.add(chapter)
    await db.flush()

    await record_world_source_observations(
        db,
        book_id=book.id,
        chapter_id=chapter.id,
        source_kind="chapter",
        source_key=str(chapter.id),
        source_fingerprint=content_sha256("first"),
        candidates=[{"name": "North Gate"}, {"name": "South Gate"}],
    )
    await record_world_source_observations(
        db,
        book_id=book.id,
        chapter_id=chapter.id,
        source_kind="chapter",
        source_key=str(chapter.id),
        source_fingerprint=content_sha256("second"),
        candidates=[{"name": "North Gate"}],
    )
    rows = (
        await db.execute(
            select(WorldSourceObservation).where(WorldSourceObservation.book_id == book.id)
        )
    ).scalars().all()
    assert [row.payload["name"] for row in rows] == ["North Gate"]
    assert rows[0].source_fingerprint == content_sha256("second")

    await record_world_source_observations(
        db,
        book_id=book.id,
        chapter_id=chapter.id,
        source_kind="chapter",
        source_key=str(chapter.id),
        source_fingerprint=content_sha256("empty"),
        candidates=[],
    )
    remaining = await db.scalar(
        select(WorldSourceObservation).where(WorldSourceObservation.book_id == book.id)
    )
    assert remaining is None


@pytest.mark.asyncio
async def test_series_fingerprint_changes_with_membership_position(db):
    user, book = await _book(db)
    series = Series(user_id=user.id, name="World Cycle")
    db.add(series)
    await db.flush()
    membership = SeriesBook(series_id=series.id, book_id=book.id, position=1)
    db.add(membership)
    await db.flush()

    before = await build_series_world_input_fingerprint(db, series.id)
    membership.position = 2
    await db.flush()
    after = await build_series_world_input_fingerprint(db, series.id)

    assert before != after


@pytest.mark.asyncio
async def test_new_stale_state_is_queued_without_a_snapshot(db):
    _, book = await _book(db)
    state = await mark_book_world_analysis_stale(db, book_id=book.id)
    persisted = await db.scalar(
        select(WorldAnalysisState).where(WorldAnalysisState.book_id == book.id)
    )

    assert persisted is state
    assert state.status == "queued"
    assert snapshot_freshness(state, input_fingerprint="different")["has_snapshot"] is False


@pytest.mark.asyncio
async def test_refresh_state_tracks_running_and_failure_without_discarding_snapshot(db):
    _, book = await _book(db, email="world-state-failure@example.com")
    state = await publish_book_world_analysis(
        db,
        book_id=book.id,
        mode="gap_detection",
        payload={"priority_gaps": [{"id": "durable-gap"}]},
    )

    await mark_book_world_analysis_running(
        db,
        book_id=book.id,
        refresh_job_id="refresh-1",
    )
    assert state.status == "running"
    assert state.started_at is not None
    assert state.payload["gap_analysis"]["priority_gaps"][0]["id"] == "durable-gap"

    await mark_world_analysis_failed(
        db,
        book_id=book.id,
        refresh_job_id="refresh-1",
        error_code="refresh_failed",
        error_detail="source temporarily unavailable",
    )
    assert state.status == "failed"
    assert state.failed_at is not None
    assert state.error_code == "refresh_failed"
    assert state.payload["gap_analysis"]["priority_gaps"][0]["id"] == "durable-gap"
