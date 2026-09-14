from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import get_openai_client
from app.core.redis import (
    get_advisor_response_cache,
    get_book_cache_version,
    get_series_advisor_response_cache,
    get_series_cache_version,
    set_advisor_response_cache,
    set_series_advisor_response_cache,
)
from app.engine.search.semantic import semantic_search
from app.models.book import Book, SeriesBook
from app.services.llm_circuit_breaker_service import (
    acquire_provider_circuit_permit,
    record_provider_failure,
    record_provider_success,
    release_provider_circuit_permit,
)
from app.services.llm_control_service import (
    fail_llm_reservation,
    finish_llm_reservation,
    finish_llm_reservation_counts,
    reserve_llm_call,
)
from app.utils.advisor_classification_utils import classify_intent_fast
from app.utils.advisor_prompt_templates import ADVISOR_SYSTEM, SERIES_ADVISOR_SYSTEM
from app.utils.advisor_prompt_utils import make_advisor_cache_key, safe_prompt_str
from app.utils.advisor_retrieval_utils import (
    advisor_retrieval_settings,
    build_advisor_world_analysis,
    detect_advisor_world_mode,
)
from app.utils.advisor_story_context_utils import build_series_story_context, build_story_context
from app.utils.advisor_world_context_utils import build_advisor_world_context
from app.utils.llm_usage_utils import (
    LLM_PROVIDER_CALL_EXCEPTIONS,
    create_tracked_chat_completion,
    estimate_chat_completion_token_parts,
    is_transient_llm_provider_error,
)


async def classify_response_type(client: AsyncOpenAI | None, reply: str) -> str:
    """Classify response type by emoji marker prefix."""
    if reply.startswith("⚠️") or "⚠️ Contradiction" in reply[:200]:
        return "warning"
    if reply.startswith("✨") or "✨ Opportunity" in reply[:200]:
        return "opportunity"
    if "🔀 Option" in reply[:400]:
        return "tradeoff"
    return "standard"


async def prepare_advisor_reply_context(
    *,
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
    total_chapters: int,
) -> dict[str, Any]:
    if not messages:
        raise ValueError("messages list is empty")

    last_user_msg = next(
        (
            str(message.get("content") or "")
            for message in reversed(messages)
            if message.get("role") == "user"
        ),
        "",
    ).strip()
    if not last_user_msg:
        raise ValueError("no user message found")

    cache_key = make_advisor_cache_key(book.id, last_user_msg)
    cache_version = await get_book_cache_version(str(book.id))
    cached = await get_advisor_response_cache(str(book.id), cache_key, version=cache_version)
    if cached is not None:
        return {"cached": {**cached, "cached": True}}

    history = messages[-20:]
    intent = classify_intent_fast(last_user_msg)
    story_context = await build_story_context(db, book.id, book.total_chapters or 0)
    world_mode = detect_advisor_world_mode(last_user_msg, intent)
    world_analysis = (
        await build_advisor_world_analysis(db, book, last_user_msg, world_mode)
        if world_mode
        else None
    )
    world_context = build_advisor_world_context(world_analysis)

    chunk_limit, threshold = advisor_retrieval_settings(intent, world_mode)
    hits = await semantic_search(
        db,
        book.id,
        last_user_msg,
        total_chapters,
        limit=chunk_limit,
        candidate_limit=chunk_limit,
        similarity_threshold=threshold,
        usage_user_id=user_id,
        usage_feature="advisor_message_query_embedding",
    )

    passage_blocks: list[str] = []
    for hit in hits:
        chapter_ref = f"Chapter {hit['chapter_num']}"
        if hit.get("chapter_title"):
            chapter_ref += f" — {hit['chapter_title']}"
        passage_blocks.append(f"[{chapter_ref}]\n{hit['text'][:380]}")

    retrieved_context = (
        "\n\n".join(passage_blocks)
        if passage_blocks
        else "No passage excerpts matched this query — reason from the STORY KNOWLEDGE above."
    )

    intent_hint = {
        "consistency": "[AUTHOR INTENT DETECTED: check for contradictions and continuity violations]",
        "plothole": "[AUTHOR INTENT DETECTED: look for logical gaps and unresolved inconsistencies]",
        "direction": "[AUTHOR INTENT DETECTED: debate options and walk through narrative tradeoffs]",
        "opportunity": "[AUTHOR INTENT DETECTED: surface foreshadowing and arc opportunities]",
    }.get(intent, "")
    if world_mode == "gap_detection":
        intent_hint = "[AUTHOR INTENT DETECTED: check world-building, canon, lore coverage, and world-gap issues]"
    elif world_mode == "story_integration":
        intent_hint = "[AUTHOR INTENT DETECTED: use world-building lore to find story integration options]"

    augmented_last = (
        f"{last_user_msg}\n\n"
        + (f"{intent_hint}\n\n" if intent_hint else "")
        + f"--- Retrieved passages ---\n{retrieved_context}"
        + (f"\n\n{world_context}" if world_context else "")
    )

    system_prompt = ADVISOR_SYSTEM.format(
        title=safe_prompt_str(book.title),
        story_context=safe_prompt_str(story_context),
    )
    llm_messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": system_prompt}]
    for message in history[:-1]:
        llm_messages.append(
            {
                "role": str(message.get("role") or "user"),
                "content": str(message.get("content") or ""),
            }
        )
    llm_messages.append({"role": "user", "content": augmented_last})

    return {
        "cached": None,
        "cache_key": cache_key,
        "cache_version": cache_version,
        "client": get_openai_client(),
        "intent": intent,
        "hits": hits,
        "world_analysis": world_analysis,
        "llm_messages": llm_messages,
    }


async def finalize_advisor_reply_payload(
    *,
    db: AsyncSession,
    client: AsyncOpenAI,
    book: Book,
    cache_key: str,
    cache_version: int,
    reply: str,
    intent: str,
    hits: list[dict[str, Any]],
    world_analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    response_type = await classify_response_type(client, reply)
    result = {
        "reply": reply,
        "intent": intent,
        "response_type": response_type,
        "retrieved_passages": [
            {
                "chapter_num": hit["chapter_num"],
                "chapter_title": hit.get("chapter_title"),
                "excerpt": hit["text"][:240],
                "relevance": hit["relevance"],
            }
            for hit in hits[:5]
        ],
        "world_analysis": world_analysis,
        "cached": False,
    }
    await set_advisor_response_cache(
        str(book.id),
        cache_key,
        result,
        expected_version=cache_version,
    )
    await db.commit()
    return result


async def build_advisor_reply_payload(
    *,
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
    total_chapters: int,
) -> dict[str, Any]:
    prepared = await prepare_advisor_reply_context(
        db=db,
        book=book,
        user_id=user_id,
        messages=messages,
        total_chapters=total_chapters,
    )
    if prepared["cached"] is not None:
        return prepared["cached"]

    client = prepared["client"]
    response = await create_tracked_chat_completion(
        client=client,
        feature="advisor_message",
        model=settings.OPENAI_INTEL_MODEL,
        db=db,
        user_id=user_id,
        book_id=book.id,
        temperature=0.55,
        max_tokens=800,
        messages=prepared["llm_messages"],
    )
    reply = (response.choices[0].message.content or "").strip()
    return await finalize_advisor_reply_payload(
        db=db,
        client=client,
        book=book,
        cache_key=prepared["cache_key"],
        cache_version=prepared["cache_version"],
        reply=reply,
        intent=prepared["intent"],
        hits=prepared["hits"],
        world_analysis=prepared["world_analysis"],
    )


async def stream_advisor_reply_payload(
    *,
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
    total_chapters: int,
) -> AsyncIterator[dict[str, Any]]:
    prepared = await prepare_advisor_reply_context(
        db=db,
        book=book,
        user_id=user_id,
        messages=messages,
        total_chapters=total_chapters,
    )
    if prepared["cached"] is not None:
        yield {"event": "done", "data": prepared["cached"]}
        return

    client = prepared["client"]
    reply_parts: list[str] = []
    usage_counts: tuple[int, int, int] | None = None
    reservation = None
    permit = None
    provider_completed = False
    provider_failure_transient: bool | None = None
    try:
        estimated_prompt_tokens, estimated_completion_tokens = estimate_chat_completion_token_parts(
            {"messages": prepared["llm_messages"], "max_tokens": 800}
        )
        permit = await acquire_provider_circuit_permit(
            provider="openai", model=settings.OPENAI_INTEL_MODEL
        )
        try:
            reservation = await reserve_llm_call(
                user_id=user_id,
                estimated_prompt_tokens=estimated_prompt_tokens,
                estimated_completion_tokens=estimated_completion_tokens,
                feature="advisor_message",
                operation="chat",
                model=settings.OPENAI_INTEL_MODEL,
                book_id=book.id,
                budget_class="interactive",
            )
        except BaseException:
            await release_provider_circuit_permit(permit)
            permit = None
            raise
        stream = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
            temperature=0.55,
            max_tokens=800,
            messages=prepared["llm_messages"],
            stream=True,
            stream_options={"include_usage": True},
        )
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
                    reply_parts.append(content)
                    yield {"event": "delta", "data": {"content": content}}
        provider_completed = True

        if usage_counts is not None:
            await finish_llm_reservation_counts(
                reservation,
                prompt_tokens=usage_counts[0],
                completion_tokens=usage_counts[1],
                total_tokens=usage_counts[2],
            )
        else:
            await finish_llm_reservation(reservation, None)
        reservation = None

        reply = "".join(reply_parts).strip()
        result = await finalize_advisor_reply_payload(
            db=db,
            client=client,
            book=book,
            cache_key=prepared["cache_key"],
            cache_version=prepared["cache_version"],
            reply=reply,
            intent=prepared["intent"],
            hits=prepared["hits"],
            world_analysis=prepared["world_analysis"],
        )
        yield {"event": "done", "data": result}
    except LLM_PROVIDER_CALL_EXCEPTIONS as exc:
        if not provider_completed:
            provider_failure_transient = is_transient_llm_provider_error(exc)
        raise
    finally:
        if reservation is not None:
            await fail_llm_reservation(reservation)
        if permit is not None:
            if provider_completed:
                await record_provider_success(permit)
            elif provider_failure_transient is not None:
                await record_provider_failure(
                    permit,
                    transient=provider_failure_transient,
                )
            else:
                await release_provider_circuit_permit(permit)


async def prepare_series_advisor_reply_context(
    *,
    db: AsyncSession,
    series: Any,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    if not messages:
        raise ValueError("messages list is empty")

    last_user_msg = next(
        (
            str(message.get("content") or "")
            for message in reversed(messages)
            if message.get("role") == "user"
        ),
        "",
    ).strip()
    if not last_user_msg:
        raise ValueError("no user message found")

    cache_key = make_advisor_cache_key(f"series:{series.id}", last_user_msg)
    cache_version = await get_series_cache_version(str(series.id))
    cached = await get_series_advisor_response_cache(
        str(series.id),
        cache_key,
        version=cache_version,
    )
    if cached is not None:
        return {"cached": {**cached, "cached": True}}

    memberships = (
        await db.execute(
            select(SeriesBook.book_id, SeriesBook.position)
            .where(SeriesBook.series_id == series.id)
            .order_by(SeriesBook.position.asc().nulls_last())
        )
    ).all()
    if not memberships:
        raise ValueError("no_books_found_in_series")

    book_ids = [row.book_id for row in memberships]
    book_rows = (await db.execute(select(Book.id, Book.title).where(Book.id.in_(book_ids)))).all()
    book_titles = {row.id: row.title for row in book_rows}
    story_context = await build_series_story_context(
        db,
        book_ids,
        book_titles,
        max_chars_per_book=6,
        max_threads_per_book=4,
    )

    history = messages[-16:]
    system_prompt = SERIES_ADVISOR_SYSTEM.format(
        series_name=safe_prompt_str(series.name),
        story_context=safe_prompt_str(story_context),
    )
    llm_messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": system_prompt}]
    for message in history[:-1]:
        llm_messages.append(
            {
                "role": str(message.get("role") or "user"),
                "content": str(message.get("content") or ""),
            }
        )
    llm_messages.append({"role": "user", "content": last_user_msg})

    return {
        "cached": None,
        "cache_key": cache_key,
        "cache_version": cache_version,
        "client": get_openai_client(),
        "intent": classify_intent_fast(last_user_msg),
        "book_count": len(book_ids),
        "llm_messages": llm_messages,
    }


async def finalize_series_advisor_reply_payload(
    *,
    db: AsyncSession,
    client: AsyncOpenAI,
    series: Any,
    cache_key: str,
    cache_version: int,
    reply: str,
    intent: str,
    book_count: int,
) -> dict[str, Any]:
    response_type = await classify_response_type(client, reply)
    result = {
        "reply": reply,
        "intent": intent,
        "response_type": response_type,
        "series_id": str(series.id),
        "book_count": book_count,
        "retrieved_passages": [],
        "cached": False,
    }
    await set_series_advisor_response_cache(
        str(series.id),
        cache_key,
        result,
        expected_version=cache_version,
    )
    await db.commit()
    return result


async def build_series_advisor_reply_payload(
    *,
    db: AsyncSession,
    series: Any,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    prepared = await prepare_series_advisor_reply_context(
        db=db,
        series=series,
        user_id=user_id,
        messages=messages,
    )
    if prepared["cached"] is not None:
        return prepared["cached"]

    client = prepared["client"]
    response = await create_tracked_chat_completion(
        client=client,
        feature="series_advisor_message",
        model=settings.OPENAI_INTEL_MODEL,
        db=db,
        user_id=user_id,
        temperature=0.55,
        max_tokens=900,
        messages=prepared["llm_messages"],
    )
    reply = (response.choices[0].message.content or "").strip()
    return await finalize_series_advisor_reply_payload(
        db=db,
        client=client,
        series=series,
        cache_key=prepared["cache_key"],
        cache_version=prepared["cache_version"],
        reply=reply,
        intent=prepared["intent"],
        book_count=prepared["book_count"],
    )


async def stream_series_advisor_reply_payload(
    *,
    db: AsyncSession,
    series: Any,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
) -> AsyncIterator[dict[str, Any]]:
    prepared = await prepare_series_advisor_reply_context(
        db=db,
        series=series,
        user_id=user_id,
        messages=messages,
    )
    if prepared["cached"] is not None:
        yield {"event": "done", "data": prepared["cached"]}
        return

    client = prepared["client"]
    reply_parts: list[str] = []
    usage_counts: tuple[int, int, int] | None = None
    reservation = None
    permit = None
    provider_completed = False
    provider_failure_transient: bool | None = None
    try:
        estimated_prompt_tokens, estimated_completion_tokens = estimate_chat_completion_token_parts(
            {"messages": prepared["llm_messages"], "max_tokens": 900}
        )
        permit = await acquire_provider_circuit_permit(
            provider="openai", model=settings.OPENAI_INTEL_MODEL
        )
        try:
            reservation = await reserve_llm_call(
                user_id=user_id,
                estimated_prompt_tokens=estimated_prompt_tokens,
                estimated_completion_tokens=estimated_completion_tokens,
                feature="series_advisor_message",
                operation="chat",
                model=settings.OPENAI_INTEL_MODEL,
                book_id=None,
                budget_class="interactive",
            )
        except BaseException:
            await release_provider_circuit_permit(permit)
            permit = None
            raise
        stream = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
            temperature=0.55,
            max_tokens=900,
            messages=prepared["llm_messages"],
            stream=True,
            stream_options={"include_usage": True},
        )
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
                    reply_parts.append(content)
                    yield {"event": "delta", "data": {"content": content}}
        provider_completed = True

        if usage_counts is not None:
            await finish_llm_reservation_counts(
                reservation,
                prompt_tokens=usage_counts[0],
                completion_tokens=usage_counts[1],
                total_tokens=usage_counts[2],
            )
        else:
            await finish_llm_reservation(reservation, None)
        reservation = None

        reply = "".join(reply_parts).strip()
        result = await finalize_series_advisor_reply_payload(
            db=db,
            client=client,
            series=series,
            cache_key=prepared["cache_key"],
            cache_version=prepared["cache_version"],
            reply=reply,
            intent=prepared["intent"],
            book_count=prepared["book_count"],
        )
        yield {"event": "done", "data": result}
    except LLM_PROVIDER_CALL_EXCEPTIONS as exc:
        if not provider_completed:
            provider_failure_transient = is_transient_llm_provider_error(exc)
        raise
    finally:
        if reservation is not None:
            await fail_llm_reservation(reservation)
        if permit is not None:
            if provider_completed:
                await record_provider_success(permit)
            elif provider_failure_transient is not None:
                await record_provider_failure(
                    permit,
                    transient=provider_failure_transient,
                )
            else:
                await release_provider_circuit_permit(permit)
