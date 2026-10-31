"""Authenticated chapter voice review job endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_continuity_rate_limit, rate_limit_api
from app.core.database import get_db
from app.models.intelligence import AdvisorJob
from app.models.user import User
from app.schemas.advisor import VoiceChapterReviewJobResponse, VoiceChapterReviewRequest
from app.services.voice_chapter_review_jobs_service import (
    VOICE_CHAPTER_SCOPE,
    VoiceChapterSourceError,
    find_latest_voice_chapter_job,
    load_saved_voice_chapter,
    public_voice_chapter_job,
    serialize_voice_chapter_job,
    start_voice_chapter_job,
    voice_chapter_job_matches_scope,
    voice_job_state,
)
from app.utils.books.collaboration import collaboration_scope_payload
from app.utils.books.collaboration_access import (
    collaboration_is_chapter_restricted,
    get_book_with_ai_scan_access,
    require_collaboration_chapter_access,
)
from app.utils.task_queue_errors import TASK_ENQUEUE_ERRORS
from app.workers.tasks.voice_chapter_tasks import review_voice_chapter_task

router = APIRouter()


@router.post("/{book_id}/advisor/voice-chapters", response_model=VoiceChapterReviewJobResponse)
async def start_voice_chapter_review(
    book_id: uuid.UUID,
    body: VoiceChapterReviewRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_api),
):
    book, collaborator, _access = await get_book_with_ai_scan_access(
        db, book_id, current_user, require_owner_plan=False
    )
    require_collaboration_chapter_access(collaborator, body.chapter_number)
    allowed_chapter_range = None
    if collaboration_is_chapter_restricted(collaborator):
        scope = collaboration_scope_payload(collaborator)
        allowed_chapter_range = (scope.get("chapter_start"), scope.get("chapter_end"))
    billing_user = current_user if collaborator is None else await db.get(User, book.user_id)
    if billing_user is None:
        raise HTTPException(404, detail="Book owner not found.")
    try:
        _chapter, _source, fingerprint = await load_saved_voice_chapter(
            db, book_id=book_id, chapter_number=body.chapter_number
        )
    except VoiceChapterSourceError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    existing = await find_latest_voice_chapter_job(
        db,
        book_id=book_id,
        user_id=current_user.id,
        chapter_number=body.chapter_number,
    )
    if (
        existing is None
        or not voice_chapter_job_matches_scope(existing, allowed_chapter_range)
        or voice_job_state(existing).get("source_fingerprint") != fingerprint
        or (body.force_refresh and existing.status == "complete")
    ):
        await enforce_continuity_rate_limit(db, billing_user)
    job, enqueue = await start_voice_chapter_job(
        db,
        book_id=book_id,
        user_id=current_user.id,
        chapter_number=body.chapter_number,
        source_fingerprint=fingerprint,
        allowed_chapter_range=allowed_chapter_range,
        retry_paused=body.retry_paused,
        force_refresh=body.force_refresh,
    )
    if enqueue:
        try:
            review_voice_chapter_task.apply_async(
                task_id=str(uuid.uuid4()), kwargs={"job_id": str(job.id)}
            )
        except TASK_ENQUEUE_ERRORS as exc:
            job.status = "failed"
            job.error_code = "queue_unavailable"
            job.error_detail = "Voice review could not start. Please retry."
            await db.commit()
            raise HTTPException(503, detail=job.error_detail) from exc
    response.status_code = 202 if job.status in {"queued", "running", "paused"} else 200
    return serialize_voice_chapter_job(job)


@router.get(
    "/{book_id}/advisor/voice-chapters/latest",
    response_model=VoiceChapterReviewJobResponse | None,
)
async def latest_voice_chapter_review(
    book_id: uuid.UUID,
    chapter_number: int = Query(ge=1),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _book, collaborator, _access = await get_book_with_ai_scan_access(
        db, book_id, current_user, require_owner_plan=False
    )
    require_collaboration_chapter_access(collaborator, chapter_number)
    allowed_chapter_range = None
    if collaboration_is_chapter_restricted(collaborator):
        scope = collaboration_scope_payload(collaborator)
        allowed_chapter_range = (scope.get("chapter_start"), scope.get("chapter_end"))
    job = await find_latest_voice_chapter_job(
        db, book_id=book_id, user_id=current_user.id, chapter_number=chapter_number
    )
    if job is None or not voice_chapter_job_matches_scope(job, allowed_chapter_range):
        return None
    return await public_voice_chapter_job(db, book_id=book_id, job=job)


@router.get(
    "/{book_id}/advisor/voice-chapters/jobs/{job_id}",
    response_model=VoiceChapterReviewJobResponse,
)
async def voice_chapter_review_status(
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _book, collaborator, _access = await get_book_with_ai_scan_access(
        db, book_id, current_user, require_owner_plan=False
    )
    job = await db.get(AdvisorJob, job_id)
    if (
        job is None
        or job.scope != VOICE_CHAPTER_SCOPE
        or job.book_id != book_id
        or job.user_id != current_user.id
        or (job.expires_at is not None and job.expires_at <= datetime.now(UTC))
    ):
        raise HTTPException(404, detail="Voice review job not found.")
    require_collaboration_chapter_access(collaborator, int(voice_job_state(job)["chapter_number"]))
    allowed_chapter_range = None
    if collaboration_is_chapter_restricted(collaborator):
        scope = collaboration_scope_payload(collaborator)
        allowed_chapter_range = (scope.get("chapter_start"), scope.get("chapter_end"))
    if not voice_chapter_job_matches_scope(job, allowed_chapter_range):
        raise HTTPException(404, detail="Voice review job not found.")
    return await public_voice_chapter_job(db, book_id=book_id, job=job)
