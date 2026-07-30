from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_advisor, rate_limit_continuity_checker
from app.api.v1.routes.advisor.chat import (
    _advisor_sse,
    _advisor_stream_response,
    _parse_advisor_job_id,
    _safe_prompt_str,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import (
    get_series_advisor_response_cache,
    get_series_continuity_cache,
    set_series_continuity_cache,
)
from app.models.book import Book, Series, SeriesBook
from app.models.intelligence import AdvisorJob
from app.schemas.advisor import AdvisorRequest, AdvisorTaskStatusResponse
from app.services.advisor_jobs_service import (
    ADVISOR_SCOPE_SERIES,
    create_advisor_job,
    mark_advisor_job_failed,
    serialize_advisor_job,
)
from app.utils.advisor_chat_utils import stream_series_advisor_reply_payload
from app.utils.advisor_route_errors import ADVISOR_STREAM_ERRORS
from app.utils.advisor_utils import (
    SERIES_CONTINUITY_SYSTEM,
    build_series_story_context,
    make_advisor_cache_key,
    make_editorial_cache_key,
    normalize_series_continuity_result,
    retrieve_series_continuity_passages,
)
from app.utils.billing_utils import require_author_access
from app.utils.llm_usage_utils import create_tracked_chat_completion
from app.utils.logging.errors import public_error_message
from app.utils.retry_utils import LLM_MAX_RETRIES
from app.utils.task_queue_errors import TASK_ENQUEUE_ERRORS
from app.workers.tasks.intelligence_tasks import generate_series_advisor_reply_task

router = APIRouter()


async def _enqueue_series_advisor_task(
    *,
    db: AsyncSession,
    series: Series,
    body: AdvisorRequest,
    current_user_id: uuid.UUID,
    response: Response,
) -> dict[str, Any]:
    last_user_msg = next(
        (message.content for message in reversed(body.messages) if message.role == "user"),
        "",
    )
    if not last_user_msg:
        raise HTTPException(400, detail="no user message found")
    cache_key = make_advisor_cache_key(f"series:{series.id}", last_user_msg)
    cached = await get_series_advisor_response_cache(str(series.id), cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    job = await create_advisor_job(
        db,
        scope=ADVISOR_SCOPE_SERIES,
        user_id=current_user_id,
        series_id=series.id,
    )
    try:
        generate_series_advisor_reply_task.apply_async(
            task_id=str(job.id),
            kwargs={
                "job_id": str(job.id),
                "series_id": str(series.id),
                "user_id": str(current_user_id),
                "messages": [{"role": msg.role, "content": msg.content} for msg in body.messages],
            },
        )
    except TASK_ENQUEUE_ERRORS:
        await mark_advisor_job_failed(
            db,
            job_id=job.id,
            error_code="advisor_enqueue_failed",
            error_detail=public_error_message(500),
        )
        raise
    response.status_code = 202
    return {"task_id": str(job.id), "status": "queued", "cached": False}


# ─── Series Ask endpoint ──────────────────────────────────────────────────────


@router.post("/series/{series_id}/advisor/message")
async def series_advisor_message(
    series_id: uuid.UUID,
    body: AdvisorRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_advisor),
):
    """Single-LLM-call advisor that answers questions spanning a whole book series.

    Cost strategy:
    - One round of RAG-free context (series story context only, capped tokens).
    - One LLM call to gpt-4o-mini.
    - No per-book round-trips.
    """
    series = await db.get(Series, series_id)
    if not series or series.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    if not body.messages:
        raise HTTPException(400, detail="messages list is empty")

    return await _enqueue_series_advisor_task(
        db=db,
        series=series,
        body=body,
        current_user_id=current_user.id,
        response=response,
    )


@router.post("/series/{series_id}/advisor/message-stream")
async def series_advisor_message_stream(
    series_id: uuid.UUID,
    body: AdvisorRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_advisor),
):
    series = await db.get(Series, series_id)
    if not series or series.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    if not body.messages:
        raise HTTPException(400, detail="messages list is empty")

    async def event_stream():
        try:
            async for item in stream_series_advisor_reply_payload(
                db=db,
                series=series,
                user_id=current_user.id,
                messages=[{"role": msg.role, "content": msg.content} for msg in body.messages],
            ):
                yield _advisor_sse(item["event"], item["data"])
        except ADVISOR_STREAM_ERRORS:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/series/{series_id}/advisor/message/{task_id}", response_model=AdvisorTaskStatusResponse
)
async def series_advisor_message_status(
    series_id: uuid.UUID,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await db.get(Series, series_id)
    if not series or series.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    job = await db.get(AdvisorJob, _parse_advisor_job_id(task_id))
    if job is None:
        raise HTTPException(404, detail="advisor task not found")
    if (
        job.user_id != current_user.id
        or job.scope != ADVISOR_SCOPE_SERIES
        or job.series_id != series.id
    ):
        raise HTTPException(403, detail="advisor task does not belong to this series")
    return serialize_advisor_job(job)


class SeriesContinuityRequest(AdvisorRequest):
    """Reuse AdvisorRequest shape but add book_id and optional chapter_num."""

    book_id: uuid.UUID
    chapter_num: int | None = None
    text: str


@router.post("/series/{series_id}/continuity-check")
async def series_continuity_check(
    series_id: uuid.UUID,
    body: SeriesContinuityRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    """Cross-series continuity check: compares a new passage against prior volumes.

    Cost strategy:
    - Context from prior books only (up to 3, capped per book).
    - Single LLM call using gpt-4o-mini with JSON mode.
    - RAG retrieval scoped to prior book IDs only (up to 6 passages).
    """
    series = await db.get(Series, series_id)
    if not series or series.user_id != current_user.id:
        raise HTTPException(404)

    if not body.text.strip():
        raise HTTPException(400, detail="Passage text is required.")

    # Current book must be in the series
    current_book = await db.get(Book, body.book_id)
    if not current_book or current_book.user_id != current_user.id:
        raise HTTPException(404, detail="Book not found.")

    # ── Cache check ───────────────────────────────────────────────────────────
    series_cache_key = make_editorial_cache_key(
        str(series_id) + str(body.book_id),  # scope to series+book pair
        body.text,
        body.chapter_num,
    )
    cached_series = await get_series_continuity_cache(
        str(series.id), str(current_book.id), series_cache_key
    )
    if cached_series is not None:
        return {**cached_series, "cached": True}

    # Load all memberships in order
    memberships = (
        await db.execute(
            select(SeriesBook.book_id, SeriesBook.position)
            .where(SeriesBook.series_id == series_id)
            .order_by(SeriesBook.position.asc().nulls_last())
        )
    ).all()

    current_position = next(
        (row.position for row in memberships if row.book_id == body.book_id), None
    )

    # Prior books = those with a lower series position, or all others if unordered
    if current_position is not None:
        prior_book_ids = [
            row.book_id
            for row in memberships
            if row.book_id != body.book_id and (row.position or 999) < current_position
        ]
    else:
        prior_book_ids = [row.book_id for row in memberships if row.book_id != body.book_id]

    # Limit to top 3 prior books for cost efficiency
    prior_book_ids = prior_book_ids[:3]

    if not prior_book_ids:
        return {
            "review": {
                "continuity_issues": [],
                "cross_book_opportunities": [],
                "thematic_fit": {
                    "score": "strong",
                    "notes": "No prior books in series to compare against.",
                },
                "overall_verdict": "This is the first book in the series — no cross-book continuity check possible.",
            },
            "retrieved_passages": [],
        }

    # Load prior book titles
    prior_book_rows = (
        await db.execute(select(Book.id, Book.title).where(Book.id.in_(prior_book_ids)))
    ).all()
    prior_titles = {row.id: row.title for row in prior_book_rows}

    # Build prior series context
    story_ctx = await build_series_story_context(
        db,
        prior_book_ids,
        prior_titles,
        max_chars_per_book=8,
        max_threads_per_book=5,
    )

    # RAG: retrieve relevant passages from prior books only (cross-series search)
    hits = await retrieve_series_continuity_passages(
        db=db,
        prior_book_ids=prior_book_ids,
        query=body.text[:600],
        user_id=current_user.id,
        book_id=current_book.id,
    )

    passages_block = (
        "\n\n".join(
            f"[{h['book_title']} — Ch. {h['chapter_num']}]: {h['text'][:300]}" for h in hits
        )
        or "No closely matching passages found in earlier books."
    )

    chapter_hint = (
        f'This passage will appear in Chapter {body.chapter_num} of "{current_book.title}".'
        if body.chapter_num
        else f'Chapter number not specified. Book: "{current_book.title}".'
    )

    system_msg = SERIES_CONTINUITY_SYSTEM.format(
        series_name=_safe_prompt_str(series.name),
        new_book_title=_safe_prompt_str(current_book.title),
        story_context=_safe_prompt_str(story_ctx),
    )
    user_msg = (
        f"{chapter_hint}\n\n"
        f"--- NEW PASSAGE ---\n{body.text[:4000]}\n\n"
        f"--- RETRIEVED PASSAGES FROM EARLIER BOOKS ---\n{passages_block}"
    )

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=LLM_MAX_RETRIES)
    try:
        response = await create_tracked_chat_completion(
            client=client,
            feature="series_continuity_check",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=current_book.id,
            temperature=0.2,
            max_tokens=1200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        result = normalize_series_continuity_result(raw)

        response_payload = {
            "review": result,
            "retrieved_passages": [
                {
                    "book_title": h["book_title"],
                    "chapter_num": h["chapter_num"],
                    "chapter_title": h.get("chapter_title"),
                    "excerpt": h["text"][:220],
                    "relevance": h["relevance"],
                }
                for h in hits[:5]
            ],
            "cached": False,
        }
        await set_series_continuity_cache(
            str(series.id), str(current_book.id), series_cache_key, response_payload
        )
        return response_payload
    finally:
        await client.close()


@router.post("/series/{series_id}/continuity-check-stream")
async def series_continuity_check_stream(
    series_id: uuid.UUID,
    body: SeriesContinuityRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    async def event_stream():
        try:
            yield _advisor_sse("stage", {"message": "Comparing this passage to earlier books..."})
            payload = await series_continuity_check(
                series_id=series_id,
                body=body,
                db=db,
                current_user=current_user,
                _=_,
            )
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(payload)))
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_error_message(exc.status_code)})
        except ADVISOR_STREAM_ERRORS:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())
