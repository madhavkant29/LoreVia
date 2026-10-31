"""Resume a saved-chapter review from durable validated passage results."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_book_cache_version
from app.models.user import User
from app.schemas.advisor import VoiceConsistencyRequest
from app.services.voice_chapter_review_jobs_service import (
    VoiceChapterSourceError,
    load_saved_voice_chapter,
    update_voice_chapter_job,
    voice_job_state,
)
from app.services.voice_consistency_orchestration_service import run_voice_consistency_review
from app.services.voice_consistency_review_service import load_voice_review_characters
from app.utils.books.collaboration_access import (
    get_book_with_ai_scan_access,
    require_collaboration_chapter_access,
)
from app.utils.voice_chapter_review_utils import (
    aggregate_voice_chapter_results,
    plan_voice_chapter_work,
)


def voice_chapter_pause(exc: HTTPException, attempts: int) -> tuple[str, str | None] | None:
    """Identify a bounded retry or a real quota refresh time."""
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    kind = str(detail.get("kind") or "")
    if kind in {"llm_tokens", "llm_budget"}:
        next_resume = detail.get("next_resume_at")
        if detail.get("auto_resume") and isinstance(next_resume, str):
            return "Token allowance will refresh before the review resumes.", next_resume
        return "AI allowance is unavailable. Retry after your plan window refreshes.", None
    if exc.status_code in {429, 503} and attempts < 3:
        next_resume = (datetime.now(UTC) + timedelta(minutes=2**attempts)).isoformat()
        return "AI processing is temporarily busy. Review will resume automatically.", next_resume
    return None


async def process_voice_chapter_job(db: AsyncSession, *, job: Any, execution_id: str) -> str:
    """Run every planned character-section pair and checkpoint each success."""
    # Include source loading and planning in the task's time budget.
    deadline = monotonic() + 12 * 60
    state = voice_job_state(job)
    job_id = job.id
    book_id = job.book_id
    user_id = job.user_id
    chapter_number = int(state["chapter_number"])
    user = await db.get(User, user_id)
    if user is None:
        await update_voice_chapter_job(
            db,
            job_id=job_id,
            execution_id=execution_id,
            status="failed",
            error_code="access_denied",
            error_detail="Voice review access is no longer available.",
        )
        return "failed"
    try:
        book, collaborator, _access = await get_book_with_ai_scan_access(
            db, book_id, user, require_owner_plan=False
        )
        require_collaboration_chapter_access(collaborator, chapter_number)
        billing_user = user if collaborator is None else await db.get(User, book.user_id)
        if billing_user is None:
            raise VoiceChapterSourceError("Book owner not found.")
        chapter, source, source_fingerprint = await load_saved_voice_chapter(
            db, book_id=book_id, chapter_number=chapter_number
        )
    except (HTTPException, VoiceChapterSourceError):
        await update_voice_chapter_job(
            db,
            job_id=job_id,
            execution_id=execution_id,
            status="failed",
            error_code="source_unavailable",
            error_detail="Saved chapter or review access is unavailable.",
        )
        return "failed"
    if source_fingerprint != state["source_fingerprint"]:
        await update_voice_chapter_job(
            db,
            job_id=job_id,
            execution_id=execution_id,
            status="failed",
            error_code="stale_source",
            error_detail="The chapter changed. Start a fresh review.",
        )
        return "failed"
    plan = state.get("plan")
    if plan is None:
        characters = await load_voice_review_characters(db, book_id=book_id)
        plan = plan_voice_chapter_work(source, chapter_number, characters)
        if not await update_voice_chapter_job(
            db,
            job_id=job_id,
            execution_id=execution_id,
            state_changes={"plan": plan, "source_version": chapter.content_version},
        ):
            return "superseded"
    completed = dict(state.get("completed") or {})
    attempts = int(state.get("attempts") or 0)
    cache_version = await get_book_cache_version(str(book_id))
    # Leave room before Celery's soft limit so a long chapter can checkpoint
    # and continue in another task instead of losing the current section.
    for item in plan["work"]:
        if item["key"] in completed:
            continue
        if monotonic() >= deadline:
            await update_voice_chapter_job(
                db,
                job_id=job_id,
                execution_id=execution_id,
                status="paused",
                state_changes={
                    "next_resume_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
                },
                error_code="continuing",
                error_detail="Reviewing the remaining voice sections shortly.",
            )
            return "paused"
        body = VoiceConsistencyRequest(
            text=source[item["start"] : item["end"]],
            chapter_num=chapter_number,
            character_id=uuid.UUID(item["character_id"]),
            voice_mode=item["voice_mode"],
        )
        try:
            result = await run_voice_consistency_review(
                db=db,
                book=book,
                body=body,
                current_user=billing_user,
                cache_version=cache_version,
            )
        except HTTPException as exc:
            pause = voice_chapter_pause(exc, attempts)
            if pause is not None:
                message, next_resume = pause
                await update_voice_chapter_job(
                    db,
                    job_id=job_id,
                    execution_id=execution_id,
                    status="paused",
                    state_changes={"attempts": attempts + 1, "next_resume_at": next_resume},
                    error_code="ai_paused",
                    error_detail=message,
                )
                return "paused"
            await update_voice_chapter_job(
                db,
                job_id=job_id,
                execution_id=execution_id,
                status="failed",
                error_code="voice_review_failed",
                error_detail="A voice section could not be reviewed. Retry the chapter.",
            )
            return "failed"
        completed[item["key"]] = {
            "review": result["review"],
            "warnings": result.get("warnings") or [],
            "coverage": result["coverage"],
        }
        attempts = 0
        if not await update_voice_chapter_job(
            db,
            job_id=job_id,
            execution_id=execution_id,
            state_changes={"completed": completed, "attempts": 0},
        ):
            return "superseded"
    try:
        _chapter, final_source, final_fingerprint = await load_saved_voice_chapter(
            db, book_id=book_id, chapter_number=chapter_number
        )
    except VoiceChapterSourceError:
        final_source, final_fingerprint = "", ""
    if final_fingerprint != source_fingerprint or final_source != source:
        await update_voice_chapter_job(
            db,
            job_id=job_id,
            execution_id=execution_id,
            status="failed",
            error_code="stale_source",
            error_detail="The chapter changed. Start a fresh review.",
        )
        return "failed"
    aggregate = aggregate_voice_chapter_results(source_text=source, plan=plan, completed=completed)
    await update_voice_chapter_job(
        db,
        job_id=job_id,
        execution_id=execution_id,
        status="complete",
        state_changes={"result": aggregate, "completed": completed},
    )
    return "complete"
