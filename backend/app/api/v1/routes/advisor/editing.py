from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_continuity_checker
from app.api.v1.routes.advisor.chat import (
    _advisor_sse,
    _advisor_stream_response,
    _best_issue_snippet,
    _safe_prompt_str,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.llm import get_openai_client
from app.core.redis import (
    get_book_cache_version,
    get_editorial_review_cache,
    get_prose_tighten_cache,
    set_editorial_review_cache,
    set_prose_tighten_cache,
)
from app.engine.analysis.summariser import _analysis_passages
from app.engine.search.semantic import hybrid_story_search
from app.models.book import Book
from app.schemas.advisor import (
    EditorialReviewRequest,
    InlineContinuityRequest,
    InlineContinuityResponse,
    ProseTightenRequest,
    ProseTightenResponse,
)
from app.utils.advisor_route_errors import ADVISOR_STREAM_ERRORS
from app.utils.advisor_utils import (
    EDITORIAL_SYSTEM,
    EDITORIAL_USER,
    PROSE_TIGHTEN_SYSTEM,
    PROSE_TIGHTEN_USER,
    build_story_context,
    make_editorial_cache_key,
    merge_editorial_review_results,
    normalize_editorial_review_result,
    normalize_prose_tighten_result,
)
from app.utils.books.continuity import detect_chapter_continuity_flags
from app.utils.llm_usage_utils import (
    create_tracked_chat_completion,
    public_llm_http_error_message,
)
from app.utils.logging.errors import public_error_message

router = APIRouter()


@router.post("/{book_id}/advisor/editorial-review")
async def editorial_review(
    book_id: uuid.UUID,
    body: EditorialReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_continuity_checker),
):
    """Run an editorial review of a submitted passage.

    The review cross-checks continuity, grammar, spelling, and formatting, and
    returns structured JSON suitable for frontend rendering.
    """
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    if not body.text.strip():
        raise HTTPException(400, detail="Passage text is required.")

    cache_key = make_editorial_cache_key(book_id, body.text, body.chapter_num)
    cache_version = await get_book_cache_version(str(book.id))
    cached = await get_editorial_review_cache(str(book.id), cache_key, version=cache_version)
    if cached is not None:
        return {**cached, "cached": True}

    total_ch = int(book.total_chapters or 0)
    client = get_openai_client()

    try:
        hits = await hybrid_story_search(
            db,
            book_id,
            body.text,
            total_ch,
            limit=settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
            candidate_limit=settings.ADVISOR_GENERAL_SEARCH_CHUNKS * 3,
            similarity_threshold=settings.ADVISOR_GENERAL_SEARCH_SIMILARITY_THRESHOLD,
            usage_user_id=current_user.id,
            usage_feature="advisor_editorial_search",
        )
        passages_block = (
            "\n\n".join(
                f"Ch. {h['chapter_num']} - {h.get('chapter_title') or 'Untitled'}:\n{h['text'][:320]}"
                for h in hits
            )
            or "No closely matching passages found."
        )

        story_ctx = await build_story_context(db, book_id, total_ch)
        chapter_hint = (
            f"This passage will appear in Chapter {body.chapter_num}."
            if body.chapter_num
            else "Chapter number not specified."
        )

        system_msg = EDITORIAL_SYSTEM.format(
            title=_safe_prompt_str(book.title),
            story_context=_safe_prompt_str(story_ctx),
        )
        review_results: list[dict] = []
        review_passages = _analysis_passages(body.text, max_chars=3800)
        for part_index, review_passage in enumerate(review_passages, start=1):
            part_hint = chapter_hint
            if len(review_passages) > 1:
                part_hint = (
                    f"{chapter_hint} This is passage {part_index} of "
                    f"{len(review_passages)} from the same submitted chapter."
                )
            user_msg = EDITORIAL_USER.format(
                chapter_hint=part_hint,
                text=review_passage,
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
            review_results.append(normalize_editorial_review_result(raw))
        result = merge_editorial_review_results(review_results)
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
        await set_editorial_review_cache(
            str(book.id),
            cache_key,
            response_payload,
            expected_version=cache_version,
        )
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
            yield _advisor_sse("error", {"error": public_llm_http_error_message(exc)})
        except ADVISOR_STREAM_ERRORS:
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
    cache_version = await get_book_cache_version(str(book.id))
    cached = await get_prose_tighten_cache(str(book.id), cache_key, version=cache_version)
    if cached is not None:
        return ProseTightenResponse(**{**cached, "cached": True})

    client = get_openai_client()
    try:
        chapter_hint = (
            f"This selection is from Chapter {body.chapter_num}."
            if body.chapter_num
            else "Chapter number not specified."
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
                    "content": PROSE_TIGHTEN_USER.format(
                        chapter_hint=chapter_hint, text=body.text[:3500]
                    ),
                },
            ],
        )
        normalized = normalize_prose_tighten_result(
            response.choices[0].message.content or "{}", body.text
        )
        response_payload = {**normalized, "cached": False}
        await set_prose_tighten_cache(
            str(book.id),
            cache_key,
            response_payload,
            expected_version=cache_version,
        )
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
            yield _advisor_sse("error", {"error": public_llm_http_error_message(exc)})
        except ADVISOR_STREAM_ERRORS:
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
        "No hard continuity contradiction surfaced in this inline pass, but keep pressure-testing setup, memory, and scene-to-scene logic before you lock the scene."
        if not issues
        else "Inline continuity pass found issues worth checking before you lock the scene."
    )
    return InlineContinuityResponse(
        issues=issues, memory_bank=memory_bank, overall_verdict=overall_verdict
    )


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
            yield _advisor_sse("error", {"error": public_llm_http_error_message(exc)})
        except ADVISOR_STREAM_ERRORS:
            yield _advisor_sse("error", {"error": public_error_message(500)})

    return _advisor_stream_response(event_stream())
