"""
Grounded intelligence routes: contextual Q&A.
"""

import hashlib
import json
import uuid
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_chat
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import (
    cache_get,
    cache_set,
    get_cross_book_intelligence_cache,
    key_grounded_answer,
    set_cross_book_intelligence_cache,
)
from app.models.book import Book, Series, SeriesBook
from app.schemas.intelligence import (
    CrossBookIntelligenceOut,
    CrossBookMatchOut,
    GroundedAnswerOut,
    GroundedCitationOut,
    QARequest,
)
from app.services.llm_control_service import (
    fail_llm_reservation,
    finish_llm_reservation_counts,
    reserve_llm_call,
)
from app.utils.billing_utils import require_author_access
from app.utils.intelligence_utils import (
    build_grounded_qa_context,
    compute_cross_book_snapshot_hash,
    get_cross_book_character_matches,
    get_cross_book_wiki_matches,
)
from app.utils.llm_usage_utils import (
    assert_llm_token_capacity,
    create_tracked_chat_completion,
    estimate_chat_completion_tokens,
    record_llm_usage_counts,
)
from app.utils.logging.errors import public_error_message
from app.utils.retry_utils import LLM_MAX_RETRIES

router = APIRouter()
GROUNDED_QA_STREAM_EXCEPTIONS = (OpenAIError, RuntimeError, ValueError, SQLAlchemyError)


@router.get("/{book_id}/cross-book-intelligence", response_model=CrossBookIntelligenceOut)
async def cross_book_intelligence(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    comparison_books = [book]
    series_name = None
    if book.primary_series_id:
        series = await db.get(Series, book.primary_series_id)
        series_name = series.name if series else None
        series_book_rows_result = await db.execute(
            select(Book)
            .join(SeriesBook, SeriesBook.book_id == Book.id)
            .where(
                SeriesBook.series_id == book.primary_series_id,
                Book.user_id == current_user.id,
            )
        )
        series_book_rows = series_book_rows_result.scalars().all()
        comparison_books = list(series_book_rows) or [book]

    book_ids = [item.id for item in comparison_books]
    sorted_book_id_strs = sorted(str(bid) for bid in book_ids)
    books_hash = hashlib.md5(",".join(sorted_book_id_strs).encode()).hexdigest()[:12]
    snapshot_hash = await compute_cross_book_snapshot_hash(db, book_ids)

    cached = await get_cross_book_intelligence_cache(books_hash, snapshot_hash)
    if cached is not None:
        return CrossBookIntelligenceOut(**{**cached, "cached": True})

    character_matches_raw = await get_cross_book_character_matches(db, book_ids)
    wiki_matches_raw = await get_cross_book_wiki_matches(db, book_ids)

    payload = {
        "series_name": series_name,
        "comparison_book_ids": sorted_book_id_strs,
        "character_matches": [CrossBookMatchOut(**match) for match in character_matches_raw],
        "wiki_matches": [CrossBookMatchOut(**match) for match in wiki_matches_raw],
    }
    await set_cross_book_intelligence_cache(books_hash, snapshot_hash, payload)
    return CrossBookIntelligenceOut(**payload)


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=LLM_MAX_RETRIES)


def _intelligence_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _grounded_answer_out_from_payload(
    payload: dict[str, Any],
    *,
    cached: bool = False,
) -> GroundedAnswerOut:
    citations_payload = cast(list[dict[str, Any]], payload.get("citations") or [])
    return GroundedAnswerOut(
        answer=str(payload["answer"]),
        citations=[
            GroundedCitationOut(
                chapter_num=int(cast(Any, citation["chapter_num"])),
                chapter_title=cast(str | None, citation.get("chapter_title")),
                excerpt=str(cast(Any, citation["excerpt"])),
                source_type=cast(
                    Literal["summary", "passage"],
                    cast(Any, citation["source_type"]),
                ),
                relevance=cast(float | None, citation.get("relevance")),
            )
            for citation in citations_payload
        ],
        cached=cached,
    )


@router.post("/{book_id}/qa", response_model=GroundedAnswerOut)
async def qa_endpoint(
    book_id: uuid.UUID,
    body: QARequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_chat),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)
    cache_key = key_grounded_answer(str(book_id), body.current_chapter, body.question)
    cached = await cache_get(cache_key)
    if cached:
        return _grounded_answer_out_from_payload(cast(dict[str, Any], cached), cached=True)

    context_blocks, citations = await build_grounded_qa_context(
        db=db,
        book=book,
        user_id=current_user.id,
        question=body.question,
        current_chapter=body.current_chapter,
    )

    system = (
        f'You answer questions about "{book.title}" using only the provided material.\n'
        f"The reader has completed up to chapter {body.current_chapter}.\n"
        "If earlier books in the same series are provided as prior-volume context, you may use them to answer questions about past lore.\n"
        "Rules:\n"
        "- Answer only from text and summaries provided.\n"
        "- Do not predict future events or speculate.\n"
        "- If the answer is not grounded in the provided material, say so plainly.\n"
        "- Keep the response concise but useful.\n"
        "- Prefer 1-3 short sentences.\n"
        "- When grounded, mention the most relevant chapter number directly in the answer.\n"
    )

    client = get_client()
    try:
        response = await create_tracked_chat_completion(
            client=client,
            feature="grounded_qa",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=book.id,
            temperature=0.2,
            max_tokens=220,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Question: {body.question}\n\nContext:\n\n"
                    + "\n\n".join(context_blocks),
                },
            ],
        )
        answer = (response.choices[0].message.content or "").strip()
        payload = {"answer": answer, "citations": citations}
        await cache_set(cache_key, payload, settings.REDIS_TTL_SUMMARY)
        return _grounded_answer_out_from_payload(payload)
    finally:
        await client.close()


@router.post("/{book_id}/qa-stream")
async def qa_stream_endpoint(
    book_id: uuid.UUID,
    body: QARequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_chat),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    cache_key = key_grounded_answer(str(book_id), body.current_chapter, body.question)
    cached = await cache_get(cache_key)
    if cached:
        cached_payload = _grounded_answer_out_from_payload(
            cast(dict[str, Any], cached), cached=True
        )

        async def cached_stream():
            yield _intelligence_sse("done", cast(dict[str, Any], jsonable_encoder(cached_payload)))

        return StreamingResponse(
            cached_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    context_blocks, citations = await build_grounded_qa_context(
        db=db,
        book=book,
        user_id=current_user.id,
        question=body.question,
        current_chapter=body.current_chapter,
    )

    system = (
        f'You answer questions about "{book.title}" using only the provided material.\n'
        f"The reader has completed up to chapter {body.current_chapter}.\n"
        "If earlier books in the same series are provided as prior-volume context, you may use them to answer questions about past lore.\n"
        "Rules:\n"
        "- Answer only from text and summaries provided.\n"
        "- Do not predict future events or speculate.\n"
        "- If the answer is not grounded in the provided material, say so plainly.\n"
        "- Keep the response concise but useful.\n"
        "- Prefer 1-3 short sentences.\n"
        "- When grounded, mention the most relevant chapter number directly in the answer.\n"
    )
    llm_messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Question: {body.question}\n\nContext:\n\n" + "\n\n".join(context_blocks),
        },
    ]

    async def event_stream():
        client = get_client()
        answer_parts: list[str] = []
        usage_counts: tuple[int, int, int] | None = None
        reservation = None
        try:
            reservation = await reserve_llm_call(
                user_id=current_user.id,
                estimated_tokens=estimate_chat_completion_tokens(
                    {"messages": llm_messages, "max_tokens": 220}
                ),
                feature="grounded_qa",
                operation="chat",
                model=settings.OPENAI_INTEL_MODEL,
                book_id=book.id,
            )
            yield _intelligence_sse("stage", {"message": "Searching grounded context..."})
            stream = await client.chat.completions.create(
                model=settings.OPENAI_INTEL_MODEL,
                temperature=0.2,
                max_tokens=220,
                messages=llm_messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            yield _intelligence_sse("stage", {"message": "Writing grounded answer..."})
            async for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    usage_counts = (
                        int(getattr(usage, "prompt_tokens", 0) or 0),
                        int(getattr(usage, "completion_tokens", 0) or 0),
                        int(getattr(usage, "total_tokens", 0) or 0),
                    )
                for choice in getattr(chunk, "choices", []) or []:
                    content = getattr(getattr(choice, "delta", None), "content", None)
                    if content:
                        answer_parts.append(content)
                        yield _intelligence_sse("delta", {"content": content})

            if usage_counts is not None:
                await finish_llm_reservation_counts(
                    reservation,
                    prompt_tokens=usage_counts[0],
                    completion_tokens=usage_counts[1],
                    total_tokens=usage_counts[2],
                )
                reservation = None

            payload = {"answer": "".join(answer_parts).strip(), "citations": citations}
            await cache_set(cache_key, payload, settings.REDIS_TTL_SUMMARY)
            response_payload = _grounded_answer_out_from_payload(payload)
            yield _intelligence_sse(
                "done", cast(dict[str, Any], jsonable_encoder(response_payload))
            )
        except HTTPException as exc:
            if reservation is not None:
                await fail_llm_reservation(reservation)
                reservation = None
            yield _intelligence_sse("error", {"error": str(exc.detail)})
        except GROUNDED_QA_STREAM_EXCEPTIONS:
            if reservation is not None:
                await fail_llm_reservation(reservation)
                reservation = None
            yield _intelligence_sse("error", {"error": public_error_message(500)})
        finally:
            if reservation is not None:
                await fail_llm_reservation(reservation)
            await client.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
