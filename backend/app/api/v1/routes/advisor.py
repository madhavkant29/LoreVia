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
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import func, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_advisor, rate_limit_continuity_checker
from app.core.config import settings
from app.core.database import get_db
from app.core.storage import download_book
from app.engine.embeddings.embedder import embed_text
from app.engine.search.semantic import semantic_search
from app.models.book import Book, Chapter, Series, SeriesBook
from app.models.character import Character, CharacterState
from app.models.intelligence import ChapterSummary, PlotThread
from app.schemas.advisor import (
    AdvisorRequest,
    EditorialReviewRequest,
    InlineContinuityRequest,
    InlineContinuityResponse,
    ProseTightenRequest,
    ProseTightenResponse,
    VoiceConsistencyRequest,
)
from app.utils.advisor_utils import (
    ADVISOR_SYSTEM,
    EDITORIAL_SYSTEM,
    EDITORIAL_USER,
    PROSE_TIGHTEN_SYSTEM,
    PROSE_TIGHTEN_USER,
    SERIES_ADVISOR_SYSTEM,
    SERIES_CONTINUITY_SYSTEM,
    SYNOPSIS_SYSTEM,
    SYNOPSIS_USER,
    VOICE_CONSISTENCY_SYSTEM,
    VOICE_CONSISTENCY_USER,
    advisor_response_cache,
    build_character_voice_context,
    build_continuity_report_markdown,
    build_continuity_report_pdf,
    build_fallback_advisor_suggestions,
    build_series_story_context,
    build_story_context,
    classify_intent,
    classify_response_type,
    identify_character_mentions,
    make_advisor_cache_key,
    make_editorial_cache_key,
    normalize_editorial_review_result,
    normalize_prose_tighten_result,
    normalize_series_continuity_result,
    normalize_synopsis_result,
    normalize_voice_consistency_result,
)
from app.utils.book_utils import detect_chapter_continuity_flags

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

# ─── Main advisor conversation endpoint ──────────────────────────────────────

@router.post("/{book_id}/advisor/message")
async def advisor_message(
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

    last_user_msg = next(
        (m.content for m in reversed(body.messages) if m.role == "user"), ""
    )
    if not last_user_msg:
        raise HTTPException(400, detail="no user message found")

    # ── Response cache: check before any LLM work ─────────────────────────────
    cache_key = make_advisor_cache_key(book_id, last_user_msg)
    cached = advisor_response_cache.get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    # Cap history to last 10 turns (20 messages) to control cost
    history = body.messages[-20:]

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        # 1. Classify intent + build story context (parallel, both cheap)
        intent, story_context = await asyncio.gather(
            classify_intent(client, last_user_msg),
            build_story_context(db, book_id, book.total_chapters or 0),
        )

        # 2. Retrieve relevant chunks
        max_ch = body.total_chapters
        chunk_limit = 10 if intent in ("consistency", "plothole") else 5
        threshold = 0.25 if intent in ("consistency", "plothole") else 0.30

        query_emb = await embed_text(last_user_msg)
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

        augmented_last = (
            f"{last_user_msg}\n\n"
            + (f"{intent_hint}\n\n" if intent_hint else "")
            + f"--- Retrieved passages ---\n{retrieved_context}"
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
        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
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


# ─── Proactive suggestions scan ──────────────────────────────────────────────

@router.get("/{book_id}/advisor/suggestions")
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
            PlotThread.status.in_(["introduced", "ongoing"]),
            PlotThread.introduced_at <= total_ch - 30,
        )
        .order_by(PlotThread.importance.desc())
        .limit(5)
    )
    dropped_threads = dropped_threads_result.scalars().all()

    for thread in dropped_threads:
        suggestions.append({
            "id": f"thread-{thread.id}",
            "type": "dropped_thread",
            "severity": "warning",
            "title": f"Unresolved thread: \"{thread.title}\"",
            "description": (
                f"Introduced at chapter {thread.introduced_at}, "
                f"still marked '{thread.status}' with {total_ch - (thread.introduced_at or 0)} chapters elapsed. "
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
            PlotThread.status == "ongoing",
            PlotThread.importance >= 7,
        )
        .order_by(PlotThread.importance.desc())
        .limit(3)
    )
    hot_threads = hot_threads_result.scalars().all()

    for thread in hot_threads:
        if thread.introduced_at and total_ch - thread.introduced_at > 15:
            suggestions.append({
                "id": f"arc-{thread.id}",
                "type": "arc_opportunity",
                "severity": "opportunity",
                "title": f"Arc decision point: \"{thread.title}\"",
                "description": (
                    f"High-importance thread (importance {thread.importance}/10), "
                    f"ongoing since chapter {thread.introduced_at}. "
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
                PlotThread.status.in_(["ongoing", "introduced"]),
                PlotThread.introduced_at <= int(total_ch * 0.4),
                PlotThread.importance >= 5,
            )
            .order_by(PlotThread.importance.desc())
            .limit(3)
        )
        late_threads = late_threads_result.scalars().all()

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

    seen_clues: set[str] = set()
    for clues, chapter_num, chapter_title in recent_summaries:
        if not clues:
            continue
        clue_list = clues if isinstance(clues, list) else list(clues.values()) if isinstance(clues, dict) else []
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
    severity_order = {"warning": 0, "direction": 1, "opportunity": 2, "info": 3}
    suggestions.sort(key=lambda s: severity_order.get(s["severity"], 4))

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
        "book_title": book.title,
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
        hits = await semantic_search(db, book_id, body.text[:600], total_ch, limit=6)
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

        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
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
        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
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
        "No major continuity issues were surfaced in this inline pass." if not issues else "Inline continuity pass found issues worth checking before you lock the scene."
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
        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
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
        hits = await semantic_search(db, book_id, body.text[:600], total_ch, limit=6)
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

        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
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
    filename_base = "".join(ch for ch in (book.title or "lorevia") if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "-") or "lorevia"

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
        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
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
    query_emb = await embed_text(body.text[:600])
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
        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
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
