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
import re
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from celery.states import FAILURE, PENDING, RETRY, STARTED, SUCCESS
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import func, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_advisor, rate_limit_continuity_checker
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import cache_del, cache_get, cache_set, key_advisor_task
from app.core.storage import download_book
from app.engine.embeddings.embedder import embed_text
from app.engine.search.semantic import semantic_search
from app.models.book import Book, Chapter, Series, SeriesBook
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, WorldElement
from app.utils.plot_thread_utils import derive_plot_thread_status, is_plot_thread_open
from app.schemas.advisor import (
    AdvisorRequest,
    AdvisorTaskStatusResponse,
    AdvisorSuggestionsResponse,
    EditorialReviewRequest,
    InlineContinuityRequest,
    InlineContinuityResponse,
    ProseTightenRequest,
    ProseTightenResponse,
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
    advisor_response_cache,
    build_advisor_world_analysis,
    build_advisor_world_context,
    build_character_voice_context,
    build_continuity_report_markdown,
    build_continuity_report_pdf,
    build_fallback_advisor_suggestions,
    generate_whats_the_word_result,
    build_series_story_context,
    build_story_context,
    classify_intent,
    classify_response_type,
    detect_advisor_world_mode,
    identify_character_mentions,
    make_advisor_cache_key,
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
from app.workers.tasks.intelligence_tasks import generate_advisor_reply_task
from app.workers.tasks.intelligence_tasks import generate_series_advisor_reply_task

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


async def _enqueue_book_advisor_task(
    *,
    book: Book,
    body: AdvisorRequest,
    current_user_id: uuid.UUID,
    response: Response,
) -> dict[str, Any]:

    cache_key = make_advisor_cache_key(book.id, last_user_msg)
    cached = advisor_response_cache.get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    task = generate_advisor_reply_task.apply_async(
        kwargs={
            "book_id": str(book.id),
            "user_id": str(current_user_id),
            "messages": [{"role": msg.role, "content": msg.content} for msg in body.messages],
            "total_chapters": body.total_chapters,
        }
    )
    await cache_set(
        key_advisor_task(task.id),
        {"scope": "book", "book_id": str(book.id), "user_id": str(current_user_id)},
        3600,
    )
    response.status_code = 202
    return {"task_id": task.id, "status": "queued", "cached": False}


async def _enqueue_series_advisor_task(
    *,
    series: Series,
    body: AdvisorRequest,
    current_user_id: uuid.UUID,
    response: Response,
) -> dict[str, Any]:
    cache_key = make_advisor_cache_key(f"series:{series.id}", last_user_msg)
    cached = advisor_response_cache.get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    task = generate_series_advisor_reply_task.apply_async(
        kwargs={
            "series_id": str(series.id),
            "user_id": str(current_user_id),
            "messages": [{"role": msg.role, "content": msg.content} for msg in body.messages],
        }
    )
    await cache_set(
        key_advisor_task(task.id),
        {"scope": "series", "series_id": str(series.id), "user_id": str(current_user_id)},
        3600,
    )
    response.status_code = 202
    return {"task_id": task.id, "status": "queued", "cached": False}

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
        book=book,
        body=body,
        current_user_id=current_user.id,
        response=response,
    )

    last_user_msg = next(
        (m.content for m in reversed(body.messages) if m.role == "user"), ""
    )
    if not last_user_msg:
        raise HTTPException(400, detail="no user message found")

    # ── Response cache: check before any LLM work ─────────────────────────────
    # Cap history to last 10 turns (20 messages) to control cost
    history = body.messages[-20:]

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        # 1. Classify intent + build story context (parallel, both cheap)
        intent, story_context = await asyncio.gather(
            classify_intent(client, last_user_msg),
            build_story_context(db, book_id, book.total_chapters or 0),
        )
        world_mode = detect_advisor_world_mode(last_user_msg, intent)
        world_analysis = (
            await build_advisor_world_analysis(db, book, last_user_msg, world_mode)
            if world_mode
            else None
        )
        world_context = build_advisor_world_context(world_analysis)

        # 2. Retrieve relevant chunks
        max_ch = body.total_chapters
        chunk_limit = 10 if intent in ("consistency", "plothole") or world_mode else 5
        threshold = 0.25 if intent in ("consistency", "plothole") or world_mode else 0.30

        query_emb = await embed_text(
            last_user_msg,
            user_id=current_user.id,
            book_id=book.id,
            feature="advisor_message_query_embedding",
        )
        rows = await db.execute(
            sql_text("""
                SELECT bc.text, bc.chunk_index,
                       ch.number AS chapter_num, ch.title AS chapter_title,
                       1 - (bc.embedding <=> CAST(:emb AS vector)) AS relevance
                FROM book_chunks bc
                JOIN chapters ch ON ch.id = bc.chapter_id
                WHERE bc.book_id = :bid
                  AND ch.number <= :max_ch
                  AND bc.embedding IS NOT NULL
                  AND 1 - (bc.embedding <=> CAST(:emb AS vector)) > :threshold
                ORDER BY relevance DESC
                LIMIT :lim
            """),
            {"emb": str(query_emb), "bid": str(book_id), "max_ch": max_ch,
             "threshold": threshold, "lim": chunk_limit},
        )
        hits = [
            {
                "text": r.text,
                "chapter_num": r.chapter_num,
                "chapter_title": r.chapter_title,
                "relevance": round(float(r.relevance), 3),
            }
            for r in rows.fetchall()
        ]

        # 3. Build retrieved passages block
        passage_blocks: list[str] = []
        for h in hits:
            chapter_ref = f"Chapter {h['chapter_num']}"
            if h.get("chapter_title"):
                chapter_ref += f" — {h['chapter_title']}"
            passage_blocks.append(f"[{chapter_ref}]\n{h['text'][:380]}")

        retrieved_context = (
            "\n\n".join(passage_blocks)
            if passage_blocks
            else "No passage excerpts matched this query — reason from the STORY KNOWLEDGE above."
        )

        # 4. Augment last user message with context + intent hint
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

        # 5. Build message list for LLM
        system_prompt = ADVISOR_SYSTEM.format(
            title=_safe_prompt_str(book.title),
            story_context=_safe_prompt_str(story_context),
        )
        llm_messages: list[ChatCompletionMessageParam] = [
            cast(ChatCompletionMessageParam, {"role": "system", "content": system_prompt})
        ]
        for msg in history[:-1]:
            llm_messages.append(cast(ChatCompletionMessageParam, {"role": msg.role, "content": msg.content}))
        llm_messages.append(cast(ChatCompletionMessageParam, {"role": "user", "content": augmented_last}))

        # 6. Call GPT-4o-mini (main response)
        response = await create_tracked_chat_completion(
            client=client,
            feature="advisor_message",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            book_id=book.id,
            temperature=0.55,
            max_tokens=800,
            messages=llm_messages,
        )
        reply = (response.choices[0].message.content or "").strip()

        # 7. Classify response type
        response_type = await classify_response_type(client, reply)

        result = {
            "reply": reply,
            "intent": intent,
            "response_type": response_type,
            "retrieved_passages": [
                {
                    "chapter_num": h["chapter_num"],
                    "chapter_title": h.get("chapter_title"),
                    "excerpt": h["text"][:240],
                    "relevance": h["relevance"],
                }
                for h in hits[:5]
            ],
            "world_analysis": world_analysis,
            "cached": False,
        }
        # Store in cache for subsequent identical queries
        advisor_response_cache.set(cache_key, result)
        return result
    finally:
        await client.close()


# ─── Opening greeting endpoint ────────────────────────────────────────────────

@router.get("/{book_id}/advisor/greeting")
async def advisor_greeting(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)

    thread_count = (
        await db.execute(
            select(func.count()).select_from(PlotThread).where(PlotThread.book_id == book_id)
        )
    ).scalar_one()
    char_count = (
        await db.execute(
            select(func.count()).select_from(Character).where(Character.book_id == book_id)
        )
    ).scalar_one()

    return {
        "message": f"What aspect of *{book.title}* feels unsolved right now?",
        "book_title": book.title,
        "stats": {
            "characters": char_count,
            "plot_threads": thread_count,
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

    task_meta = await cache_get(key_advisor_task(task_id))
    if not isinstance(task_meta, dict):
        raise HTTPException(404, detail="advisor task not found")
    if task_meta.get("book_id") != str(book.id) or task_meta.get("user_id") != str(current_user.id):
        raise HTTPException(403, detail="advisor task does not belong to this book")

    result = generate_advisor_reply_task.AsyncResult(task_id)
    if result.state in {PENDING, RETRY}:
        return {"task_id": task_id, "status": "queued", "result": None, "error": None}
    if result.state == STARTED:
        return {"task_id": task_id, "status": "running", "result": None, "error": None}
    if result.state == SUCCESS:
        await cache_del(key_advisor_task(task_id))
        return {"task_id": task_id, "status": "complete", "result": result.result, "error": None}
    if result.state == FAILURE:
        await cache_del(key_advisor_task(task_id))
        return {"task_id": task_id, "status": "failed", "result": None, "error": "advisor_generation_failed"}
    return {"task_id": task_id, "status": "running", "result": None, "error": None}


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

    total_ch = book.total_chapters or 1
    suggestions: list[dict] = []
    scan_basis: list[str] = []
    data_gaps: list[str] = []

    all_chars = (
        await db.execute(
            select(Character)
            .where(Character.book_id == book_id)
            .order_by(Character.mention_count.desc(), Character.first_chapter, Character.name)
        )
    ).scalars().all()
    character_count = len(all_chars)
    character_names = {char.id: char.name for char in all_chars}
    if character_count:
        scan_basis.append("characters")
    else:
        data_gaps.append("characters")

    all_threads = (
        await db.execute(
            select(PlotThread)
            .where(PlotThread.book_id == book_id)
            .order_by(PlotThread.importance.desc(), PlotThread.introduced_at, PlotThread.title)
        )
    ).scalars().all()
    if all_threads:
        scan_basis.append("plot threads")
    else:
        data_gaps.append("plot threads")

    relationship_rows = (
        await db.execute(
            select(CharacterRelationship)
            .where(CharacterRelationship.book_id == book_id)
            .order_by(CharacterRelationship.from_chapter, CharacterRelationship.id)
        )
    ).scalars().all()
    relationship_count = len(relationship_rows)
    if relationship_count:
        scan_basis.append("relationships")
    else:
        data_gaps.append("relationships")

    world_rows = (
        await db.execute(
            select(WorldElement)
            .where(WorldElement.book_id == book_id)
            .order_by(WorldElement.usage_count.desc(), WorldElement.name.asc())
        )
    ).scalars().all()
    world_element_count = len(world_rows)
    if world_element_count:
        scan_basis.append("world elements")
    else:
        data_gaps.append("world elements")

    # ── 0. Trait contradictions ───────────────────────────────────────────────
    PHYSICAL_TRAITS = ["eyes", "hair", "build", "age_descriptor", "distinguishing"]

    all_states = (
        await db.execute(
            select(
                CharacterState.character_id,
                CharacterState.at_chapter,
                CharacterState.trait_snapshot,
                Character.name,
            )
            .join(Character, Character.id == CharacterState.character_id)
            .where(
                Character.book_id == book_id,
                CharacterState.trait_snapshot.isnot(None),
            )
            .order_by(CharacterState.character_id, CharacterState.at_chapter)
        )
    ).all()
    state_count = len(all_states)
    if state_count:
        scan_basis.append("character states")
    else:
        data_gaps.append("character states")

    char_state_map: dict[str, list[Any]] = {}
    for row in all_states:
        key = str(row.character_id)
        if key not in char_state_map:
            char_state_map[key] = []
        char_state_map[key].append(row)

    contradiction_count = 0
    for char_id, states in char_state_map.items():
        if len(states) < 2 or contradiction_count >= 3:
            break
        char_name = states[0].name
        earliest = states[0]
        for later in states[1:]:
            if contradiction_count >= 3:
                break
            snap_a = earliest.trait_snapshot or {}
            snap_b = later.trait_snapshot or {}
            for trait in PHYSICAL_TRAITS:
                val_a = None
                val_b = None
                raw_a = snap_a.get(trait)
                raw_b = snap_b.get(trait)
                if isinstance(raw_a, dict):
                    val_a = raw_a.get("value")
                elif isinstance(raw_a, str):
                    val_a = raw_a
                if isinstance(raw_b, dict):
                    val_b = raw_b.get("value")
                elif isinstance(raw_b, str):
                    val_b = raw_b

                if val_a and val_b and val_a.lower() != val_b.lower():
                    suggestions.append({
                        "id": f"trait-{char_id}-{trait}",
                        "type": "trait_contradiction",
                        "severity": "warning",
                        "title": f"Conflicting {trait} description: {char_name}",
                        "description": (
                            f"{char_name}'s {trait} is described as \"{val_a}\" in chapter "
                            f"{earliest.at_chapter} but \"{val_b}\" in chapter {later.at_chapter}. "
                            f"No character state change was recorded between these chapters."
                        ),
                        "chapter_ref": earliest.at_chapter,
                        "action_label": "Investigate this contradiction",
                        "ask_prompt": (
                            f"There's a potential continuity issue with {char_name}'s {trait}: "
                            f"\"{val_a}\" in chapter {earliest.at_chapter} vs \"{val_b}\" in chapter "
                            f"{later.at_chapter}. Is this a plothole or an intentional change?"
                        ),
                    })
                    contradiction_count += 1
                    break

    # ── 1. Dropped plot threads ────────────────────────────────────────────────
    dropped_threads_result = await db.execute(
        select(PlotThread)
        .where(
            PlotThread.book_id == book_id,
            PlotThread.introduced_at <= total_ch - 30,
        )
        .order_by(PlotThread.importance.desc())
        .limit(12)
    )
    dropped_threads = [
        thread
        for thread in dropped_threads_result.scalars().all()
        if is_plot_thread_open(
            derive_plot_thread_status(
                thread.status,
                introduced_at=thread.introduced_at,
                last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                resolved_at=thread.resolved_at,
                current_chapter=total_ch,
            )
        )
    ][:5]

    for thread in dropped_threads:
        suggestions.append({
            "id": f"thread-{thread.id}",
            "type": "dropped_thread",
            "severity": "warning",
            "title": f"Unresolved thread: \"{thread.title}\"",
            "description": (
                f"Introduced at chapter {thread.introduced_at}, "
                f"still marked '{derive_plot_thread_status(thread.status, introduced_at=thread.introduced_at, last_mentioned_at=thread.last_mentioned_at or thread.introduced_at, resolved_at=thread.resolved_at, current_chapter=total_ch)}' with {total_ch - (thread.introduced_at or 0)} chapters elapsed. "
                f"{thread.description or 'No additional detail recorded.'}"
            ),
            "chapter_ref": thread.introduced_at,
            "action_label": "Ask advisor about this thread",
            "ask_prompt": f"Is there a plothole or missed opportunity with the \"{thread.title}\" plot thread?",
        })

    # ── 2. Characters absent 30+ chapters ─────────────────────────────────────
    absent_chars: list[Character] = []
    try:
        absent_chars_result = await db.execute(
            select(Character)
            .where(
                Character.book_id == book_id,
                Character.mention_count > 5,
                Character.last_seen_chapter <= total_ch - 30,
            )
            .order_by(Character.mention_count.desc())
            .limit(5)
        )
        absent_chars = list(absent_chars_result.scalars().all())
    except Exception:
        pass

    for char in absent_chars:
        suggestions.append({
            "id": f"absent-{char.id}",
            "type": "character_absent",
            "severity": "info",
            "title": f"{char.name} hasn't appeared in {total_ch - (char.last_seen_chapter or 0)} chapters",
            "description": (
                f"Last seen around chapter {char.last_seen_chapter}. "
                f"Mentioned {char.mention_count} times overall. "
                f"{char.role or ''} — {char.arc_summary[:120] + '...' if char.arc_summary and len(char.arc_summary) > 120 else (char.arc_summary or 'No arc summary yet.')}"
            ),
            "chapter_ref": char.last_seen_chapter,
            "action_label": "Explore this character's arc",
            "ask_prompt": f"What are good opportunities to bring {char.name} back into the story?",
        })

    # ── 3. Ongoing high-importance plot threads ────────────────────────────────
    hot_threads_result = await db.execute(
        select(PlotThread)
        .where(
            PlotThread.book_id == book_id,
            PlotThread.importance >= 7,
        )
        .order_by(PlotThread.importance.desc())
        .limit(8)
    )
    hot_threads = [
        thread
        for thread in hot_threads_result.scalars().all()
        if derive_plot_thread_status(
            thread.status,
            introduced_at=thread.introduced_at,
            last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
            resolved_at=thread.resolved_at,
            current_chapter=total_ch,
        ) in {"developing", "paused", "possibly_abandoned", "forgotten", "introduced"}
    ][:3]

    for thread in hot_threads:
        if thread.introduced_at and total_ch - thread.introduced_at > 15:
            suggestions.append({
                "id": f"arc-{thread.id}",
                "type": "arc_opportunity",
                "severity": "opportunity",
                "title": f"Arc decision point: \"{thread.title}\"",
                "description": (
                    f"High-importance thread (importance {thread.importance}/10), "
                    f"active since chapter {thread.introduced_at}. "
                    f"Decision points examined now can be planted as foreshadowing retroactively. "
                    f"{thread.description or ''}"
                ),
                "chapter_ref": thread.introduced_at,
                "action_label": "Debate how to end this arc",
                "ask_prompt": f"What are the best ways to resolve the \"{thread.title}\" arc? What are the story tradeoffs?",
            })

    # ── 3b. Future direction ──────────────────────────────────────────────────
    if total_ch >= 20:
        late_threads_result = await db.execute(
            select(PlotThread)
            .where(
                PlotThread.book_id == book_id,
                PlotThread.introduced_at <= int(total_ch * 0.4),
                PlotThread.importance >= 5,
            )
            .order_by(PlotThread.importance.desc())
            .limit(8)
        )
        late_threads = [
            thread
            for thread in late_threads_result.scalars().all()
            if is_plot_thread_open(
                derive_plot_thread_status(
                    thread.status,
                    introduced_at=thread.introduced_at,
                    last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                    resolved_at=thread.resolved_at,
                    current_chapter=total_ch,
                )
            )
        ][:3]

        for thread in late_threads:
            already_covered = any(s["id"] == f"arc-{thread.id}" for s in suggestions)
            if already_covered:
                continue
            suggestions.append({
                "id": f"direction-{thread.id}",
                "type": "future_direction",
                "severity": "direction",
                "title": f"Future direction: how does \"{thread.title}\" end?",
                "description": (
                    f"This thread has been running since chapter {thread.introduced_at} "
                    f"— {total_ch - (thread.introduced_at or 0)} chapters in. "
                    f"At this stage, it's worth stress-testing your ending options and "
                    f"checking whether earlier chapters planted enough foreshadowing. "
                    f"{thread.description[:120] + '...' if thread.description and len(thread.description) > 120 else (thread.description or '')}"
                ),
                "chapter_ref": thread.introduced_at,
                "action_label": "Explore ending options",
                "ask_prompt": (
                    f"I'm thinking about how to end the \"{thread.title}\" thread. "
                    f"What options do I have and what are the narrative tradeoffs of each?"
                ),
            })

    # ── 4. Underused minor characters ─────────────────────────────────────────
    underused_chars: list[Character] = []
    try:
        underused_chars_result = await db.execute(
            select(Character)
            .where(
                Character.book_id == book_id,
                Character.role == "minor",
                Character.mention_count > 8,
            )
            .order_by(Character.mention_count.desc())
            .limit(3)
        )
        underused_chars = list(underused_chars_result.scalars().all())
    except Exception:
        pass

    for char in underused_chars:
        suggestions.append({
            "id": f"underused-{char.id}",
            "type": "foreshadowing_opportunity",
            "severity": "opportunity",
            "title": f"Foreshadowing opportunity: {char.name}",
            "description": (
                f"{char.name} appears {char.mention_count} times but is still tagged as a minor character. "
                f"High mention count with a minor role often signals unused narrative potential — "
                f"this character could serve as a plot connector or a foreshadowing anchor."
            ),
            "chapter_ref": char.first_chapter,
            "action_label": "Explore narrative potential",
            "ask_prompt": f"How could {char.name} be used more effectively in the story? Are there foreshadowing opportunities?",
        })

    # ── 5. Recent chapter clues ────────────────────────────────────────────────
    from app.models.book import Chapter as Ch
    recent_summaries = (
        await db.execute(
            select(ChapterSummary.clues, Ch.number, Ch.title)
            .join(Ch, Ch.id == ChapterSummary.chapter_id)
            .where(
                Ch.book_id == book_id,
                ChapterSummary.mode == "short",
                ChapterSummary.clues.isnot(None),
            )
            .order_by(Ch.number.asc())
            .limit(10)
        )
    ).all()
    clue_count = 0
    if recent_summaries:
        scan_basis.append("chapter summaries")
    else:
        data_gaps.append("chapter summaries")

    seen_clues: set[str] = set()
    for clues, chapter_num, chapter_title in recent_summaries:
        if not clues:
            continue
        clue_list = clues if isinstance(clues, list) else list(clues.values()) if isinstance(clues, dict) else []
        clue_count += len(clue_list)
        for clue in clue_list[:2]:
            clue_str = str(clue)[:120]
            if clue_str not in seen_clues:
                seen_clues.add(clue_str)
                suggestions.append({
                    "id": f"clue-{book_id}-{chapter_num}-{len(seen_clues)}",
                    "type": "unresolved_clue",
                    "severity": "opportunity",
                    "title": f"Planted clue from chapter {chapter_num}",
                    "description": (
                        f"Chapter {chapter_num} ({chapter_title or 'Untitled'}) contains: \"{clue_str}\". "
                        f"If this hasn't paid off yet, it's either a plothole or a foreshadowing opportunity."
                    ),
                    "chapter_ref": chapter_num,
                    "action_label": "Check if this clue resolved",
                    "ask_prompt": f"Has the clue from chapter {chapter_num} been resolved? '{clue_str}'",
                })
            if len(seen_clues) >= 3:
                break
        if len(seen_clues) >= 3:
            break

    # Sort: warnings → direction → opportunities → info
    thread_statuses = {
        thread.id: derive_plot_thread_status(
            thread.status,
            introduced_at=thread.introduced_at,
            last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
            resolved_at=thread.resolved_at,
            current_chapter=total_ch,
        )
        for thread in all_threads
    }
    open_threads = [thread for thread in all_threads if is_plot_thread_open(thread_statuses[thread.id])]
    open_thread_count = len(open_threads)

    for thread in [item for item in all_threads if item.status == "contradicted" or thread_statuses[item.id] == "contradicted"][:2]:
        suggestions.append({
            "id": f"contradicted-{thread.id}",
            "type": "event_conflict",
            "severity": "warning",
            "title": f"Thread contradiction: \"{thread.title}\"",
            "description": (
                "This tracked thread is already marked as contradicted"
                + (f" after chapter {thread.last_mentioned_at}" if thread.last_mentioned_at else "")
                + ". Review the affected scenes before building more logic on top of it."
                + (f" {thread.description}" if thread.description else "")
            ),
            "chapter_ref": thread.last_mentioned_at or thread.introduced_at,
            "action_label": "Trace the contradiction",
            "ask_prompt": f"Walk me through where the \"{thread.title}\" thread started contradicting itself and how to fix it.",
            "source": "heuristic",
        })

    relationship_groups: dict[tuple[str, str], list[CharacterRelationship]] = {}
    for rel in relationship_rows:
        key = tuple(sorted([str(rel.character_a_id), str(rel.character_b_id)]))
        relationship_groups.setdefault(key, []).append(rel)
    for pair_key, rel_items in relationship_groups.items():
        if len(rel_items) < 2:
            continue
        first = rel_items[0]
        last = rel_items[-1]
        rel_names = " / ".join(
            name for name in [character_names.get(first.character_a_id), character_names.get(first.character_b_id)] if name
        ) or "Character relationship"
        type_changed = first.rel_type != last.rel_type
        sentiment_changed = (
            first.sentiment is not None
            and last.sentiment is not None
            and abs(first.sentiment - last.sentiment) >= 1.1
        )
        if not type_changed and not sentiment_changed:
            continue
        suggestions.append({
            "id": f"relationship-{pair_key[0]}-{pair_key[1]}",
            "type": "relationship_flip",
            "severity": "warning" if type_changed else "info",
            "title": f"Relationship drift: {rel_names}",
            "description": (
                f"This relationship shifts from {first.rel_type.replace('_', ' ')} in chapter {first.from_chapter} "
                f"to {last.rel_type.replace('_', ' ')} in chapter {last.from_chapter}."
                if type_changed
                else f"The emotional tone around {rel_names} swings sharply between chapter {first.from_chapter} and chapter {last.from_chapter}."
            ) + (f" {last.description}" if last.description else ""),
            "chapter_ref": last.from_chapter,
            "action_label": "Check the relationship arc",
            "ask_prompt": f"Is the shift in the {rel_names} relationship earned on page, or am I skipping a transition?",
            "source": "heuristic",
        })

    world_groups: dict[tuple[str, str], list[WorldElement]] = {}
    for element in world_rows:
        group_key = (" ".join(str(element.element_type or "").split()).strip().lower(), " ".join(str(element.name or "").split()).strip().lower())
        world_groups.setdefault(group_key, []).append(element)
    for (element_type, element_name), items in world_groups.items():
        descriptions = [" ".join(str(item.description or "").split()).strip() for item in items if " ".join(str(item.description or "").split()).strip()]
        normalized = list(dict.fromkeys(description.lower() for description in descriptions))
        if len(items) < 2 or len(normalized) < 2:
            continue
        if all(a in b or b in a for index, a in enumerate(normalized) for b in normalized[index + 1:]):
            continue
        if element_type in {"place", "location"}:
            issue_type = "location_conflict"
            title = f"Location details drift: {items[0].name}"
            prompt = f"Check the canon for {items[0].name}. Do these location details contradict each other?"
        elif element_type in {"item", "artifact", "object"}:
            issue_type = "object_continuity"
            title = f"Object continuity drift: {items[0].name}"
            prompt = f"Check the continuity of {items[0].name}. Am I describing or handling it inconsistently?"
        elif element_type in {"concept", "rule", "magic", "system"}:
            issue_type = "world_rule_conflict"
            title = f"World-rule conflict: {items[0].name}"
            prompt = f"Check the canon for {items[0].name}. Do my world rules now conflict?"
        else:
            continue
        suggestions.append({
            "id": f"world-{issue_type}-{element_name}",
            "type": issue_type,
            "severity": "warning",
            "title": title,
            "description": (
                f"Multiple canon descriptions for {items[0].name} now diverge across extracted world elements. "
                f"Example one: {descriptions[0][:120]} Example two: {descriptions[1][:120]}"
            ),
            "chapter_ref": None,
            "action_label": "Reconcile the canon",
            "ask_prompt": prompt,
            "source": "heuristic",
        })

    heuristic_count = len(suggestions)
    proactive_audit_applied = False
    audit_summary: str | None = None
    if heuristic_count < 3 and (recent_summaries or open_threads or world_rows):
        detailed_summary_rows = (
            await db.execute(
                select(Ch.number, Ch.title, ChapterSummary.content, ChapterSummary.key_events)
                .join(Ch, Ch.id == ChapterSummary.chapter_id)
                .where(
                    Ch.book_id == book_id,
                    ChapterSummary.mode.in_(["short", "detailed"]),
                )
                .order_by(Ch.number.desc(), ChapterSummary.mode.asc())
                .limit(10)
            )
        ).all()
        recent_summary_blocks: list[str] = []
        seen_summary_chapters: set[int] = set()
        for chapter_num, chapter_title, content, key_events in detailed_summary_rows:
            if chapter_num in seen_summary_chapters:
                continue
            seen_summary_chapters.add(chapter_num)
            key_bits: list[str] = []
            if isinstance(key_events, list):
                for item in key_events[:3]:
                    if isinstance(item, dict):
                        key_bits.append(" ".join(str(item.get("event_title") or item.get("event") or "").split()).strip())
            key_line = "; ".join(item for item in key_bits if item)
            recent_summary_blocks.append(
                f"Chapter {chapter_num} ({chapter_title or 'Untitled'}): "
                f"{' '.join(str(content or '').split())[:240]}"
                + (f" Key events: {key_line[:180]}" if key_line else "")
            )
            if len(recent_summary_blocks) >= 4:
                break

        open_thread_blocks = [
            f"- {thread.title} [{thread_statuses[thread.id]}]"
            + (f" introduced ch.{thread.introduced_at}" if thread.introduced_at else "")
            + (f": {' '.join(str(thread.description or '').split())[:160]}" if thread.description else "")
            for thread in open_threads[:5]
        ]
        relationship_blocks = [
            f"- {character_names.get(rel.character_a_id, 'Unknown')} / {character_names.get(rel.character_b_id, 'Unknown')}: "
            f"{rel.rel_type.replace('_', ' ')} at chapter {rel.from_chapter}"
            + (f". {' '.join(str(rel.description or '').split())[:140]}" if rel.description else "")
            for rel in relationship_rows[-5:]
        ]
        world_watch_blocks = [
            f"- {element.name} [{element.element_type}] usage={element.usage_count}"
            + (f" gap={round(float(element.gap_score), 2)}" if element.gap_score is not None else "")
            + (f". {' '.join(str(element.description or '').split())[:160]}" if element.description else "")
            for element in world_rows[:6]
        ]
        story_context = await build_story_context(db, book_id, total_ch)
        proactive_cache_key = make_editorial_cache_key(
            f"scan:{book_id}:{total_ch}",
            "\n".join(recent_summary_blocks + open_thread_blocks + world_watch_blocks),
            heuristic_count,
        )
        proactive_result = advisor_response_cache.get(proactive_cache_key)
        if proactive_result is None:
            if settings.OPENAI_API_KEY and settings.OPENAI_INTEL_MODEL:
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                try:
                    response = await create_tracked_chat_completion(
                        client=client,
                        feature="advisor_proactive_scan",
                        model=settings.OPENAI_INTEL_MODEL,
                        db=db,
                        user_id=current_user.id,
                        book_id=book.id,
                        temperature=0.2,
                        max_tokens=900,
                        response_format={"type": "json_object"},
                        messages=[
                            {
                                "role": "system",
                                "content": PROACTIVE_SCAN_SYSTEM.format(
                                    title=_safe_prompt_str(book.title),
                                    story_context=_safe_prompt_str(story_context),
                                ),
                            },
                            {
                                "role": "user",
                                "content": PROACTIVE_SCAN_USER.format(
                                    recent_summaries="\n".join(recent_summary_blocks) or "No recent summaries available.",
                                    open_threads="\n".join(open_thread_blocks) or "No open threads available.",
                                    relationships="\n".join(relationship_blocks) or "No relationship transitions available.",
                                    world_watch="\n".join(world_watch_blocks) or "No world elements available.",
                                ),
                            },
                        ],
                    )
                    proactive_result = normalize_proactive_scan_result(response.choices[0].message.content or "{}")
                    advisor_response_cache.set(proactive_cache_key, proactive_result)
                except Exception:
                    proactive_result = {
                        "findings": [],
                        "overall_note": "Proactive audit was unavailable, so this scan is showing heuristic-only results.",
                    }
                finally:
                    await client.close()
            else:
                proactive_result = {
                    "findings": [],
                    "overall_note": "Proactive audit is unavailable until AI scan settings are configured.",
                }

        proactive_findings = (proactive_result or {}).get("findings") or []
        for index, finding in enumerate(proactive_findings):
            suggestions.append({
                "id": f"proactive-{index}-{finding['type']}",
                **finding,
                "source": "proactive_audit",
            })
        proactive_audit_applied = bool(proactive_findings)
        audit_summary = (proactive_result or {}).get("overall_note") or None

    for item in suggestions:
        item.setdefault("source", "heuristic")

    deduped_suggestions: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in suggestions:
        dedupe_key = (
            " ".join(str(item.get("title") or "").split()).strip().lower(),
            " ".join(str(item.get("description") or "").split()).strip().lower(),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        deduped_suggestions.append(item)
    suggestions = deduped_suggestions

    fallback_applied = False
    if not suggestions:
        focus_thread = None
        if open_threads:
            thread = open_threads[0]
            focus_thread = {
                "title": thread.title,
                "introduced_at": thread.introduced_at,
                "description": thread.description,
            }
        suggestions = [
            {**item, "source": "fallback"}
            for item in build_fallback_advisor_suggestions(
                book_title=book.title,
                total_chapters=total_ch,
                character_count=character_count,
                open_thread_count=open_thread_count,
                focus_thread=focus_thread,
            )
        ]
        fallback_applied = True

    severity_order = {"warning": 0, "direction": 1, "opportunity": 2, "info": 3}
    suggestions.sort(key=lambda s: severity_order.get(s["severity"], 4))

    scan_basis = list(dict.fromkeys(scan_basis))
    data_gaps = list(dict.fromkeys(data_gaps))

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
        "book_title": book.title,
        "meta": {
            "character_count": character_count,
            "state_count": state_count,
            "open_thread_count": open_thread_count,
            "clue_count": clue_count,
            "relationship_count": relationship_count,
            "world_element_count": world_element_count,
            "heuristic_count": heuristic_count,
            "fallback_applied": fallback_applied,
            "proactive_audit_applied": proactive_audit_applied,
            "scan_basis": scan_basis,
            "data_gaps": data_gaps,
            "audit_summary": audit_summary,
        },
    }


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
    cached = advisor_response_cache.get(cache_key)
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
            limit=6,
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
        advisor_response_cache.set(cache_key, response_payload)
        return response_payload

    finally:
        await client.close()


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
        return ProseTightenResponse(**normalized)
    finally:
        await client.close()


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


@router.get("/{book_id}/advisor/synopsis")
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
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book_id)
            .order_by(Chapter.number.asc())
            .limit(3)
        )
    ).all()
    if not chapter_rows:
        raise HTTPException(404, "No chapters available for synopsis generation.")

    passage_blocks: list[str] = []
    coverage: list[str] = []
    for number, chapter_title, s3_key in chapter_rows:
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
        return normalized
    finally:
        await client.close()


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

    total_ch = book.total_chapters or 9999
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        hits = await semantic_search(
            db,
            book_id,
            body.text[:600],
            total_ch,
            limit=6,
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
                .limit(80)
            )
        ).mappings().all()
        relevant_characters = identify_character_mentions(body.text, [dict(row) for row in character_rows])
        all_voice_profiles = (
            await db.execute(
                select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book_id)
            )
        ).scalars().all()
        profiles_by_character_id = {profile.character_id: profile for profile in all_voice_profiles}
        attributed_dialogue = extract_dialogue_samples_by_character(body.text, [dict(row) for row in character_rows])
        if len(relevant_characters) == 1 and not attributed_dialogue.get(relevant_characters[0]["name"]):
            attributed_dialogue[relevant_characters[0]["name"]] = [body.text[:4000]]
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
            for candidate_profile in all_voice_profiles:
                if profile is not None and candidate_profile.character_id == profile.character_id:
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

        return {
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
        }
    finally:
        await client.close()


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
        series=series,
        body=body,
        current_user_id=current_user.id,
        response=response,
    )

    last_user_msg = next(
        (m.content for m in reversed(body.messages) if m.role == "user"), ""
    )
    if not last_user_msg:
        raise HTTPException(400, detail="no user message found")

    # Cache check
    cache_key = make_advisor_cache_key(f"series:{series_id}", last_user_msg)
    cached = advisor_response_cache.get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    # Load all books in this series
    memberships = (
        await db.execute(
            select(SeriesBook.book_id, SeriesBook.position)
            .where(SeriesBook.series_id == series_id)
            .order_by(SeriesBook.position.asc().nulls_last())
        )
    ).all()

    if not memberships:
        raise HTTPException(400, detail="No books found in this series.")

    book_ids = [row.book_id for row in memberships]

    # Load book titles for labelling
    book_rows = (
        await db.execute(
            select(Book.id, Book.title).where(Book.id.in_(book_ids))
        )
    ).all()
    book_titles = {row.id: row.title for row in book_rows}

    # Build merged series context (capped per-book to keep token count low)
    story_context = await build_series_story_context(
        db, book_ids, book_titles,
        max_chars_per_book=6, max_threads_per_book=4,
    )

    history = body.messages[-16:]  # cap history tighter for series context

    system_prompt = SERIES_ADVISOR_SYSTEM.format(
        series_name=_safe_prompt_str(series.name),
        story_context=_safe_prompt_str(story_context),
    )

    llm_messages: list[ChatCompletionMessageParam] = [
        cast(ChatCompletionMessageParam, {"role": "system", "content": system_prompt})
    ]
    for msg in history[:-1]:
        llm_messages.append(
            cast(ChatCompletionMessageParam, {"role": msg.role, "content": msg.content})
        )
    llm_messages.append(cast(ChatCompletionMessageParam, {"role": "user", "content": last_user_msg}))

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        # Single call — gpt-4o-mini for cost efficiency
        response = await create_tracked_chat_completion(
            client=client,
            feature="series_advisor_message",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=current_user.id,
            temperature=0.55,
            max_tokens=900,
            messages=llm_messages,
        )
        reply = (response.choices[0].message.content or "").strip()
        response_type = await classify_response_type(client, reply)
        intent = await classify_intent(client, last_user_msg)

        result = {
            "reply": reply,
            "intent": intent,
            "response_type": response_type,
            "series_id": str(series_id),
            "book_count": len(book_ids),
            "retrieved_passages": [],
            "cached": False,
        }
        advisor_response_cache.set(cache_key, result)
        return result
    finally:
        await client.close()


# ─── Series continuity check endpoint ────────────────────────────────────────

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

    task_meta = await cache_get(key_advisor_task(task_id))
    if not isinstance(task_meta, dict):
        raise HTTPException(404, detail="advisor task not found")
    if task_meta.get("scope") != "series" or task_meta.get("series_id") != str(series.id) or task_meta.get("user_id") != str(current_user.id):
        raise HTTPException(403, detail="advisor task does not belong to this series")

    result = generate_series_advisor_reply_task.AsyncResult(task_id)
    if result.state in {PENDING, RETRY}:
        return {"task_id": task_id, "status": "queued", "result": None, "error": None}
    if result.state == STARTED:
        return {"task_id": task_id, "status": "running", "result": None, "error": None}
    if result.state == SUCCESS:
        await cache_del(key_advisor_task(task_id))
        return {"task_id": task_id, "status": "complete", "result": result.result, "error": None}
    if result.state == FAILURE:
        await cache_del(key_advisor_task(task_id))
        return {"task_id": task_id, "status": "failed", "result": None, "error": "advisor_generation_failed"}
    return {"task_id": task_id, "status": "running", "result": None, "error": None}


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
    cached_series = advisor_response_cache.get(series_cache_key)
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
    prior_book_id_strs = ", ".join(f"'{bid}'" for bid in prior_book_ids)
    query_emb = await embed_text(
        body.text[:600],
        user_id=current_user.id,
        book_id=current_book.id,
        feature="series_continuity_query_embedding",
    )
    rows = await db.execute(
        sql_text(f"""
            SELECT bc.text, ch.number AS chapter_num, ch.title AS chapter_title,
                   b.title AS book_title,
                   1 - (bc.embedding <=> CAST(:emb AS vector)) AS relevance
            FROM book_chunks bc
            JOIN chapters ch ON ch.id = bc.chapter_id
            JOIN books b ON b.id = bc.book_id
            WHERE bc.book_id IN ({prior_book_id_strs})
              AND bc.embedding IS NOT NULL
              AND 1 - (bc.embedding <=> CAST(:emb AS vector)) > 0.22
            ORDER BY relevance DESC
            LIMIT 6
        """),
        {"emb": str(query_emb)},
    )
    hits = [
        {
            "text": r.text,
            "chapter_num": r.chapter_num,
            "chapter_title": r.chapter_title,
            "book_title": r.book_title,
            "relevance": round(float(r.relevance), 3),
        }
        for r in rows.fetchall()
    ]

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
        advisor_response_cache.set(series_cache_key, response_payload)
        return response_payload
    finally:
        await client.close()
