from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_continuity_rate_limit, rate_limit_api
from app.api.v1.routes.advisor.chat import _advisor_sse, _advisor_stream_response
from app.core.database import get_db
from app.core.redis import get_book_cache_version
from app.models.user import User
from app.schemas.advisor import (
    VoiceConsistencyRequest,
    VoiceReviewDecisionRequest,
    VoiceReviewDecisionResponse,
)
from app.services.voice_consistency_orchestration_service import run_voice_consistency_review
from app.services.voice_consistency_review_service import save_voice_review_decision
from app.utils.advisor_route_errors import ADVISOR_STREAM_ERRORS
from app.utils.books.collaboration import collaboration_scope_payload
from app.utils.books.collaboration_access import (
    collaboration_is_chapter_restricted,
    get_book_with_ai_scan_access,
    require_collaboration_chapter_access,
)
from app.utils.llm_usage_utils import public_llm_http_error_message
from app.utils.logging.errors import public_error_message

router = APIRouter()
logger = logging.getLogger(__name__)
VOICE_STREAM_HEARTBEAT_SECONDS = 15


@router.put(
    "/{book_id}/advisor/voice-decisions/{finding_key}",
    response_model=VoiceReviewDecisionResponse,
)
async def set_voice_review_decision(
    book_id: uuid.UUID,
    body: VoiceReviewDecisionRequest,
    finding_key: str = Path(pattern=r"^[0-9a-f]{64}$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_api),
):
    await get_book_with_ai_scan_access(db, book_id, current_user, require_owner_plan=False)
    return await save_voice_review_decision(
        db,
        book_id=book_id,
        user_id=current_user.id,
        finding_key=finding_key,
        decision=body.decision,
        note=body.note,
    )


@router.post("/{book_id}/advisor/voice-consistency")
async def voice_consistency_review(
    book_id: uuid.UUID,
    body: VoiceConsistencyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(get_current_user),
):
    book, collaborator, _access = await get_book_with_ai_scan_access(
        db, book_id, current_user, require_owner_plan=False
    )
    if body.chapter_num is not None:
        require_collaboration_chapter_access(collaborator, body.chapter_num)
    allowed_chapter_range = None
    if collaboration_is_chapter_restricted(collaborator):
        scope = collaboration_scope_payload(collaborator)
        allowed_chapter_range = (scope.get("chapter_start"), scope.get("chapter_end"))
    billing_user = current_user if collaborator is None else await db.get(User, book.user_id)
    if billing_user is None:
        raise HTTPException(404, "Book owner not found.")
    if _ is not None:
        await enforce_continuity_rate_limit(db, billing_user)

    if not body.text.strip():
        raise HTTPException(400, detail="Passage text is required.")
    cache_version = await get_book_cache_version(str(book.id))
    return await run_voice_consistency_review(
        db=db,
        book=book,
        body=body,
        current_user=current_user,
        cache_version=cache_version,
        billing_user=billing_user,
        allowed_chapter_range=allowed_chapter_range,
    )


@router.post("/{book_id}/advisor/voice-consistency-stream")
async def voice_consistency_review_stream(
    book_id: uuid.UUID,
    body: VoiceConsistencyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(get_current_user),
):
    async def event_stream():
        review_task: asyncio.Task | None = None
        try:
            yield _advisor_sse("stage", {"message": "Comparing the passage to voice baselines..."})
            review_task = asyncio.create_task(
                voice_consistency_review(
                    book_id=book_id,
                    body=body,
                    db=db,
                    current_user=current_user,
                    _=_,
                )
            )
            while not review_task.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(review_task),
                        timeout=VOICE_STREAM_HEARTBEAT_SECONDS,
                    )
                except TimeoutError:
                    yield _advisor_sse("stage", {"message": "Still reviewing the full passage..."})
            payload = await review_task
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(payload)))
        except HTTPException as exc:
            if exc.status_code >= 500:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                kind = detail.get("kind")
                category = (
                    kind
                    if kind in {"manuscript_source", "llm_budget", "llm_capacity"}
                    else "http_error"
                )
                logger.warning(
                    "voice_review_stream_failed stage=review error_category=%s status_code=%s book_id=%s",
                    category,
                    exc.status_code,
                    book_id,
                )
            yield _advisor_sse("error", {"error": public_llm_http_error_message(exc)})
        except ADVISOR_STREAM_ERRORS as exc:
            logger.warning(
                "voice_review_stream_failed stage=review error_category=%s book_id=%s",
                type(exc).__name__,
                book_id,
            )
            yield _advisor_sse("error", {"error": public_error_message(500)})
        finally:
            if review_task is not None and not review_task.done():
                review_task.cancel()
                with suppress(asyncio.CancelledError):
                    await review_task

    return _advisor_stream_response(event_stream())
