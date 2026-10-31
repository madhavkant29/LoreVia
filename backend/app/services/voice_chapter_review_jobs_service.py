"""Durable, source-bound jobs for complete saved-chapter voice reviews."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, and_, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.intelligence import AdvisorJob
from app.utils.ingestion_utils import load_staged_chapter_payload
from app.utils.voice_chapter_review_utils import voice_chapter_fingerprint

VOICE_CHAPTER_SCOPE = "book_voice_chapter"
VOICE_CHAPTER_RETENTION = timedelta(days=7)
VOICE_CHAPTER_STALE_AFTER = timedelta(minutes=25)


def voice_chapter_resume_candidates(now: datetime, *, limit: int):
    """Select only ready jobs so manual pauses cannot starve automatic resumes."""
    resume_at = cast(AdvisorJob.result_json["next_resume_at"].as_string(), DateTime(timezone=True))
    return (
        select(AdvisorJob)
        .where(
            AdvisorJob.scope == VOICE_CHAPTER_SCOPE,
            AdvisorJob.expires_at > now,
            or_(
                and_(
                    AdvisorJob.status == "queued",
                    AdvisorJob.updated_at <= now - timedelta(minutes=5),
                ),
                and_(
                    AdvisorJob.status == "running",
                    AdvisorJob.updated_at <= now - VOICE_CHAPTER_STALE_AFTER,
                ),
                and_(AdvisorJob.status == "paused", resume_at <= now),
            ),
        )
        .order_by(AdvisorJob.updated_at)
        .limit(max(1, min(limit, 500)))
    )


class VoiceChapterSourceError(ValueError):
    """The saved chapter cannot be used for a reliable review."""


async def load_saved_voice_chapter(
    db: AsyncSession, *, book_id: uuid.UUID, chapter_number: int
) -> tuple[Chapter, str, str]:
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_number)
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise VoiceChapterSourceError("Chapter not found.")
    # Object storage may be slow; do not hold a read transaction while it responds.
    await db.commit()
    payload = await load_staged_chapter_payload(
        book_id, chapter_number, chapter_s3_key=chapter.s3_key
    )
    text = str((payload or {}).get("text") or "")
    if not text.strip():
        raise VoiceChapterSourceError("Saved chapter text is unavailable.")
    return chapter, text, voice_chapter_fingerprint(text)


def voice_job_state(job: AdvisorJob) -> dict[str, Any]:
    return dict(job.result_json or {})


def voice_chapter_job_matches_scope(
    job: AdvisorJob, allowed_chapter_range: tuple[int | None, int | None] | None
) -> bool:
    """Invalidate saved reviews when the viewer's chapter access changes."""
    expected = list(allowed_chapter_range) if allowed_chapter_range is not None else None
    return voice_job_state(job).get("access_scope") == expected


async def find_latest_voice_chapter_job(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_number: int,
) -> AdvisorJob | None:
    return (
        await db.execute(
            select(AdvisorJob)
            .where(
                AdvisorJob.scope == VOICE_CHAPTER_SCOPE,
                AdvisorJob.book_id == book_id,
                AdvisorJob.user_id == user_id,
                AdvisorJob.result_json["chapter_number"].as_integer() == chapter_number,
                AdvisorJob.expires_at > datetime.now(UTC),
            )
            .order_by(AdvisorJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def start_voice_chapter_job(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_number: int,
    source_fingerprint: str,
    allowed_chapter_range: tuple[int | None, int | None] | None = None,
    retry_paused: bool = False,
    force_refresh: bool = False,
) -> tuple[AdvisorJob, bool]:
    """Serialize starts for a book and reuse live work or a matching result."""
    await db.execute(select(Book.id).where(Book.id == book_id).with_for_update())
    current = await find_latest_voice_chapter_job(
        db, book_id=book_id, user_id=user_id, chapter_number=chapter_number
    )
    if current is not None:
        state = voice_job_state(current)
        if (
            state.get("source_fingerprint") == source_fingerprint
            and voice_chapter_job_matches_scope(current, allowed_chapter_range)
            and current.status
            in {
                "queued",
                "running",
                "paused",
                "complete",
                "failed",
            }
            and not (force_refresh and current.status == "complete")
        ):
            if current.status == "failed" or (current.status == "paused" and retry_paused):
                current.status = "queued"
                current.result_json = {**state, "next_resume_at": None}
                current.error_code = None
                current.error_detail = None
                current.updated_at = datetime.now(UTC)
                await db.commit()
                return current, True
            await db.commit()
            return current, False
    job = AdvisorJob(
        id=uuid.uuid4(),
        user_id=user_id,
        book_id=book_id,
        scope=VOICE_CHAPTER_SCOPE,
        status="queued",
        result_json={
            "chapter_number": chapter_number,
            "source_fingerprint": source_fingerprint,
            "access_scope": (
                list(allowed_chapter_range) if allowed_chapter_range is not None else None
            ),
            "completed": {},
        },
        expires_at=datetime.now(UTC) + VOICE_CHAPTER_RETENTION,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job, True


async def claim_voice_chapter_job(
    db: AsyncSession, *, job_id: uuid.UUID, execution_id: str
) -> AdvisorJob | None:
    job = await db.get(AdvisorJob, job_id, with_for_update=True)
    if job is None or job.scope != VOICE_CHAPTER_SCOPE:
        return None
    state = voice_job_state(job)
    now = datetime.now(UTC)
    if job.expires_at is not None and job.expires_at <= now:
        return None
    updated = job.updated_at or now
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    if job.status == "running" and now - updated < VOICE_CHAPTER_STALE_AFTER:
        return None
    if job.status not in {"queued", "paused", "running"}:
        return None
    if job.status == "paused":
        resume_at = state.get("next_resume_at")
        if not resume_at or datetime.fromisoformat(resume_at) > now:
            return None
    job.status = "running"
    job.result_json = {**state, "_execution_id": execution_id, "next_resume_at": None}
    job.updated_at = now
    await db.commit()
    await db.refresh(job)
    return job


async def update_voice_chapter_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    execution_id: str,
    status: str = "running",
    state_changes: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> bool:
    job = await db.get(AdvisorJob, job_id, with_for_update=True)
    if job is None or job.status != "running":
        return False
    state = voice_job_state(job)
    if state.get("_execution_id") != execution_id:
        return False
    job.status = status
    job.result_json = {**state, **(state_changes or {})}
    job.error_code = error_code
    job.error_detail = error_detail
    job.updated_at = datetime.now(UTC)
    if status == "complete":
        job.expires_at = job.updated_at + VOICE_CHAPTER_RETENTION
    if status == "paused" and job.result_json.get("next_resume_at"):
        resume_at = datetime.fromisoformat(job.result_json["next_resume_at"])
        job.expires_at = max(job.expires_at, resume_at + VOICE_CHAPTER_RETENTION)
    await db.commit()
    return True


def serialize_voice_chapter_job(job: AdvisorJob) -> dict[str, Any]:
    state = voice_job_state(job)
    completed = state.get("completed") or {}
    plan = state.get("plan") or {}
    return {
        "job_id": str(job.id),
        "status": job.status,
        "chapter_number": state.get("chapter_number"),
        "progress": {"completed": len(completed), "total": len(plan.get("work") or [])},
        "next_resume_at": state.get("next_resume_at"),
        "result": state.get("result") if job.status == "complete" else None,
        "error": job.error_detail or job.error_code,
    }


async def public_voice_chapter_job(
    db: AsyncSession, *, book_id: uuid.UUID, job: AdvisorJob
) -> dict[str, Any]:
    """Hide a finished review when its saved source has since changed."""
    payload = serialize_voice_chapter_job(job)
    if job.status != "complete":
        return payload
    try:
        _chapter, _source, fingerprint = await load_saved_voice_chapter(
            db,
            book_id=book_id,
            chapter_number=int(voice_job_state(job)["chapter_number"]),
        )
    except VoiceChapterSourceError:
        fingerprint = ""
    if fingerprint != voice_job_state(job)["source_fingerprint"]:
        payload.update(
            status="failed", result=None, error="The chapter changed. Start a fresh review."
        )
    return payload
