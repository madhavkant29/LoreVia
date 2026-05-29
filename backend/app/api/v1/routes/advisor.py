"""
Story Advisor — author-mode intelligence endpoint.
RAG-grounded conversation: embeds each user message, retrieves top-5 relevant
chunks, sends only those chunks + last 10 conversation turns to GPT-4o-mini.

Also provides:
- /advisor/suggestions  — proactive scan for plotholes, dropped threads, dead
                          characters, unused setups, future directions (DB-only)
- /advisor/message      — conversational turn
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response, StreamingResponse
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_advisor, rate_limit_continuity_checker
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import (
    get_advisor_response_cache,
    get_editorial_review_cache,
    get_proactive_scan_cache,
    get_prose_tighten_cache,
    get_series_advisor_response_cache,
    get_series_continuity_cache,
    get_suggestion_scan_cache,
    get_synopsis_cache,
    get_voice_consistency_cache,
    set_advisor_response_cache,
    set_editorial_review_cache,
    set_proactive_scan_cache,
    set_prose_tighten_cache,
    set_series_advisor_response_cache,
    set_series_continuity_cache,
    set_suggestion_scan_cache,
    set_synopsis_cache,
    set_voice_consistency_cache,
)
from app.core.storage import download_book
from app.engine.search.semantic import semantic_search
from app.models.book import Book, Chapter, Series, SeriesBook
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import AdvisorJob, AdvisorSuggestionJob, ChapterSummary, CharacterRelationship, PlotThread, WorldElement
from app.services.advisor_jobs_service import (
    ADVISOR_SCOPE_BOOK,
    ADVISOR_SCOPE_SERIES,
    create_advisor_job,
    mark_advisor_job_failed,
    serialize_advisor_job,
)
from app.services.advisor_suggestion_jobs_service import (
    create_advisor_suggestion_job,
    mark_advisor_suggestion_job_failed,
    serialize_advisor_suggestion_job,
)
from app.utils.plot_thread_utils import derive_plot_thread_status, is_plot_thread_open
from app.schemas.advisor import (
    AdvisorRequest,
    AdvisorSuggestionJobStatusResponse,
    AdvisorSuggestionScanResponse,
    AdvisorSuggestionsResponse,
    AdvisorTaskStatusResponse,
    EditorialReviewRequest,
    InlineContinuityRequest,
    InlineContinuityResponse,
    ProseTightenRequest,
    ProseTightenResponse,
    SynopsisResponse,
    VoiceConsistencyRequest,
    WhatsTheWordRequest,
    WhatsTheWordResponse,
)
from app.utils.advisor_utils import (
    ADVISOR_SYSTEM,
    EDITORIAL_SYSTEM,
    EDITORIAL_USER,
    PROACTIVE_SCAN_SYSTEM,
    PROACTIVE_SCAN_USER,
    PROSE_TIGHTEN_SYSTEM,
    PROSE_TIGHTEN_USER,
    SERIES_ADVISOR_SYSTEM,
    SERIES_CONTINUITY_SYSTEM,
    SYNOPSIS_SYSTEM,
    SYNOPSIS_USER,
    VOICE_CONSISTENCY_SYSTEM,
    VOICE_CONSISTENCY_USER,
    build_advisor_suggestions_payload,
    build_advisor_world_analysis,
    build_advisor_world_context,
    build_character_voice_context,
    build_continuity_report_markdown,
    build_continuity_report_pdf,
    build_fallback_advisor_suggestions,
    compute_synopsis_content_fingerprint,
    retrieve_series_continuity_passages,
    generate_whats_the_word_result,
    build_series_story_context,
    build_story_context,
    stream_advisor_reply_payload,
    stream_series_advisor_reply_payload,
    classify_intent,
    classify_response_type,
    detect_advisor_world_mode,
    identify_character_mentions,
    make_advisor_cache_key,
    make_advisor_suggestions_cache_key,
    make_editorial_cache_key,
    normalize_editorial_review_result,
    normalize_proactive_scan_result,
    normalize_prose_tighten_result,
    normalize_series_continuity_result,
    normalize_synopsis_result,
    normalize_voice_consistency_result,
)
from app.utils.book_utils import detect_chapter_continuity_flags
from app.utils.export_utils import export_filename_base
from app.utils.intelligence_utils import compute_voice_metrics, extract_dialogue_samples_by_character, score_voice_match
from app.utils.llm_usage_utils import create_tracked_chat_completion
from app.utils.logging.errors import public_error_message
from app.workers.tasks.intelligence_tasks import generate_advisor_reply_task
from app.workers.tasks.intelligence_tasks import generate_series_advisor_reply_task
from app.workers.tasks.intelligence_tasks import generate_advisor_suggestions_task

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
    description_tokens = {token for token in re.findall(r"[a-z0-9']+", (description or "").lower()) if len(token) > 3}
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
                "total_chapters": body.total_chapters,
            },
        )
    except Exception as exc:
        await mark_advisor_job_failed(
            db,
            job_id=job.id,
            error_code="advisor_enqueue_failed",
            error_detail=public_error_message(500),
        )
        raise
    response.status_code = 202
    return {"task_id": str(job.id), "status": "queued", "cached": False}


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
    except Exception as exc:
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
                total_chapters=body.total_chapters,
            ):
                yield _advisor_sse(item["event"], item["data"])
        except Exception as exc:
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
    result = await db.execute(
        select(Book)
        .where(Book.id == book_id, Book.user_id == current_user.id)
        .options(
            selectinload(Book.characters),
            selectinload(Book.plot_threads),
        )
    )
    book = result.scalars().first()
    if not book:
        raise HTTPException(404)

    return {
        "message": f"What aspect of *{book.title}* feels unsolved right now?",
        "book_title": book.title,
        "stats": {
            "characters": len(book.characters) if book.characters else 0,
            "plot_threads": len(book.plot_threads) if book.plot_threads else 0,
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

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        payload = await generate_whats_the_word_result(
            client=client,
            model=settings.OPENAI_INTEL_MODEL,
            book_title=book.title,
            description=body.description,
            previous_word=body.previous_word,
        )
        return WhatsTheWordResponse(**payload)
    finally:
        await client.close()


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

    async def event_stream():
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            yield _advisor_sse("stage", {"message": "Finding the closest fit..."})
            payload = await generate_whats_the_word_result(
                client=client,
                model=settings.OPENAI_INTEL_MODEL,
                book_title=book.title,
                description=body.description,
                previous_word=body.previous_word,
            )
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(WhatsTheWordResponse(**payload))))
        except Exception as exc:
            yield _advisor_sse("error", {"error": public_error_message(500)})
        finally:
            await client.close()

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

    job = await db.get(AdvisorSuggestionJob, _parse_advisor_job_id(job_id))
    if job is None:
        raise HTTPException(404, detail="suggestion scan job not found")
    if job.user_id != current_user.id or job.book_id != book.id:
        raise HTTPException(403, detail="scan job does not belong to this book")
    return serialize_advisor_suggestion_job(job)


# ─── Editorial Review ─────────────────────────────────────────────────────────

@router.post("/{book_id}/advisor/editorial-review")
async def editorial_review(
    book_id: uuid.UUID,
    body: EditorialReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    """Run an editorial review of a submitted passage:
    - Continuity cross-check against character personality, events, and theme
    - Grammar, spelling, and formatting analysis
    Returns structured JSON suitable for the frontend to render as a categorised report.
    """
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    if not body.text.strip():
        raise HTTPException(400, detail="Passage text is required.")

    # Cache check
    cache_key = make_editorial_cache_key(book_id, body.text, body.chapter_num)
    cached = await get_editorial_review_cache(str(book.id), cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    total_ch = book.total_chapters or 9999
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        # 1. Semantic search
        hits = await semantic_search(
            db,
            book_id,
            body.text[:600],
            total_ch,
            limit=settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
            candidate_limit=settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
            similarity_threshold=settings.ADVISOR_GENERAL_SEARCH_SIMILARITY_THRESHOLD,
            usage_user_id=current_user.id,
            usage_feature="advisor_editorial_search",
        )
        passages_block = "\n\n".join(
            f"Ch. {h['chapter_num']} – {h.get('chapter_title') or 'Untitled'}:\n{h['text'][:320]}"
            for h in hits
        ) or "No closely matching passages found."

        # 2. Build story context
        story_ctx = await build_story_context(db, book_id, total_ch)

        chapter_hint = (
            f"This passage will appear in Chapter {body.chapter_num}."
            if body.chapter_num else
            "Chapter number not specified."
        )

        system_msg = EDITORIAL_SYSTEM.format(
            title=_safe_prompt_str(book.title),
            story_context=_safe_prompt_str(story_ctx),
        )
        user_msg = EDITORIAL_USER.format(
            chapter_hint=chapter_hint,
            text=body.text[:4000],
            passages=passages_block,
        )

        response = await create_tracked_chat_completion(
            client=client,
            feature="advisor_editorial_review",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=book.id,
            temperature=0.2,
            max_tokens=1400,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        result = normalize_editorial_review_result(raw)

        response_payload = {
            "review": result,
            "retrieved_passages": [
                {
                    "chapter_num": h["chapter_num"],
                    "chapter_title": h.get("chapter_title"),
                    "chunk_index": h.get("chunk_index"),
                    "excerpt": h["text"][:220],
                    "relevance": round(h.get("score", 0.0), 3),
                }
                for h in hits[:4]
            ],
            "cached": False,
        }
        await set_editorial_review_cache(str(book.id), cache_key, response_payload)
        return response_payload

    finally:
        await client.close()


@router.post("/{book_id}/advisor/editorial-review-stream")
async def editorial_review_stream(
    book_id: uuid.UUID,
    body: EditorialReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    async def event_stream():
        try:
            yield _advisor_sse("stage", {"message": "Cross-checking continuity and grammar..."})
            payload = await editorial_review(
                book_id=book_id,
                body=body,
                db=db,
                current_user=current_user,
                _=_,
            )
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(payload)))
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_error_message(exc.status_code)})
        except Exception:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())


@router.post("/{book_id}/advisor/prose-tighten", response_model=ProseTightenResponse)
async def prose_tighten(
    book_id: uuid.UUID,
    body: ProseTightenRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    if not body.text.strip():
        raise HTTPException(400, detail="Selected text is required.")

    cache_key = make_editorial_cache_key(book_id, body.text, body.chapter_num)
    cached = await get_prose_tighten_cache(str(book.id), cache_key)
    if cached is not None:
        return ProseTightenResponse(**{**cached, "cached": True})

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        chapter_hint = (
            f"This selection is from Chapter {body.chapter_num}."
            if body.chapter_num else
            "Chapter number not specified."
        )
        response = await create_tracked_chat_completion(
            client=client,
            feature="advisor_prose_tighten",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=book.id,
            temperature=0.2,
            max_tokens=700,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": PROSE_TIGHTEN_SYSTEM.format(title=_safe_prompt_str(book.title)),
                },
                {
                    "role": "user",
                    "content": PROSE_TIGHTEN_USER.format(chapter_hint=chapter_hint, text=body.text[:3500]),
                },
            ],
        )
        normalized = normalize_prose_tighten_result(response.choices[0].message.content or "{}", body.text)
        response_payload = {**normalized, "cached": False}
        await set_prose_tighten_cache(str(book.id), cache_key, response_payload)
        return ProseTightenResponse(**response_payload)
    finally:
        await client.close()


@router.post("/{book_id}/advisor/prose-tighten-stream")
async def prose_tighten_stream(
    book_id: uuid.UUID,
    body: ProseTightenRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    async def event_stream():
        try:
            yield _advisor_sse("stage", {"message": "Tightening the selected prose..."})
            payload = await prose_tighten(
                book_id=book_id,
                body=body,
                db=db,
                current_user=current_user,
                _=_,
            )
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(payload)))
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_error_message(exc.status_code)})
        except Exception:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())


@router.post("/{book_id}/advisor/inline-continuity", response_model=InlineContinuityResponse)
async def inline_continuity_check(
    book_id: uuid.UUID,
    body: InlineContinuityRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    if not body.text.strip():
        raise HTTPException(400, detail="Passage text is required.")

    review_payload = await editorial_review(
        book_id=book_id,
        body=EditorialReviewRequest(text=body.text, chapter_num=body.chapter_num),
        db=db,
        current_user=current_user,
        _=_,
    )
    chapter_flags = (
        await detect_chapter_continuity_flags(db, book_id, body.chapter_num)
        if body.chapter_num is not None
        else []
    )

    issues: list[dict[str, str]] = []
    for issue in review_payload["review"].get("continuity_issues", [])[:8]:
        description = str(issue.get("description") or "").strip()
        issues.append(
            {
                "severity": str(issue.get("severity") or "moderate"),
                "title": str(issue.get("title") or "Continuity check"),
                "snippet": _best_issue_snippet(body.text, description),
                "explanation": description,
                "suggestion": str(issue.get("suggestion") or "").strip(),
            }
        )

    for flag in chapter_flags[:4]:
        issues.append(
            {
                "severity": "moderate",
                "title": "Tracked character memory mismatch",
                "snippet": _best_issue_snippet(body.text, flag),
                "explanation": flag,
                "suggestion": "Reconcile the chapter with the established character state or make the change explicit on page.",
            }
        )

    memory_bank = [
        f"Chapter {item['chapter_num']}: {item['excerpt']}"
        for item in review_payload.get("retrieved_passages", [])[:4]
    ]
    overall_verdict = review_payload["review"].get("overall_verdict") or (
        "No hard continuity contradiction surfaced in this inline pass, but keep pressure-testing setup, memory, and scene-to-scene logic before you lock the scene." if not issues else "Inline continuity pass found issues worth checking before you lock the scene."
    )
    return InlineContinuityResponse(issues=issues, memory_bank=memory_bank, overall_verdict=overall_verdict)


@router.post("/{book_id}/advisor/inline-continuity-stream")
async def inline_continuity_check_stream(
    book_id: uuid.UUID,
    body: InlineContinuityRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    async def event_stream():
        try:
            yield _advisor_sse("stage", {"message": "Checking inline continuity..."})
            payload = await inline_continuity_check(
                book_id=book_id,
                body=body,
                db=db,
                current_user=current_user,
                _=_,
            )
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(payload)))
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_error_message(exc.status_code)})
        except Exception:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())


@router.get("/{book_id}/advisor/synopsis", response_model=SynopsisResponse)
async def manuscript_synopsis(
    book_id: uuid.UUID,
    spoiler_level: str = Query("minimal", pattern="^(minimal|none)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key, Chapter.content_version)
            .where(Chapter.book_id == book_id)
            .order_by(Chapter.number.asc())
            .limit(3)
        )
    ).all()
    if not chapter_rows:
        raise HTTPException(404, "No chapters available for synopsis generation.")

    content_hash = compute_synopsis_content_fingerprint(chapter_rows)
    cached_payload = await get_synopsis_cache(str(book_id), spoiler_level, content_hash)
    if cached_payload is not None:
        cached_payload["cached"] = True
        return SynopsisResponse(**cached_payload)

    passage_blocks: list[str] = []
    coverage: list[str] = []
    for number, chapter_title, s3_key, _content_version in chapter_rows:
        coverage.append(str(number))
        chapter_text = ""
        if s3_key:
            try:
                chapter_text = download_book(s3_key).decode("utf-8", errors="ignore")
            except Exception:
                chapter_text = ""
        chapter_ref = f"Chapter {number}"
        if chapter_title:
            chapter_ref += f" - {chapter_title}"
        passage_blocks.append(f"[{chapter_ref}]\n{chapter_text[:1400]}")

    story_context = await build_story_context(db, book_id, book.total_chapters or len(chapter_rows))
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = await create_tracked_chat_completion(
            client=client,
            feature="advisor_synopsis",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=book.id,
            temperature=0.3,
            max_tokens=700,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": SYNOPSIS_SYSTEM.format(
                        title=_safe_prompt_str(book.title),
                        spoiler_level=spoiler_level,
                        story_context=_safe_prompt_str(story_context),
                    ),
                },
                {
                    "role": "user",
                    "content": SYNOPSIS_USER.format(
                        coverage=", ".join(coverage),
                        passages="\n\n".join(passage_blocks),
                    ),
                },
            ],
        )
        normalized = normalize_synopsis_result(response.choices[0].message.content or "{}", spoiler_level)
        normalized["coverage_chapters"] = [int(item) for item in coverage]
        normalized["cached"] = False
        await set_synopsis_cache(str(book_id), spoiler_level, content_hash, normalized)
        return SynopsisResponse(**normalized)
    finally:
        await client.close()


@router.get("/{book_id}/advisor/synopsis-stream")
async def manuscript_synopsis_stream(
    book_id: uuid.UUID,
    spoiler_level: str = Query("minimal", pattern="^(minimal|none)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    async def event_stream():
        try:
            yield _advisor_sse("stage", {"message": "Summarizing the manuscript..."})
            payload = await manuscript_synopsis(
                book_id=book_id,
                spoiler_level=spoiler_level,
                db=db,
                current_user=current_user,
            )
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(payload)))
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_error_message(exc.status_code)})
        except Exception:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())


@router.post("/{book_id}/advisor/voice-consistency")
async def voice_consistency_review(
    book_id: uuid.UUID,
    body: VoiceConsistencyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    if not body.text.strip():
        raise HTTPException(400, detail="Passage text is required.")

    cache_key = make_editorial_cache_key(book_id, body.text, body.chapter_num, body.character_id)
    cached = await get_voice_consistency_cache(str(book.id), cache_key)
    if cached is not None:
        return {
            **cached,
            "warnings": list(cached.get("warnings") or []),
            "cached": True,
        }

    total_ch = book.total_chapters or 9999
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        hits = await semantic_search(
            db,
            book_id,
            body.text[:600],
            total_ch,
            limit=settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
            candidate_limit=settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
            similarity_threshold=settings.ADVISOR_GENERAL_SEARCH_SIMILARITY_THRESHOLD,
            usage_user_id=current_user.id,
            usage_feature="advisor_voice_consistency_search",
        )
        passages_block = "\n\n".join(
            f"Ch. {h['chapter_num']} - {h.get('chapter_title') or 'Untitled'}:\n{h['text'][:320]}"
            for h in hits
        ) or "No closely matching passages found."

        story_ctx = await build_story_context(db, book_id, total_ch)
        character_rows = (
            await db.execute(
                select(
                    Character.id,
                    Character.name,
                    Character.aliases,
                    Character.role,
                    Character.first_chapter,
                    Character.arc_summary,
                    Character.personality_tags,
                    Character.motivations,
                    Character.fears,
                    Character.trait_state,
                )
                .where(Character.book_id == book_id)
                .order_by(Character.mention_count.desc(), Character.first_chapter, Character.name)
            )
        ).mappings().all()
        character_payloads = [dict(row) for row in character_rows]
        selected_character = None
        if body.character_id is not None:
            selected_character = next(
                (row for row in character_payloads if str(row["id"]) == str(body.character_id)),
                None,
            )
            if selected_character is None:
                raise HTTPException(400, detail="Selected character does not belong to this book.")
            relevant_characters = [selected_character]
        else:
            relevant_characters = identify_character_mentions(body.text, character_payloads)
        all_voice_profiles = (
            await db.execute(
                select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book_id)
            )
        ).scalars().all()
        profiles_by_character_id = {profile.character_id: profile for profile in all_voice_profiles}
        attributed_dialogue = extract_dialogue_samples_by_character(body.text, character_payloads)
        warnings: list[str] = []
        if len(relevant_characters) == 1 and not attributed_dialogue.get(relevant_characters[0]["name"]):
            attributed_dialogue[relevant_characters[0]["name"]] = [body.text[:4000]]
            if body.character_id is not None:
                warnings.append(
                    f"Dialogue could not be confidently attributed to {relevant_characters[0]['name']}; "
                    "the review used the full submitted passage instead."
                )
        character_context = build_character_voice_context(relevant_characters)
        chapter_hint = (
            f"This passage will appear in Chapter {body.chapter_num}."
            if body.chapter_num else
            "Chapter number not specified."
        )

        system_msg = VOICE_CONSISTENCY_SYSTEM.format(
            title=_safe_prompt_str(book.title),
            story_context=_safe_prompt_str(story_ctx),
        )
        user_msg = VOICE_CONSISTENCY_USER.format(
            chapter_hint=chapter_hint,
            character_context=character_context,
            passages=passages_block,
            text=body.text[:4000],
        )

        response = await create_tracked_chat_completion(
            client=client,
            feature="advisor_voice_consistency",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=book.id,
            temperature=0.2,
            max_tokens=1200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        result = normalize_voice_consistency_result(raw)
        character_matches: list[dict[str, Any]] = []
        for character in relevant_characters:
            char_id = character.get("id")
            char_name = character.get("name")
            profile = profiles_by_character_id.get(uuid.UUID(str(char_id))) if char_id else None
            samples = attributed_dialogue.get(str(char_name), [])
            sample_metrics = compute_voice_metrics(samples)
            profile_payload = {
                "sample_dialogue_count": profile.sample_dialogue_count if profile else 0,
                "sample_word_count": profile.sample_word_count if profile else 0,
                "avg_sentence_length": profile.avg_sentence_length if profile else 0,
                "avg_word_length_x100": profile.avg_word_length_x100 if profile else 0,
                "contraction_rate_x1000": profile.contraction_rate_x1000 if profile else 0,
                "question_rate_x1000": profile.question_rate_x1000 if profile else 0,
                "exclamation_rate_x1000": profile.exclamation_rate_x1000 if profile else 0,
                "ellipsis_rate_x1000": profile.ellipsis_rate_x1000 if profile else 0,
                "dash_rate_x1000": profile.dash_rate_x1000 if profile else 0,
                "uppercase_rate_x1000": profile.uppercase_rate_x1000 if profile else 0,
                "formality_score_x1000": profile.formality_score_x1000 if profile else 0,
                "lexical_complexity_x1000": profile.lexical_complexity_x1000 if profile else 0,
                "emotional_intensity_x1000": profile.emotional_intensity_x1000 if profile else 0,
            }
            score, signals = score_voice_match(profile_payload, sample_metrics)
            closest_other_character = None
            closest_other_score = -1
            character_uuid = uuid.UUID(str(char_id)) if char_id else None
            for candidate_profile in all_voice_profiles:
                if character_uuid is not None and candidate_profile.character_id == character_uuid:
                    continue
                candidate_score, _ = score_voice_match(
                    {
                        "sample_dialogue_count": candidate_profile.sample_dialogue_count,
                        "sample_word_count": candidate_profile.sample_word_count,
                        "avg_sentence_length": candidate_profile.avg_sentence_length,
                        "avg_word_length_x100": candidate_profile.avg_word_length_x100,
                        "contraction_rate_x1000": candidate_profile.contraction_rate_x1000,
                        "question_rate_x1000": candidate_profile.question_rate_x1000,
                        "exclamation_rate_x1000": candidate_profile.exclamation_rate_x1000,
                        "ellipsis_rate_x1000": candidate_profile.ellipsis_rate_x1000,
                        "dash_rate_x1000": candidate_profile.dash_rate_x1000,
                        "uppercase_rate_x1000": candidate_profile.uppercase_rate_x1000,
                        "formality_score_x1000": candidate_profile.formality_score_x1000,
                        "lexical_complexity_x1000": candidate_profile.lexical_complexity_x1000,
                        "emotional_intensity_x1000": candidate_profile.emotional_intensity_x1000,
                    },
                    sample_metrics,
                )
                if candidate_score > closest_other_score:
                    closest_other_score = candidate_score
                    closest_other_character = next(
                        (row["name"] for row in character_rows if str(row["id"]) == str(candidate_profile.character_id)),
                        None,
                    )
            character_matches.append(
                {
                    "character_name": char_name,
                    "match_score": score,
                    "baseline_sample_size": int(profile.sample_dialogue_count if profile else 0),
                    "sample_dialogue_count": int(sample_metrics.get("sample_dialogue_count") or 0),
                    "strongest_signals": signals,
                    "closest_other_character": closest_other_character,
                    "closest_other_score": closest_other_score if closest_other_score >= 0 else None,
                }
            )

        response_payload = {
            "review": result,
            "retrieved_passages": [
                {
                    "chapter_num": h["chapter_num"],
                    "chapter_title": h.get("chapter_title"),
                    "chunk_index": h.get("chunk_index"),
                    "excerpt": h["text"][:220],
                    "relevance": round(h.get("score", 0.0), 3),
                }
                for h in hits[:4]
            ],
            "characters_reviewed": [character["name"] for character in relevant_characters],
            "character_matches": character_matches,
            "warnings": warnings,
        }
        response_payload["cached"] = False
        await set_voice_consistency_cache(str(book.id), cache_key, response_payload)
        return response_payload
    finally:
        await client.close()


@router.post("/{book_id}/advisor/voice-consistency-stream")
async def voice_consistency_review_stream(
    book_id: uuid.UUID,
    body: VoiceConsistencyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    async def event_stream():
        try:
            yield _advisor_sse("stage", {"message": "Comparing the passage to voice baselines..."})
            payload = await voice_consistency_review(
                book_id=book_id,
                body=body,
                db=db,
                current_user=current_user,
                _=_,
            )
            yield _advisor_sse("done", cast(dict[str, Any], jsonable_encoder(payload)))
        except HTTPException as exc:
            yield _advisor_sse("error", {"error": public_error_message(exc.status_code)})
        except Exception:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())


# ─── Continuity report download ───────────────────────────────────────────────

@router.get("/{book_id}/advisor/continuity-report")
async def continuity_report(
    book_id: uuid.UUID,
    text: str = Query(...),
    chapter_num: int | None = Query(None),
    format: str = Query("pdf", pattern="^(pdf|md)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    if not text.strip():
        raise HTTPException(400, detail="Passage text is required.")

    review_payload = await editorial_review(
        book_id=book_id,
        body=EditorialReviewRequest(text=text, chapter_num=chapter_num),
        db=db,
        current_user=current_user,
        _=_,
    )
    suggestions_payload = await advisor_suggestions(book_id=book_id, db=db, current_user=current_user)
    open_threads = [
        item for item in suggestions_payload.get("suggestions", [])
        if item.get("type") in {"dropped_thread", "future_direction", "unresolved_clue", "arc_opportunity"}
    ][:8]

    markdown = build_continuity_report_markdown(
        title=book.title,
        chapter_num=chapter_num,
        review=review_payload["review"],
        retrieved_passages=review_payload["retrieved_passages"],
        open_threads=open_threads,
    )
    filename_base = export_filename_base(book.title)

    if format == "md":
        return Response(
            content=markdown.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}-continuity-report.md"'},
        )

    raw = build_continuity_report_pdf(markdown, title=book.title, chapter_num=chapter_num)
    return Response(
        content=raw,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}-continuity-report.pdf"'},
    )


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
        except Exception as exc:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/series/{series_id}/advisor/message/{task_id}", response_model=AdvisorTaskStatusResponse)
async def series_advisor_message_status(
    series_id: uuid.UUID,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await db.get(Series, series_id)
    if not series or series.user_id != current_user.id:
        raise HTTPException(404)

    job = await db.get(AdvisorJob, _parse_advisor_job_id(task_id))
    if job is None:
        raise HTTPException(404, detail="advisor task not found")
    if job.user_id != current_user.id or job.scope != ADVISOR_SCOPE_SERIES or job.series_id != series.id:
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
    cached_series = await get_series_continuity_cache(str(series.id), str(current_book.id), series_cache_key)
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
            row.book_id for row in memberships
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
                "thematic_fit": {"score": "strong", "notes": "No prior books in series to compare against."},
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
        db, prior_book_ids, prior_titles,
        max_chars_per_book=8, max_threads_per_book=5,
    )

    # RAG: retrieve relevant passages from prior books only (cross-series search)
    hits = await retrieve_series_continuity_passages(
        db=db,
        prior_book_ids=prior_book_ids,
        query=body.text[:600],
        user_id=current_user.id,
        book_id=current_book.id,
    )

    passages_block = "\n\n".join(
        f"[{h['book_title']} — Ch. {h['chapter_num']}]: {h['text'][:300]}"
        for h in hits
    ) or "No closely matching passages found in earlier books."

    chapter_hint = (
        f"This passage will appear in Chapter {body.chapter_num} of \"{current_book.title}\"."
        if body.chapter_num
        else f"Chapter number not specified. Book: \"{current_book.title}\"."
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

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
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
        await set_series_continuity_cache(str(series.id), str(current_book.id), series_cache_key, response_payload)
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
        except Exception:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())
