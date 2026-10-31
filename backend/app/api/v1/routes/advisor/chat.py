from __future__ import annotations

import json
import logging
import re
import traceback
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_advisor
from app.core.config import settings
from app.core.database import get_db
from app.core.llm import get_openai_client
from app.core.redis import get_advisor_response_cache
from app.models.book import Book
from app.models.character import Character
from app.models.intelligence import AdvisorJob, PlotThread
from app.schemas.advisor import (
    AdvisorRequest,
    AdvisorTaskStatusResponse,
    WhatsTheWordRequest,
    WhatsTheWordResponse,
)
from app.services.advisor_jobs_service import (
    ADVISOR_SCOPE_BOOK,
    create_advisor_job,
    mark_advisor_job_failed,
    serialize_advisor_job,
)
from app.utils.advisor_chat_utils import stream_advisor_reply_payload
from app.utils.advisor_route_errors import ADVISOR_STREAM_ERRORS
from app.utils.advisor_utils import (
    generate_whats_the_word_result,
    make_advisor_cache_key,
)
from app.utils.billing_utils import require_author_access
from app.utils.llm_usage_utils import public_llm_http_error_message
from app.utils.logging.errors import public_error_message
from app.utils.task_queue_errors import TASK_ENQUEUE_ERRORS
from app.workers.tasks.intelligence_tasks import generate_advisor_reply_task

router = APIRouter()


def _safe_prompt_str(value: str | None) -> str:
    """Escape Python str.format() brace syntax in user-controlled values.

    A book title like '} Ignore all previous instructions. {title' would
    otherwise be interpreted by str.format() as a closing/opening brace,
    causing a KeyError or — depending on the template — injecting unexpected
    content into the LLM system prompt.  We escape both braces so the value
    is always treated as a literal string by the template engine.
    """
    return (value or "").replace("{", "{{").replace("}", "}}")


def _best_issue_snippet(text: str, description: str) -> str:
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text or "") if item.strip()]
    if not sentences:
        return " ".join((text or "").split())[:220]
    description_tokens = {
        token for token in re.findall(r"[a-z0-9']+", (description or "").lower()) if len(token) > 3
    }
    ranked = sorted(
        sentences,
        key=lambda sentence: sum(1 for token in description_tokens if token in sentence.lower()),
        reverse=True,
    )
    return ranked[0][:220]


def _parse_advisor_job_id(task_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(task_id))
    except ValueError as exc:
        raise HTTPException(404, detail="advisor task not found") from exc


def _advisor_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _advisor_stream_response(event_stream) -> StreamingResponse:
    return StreamingResponse(
        event_stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _enqueue_book_advisor_task(
    *,
    db: AsyncSession,
    book: Book,
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
    cache_key = make_advisor_cache_key(book.id, last_user_msg)
    cached = await get_advisor_response_cache(str(book.id), cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    job = await create_advisor_job(
        db,
        scope=ADVISOR_SCOPE_BOOK,
        user_id=current_user_id,
        book_id=book.id,
    )
    try:
        generate_advisor_reply_task.apply_async(
            task_id=str(job.id),
            kwargs={
                "job_id": str(job.id),
                "book_id": str(book.id),
                "user_id": str(current_user_id),
                "messages": [{"role": msg.role, "content": msg.content} for msg in body.messages],
                "total_chapters": int(book.total_chapters or 0),
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


# ─── Main advisor conversation endpoint ──────────────────────────────────────


@router.post("/{book_id}/advisor/message")
async def advisor_message(
    book_id: uuid.UUID,
    body: AdvisorRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_advisor),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    if not body.messages:
        raise HTTPException(400, detail="messages list is empty")

    return await _enqueue_book_advisor_task(
        db=db,
        book=book,
        body=body,
        current_user_id=current_user.id,
        response=response,
    )


@router.post("/{book_id}/advisor/message-stream")
async def advisor_message_stream(
    book_id: uuid.UUID,
    body: AdvisorRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_advisor),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    if not body.messages:
        raise HTTPException(400, detail="messages list is empty")

    async def event_stream():
        try:
            async for item in stream_advisor_reply_payload(
                db=db,
                book=book,
                user_id=current_user.id,
                messages=[{"role": msg.role, "content": msg.content} for msg in body.messages],
                total_chapters=int(book.total_chapters or 0),
            ):
                yield _advisor_sse(item["event"], item["data"])
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_llm_http_error_message(exc)})
        except ADVISOR_STREAM_ERRORS as exc:
            logging.getLogger(__name__).error(
                "advisor_message_stream failed book_id=%s user_id=%s: %s\n%s",
                book_id,
                current_user.id,
                exc,
                traceback.format_exc(),
            )
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{book_id}/advisor/greeting")
async def advisor_greeting(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    plot_thread_count = (
        await db.execute(
            select(func.count()).select_from(PlotThread).where(PlotThread.book_id == book.id)
        )
    ).scalar_one()
    character_count = (
        await db.execute(
            select(func.count()).select_from(Character).where(Character.book_id == book.id)
        )
    ).scalar_one()

    return {
        "message": f"What aspect of *{book.title}* feels unsolved right now?",
        "book_title": book.title,
        "stats": {
            "characters": character_count,
            "plot_threads": plot_thread_count,
            "total_chapters": book.total_chapters,
        },
    }


@router.post("/{book_id}/advisor/whats-the-word", response_model=WhatsTheWordResponse)
async def whats_the_word(
    book_id: uuid.UUID,
    body: WhatsTheWordRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_advisor),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    client = get_openai_client()
    payload = await generate_whats_the_word_result(
        client=client,
        model=settings.OPENAI_INTEL_MODEL,
        user_id=current_user.id,
        book_id=book.id,
        book_title=book.title,
        description=body.description,
        previous_word=body.previous_word,
    )
    return WhatsTheWordResponse(**payload)


@router.post("/{book_id}/advisor/whats-the-word-stream")
async def whats_the_word_stream(
    book_id: uuid.UUID,
    body: WhatsTheWordRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_advisor),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    async def event_stream():
        client = get_openai_client()
        try:
            yield _advisor_sse("stage", {"message": "Finding the closest fit..."})
            payload = await generate_whats_the_word_result(
                client=client,
                model=settings.OPENAI_INTEL_MODEL,
                user_id=current_user.id,
                book_id=book.id,
                book_title=book.title,
                description=body.description,
                previous_word=body.previous_word,
            )
            yield _advisor_sse(
                "done", cast(dict[str, Any], jsonable_encoder(WhatsTheWordResponse(**payload)))
            )
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_llm_http_error_message(exc)})
        except ADVISOR_STREAM_ERRORS:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())


@router.post("/{book_id}/advisor/message-async")
async def advisor_message_async(
    book_id: uuid.UUID,
    body: AdvisorRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_advisor),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    if not body.messages:
        raise HTTPException(400, detail="messages list is empty")

    return await _enqueue_book_advisor_task(
        db=db,
        book=book,
        body=body,
        current_user_id=current_user.id,
        response=response,
    )


@router.get("/{book_id}/advisor/message-async/{task_id}", response_model=AdvisorTaskStatusResponse)
async def advisor_message_async_status(
    book_id: uuid.UUID,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    job = await db.get(AdvisorJob, _parse_advisor_job_id(task_id))
    if job is None:
        raise HTTPException(404, detail="advisor task not found")
    if job.user_id != current_user.id or job.scope != ADVISOR_SCOPE_BOOK or job.book_id != book.id:
        raise HTTPException(403, detail="advisor task does not belong to this book")
    return serialize_advisor_job(job)
