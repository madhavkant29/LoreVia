from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.v1.routes.advisor.chat import (
    _advisor_sse,
    _advisor_stream_response,
    _safe_prompt_str,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.llm import get_openai_client
from app.core.redis import get_synopsis_cache, set_synopsis_cache
from app.core.storage import download_book
from app.models.book import Book, Chapter
from app.schemas.advisor import SynopsisResponse
from app.utils.advisor_route_errors import ADVISOR_CONTENT_READ_ERRORS, ADVISOR_STREAM_ERRORS
from app.utils.advisor_utils import (
    SYNOPSIS_SYSTEM,
    SYNOPSIS_USER,
    build_story_context,
    compute_synopsis_content_fingerprint,
    normalize_synopsis_result,
)
from app.utils.billing_utils import require_author_access
from app.utils.llm_usage_utils import (
    create_tracked_chat_completion,
    public_llm_http_error_message,
)
from app.utils.logging.errors import public_error_message

router = APIRouter()


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
    require_author_access(current_user)

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
                chapter_text = (await asyncio.to_thread(download_book, s3_key)).decode(
                    "utf-8", errors="ignore"
                )
            except ADVISOR_CONTENT_READ_ERRORS:
                chapter_text = ""
        chapter_ref = f"Chapter {number}"
        if chapter_title:
            chapter_ref += f" - {chapter_title}"
        passage_blocks.append(f"[{chapter_ref}]\n{chapter_text[:1400]}")

    story_context = await build_story_context(db, book_id, book.total_chapters or len(chapter_rows))
    client = get_openai_client()
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
    normalized = normalize_synopsis_result(
        response.choices[0].message.content or "{}", spoiler_level
    )
    normalized["coverage_chapters"] = [int(item) for item in coverage]
    normalized["cached"] = False
    await set_synopsis_cache(str(book_id), spoiler_level, content_hash, normalized)
    return SynopsisResponse(**normalized)


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
            yield _advisor_sse("error", {"error": public_llm_http_error_message(exc)})
        except ADVISOR_STREAM_ERRORS:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())
