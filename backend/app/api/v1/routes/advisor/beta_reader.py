from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_continuity_rate_limit
from app.core.database import get_db
from app.models.user import User
from app.schemas.advisor import (
    BetaReaderAnalysisRequest,
    BetaReaderJobOut,
    BetaReaderReportsOut,
    BetaReaderRevisionTaskOut,
    BetaReaderRunOut,
    FirstImpressionOut,
)
from app.services.advisor_jobs_service import (
    ADVISOR_SCOPE_BETA_READER,
    create_advisor_job,
    get_advisor_job,
    mark_advisor_job_failed,
)
from app.services.beta_reader_analysis_service import (
    list_beta_reader_reports,
    prepare_beta_reader_run,
)
from app.services.beta_reader_revision_service import create_beta_reader_revision_task
from app.services.first_impression_service import (
    get_first_impression_status,
    queue_first_impression,
)
from app.utils.books.collaboration_access import (
    collaboration_can_edit,
    get_book_with_ai_scan_access,
)
from app.utils.logging.errors import public_error_message
from app.utils.task_queue_errors import TASK_ENQUEUE_ERRORS
from app.workers.tasks.intelligence_tasks import generate_beta_reader_report_task

router = APIRouter()


@router.get(
    "/{book_id}/advisor/first-impression",
    response_model=FirstImpressionOut,
)
async def get_first_impression(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator, _ = await get_book_with_ai_scan_access(db, book_id, current_user)
    if collaborator is not None:
        raise HTTPException(403, "Only the manuscript owner can view the first read.")
    return await get_first_impression_status(db, book=book, user=current_user)


@router.post(
    "/{book_id}/advisor/first-impression/retry",
    response_model=FirstImpressionOut,
)
async def retry_first_impression(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator, _ = await get_book_with_ai_scan_access(db, book_id, current_user)
    if collaborator is not None:
        raise HTTPException(403, "Only the manuscript owner can retry the first read.")
    result = await queue_first_impression(
        db,
        book_id=book.id,
        user_id=current_user.id,
        allow_retry=True,
        strict=True,
    )
    if result is None:
        raise HTTPException(409, "The first read is not available yet.")
    return result


@router.post(
    "/{book_id}/advisor/beta-reader",
    response_model=BetaReaderRunOut,
)
async def run_beta_reader_analysis(
    book_id: uuid.UUID,
    body: BetaReaderAnalysisRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator, _ = await get_book_with_ai_scan_access(db, book_id, current_user)
    billing_user = current_user if collaborator is None else await db.get(User, book.user_id)
    if billing_user is None:
        raise HTTPException(404, "Book owner not found.")
    await enforce_continuity_rate_limit(db, billing_user)
    prepared = await prepare_beta_reader_run(db, book=book, collaborator=collaborator, body=body)
    if prepared["cached"] is not None:
        return BetaReaderRunOut(
            status="complete",
            cached=True,
            report=prepared["cached"],
        )

    job = await create_advisor_job(
        db,
        scope=ADVISOR_SCOPE_BETA_READER,
        user_id=current_user.id,
        book_id=book.id,
    )
    try:
        generate_beta_reader_report_task.apply_async(
            task_id=str(job.id),
            kwargs={
                "job_id": str(job.id),
                "book_id": str(book.id),
                "user_id": str(current_user.id),
                "request_payload": body.model_dump(mode="json"),
            },
        )
    except TASK_ENQUEUE_ERRORS as exc:
        await mark_advisor_job_failed(
            db,
            job_id=job.id,
            error_code="beta_reader_enqueue_failed",
            error_detail=public_error_message(500),
        )
        raise HTTPException(503, public_error_message(503)) from exc
    response.status_code = 202
    return BetaReaderRunOut(status="queued", task_id=str(job.id), cached=False)


@router.get(
    "/{book_id}/advisor/beta-reader/jobs/{task_id}",
    response_model=BetaReaderJobOut,
)
async def get_beta_reader_job(
    book_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, _, _ = await get_book_with_ai_scan_access(db, book_id, current_user)
    job = await get_advisor_job(db, job_id=task_id)
    if (
        job is None
        or job.user_id != current_user.id
        or job.book_id != book.id
        or job.scope != ADVISOR_SCOPE_BETA_READER
    ):
        raise HTTPException(404, "AI beta reader job not found.")
    progress = None
    report = None
    if job.status == "running" and isinstance(job.result_json, dict):
        progress = job.result_json.get("progress")
    elif job.status == "complete":
        report = job.result_json
    return BetaReaderJobOut(
        task_id=str(job.id),
        status=job.status,
        progress=progress,
        report=report,
        error=job.error_code if job.status == "failed" else None,
    )


@router.get(
    "/{book_id}/advisor/beta-reader/reports",
    response_model=BetaReaderReportsOut,
)
async def get_beta_reader_reports(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator, _ = await get_book_with_ai_scan_access(db, book_id, current_user)
    return BetaReaderReportsOut(
        reports=await list_beta_reader_reports(db, book=book, collaborator=collaborator)
    )


@router.post(
    "/{book_id}/advisor/beta-reader/reports/{report_id}/revision-candidates/{candidate_id}",
    response_model=BetaReaderRevisionTaskOut,
)
async def create_revision_task_from_beta_reader(
    book_id: uuid.UUID,
    report_id: str,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator, _ = await get_book_with_ai_scan_access(db, book_id, current_user)
    if collaborator is not None and not collaboration_can_edit(collaborator):
        raise HTTPException(403, "This collaboration cannot edit the manuscript.")
    task_id, created = await create_beta_reader_revision_task(
        db,
        book_id=book.id,
        report_id=report_id,
        candidate_id=candidate_id,
        collaborator=collaborator,
    )
    return BetaReaderRevisionTaskOut(
        task_id=task_id,
        candidate_id=candidate_id,
        created=created,
    )
