from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_advisor
from app.api.v1.routes.advisor.chat import _parse_advisor_job_id
from app.core.database import get_db
from app.core.redis import get_suggestion_scan_cache
from app.models.book import Book
from app.models.intelligence import AdvisorSuggestionJob
from app.schemas.advisor import (
    AdvisorSuggestionJobStatusResponse,
    AdvisorSuggestionScanResponse,
    AdvisorSuggestionsResponse,
)
from app.utils.billing_utils import require_author_access
from app.services.advisor_suggestion_jobs_service import (
    create_advisor_suggestion_job,
    mark_advisor_suggestion_job_failed,
    serialize_advisor_suggestion_job,
)
from app.utils.advisor_utils import (
    build_advisor_suggestions_payload,
    make_advisor_suggestions_cache_key,
)
from app.utils.logging.errors import public_error_message
from app.workers.tasks.intelligence_tasks import generate_advisor_suggestions_task

router = APIRouter()


# ─── Proactive suggestions scan ──────────────────────────────────────────────

@router.get("/{book_id}/advisor/suggestions", response_model=AdvisorSuggestionsResponse)
async def advisor_suggestions(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    result = await build_advisor_suggestions_payload(
        db=db,
        book=book,
        user_id=current_user.id,
    )
    result["cached"] = False
    return result


@router.post("/{book_id}/advisor/suggestions/scan", response_model=AdvisorSuggestionScanResponse)
async def advisor_suggestions_scan(
    book_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_advisor),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    total_ch = book.total_chapters or 1
    cache_key = make_advisor_suggestions_cache_key(
        book_id=book_id,
        total_chapters=total_ch,
        character_count=0,
        thread_count=0,
        state_count=0,
        relationship_count=0,
        world_element_count=0,
    )
    cached = await get_suggestion_scan_cache(str(book.id), cache_key)
    if cached is not None:
        return {"job_id": str(uuid.uuid4()), "status": "queued", "cached": True}

    job = await create_advisor_suggestion_job(
        db,
        user_id=current_user.id,
        book_id=book.id,
        cache_key=cache_key,
    )
    try:
        generate_advisor_suggestions_task.apply_async(
            task_id=str(job.id),
            kwargs={
                "job_id": str(job.id),
                "book_id": str(book.id),
                "user_id": str(current_user.id),
                "total_chapters": total_ch,
            },
        )
    except Exception as exc:
        await mark_advisor_suggestion_job_failed(
            db,
            job_id=job.id,
            error_code="advisor_suggestions_enqueue_failed",
            error_detail=public_error_message(500),
        )
        raise
    response.status_code = 202
    return {"job_id": str(job.id), "status": "queued", "cached": False}


@router.get(
    "/{book_id}/advisor/suggestions/jobs/{job_id}",
    response_model=AdvisorSuggestionJobStatusResponse,
)
async def advisor_suggestions_job_status(
    book_id: uuid.UUID,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    job = await db.get(AdvisorSuggestionJob, _parse_advisor_job_id(job_id))
    if job is None:
        raise HTTPException(404, detail="suggestion scan job not found")
    if job.user_id != current_user.id or job.book_id != book.id:
        raise HTTPException(403, detail="scan job does not belong to this book")
    return serialize_advisor_suggestion_job(job)
