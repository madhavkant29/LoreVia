"""Durable, storage-free state and freshness helpers for world analysis."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Chapter, SeriesBook
from app.models.generation import BookDataGeneration
from app.models.intelligence import (
    WorldAnalysisState,
    WorldBuildingDocument,
    WorldCanonicalIdentity,
    WorldElement,
    WorldSourceObservation,
)
from app.services.data_generation_service import current_generation_id

WORLD_ANALYSIS_READY = "ready"
WORLD_ANALYSIS_QUEUED = "queued"
WORLD_ANALYSIS_RUNNING = "running"
WORLD_ANALYSIS_FAILED = "failed"


def content_sha256(content: str | bytes) -> str:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value


def _fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def build_book_world_input_fingerprint(db: AsyncSession, book_id: uuid.UUID) -> str:
    """Hash only persisted input metadata; never download source storage on a read."""

    document_rows = (
        await db.execute(
            select(
                WorldBuildingDocument.id,
                WorldBuildingDocument.title,
                WorldBuildingDocument.source_name,
                WorldBuildingDocument.s3_key,
                WorldBuildingDocument.content_sha256,
                WorldBuildingDocument.is_active,
                WorldBuildingDocument.updated_at,
            )
            .where(WorldBuildingDocument.book_id == book_id)
            .order_by(WorldBuildingDocument.id.asc())
        )
    ).all()
    canonical_rows = (
        await db.execute(
            select(
                WorldCanonicalIdentity.id,
                WorldCanonicalIdentity.canonical_name,
                WorldCanonicalIdentity.entity_type,
                WorldCanonicalIdentity.aliases,
                WorldCanonicalIdentity.notes,
                WorldCanonicalIdentity.updated_at,
            )
            .where(WorldCanonicalIdentity.book_id == book_id)
            .order_by(WorldCanonicalIdentity.id.asc())
        )
    ).all()
    chapter_rows = (
        await db.execute(
            select(
                Chapter.id,
                Chapter.number,
                Chapter.content_version,
                Chapter.structure_version,
                Chapter.s3_key,
                Chapter.processed,
            )
            .where(Chapter.book_id == book_id)
            .order_by(Chapter.number.asc(), Chapter.id.asc())
        )
    ).all()
    element_rows = (
        await db.execute(
            select(
                WorldElement.id,
                WorldElement.source_scope,
                WorldElement.world_document_id,
                WorldElement.name,
                WorldElement.updated_at,
                WorldElement.generation_id,
            )
            .where(WorldElement.book_id == book_id)
            .order_by(WorldElement.id.asc())
        )
    ).all()
    active_generation_id = await db.scalar(
        select(BookDataGeneration.id)
        .where(
            BookDataGeneration.book_id == book_id,
            BookDataGeneration.status == "active",
        )
        .limit(1)
    )
    return _fingerprint(
        {
            "book_id": book_id,
            "active_generation_id": active_generation_id,
            "documents": [
                {
                    "id": row.id,
                    "title": row.title,
                    "source_name": row.source_name,
                    "s3_key": row.s3_key,
                    "content_sha256": row.content_sha256,
                    "is_active": row.is_active,
                    "updated_at": row.updated_at,
                }
                for row in document_rows
            ],
            "canon_overrides": [
                {
                    "id": row.id,
                    "canonical_name": row.canonical_name,
                    "entity_type": row.entity_type,
                    "aliases": row.aliases or [],
                    "notes": row.notes,
                    "updated_at": row.updated_at,
                }
                for row in canonical_rows
            ],
            "chapters": [
                {
                    "id": row.id,
                    "number": row.number,
                    "content_version": row.content_version,
                    "structure_version": row.structure_version,
                    "s3_key": row.s3_key,
                    "processed": row.processed,
                }
                for row in chapter_rows
            ],
            "elements": [
                {
                    "id": row.id,
                    "source_scope": row.source_scope,
                    "world_document_id": row.world_document_id,
                    "name": row.name,
                    "updated_at": row.updated_at,
                    "generation_id": row.generation_id,
                }
                for row in element_rows
            ],
        }
    )


async def build_series_world_input_fingerprint(db: AsyncSession, series_id: uuid.UUID) -> str:
    """Fingerprint persisted membership and member inputs without parallel DB calls."""

    memberships = (
        await db.execute(
            select(SeriesBook.book_id, SeriesBook.position)
            .where(SeriesBook.series_id == series_id)
            .order_by(SeriesBook.position.asc().nullslast(), SeriesBook.book_id.asc())
        )
    ).all()
    members: list[dict[str, Any]] = []
    for book_id, position in memberships:
        members.append(
            {
                "book_id": book_id,
                "position": position,
                "input_fingerprint": await build_book_world_input_fingerprint(db, book_id),
            }
        )
    return _fingerprint({"series_id": series_id, "members": members})


async def get_book_world_analysis_state(
    db: AsyncSession, book_id: uuid.UUID, *, for_update: bool = False
) -> WorldAnalysisState | None:
    statement = select(WorldAnalysisState).where(WorldAnalysisState.book_id == book_id)
    if for_update:
        statement = statement.with_for_update()
    return (await db.execute(statement)).scalars().first()


async def get_series_world_analysis_state(
    db: AsyncSession, series_id: uuid.UUID, *, for_update: bool = False
) -> WorldAnalysisState | None:
    statement = select(WorldAnalysisState).where(WorldAnalysisState.series_id == series_id)
    if for_update:
        statement = statement.with_for_update()
    return (await db.execute(statement)).scalars().first()


def snapshot_freshness(
    state: WorldAnalysisState | None, *, input_fingerprint: str
) -> dict[str, Any]:
    if state is None:
        return {
            "status": WORLD_ANALYSIS_QUEUED,
            "is_stale": True,
            "refresh_job_id": None,
            "generated_at": None,
            "has_snapshot": False,
        }

    has_snapshot = bool(state.payload) and state.completed_at is not None
    is_stale = (
        not has_snapshot
        or state.input_fingerprint != input_fingerprint
        or (
            state.stale_at is not None
            and (state.completed_at is None or state.stale_at > state.completed_at)
        )
    )
    return {
        "status": state.status if has_snapshot else WORLD_ANALYSIS_QUEUED,
        "is_stale": is_stale,
        "refresh_job_id": state.refresh_job_id,
        "generated_at": state.completed_at,
        "has_snapshot": has_snapshot,
    }


async def publish_book_world_analysis(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    mode: str,
    payload: Mapping[str, Any],
) -> WorldAnalysisState:
    """Atomically publish one analysis mode while retaining other completed modes."""

    input_fingerprint = await build_book_world_input_fingerprint(db, book_id)
    state = await get_book_world_analysis_state(db, book_id, for_update=True)
    if state is None:
        state = WorldAnalysisState(book_id=book_id, scope="book")
        db.add(state)
        await db.flush()
    snapshot = dict(state.payload or {})
    snapshot["gap_analysis" if mode == "gap_detection" else "integration_analysis"] = _json_value(
        dict(payload)
    )
    snapshot["world_elements"] = _json_value(payload.get("world_elements") or [])
    snapshot["world_documents"] = _json_value(payload.get("world_documents") or [])
    now = datetime.now(UTC)
    state.payload = snapshot
    state.status = WORLD_ANALYSIS_READY
    state.input_fingerprint = input_fingerprint
    state.refresh_job_id = None
    state.stale_at = None
    state.started_at = None
    state.completed_at = now
    state.failed_at = None
    state.error_code = None
    state.error_detail = None
    await db.flush()
    return state


async def publish_series_world_analysis(
    db: AsyncSession,
    *,
    series_id: uuid.UUID,
    payload: Mapping[str, Any],
) -> WorldAnalysisState:
    input_fingerprint = await build_series_world_input_fingerprint(db, series_id)
    state = await get_series_world_analysis_state(db, series_id, for_update=True)
    if state is None:
        state = WorldAnalysisState(series_id=series_id, scope="series")
        db.add(state)
        await db.flush()
    state.payload = _json_value(dict(payload))
    state.status = WORLD_ANALYSIS_READY
    state.input_fingerprint = input_fingerprint
    state.refresh_job_id = None
    state.stale_at = None
    state.started_at = None
    state.completed_at = datetime.now(UTC)
    state.failed_at = None
    state.error_code = None
    state.error_detail = None
    await db.flush()
    return state


async def mark_book_world_analysis_stale(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    refresh_job_id: str | None = None,
) -> WorldAnalysisState:
    """Persist staleness after an explicit source mutation without rebuilding inline."""

    state = await get_book_world_analysis_state(db, book_id, for_update=True)
    if state is None:
        state = WorldAnalysisState(book_id=book_id, scope="book", status=WORLD_ANALYSIS_QUEUED)
        db.add(state)
    state.stale_at = datetime.now(UTC)
    state.refresh_job_id = refresh_job_id
    if not state.payload:
        state.status = WORLD_ANALYSIS_QUEUED
    await db.flush()
    return state


async def mark_series_world_analysis_stale(
    db: AsyncSession,
    *,
    series_id: uuid.UUID,
    refresh_job_id: str | None = None,
) -> WorldAnalysisState:
    state = await get_series_world_analysis_state(db, series_id, for_update=True)
    if state is None:
        state = WorldAnalysisState(series_id=series_id, scope="series", status=WORLD_ANALYSIS_QUEUED)
        db.add(state)
    state.stale_at = datetime.now(UTC)
    state.refresh_job_id = refresh_job_id
    if not state.payload:
        state.status = WORLD_ANALYSIS_QUEUED
    await db.flush()
    return state


async def mark_book_world_analysis_running(
    db: AsyncSession, *, book_id: uuid.UUID, refresh_job_id: str
) -> WorldAnalysisState:
    state = await get_book_world_analysis_state(db, book_id, for_update=True)
    if state is None:
        state = WorldAnalysisState(book_id=book_id, scope="book")
        db.add(state)
    state.status = WORLD_ANALYSIS_RUNNING
    state.refresh_job_id = refresh_job_id
    state.started_at = datetime.now(UTC)
    state.failed_at = None
    state.error_code = None
    state.error_detail = None
    await db.flush()
    return state


async def mark_series_world_analysis_running(
    db: AsyncSession, *, series_id: uuid.UUID, refresh_job_id: str
) -> WorldAnalysisState:
    state = await get_series_world_analysis_state(db, series_id, for_update=True)
    if state is None:
        state = WorldAnalysisState(series_id=series_id, scope="series")
        db.add(state)
    state.status = WORLD_ANALYSIS_RUNNING
    state.refresh_job_id = refresh_job_id
    state.started_at = datetime.now(UTC)
    state.failed_at = None
    state.error_code = None
    state.error_detail = None
    await db.flush()
    return state


async def mark_world_analysis_failed(
    db: AsyncSession,
    *,
    book_id: uuid.UUID | None = None,
    series_id: uuid.UUID | None = None,
    refresh_job_id: str,
    error_code: str,
    error_detail: str,
) -> WorldAnalysisState:
    if (book_id is None) == (series_id is None):
        raise ValueError("Exactly one world-analysis target is required")
    state = (
        await get_book_world_analysis_state(db, book_id, for_update=True)
        if book_id is not None
        else await get_series_world_analysis_state(db, series_id, for_update=True)
    )
    if state is None:
        state = WorldAnalysisState(
            book_id=book_id,
            series_id=series_id,
            scope="book" if book_id is not None else "series",
        )
        db.add(state)
    state.status = WORLD_ANALYSIS_FAILED
    state.refresh_job_id = refresh_job_id
    state.started_at = None
    state.failed_at = datetime.now(UTC)
    state.error_code = error_code
    state.error_detail = error_detail[:2000]
    await db.flush()
    return state


async def mark_related_series_world_analysis_stale(
    db: AsyncSession, *, book_id: uuid.UUID
) -> None:
    series_ids = set(
        (
            await db.scalars(
                select(SeriesBook.series_id).where(SeriesBook.book_id == book_id)
            )
        ).all()
    )
    for series_id in series_ids:
        await mark_series_world_analysis_stale(db, series_id=series_id)


async def record_world_source_observations(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    source_kind: str,
    source_key: str,
    source_fingerprint: str,
    candidates: list[dict[str, Any]],
    world_document_id: uuid.UUID | None = None,
    chapter_id: uuid.UUID | None = None,
) -> list[WorldSourceObservation]:
    """Upsert observations for one source revision without exposing them to reads."""

    generation_id = current_generation_id()
    existing_statement = select(WorldSourceObservation).where(
        WorldSourceObservation.book_id == book_id,
        WorldSourceObservation.source_kind == source_kind,
        WorldSourceObservation.source_key == source_key,
    )
    if generation_id is None:
        existing_statement = existing_statement.where(
            WorldSourceObservation.generation_id.is_(None)
        )
    else:
        existing_statement = existing_statement.where(
            WorldSourceObservation.generation_id == generation_id
        )
    existing = {
        row.candidate_key: row
        for row in (await db.execute(existing_statement)).scalars().all()
    }
    observations: list[WorldSourceObservation] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_key = content_sha256(
            json.dumps(_json_value(candidate), sort_keys=True, separators=(",", ":"))
        )
        observation = existing.pop(candidate_key, None)
        if observation is None:
            observation = WorldSourceObservation(
                book_id=book_id,
                world_document_id=world_document_id,
                chapter_id=chapter_id,
                source_kind=source_kind,
                source_key=source_key,
                source_fingerprint=source_fingerprint,
                candidate_key=candidate_key,
                payload=_json_value(candidate),
                generation_id=generation_id,
            )
            db.add(observation)
        else:
            observation.world_document_id = world_document_id
            observation.chapter_id = chapter_id
            observation.source_fingerprint = source_fingerprint
            observation.payload = _json_value(candidate)
        observations.append(observation)
    for obsolete in existing.values():
        await db.delete(obsolete)
    await db.flush()
    return observations


async def list_world_source_candidate_payloads(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    source_kind: str,
) -> list[dict[str, Any]]:
    """Load normalized persisted candidates for analysis without source I/O."""

    statement = select(WorldSourceObservation.payload).where(
        WorldSourceObservation.book_id == book_id,
        WorldSourceObservation.source_kind == source_kind,
    )
    if source_kind == "world_document":
        statement = statement.join(
            WorldBuildingDocument,
            WorldBuildingDocument.id == WorldSourceObservation.world_document_id,
        ).where(WorldBuildingDocument.is_active.is_(True))
    elif source_kind == "chapter":
        statement = statement.join(
            Chapter, Chapter.id == WorldSourceObservation.chapter_id
        )
    rows = (await db.execute(statement)).scalars().all()
    return [dict(payload) for payload in rows if isinstance(payload, dict)]
