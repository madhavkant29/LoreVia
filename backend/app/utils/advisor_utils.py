"""
Advisor utility helpers — LLM intent/response classifiers, story context
builder, and continuity report renderers extracted from the advisor route.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.redis import (
    get_advisor_response_cache,
    get_book_cache_version,
    get_editorial_review_cache,
    get_proactive_scan_cache,
    get_series_cache_version,
    get_series_advisor_response_cache,
    get_series_story_context_cache,
    get_story_context_cache,
    get_suggestion_scan_cache,
    invalidate_advisor_cache_namespaces,
    mark_book_cache_dirty,
    mark_series_cache_dirty,
    set_advisor_response_cache,
    set_editorial_review_cache,
    set_proactive_scan_cache,
    set_series_advisor_response_cache,
    set_series_story_context_cache,
    set_story_context_cache,
    set_suggestion_scan_cache,
)
from app.engine.embeddings.embedder import embed_text
from app.engine.search.semantic import semantic_search
from app.models.book import Book, Chapter, SeriesBook
from app.models.character import Character, CharacterState
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, WorldElement
from app.utils.plot_thread_utils import derive_plot_thread_status, is_plot_thread_open
from app.utils.llm_usage_utils import create_tracked_chat_completion, record_llm_usage_counts
from app.utils.world_building_utils import build_world_logic_response, classify_world_intent

log = logging.getLogger(__name__)


# ─── Advisor response cache ───────────────────────────────────────────────────
# Simple TTL-based LRU in-process cache keyed on sha256(book_id + last_msg).
# No external dependency — expires automatically in CACHE_TTL_SECONDS.

async def invalidate_advisor_caches(
    *,
    book_id: uuid.UUID | str | None = None,
    series_ids: list[uuid.UUID | str] | None = None,
) -> None:
    """Drop shared advisor/editorial cache namespaces after semantic content changes."""
    await invalidate_advisor_cache_namespaces(
        book_id=str(book_id) if book_id is not None else None,
        series_ids=[str(series_id) for series_id in (series_ids or [])],
    )


async def invalidate_advisor_caches_for_book(db: AsyncSession, *, book_id: uuid.UUID | str) -> None:
    series_rows = (
        await db.execute(
            select(SeriesBook.series_id).where(SeriesBook.book_id == uuid.UUID(str(book_id)))
        )
    ).all()
    await mark_book_cache_dirty(str(book_id))
    for row in series_rows:
        await mark_series_cache_dirty(str(row.series_id))
    await invalidate_advisor_caches(
        book_id=book_id,
        series_ids=[row.series_id for row in series_rows],
    )


def make_advisor_cache_key(book_id: str | uuid.UUID, last_user_message: str) -> str:
    """SHA-256 key for the (book, message) pair."""
    payload = f"{book_id}||{last_user_message.strip()}"
    return hashlib.sha256(payload.encode()).hexdigest()


def make_editorial_cache_key(
    book_id: str | uuid.UUID,
    text: str,
    chapter_num: int | None,
    discriminator: str | uuid.UUID | None = None,
) -> str:
    """SHA-256 key for editorial review (book, text, chapter)."""
    payload = f"{book_id}||{text.strip()[:500]}||{chapter_num or 0}||{discriminator or ''}"
    return hashlib.sha256(payload.encode()).hexdigest()


def make_advisor_suggestions_cache_key(
    *,
    book_id: str | uuid.UUID,
    total_chapters: int,
    character_count: int,
    thread_count: int,
    state_count: int,
    relationship_count: int,
    world_element_count: int,
) -> str:
    """SHA-256 cache key for advisor suggestions scan results."""
    payload = (
        f"scan:{book_id}:ch{total_chapters}"
        f":cc{character_count}:tc{thread_count}:sc{state_count}"
        f":rc{relationship_count}:wc{world_element_count}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_synopsis_content_fingerprint(chapter_rows: list[tuple]) -> str:
    """SHA-256 fingerprint from first 3 chapters' (s3_key, content_version) tuples."""
    parts: list[str] = []
    for row in chapter_rows:
        s3_key = str(row[2] or "") if len(row) > 2 else ""
        content_version = str(row[3] or "1") if len(row) > 3 else "1"
        parts.append(f"{s3_key}|{content_version}")
    payload = "||".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def safe_prompt_str(value: str | None) -> str:
    return (value or "").replace("{", "{{").replace("}", "}}")

# ─── System / prompt templates ────────────────────────────────────────────────

ADVISOR_SYSTEM = """\
You are a Story Advisor for the novel "{title}". You are talking directly with the author.

You have two sources of knowledge about this book:
1. STORY KNOWLEDGE — structured data extracted from the full manuscript (characters, plot threads, chapter count)
2. RETRIEVED PASSAGES — specific text excerpts most relevant to the author's question

Core responsibilities:
- If WORLD ANALYSIS is supplied, use it to answer lore, canon, world-rule, and world-gap questions. Treat its alerts and suggestions as first-class evidence.
- ANSWER using both sources. Lead with story data, ground specifics in passages.
- Quote retrieved passages with chapter references when relevant.
- When passages are sparse, reason from STORY KNOWLEDGE — you always have character names, roles, arcs, and plot threads.
- NEVER say "I have no context" or "no passages found". You always know the characters and threads.
- NEVER present the manuscript as issue-free or fully solved. If no hard contradiction is present, surface the most useful soft risk, missing setup, or unrealized opportunity instead.

CRITICAL — INTERCEPT CONTRADICTIONS BEFORE ANYTHING ELSE:
If the author's message describes a plan, idea, or event that conflicts with established story facts, you MUST lead with a ⚠️ block before giving any creative advice. Do not silently accept contradictions.
Contradict if:
  - A character does something that violates their established traits, relationships, or status (e.g. a dead character reappears without explanation)
  - An event violates an established rule (magic system, geography, timeline)
  - The proposed direction suddenly shifts the genre, tone, or central theme established across the majority of the book (e.g. adding comedy to a dark tragedy, introducing sci-fi to a fantasy)
  - A new character's role directly undermines the arc of an existing character without narrative justification

Format contradictions EXACTLY as:
⚠️ Contradiction: [what clashes — be specific]
Text says: "[direct quote or close paraphrase]" (Chapter X)
Author plan: [what the author described]
Tradeoff: [what breaks if you proceed as planned]
Suggestion: [a concrete alternative that achieves the author's goal without breaking continuity]

OPPORTUNITY DETECTION — Surface proactively:
If retrieving passages reveals a setup that hasn't paid off, a character whose arc intersects naturally with the author's question, or a moment that could serve as foreshadowing if reframed, use:
✨ Opportunity: [title]
[Specific, actionable explanation tied to a character, chapter, or thread. Show the author exactly what to write.]

TRADEOFF DEBATES — When asked about arc endings, plot directions, or story decisions:
🔀 Option A: [name] — [outcome + what it costs narratively]
🔀 Option B: [name] — [outcome + what it costs narratively]
[Then give your recommendation with reasoning grounded in the manuscript.]

Tone: direct, specific, like a smart developmental editor who has read every page.
Length: 3–5 paragraphs max. Always name specific characters and chapter numbers. No vague generalities.

--- STORY KNOWLEDGE ---
{story_context}
-----------------------
"""

INTENT_CLASSIFIER_PROMPT = """\
Classify this author message into ONE of:
  plothole | direction | opportunity | consistency | general

Message: {message}

Reply with just the label, nothing else."""

WORLD_ADVISOR_QUERY_TERMS = (
    "worldbuilding",
    "world-building",
    "world build",
    "world gap",
    "world gaps",
    "world rule",
    "world rules",
    "lore",
    "canon",
    "magic system",
    "geography",
    "kingdom",
    "empire",
    "faction",
    "culture",
    "religion",
    "technology",
    "species",
    "race",
    "realm",
    "region",
    "country",
    "city",
    "language",
    "mythology",
)
WORLD_GAP_QUERY_TERMS = (
    "gap",
    "missing",
    "contradiction",
    "inconsistency",
    "consistency",
    "conflict",
    "continuity",
    "incomplete",
    "hole",
    "doesn't make sense",
    "does not make sense",
    "breaks",
)
WORLD_INTEGRATION_QUERY_TERMS = (
    "use",
    "integrate",
    "introduce",
    "where",
    "scene",
    "chapter",
    "thread",
    "plant",
    "seed",
    "foreshadow",
    "react",
    "respond",
    "response",
    "how would",
    "what would",
    "what happens if",
)


def detect_advisor_world_mode(message: str, intent: str | None = None) -> str | None:
    """Return the world-analysis mode when an advisor question is lore-focused."""
    text = (message or "").strip().lower()
    if not text:
        return None
    has_world_signal = any(term in text for term in WORLD_ADVISOR_QUERY_TERMS)
    if not has_world_signal:
        return None
    if intent in {"plothole", "consistency"} or any(term in text for term in WORLD_GAP_QUERY_TERMS):
        return "gap_detection"
    if any(term in text for term in WORLD_INTEGRATION_QUERY_TERMS):
        return "story_integration"
    return classify_world_intent(message)


def advisor_retrieval_settings(intent: str | None, world_mode: str | None = None) -> tuple[int, float]:
    if intent in {"consistency", "plothole"} or world_mode:
        return (
            settings.ADVISOR_CONTINUITY_SEARCH_CHUNKS,
            settings.ADVISOR_CONTINUITY_SEARCH_SIMILARITY_THRESHOLD,
        )
    return (
        settings.ADVISOR_GENERAL_SEARCH_CHUNKS,
        settings.ADVISOR_GENERAL_SEARCH_SIMILARITY_THRESHOLD,
    )


async def retrieve_series_continuity_passages(
    *,
    db: AsyncSession,
    prior_book_ids: list[uuid.UUID],
    query: str,
    similarity_threshold: float | None = None,
    candidate_limit: int | None = None,
    return_limit: int | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    if not prior_book_ids:
        return []

    query_emb = await embed_text(
        query,
        db=db,
        user_id=user_id,
        book_id=book_id,
        feature="series_continuity_query_embedding",
    )
    threshold = (
        settings.SERIES_CONTINUITY_SEARCH_SIMILARITY_THRESHOLD
        if similarity_threshold is None
        else float(similarity_threshold)
    )
    retrieval_limit = (
        settings.SERIES_CONTINUITY_SEARCH_CANDIDATE_CHUNKS
        if candidate_limit is None
        else int(candidate_limit)
    )
    final_limit = (
        settings.SERIES_CONTINUITY_SEARCH_RETURN_CHUNKS
        if return_limit is None
        else int(return_limit)
    )
    prior_book_id_strs = ", ".join(f"'{bid}'" for bid in prior_book_ids)
    try:
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
                  AND 1 - (bc.embedding <=> CAST(:emb AS vector)) > :threshold
                ORDER BY relevance DESC
                LIMIT :lim
            """),
            {
                "emb": str(query_emb),
                "threshold": threshold,
                "lim": retrieval_limit,
            },
        )
    except ProgrammingError as exc:
        if 'type "vector" does not exist' in str(getattr(exc, "orig", exc)).lower():
            log.warning(
                "series_continuity_pgvector_unavailable book_id=%s prior_books=%s",
                book_id,
                [str(item) for item in prior_book_ids],
            )
            return []
        raise
    return [
        {
            "text": row.text,
            "chapter_num": row.chapter_num,
            "chapter_title": row.chapter_title,
            "book_title": row.book_title,
            "relevance": round(float(row.relevance), 3),
        }
        for row in rows.fetchall()[:final_limit]
    ]


def _short_world_value(value: object, limit: int = 220) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        text = "; ".join(_short_world_value(item, limit=limit) for item in value if item)
    elif isinstance(value, dict):
        preferred = (
            value.get("title")
            or value.get("element_name")
            or value.get("name")
            or value.get("description")
            or value.get("suggested_fix")
            or value.get("answer")
            or ""
        )
        text = _short_world_value(preferred, limit=limit) if preferred else json.dumps(value, default=str)
    else:
        text = str(value)
    text = " ".join(text.split()).strip()
    return (text[: limit - 3] + "...") if len(text) > limit else text


def _format_world_item(item: object) -> str:
    if not isinstance(item, dict):
        return _short_world_value(item)
    label = _short_world_value(
        item.get("title")
        or item.get("element_name")
        or item.get("name")
        or item.get("category")
        or item.get("severity")
    )
    description = _short_world_value(item.get("description") or item.get("body") or item.get("problem"))
    fix = _short_world_value(item.get("suggested_fix") or item.get("suggestion") or item.get("what_to_add"))
    parts = [part for part in (label, description, f"Fix: {fix}" if fix else "") if part]
    return " - ".join(parts)


def build_advisor_world_context(world_analysis: dict[str, Any] | None) -> str:
    """Compact world-building analysis so the advisor LLM can cite it cleanly."""
    if not world_analysis:
        return ""
    lines = [
        "--- WORLD ANALYSIS ---",
        f"Mode: {world_analysis.get('mode') or 'gap_detection'}",
    ]
    answer = _short_world_value(world_analysis.get("answer"), limit=700)
    if answer:
        lines.append(f"Summary: {answer}")
    logic_alerts = [item for item in world_analysis.get("logic_alerts") or [] if item][:4]
    if logic_alerts:
        lines.append("Logic alerts:")
        lines.extend(f"- {_format_world_item(item)}" for item in logic_alerts)
    suggestions = [item for item in world_analysis.get("suggestions") or [] if item][:5]
    if suggestions:
        lines.append("Priority suggestions:")
        lines.extend(f"- {_format_world_item(item)}" for item in suggestions)
    citations = [item for item in world_analysis.get("citations") or [] if isinstance(item, dict)][:5]
    if citations:
        lines.append("World citations:")
        for item in citations:
            name = _short_world_value(item.get("name"))
            element_type = _short_world_value(item.get("element_type"), limit=80)
            scope = _short_world_value(item.get("source_scope"), limit=80)
            lines.append(f"- {name} [{element_type}] source={scope}".strip())
    steps = [_short_world_value(item) for item in world_analysis.get("simulation_steps") or [] if item][:4]
    if steps:
        lines.append("World-logic steps:")
        lines.extend(f"- {step}" for step in steps)
    lines.append("----------------------")
    return "\n".join(lines)


WHATS_THE_WORD_SYSTEM = """\
You help fiction writers find one precise English word from a short description.

Return JSON only with this exact shape:
{
  "word": "single-word answer",
  "gloss": "brief explanation in under 16 words"
}

Rules:
- Return exactly one English word.
- Prefer precise, natural, contemporary vocabulary over obscure showboating.
- If a previous suggestion is provided, do not repeat it.
- Keep the gloss short, plain, and useful.
- Do not ask follow-up questions.
"""

WHATS_THE_WORD_USER = """\
Book: {title}
Description: {description}
Previous suggestion to avoid: {previous_word}
"""

_WHATS_THE_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _normalize_single_word(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    if _WHATS_THE_WORD_RE.fullmatch(text):
        return text.lower()
    match = _WHATS_THE_WORD_RE.search(text)
    return match.group(0).lower() if match else ""


def normalize_whats_the_word_result(raw: str) -> dict[str, str]:
    fallback_word = _normalize_single_word(raw)
    fallback = {
        "word": fallback_word or "word",
        "gloss": "A close fit for the description.",
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return fallback

    word = _normalize_single_word(parsed.get("word")) if isinstance(parsed, dict) else ""
    if not word:
        return fallback

    gloss = " ".join(str((parsed or {}).get("gloss") or "").split()).strip()
    if not gloss:
        gloss = fallback["gloss"]
    return {"word": word, "gloss": gloss[:120]}


async def generate_whats_the_word_result(
    *,
    client: AsyncOpenAI,
    model: str,
    book_title: str,
    description: str,
    previous_word: str | None = None,
) -> dict[str, str]:
    response = await create_tracked_chat_completion(
        client=client,
        feature="advisor_whats_the_word",
        model=model,
        temperature=0.9,
        max_tokens=120,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": WHATS_THE_WORD_SYSTEM},
            {
                "role": "user",
                "content": WHATS_THE_WORD_USER.format(
                    title=book_title.strip() or "Untitled book",
                    description=description.strip(),
                    previous_word=(previous_word or "None").strip() or "None",
                ),
            },
        ],
    )
    raw = response.choices[0].message.content or "{}"
    return normalize_whats_the_word_result(raw)


async def build_advisor_world_analysis(
    db: AsyncSession,
    book: Book,
    query: str,
    mode: str,
) -> dict[str, Any]:
    """Run the world-building analyzer for advisor chat questions."""
    return await build_world_logic_response(db, book, query, mode)


EDITORIAL_SYSTEM = """\
You are a developmental editor and line editor for the novel "{title}".
The author has submitted a passage of their own writing for review.

You have access to:
- STORY KNOWLEDGE: the established characters (personality, role, arcs, traits), plot threads, and themes
- RETRIEVED PASSAGES: relevant excerpts from the manuscript surrounding this passage

Your job is to return a structured JSON object (and nothing else) with this exact shape:

{{
  "continuity_issues": [
    {{
      "type": "character_personality" | "character_trait" | "event_conflict" | "theme_drift" | "timeline",
      "severity": "critical" | "moderate" | "minor",
      "title": "short label",
      "description": "clear explanation of the clash — reference character name, chapter number, or established fact",
      "suggestion": "concrete fix"
    }}
  ],
  "insertion_opportunities": [
    {{
      "title": "short label",
      "problem": "what gap, plothole, or missed beat this would help",
      "target_chapter": 0,
      "target_chapter_title": "chapter title or null",
      "anchor_excerpt": "short excerpt from retrieved context or empty string",
      "what_to_add": "brief event, beat, memory, or line of setup to add",
      "why_here": "why this is the most natural insertion point",
      "purpose": "plothole_fix" | "characterization" | "backstory" | "foreshadowing"
    }}
  ],
  "grammar_issues": [
    {{
      "original": "exact quote from the submitted text",
      "issue": "concise label (e.g. comma splice, subject-verb agreement)",
      "fix": "corrected version"
    }}
  ],
  "formatting_notes": [
    "short bullet-style observation about paragraph breaks, dialogue punctuation, pacing, or whitespace"
  ],
  "thematic_fit": {{
    "score": "strong" | "moderate" | "weak",
    "notes": "2-3 sentences on how well the passage fits the book's established tone and themes"
  }},
  "overall_verdict": "1-2 sentence summary: is this passage ready, or what is the single most important fix?"
}}

Rules:
- Only flag real issues. If there are no grammar problems, return an empty array.
- For continuity_issues, always cite the specific character name and chapter number when available.
- Only include insertion_opportunities when there is a meaningful earlier place to plant setup, backstory, characterization, or foreshadowing.
- insertion_opportunities must be grounded in retrieved context and must point to a specific chapter number already in the manuscript.
- If the reviewed passage is for a later chapter and the issue is missing setup/payoff, prefer insertion_opportunities in earlier chapters rather than the current chapter.
- Treat generated wording as a shape of the event to add, not polished final prose.
- Use "event_conflict" for resurrection errors, impossible prop/item continuity, broken world rules, or objects reappearing after destruction.
- For grammar, quote the exact phrase from the submitted text — do not paraphrase.
- For thematic_fit, reference the book's actual established themes from STORY KNOWLEDGE.
- Treat complex themes as valid themes when grounded: false altruism, self-hatred, denial, obsession, moral injury, unreliable narration, dissociation, class resentment, identity fracture.
- Be direct and specific. No vague generalities.

--- STORY KNOWLEDGE ---
{story_context}
-----------------------
"""

EDITORIAL_USER = """\
Please review the following passage.
{chapter_hint}

--- PASSAGE ---
{text}
---------------

Retrieved manuscript context for cross-referencing:
{passages}
"""

PROACTIVE_SCAN_SYSTEM = """\
You are performing a proactive continuity and editorial scan for the novel "{title}".

You will receive:
- STORY KNOWLEDGE summarizing the manuscript state
- RECENT CHAPTER SUMMARIES
- OPEN PLOT THREADS
- RELATIONSHIP CHANGES
- WORLD ELEMENT WATCHLIST

Return JSON only with this exact shape:
{{
  "findings": [
    {{
      "severity": "warning" | "direction" | "opportunity" | "info",
      "type": "event_conflict" | "relationship_flip" | "location_conflict" | "object_continuity" | "world_rule_conflict" | "role_drift" | "foreshadowing_opportunity" | "future_direction",
      "title": "short label",
      "description": "specific explanation grounded in the provided story context",
      "chapter_ref": 0,
      "action_label": "short CTA",
      "ask_prompt": "follow-up prompt the author can send to the advisor"
    }}
  ],
  "overall_note": "1-2 sentences explaining the highest-value proactive concern or opportunity."
}}

Rules:
- Prefer high-confidence findings over speculative ones.
- Do not repeat obvious duplicates from the same root issue.
- Use "warning" only for likely contradictions or structural risks.
- Use "direction" for unresolved arcs that need an ending decision soon.
- Use "opportunity" for foreshadowing, setup, payoff, or underused narrative material.
- Use "info" only for light watchlist items.
- Keep findings to at most 4 items.
- If there are no strong findings, return an empty findings array and a brief overall_note.

--- STORY KNOWLEDGE ---
{story_context}
-----------------------
"""

PROACTIVE_SCAN_USER = """\
Run a proactive continuity scan using the manuscript evidence below.

--- RECENT CHAPTER SUMMARIES ---
{recent_summaries}
-------------------------------

--- OPEN PLOT THREADS ---
{open_threads}
-------------------------

--- RELATIONSHIP CHANGES ---
{relationships}
----------------------------

--- WORLD ELEMENT WATCHLIST ---
{world_watch}
-------------------------------
"""

VOICE_CONSISTENCY_SYSTEM = """\
You are a developmental editor reviewing dialogue and behaviour consistency for the novel "{title}".

You will receive:
- STORY KNOWLEDGE about the manuscript
- CHARACTER BASELINES for characters likely present in the passage
- RETRIEVED PASSAGES from the manuscript for comparison
- A NEW PASSAGE the author just wrote

Return JSON only with this exact shape:
{{
  "issues": [
    {{
      "character_name": "name",
      "severity": "critical" | "moderate" | "minor",
      "title": "short label",
      "description": "specific explanation of what feels off and why",
      "evidence": "reference the established personality or earlier behaviour",
      "suggestion": "a concrete adjustment the author could make",
      "intentionality_prompt": "short question asking whether the change is intentional"
    }}
  ],
  "overall_verdict": "1-2 sentence summary of whether the passage feels voice-consistent overall."
}}

Rules:
- Only flag genuine inconsistencies in dialogue, behaviour, emotional response, or decision-making.
- Compare against the CHARACTER BASELINES first, then use retrieved passages as supporting evidence.
- Do not flag growth when it is plausibly earned; only flag it if the passage skips the transition.
- Prefer fewer, high-confidence issues over speculative ones.
- If nothing is clearly off, return an empty issues array but use overall_verdict to name the next-best refinement target or watchpoint. Never call the passage perfect.

--- STORY KNOWLEDGE ---
{story_context}
----------------------
"""

VOICE_CONSISTENCY_USER = """\
Review this passage for character voice consistency.
{chapter_hint}

--- CHARACTER BASELINES ---
{character_context}
---------------------------

--- RETRIEVED PASSAGES ---
{passages}
--------------------------

--- NEW PASSAGE ---
{text}
-------------------
"""

SYNOPSIS_SYSTEM = """\
You are generating a concise, factual synopsis for the novel "{title}".

You have:
- STORY KNOWLEDGE about the manuscript
- EARLY CHAPTER CONTEXT from the beginning of the book

Return JSON only:
{{
  "spoiler_level": "none" | "minimal",
  "synopsis": "2-3 paragraphs",
  "focus_points": ["premise", "main characters", "conflict"]
}}

Rules:
- Keep spoilers at {spoiler_level} level.
- Write clearly and directly. Avoid flowery language, dramatic phrasing, or marketing hype.
- Focus on: what the story is about, who the main characters are, and the central conflict.
- Do not reveal major twists, endings, betrayals, secret identities, or late-book resolutions.
- Use simple, straightforward sentences. State facts without embellishment.
- If uncertain, stay vaguer rather than spoil.

--- STORY KNOWLEDGE ---
{story_context}
----------------------
"""

SYNOPSIS_USER = """\
Generate a spoiler-light synopsis for this manuscript.

Coverage chapters: {coverage}

--- EARLY CHAPTER CONTEXT ---
{passages}
-----------------------------
"""

PROSE_TIGHTEN_SYSTEM = """\
You are tightening prose for the novel "{title}".

Return JSON only with this exact shape:
{{
  "tightened_text": "the rewritten passage",
  "rationale": ["short note", "short note"]
}}

Rules:
- Only rewrite the submitted selection, not the surrounding chapter.
- Preserve meaning, point of view, tense, and story facts.
- Keep the same general tone, but make the prose leaner, cleaner, and more vivid.
- Do not add new plot facts.
- Do not explain inside the tightened_text.
"""

PROSE_TIGHTEN_USER = """\
Tighten this selected passage from the manuscript.
{chapter_hint}

--- SELECTED PASSAGE ---
{text}
------------------------
"""


# ─── LLM classifiers ─────────────────────────────────────────────────────────

INTENT_KEYWORDS: dict[str, list[str]] = {
    "plothole": [
        "plot hole", "plot-hole", "plothole",
        "contradiction", "contradicts", "contradicting",
        "inconsistency", "inconsistent",
        "doesn't make sense", "does not make sense",
        "doesn't add up", "does not add up",
        "broken logic", "logic issue",
    ],
    "direction": [
        "what should", "what next", "what now",
        "where should", "where do i", "where to go",
        "how should", "how do i continue",
        "should i", "which direction",
        "next step", "next chapter", "next scene",
        "what happens next", "what do i do",
        "stuck", "writer's block", "writers block",
        "don't know where", "dont know where",
    ],
    "opportunity": [
        "opportunity", "opportunities",
        "potential", "untapped", "unexplored",
        "could i", "what if i",
        "expand", "develop further",
        "seed", "plant", "foreshadow",
        "unused", "underused", "under-utilised",
    ],
    "consistency": [
        "consistency", "consistent",
        "canon", "lore",
        "rule", "rules",
        "worldbuild", "world-build", "world build",
        "timeline", "continuity",
        "does this fit",
        "does it make sense in",
        "contradiction", "contradicts",
    ],
}


def classify_intent_fast(user_message: str | None) -> str:
    if not user_message or not user_message.strip():
        return "general"
    lower = user_message.strip().lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return intent
    return "general"


async def classify_intent(client: AsyncOpenAI, message: str) -> str:
    from app.core.config import settings
    try:
        r = await create_tracked_chat_completion(
            client=client,
            feature="advisor_intent_classification",
            model=settings.OPENAI_INTEL_MODEL,
            max_tokens=10,
            temperature=0,
            messages=[
                {"role": "user", "content": INTENT_CLASSIFIER_PROMPT.format(message=message[:500])},
            ],
        )
        return (r.choices[0].message.content or "").strip().lower()
    except Exception:
        return "general"


async def classify_response_type(client: AsyncOpenAI, reply: str) -> str:
    """Classify response type by emoji marker prefix."""
    if reply.startswith("⚠️") or "⚠️ Contradiction" in reply[:200]:
        return "warning"
    if reply.startswith("✨") or "✨ Opportunity" in reply[:200]:
        return "opportunity"
    if "🔀 Option" in reply[:400]:
        return "tradeoff"
    return "standard"


# ─── Story context builder ────────────────────────────────────────────────────

async def build_story_context(db: AsyncSession, book_id: uuid.UUID, total_ch: int) -> str:
    version = await get_book_cache_version(str(book_id))
    cached = await get_story_context_cache(str(book_id), version, int(total_ch or 0))
    if cached is not None:
        return cached
    lines: list[str] = [f"Total chapters processed: {total_ch}"]

    book_result = await db.execute(
        select(Book)
        .where(Book.id == book_id)
        .options(
            selectinload(Book.characters),
            selectinload(Book.plot_threads),
            selectinload(Book.world_elements),
        )
    )
    book = book_result.scalars().first()

    if book is not None and book.characters:
        sorted_chars = sorted(book.characters, key=lambda c: (c.first_chapter or 0, c.name or ""))[:20]
        lines.append("\nCHARACTERS (extracted from manuscript):")
        for c in sorted_chars:
            role_str = f"[{c.role}]" if c.role else ""
            arc = (c.arc_summary[:120] + "...") if c.arc_summary and len(c.arc_summary) > 120 else (c.arc_summary or "")
            tags = ", ".join((c.personality_tags or [])[:3])
            motives = "; ".join((c.motivations or [])[:2])
            growth = ""
            if isinstance(c.growth_events, list) and c.growth_events:
                latest_growth = next(
                    (
                        item for item in reversed(c.growth_events)
                        if isinstance(item, dict) and (item.get("event") or item.get("event_title"))
                    ),
                    None,
                )
                if latest_growth:
                    growth_title = latest_growth.get("event") or latest_growth.get("event_title")
                    growth = f"Recent growth beat: {growth_title}."
            trait_bits: list[str] = []
            if isinstance(c.trait_state, dict):
                for trait_k in ("eyes", "hair", "build", "age_descriptor"):
                    raw = c.trait_state.get(trait_k)
                    val = raw.get("value") if isinstance(raw, dict) else (raw if isinstance(raw, str) else None)
                    if val:
                        trait_bits.append(f"{trait_k}={val}")
            traits_str = "; ".join(trait_bits[:3])
            lines.append(
                f"  • {c.name} {role_str} — first ch.{c.first_chapter}. "
                + (f"Arc: {arc} " if arc else "")
                + (f"Personality: {tags}. " if tags else "")
                + (f"Physical: {traits_str}. " if traits_str else "")
                + (f"Drives: {motives}. " if motives else "")
                + growth
            )

    if book is not None and book.plot_threads:
        sorted_threads = sorted(
            book.plot_threads,
            key=lambda t: (t.importance or 5),
            reverse=True,
        )[:12]
        lines.append("\nPLOT THREADS (extracted from manuscript):")
        for t in sorted_threads:
            desc = (t.description[:100] + "...") if t.description and len(t.description) > 100 else (t.description or "")
            status_label = str(t.status or "introduced").upper()
            lines.append(
                f"  • [{status_label}] {t.title} (importance {t.importance}/10, "
                f"introduced ch.{t.introduced_at}). {desc}"
            )

    world_rows = (
        await db.execute(
            select(WorldElement.name, WorldElement.element_type, WorldElement.description, WorldElement.usage_count)
            .where(WorldElement.book_id == book_id, WorldElement.source_scope == "worldbuilding")
            .order_by(WorldElement.usage_count.desc(), WorldElement.name.asc())
            .limit(10)
        )
    ).all()
    if world_rows:
        lines.append("\nWORLD REFERENCE CORPUS (author-supplied lore):")
        for name, element_type, description in world_rows:
            snippet = (description[:120] + "...") if description and len(description) > 120 else (description or "")
            lines.append(f"  • {name} [{element_type}] {snippet}")

    event_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "detailed",
                ChapterSummary.key_events.isnot(None),
            )
            .order_by(Chapter.number.desc())
            .limit(8)
        )
    ).all()
    event_lines: list[str] = []
    for chapter_num, chapter_title, key_events in event_rows:
        if not isinstance(key_events, list):
            continue
        for item in key_events[:3]:
            if not isinstance(item, dict):
                continue
            title = " ".join(str(item.get("event_title") or item.get("event") or "").split()).strip()
            if not title:
                continue
            chapter_label = f"ch.{chapter_num}"
            if chapter_title:
                chapter_label += f" ({chapter_title})"
            event_lines.append(f"  - {title} [{chapter_label}]")
    if event_lines:
        lines.append("\nMAJOR EVENTS (extracted from manuscript):")
        lines.extend(event_lines[:12])

    if book is not None and book.world_elements:
        sorted_world = sorted(
            book.world_elements,
            key=lambda we: (we.usage_count or 0),
            reverse=True,
        )[:12]
        lines.append("\nWORLD ELEMENTS (extracted from manuscript):")
        for we in sorted_world:
            desc = " ".join(str(we.description or "").split()).strip()
            if len(desc) > 100:
                desc = desc[:100] + "..."
            lines.append(f"  - {we.name} [{we.element_type}] usage={we.usage_count}. {desc}")

    theme_rows = (
        await db.execute(
            select(Chapter.number, ChapterSummary.themes)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "detailed",
                ChapterSummary.themes.isnot(None),
            )
            .order_by(Chapter.number.desc())
            .limit(8)
        )
    ).all()
    theme_lines: list[str] = []
    seen_themes: set[str] = set()
    for chapter_num, themes in theme_rows:
        if not isinstance(themes, list):
            continue
        for item in themes:
            if not isinstance(item, dict):
                continue
            name = " ".join(str(item.get("theme") or "").split()).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen_themes:
                continue
            seen_themes.add(key)
            signal = item.get("signal")
            depth = item.get("depth")
            evidence = " ".join(str(item.get("evidence") or "").split()).strip()
            theme_lines.append(
                f"  • {name} (chapter {chapter_num}"
                + (f", {signal}" if signal else "")
                + (f", {depth}" if depth else "")
                + f"). {evidence[:120]}"
            )
            if len(theme_lines) >= 10:
                break
        if len(theme_lines) >= 10:
            break
    if theme_lines:
        lines.append("\nTHEMES (including philosophical subtext):")
        lines.extend(theme_lines)

    payload = "\n".join(lines)
    await set_story_context_cache(str(book_id), version, int(total_ch or 0), payload)
    return payload


async def _prepare_advisor_reply_context(
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
        (str(message.get("content") or "") for message in reversed(messages) if message.get("role") == "user"),
        "",
    ).strip()
    if not last_user_msg:
        raise ValueError("no user message found")

    cache_key = make_advisor_cache_key(book.id, last_user_msg)
    cached = await get_advisor_response_cache(str(book.id), cache_key)
    if cached is not None:
        return {"cached": {**cached, "cached": True}}

    history = messages[-20:]
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
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
        llm_messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt}
        ]
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
            "client": client,
            "intent": intent,
            "hits": hits,
            "world_analysis": world_analysis,
            "llm_messages": llm_messages,
        }
    except Exception:
        await client.close()
        raise


async def _finalize_advisor_reply_payload(
    *,
    db: AsyncSession,
    client: AsyncOpenAI,
    book: Book,
    cache_key: str,
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
    await set_advisor_response_cache(str(book.id), cache_key, result)
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
    prepared = await _prepare_advisor_reply_context(
        db=db,
        book=book,
        user_id=user_id,
        messages=messages,
        total_chapters=total_chapters,
    )
    if prepared["cached"] is not None:
        return prepared["cached"]

    client = prepared["client"]
    try:
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
        return await _finalize_advisor_reply_payload(
            db=db,
            client=client,
            book=book,
            cache_key=prepared["cache_key"],
            reply=reply,
            intent=prepared["intent"],
            hits=prepared["hits"],
            world_analysis=prepared["world_analysis"],
        )
    finally:
        await client.close()


async def stream_advisor_reply_payload(
    *,
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
    total_chapters: int,
) -> AsyncIterator[dict[str, Any]]:
    prepared = await _prepare_advisor_reply_context(
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
    try:
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

        if usage_counts is not None:
            await record_llm_usage_counts(
                prompt_tokens=usage_counts[0],
                completion_tokens=usage_counts[1],
                total_tokens=usage_counts[2],
                feature="advisor_message",
                operation="chat_completion_stream",
                model=settings.OPENAI_INTEL_MODEL,
                db=db,
                user_id=user_id,
                book_id=book.id,
            )

        reply = "".join(reply_parts).strip()
        result = await _finalize_advisor_reply_payload(
            db=db,
            client=client,
            book=book,
            cache_key=prepared["cache_key"],
            reply=reply,
            intent=prepared["intent"],
            hits=prepared["hits"],
            world_analysis=prepared["world_analysis"],
        )
        yield {"event": "done", "data": result}
    finally:
        await client.close()


async def _prepare_series_advisor_reply_context(
    *,
    db: AsyncSession,
    series: Any,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    if not messages:
        raise ValueError("messages list is empty")

    last_user_msg = next(
        (str(message.get("content") or "") for message in reversed(messages) if message.get("role") == "user"),
        "",
    ).strip()
    if not last_user_msg:
        raise ValueError("no user message found")

    cache_key = make_advisor_cache_key(f"series:{series.id}", last_user_msg)
    cached = await get_series_advisor_response_cache(str(series.id), cache_key)
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
    book_rows = (
        await db.execute(
            select(Book.id, Book.title).where(Book.id.in_(book_ids))
        )
    ).all()
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
    llm_messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt}
    ]
    for message in history[:-1]:
        llm_messages.append(
            {
                "role": str(message.get("role") or "user"),
                "content": str(message.get("content") or ""),
            }
        )
    llm_messages.append({"role": "user", "content": last_user_msg})

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        intent = classify_intent_fast(last_user_msg)
        return {
            "cached": None,
            "cache_key": cache_key,
            "client": client,
            "intent": intent,
            "book_count": len(book_ids),
            "llm_messages": llm_messages,
        }
    except Exception:
        await client.close()
        raise


async def _finalize_series_advisor_reply_payload(
    *,
    db: AsyncSession,
    client: AsyncOpenAI,
    series: Any,
    cache_key: str,
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
    await set_series_advisor_response_cache(str(series.id), cache_key, result)
    await db.commit()
    return result


async def build_series_advisor_reply_payload(
    *,
    db: AsyncSession,
    series: Any,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    prepared = await _prepare_series_advisor_reply_context(
        db=db,
        series=series,
        user_id=user_id,
        messages=messages,
    )
    if prepared["cached"] is not None:
        return prepared["cached"]

    client = prepared["client"]
    try:
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
        return await _finalize_series_advisor_reply_payload(
            db=db,
            client=client,
            series=series,
            cache_key=prepared["cache_key"],
            reply=reply,
            intent=prepared["intent"],
            book_count=prepared["book_count"],
        )
    finally:
        await client.close()


async def stream_series_advisor_reply_payload(
    *,
    db: AsyncSession,
    series: Any,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
) -> AsyncIterator[dict[str, Any]]:
    prepared = await _prepare_series_advisor_reply_context(
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
    try:
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

        if usage_counts is not None:
            await record_llm_usage_counts(
                prompt_tokens=usage_counts[0],
                completion_tokens=usage_counts[1],
                total_tokens=usage_counts[2],
                feature="series_advisor_message",
                operation="chat_completion_stream",
                model=settings.OPENAI_INTEL_MODEL,
                db=db,
                user_id=user_id,
            )

        reply = "".join(reply_parts).strip()
        result = await _finalize_series_advisor_reply_payload(
            db=db,
            client=client,
            series=series,
            cache_key=prepared["cache_key"],
            reply=reply,
            intent=prepared["intent"],
            book_count=prepared["book_count"],
        )
        yield {"event": "done", "data": result}
    finally:
        await client.close()


def identify_character_mentions(
    text: str,
    character_rows: list[dict],
    limit: int = 5,
) -> list[dict]:
    stripped_text = re.sub(r"\s+", " ", text.casefold()).strip()
    normalized_text = f" {stripped_text} "
    matches: list[tuple[int, dict]] = []

    for row in character_rows:
        score = 0
        seen_candidates: set[str] = set()
        for candidate in [row.get("name"), *(row.get("aliases") or [])]:
            cleaned = " ".join(str(candidate or "").split()).strip()
            if not cleaned:
                continue
            folded = cleaned.casefold()
            if folded in seen_candidates:
                continue
            seen_candidates.add(folded)
            occurrences = len(
                re.findall(
                    f"(?<!\\w){re.escape(folded)}(?:['\\u2019]s)?(?!\\w)",
                    normalized_text,
                )
            )
            if occurrences > 0:
                score += occurrences * max(1, len(cleaned.split()))
        if score > 0:
            matches.append((score, row))

    matches.sort(key=lambda item: (-item[0], item[1]["first_chapter"], item[1]["name"]))
    return [row for _, row in matches[:limit]]


def build_character_voice_context(characters: list[dict]) -> str:
    if not characters:
        return "No obvious named characters were detected in the submitted passage."

    lines: list[str] = []
    for char in characters:
        personality = ", ".join((char.get("personality_tags") or [])[:4])
        motivations = ", ".join((char.get("motivations") or [])[:3])
        fears = ", ".join((char.get("fears") or [])[:3])
        trait_bits: list[str] = []
        trait_state = char.get("trait_state")
        if isinstance(trait_state, dict):
            for trait_name in ("eyes", "hair", "build", "age_descriptor", "distinguishing"):
                raw = trait_state.get(trait_name)
                value = raw.get("value") if isinstance(raw, dict) else raw
                if isinstance(value, str) and value.strip():
                    trait_bits.append(f"{trait_name}={value.strip()}")
        lines.append(
            f"- {char['name']} (first chapter {char['first_chapter']}, role {char.get('role') or 'unknown'})"
            + (f". Arc: {char.get('arc_summary')}" if char.get("arc_summary") else "")
            + (f" Personality: {personality}." if personality else "")
            + (f" Motivations: {motivations}." if motivations else "")
            + (f" Fears: {fears}." if fears else "")
            + (f" Traits: {'; '.join(trait_bits[:3])}." if trait_bits else "")
        )
    return "\n".join(lines)


def normalize_voice_consistency_result(raw: str) -> dict:
    fallback = {
        "issues": [],
        "overall_verdict": "Voice consistency review could not be parsed.",
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        fallback["overall_verdict"] = raw[:400] or fallback["overall_verdict"]
        return fallback

    cleaned_issues = []
    for issue in parsed.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        character_name = " ".join(str(issue.get("character_name") or "").split()).strip()
        title = " ".join(str(issue.get("title") or "").split()).strip()
        description = " ".join(str(issue.get("description") or "").split()).strip()
        if not character_name or not title or not description:
            continue
        cleaned_issues.append({
            "character_name": character_name,
            "severity": str(issue.get("severity") or "moderate"),
            "title": title,
            "description": description,
            "evidence": " ".join(str(issue.get("evidence") or "").split()).strip(),
            "suggestion": " ".join(str(issue.get("suggestion") or "").split()).strip(),
            "intentionality_prompt": " ".join(str(issue.get("intentionality_prompt") or "").split()).strip(),
        })

    overall_verdict = " ".join(str(parsed.get("overall_verdict") or "").split()).strip() or fallback["overall_verdict"]
    return {"issues": cleaned_issues, "overall_verdict": overall_verdict}


def normalize_editorial_review_result(raw: str) -> dict:
    fallback = {
        "continuity_issues": [],
        "insertion_opportunities": [],
        "grammar_issues": [],
        "formatting_notes": [],
        "thematic_fit": {"score": "moderate", "notes": "Unable to parse structured result."},
        "overall_verdict": "Editorial review could not be parsed.",
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        fallback["overall_verdict"] = raw[:400] or fallback["overall_verdict"]
        return fallback

    continuity_issues = []
    for issue in parsed.get("continuity_issues") or []:
        if not isinstance(issue, dict):
            continue
        title = " ".join(str(issue.get("title") or "").split()).strip()
        description = " ".join(str(issue.get("description") or "").split()).strip()
        if not title or not description:
            continue
        continuity_issues.append({
            "type": str(issue.get("type") or "event_conflict"),
            "severity": str(issue.get("severity") or "moderate"),
            "title": title,
            "description": description,
            "suggestion": " ".join(str(issue.get("suggestion") or "").split()).strip(),
        })

    insertion_opportunities = []
    for item in parsed.get("insertion_opportunities") or []:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title") or "").split()).strip()
        problem = " ".join(str(item.get("problem") or "").split()).strip()
        what_to_add = " ".join(str(item.get("what_to_add") or "").split()).strip()
        why_here = " ".join(str(item.get("why_here") or "").split()).strip()
        target_chapter = item.get("target_chapter")
        if not title or not problem or not what_to_add or not why_here:
            continue
        if not isinstance(target_chapter, int) or target_chapter < 1:
            continue
        insertion_opportunities.append({
            "title": title,
            "problem": problem,
            "target_chapter": target_chapter,
            "target_chapter_title": " ".join(str(item.get("target_chapter_title") or "").split()).strip() or None,
            "anchor_excerpt": " ".join(str(item.get("anchor_excerpt") or "").split()).strip(),
            "what_to_add": what_to_add,
            "why_here": why_here,
            "purpose": str(item.get("purpose") or "foreshadowing"),
        })

    grammar_issues = []
    for issue in parsed.get("grammar_issues") or []:
        if not isinstance(issue, dict):
            continue
        original = str(issue.get("original") or "").strip()
        label = " ".join(str(issue.get("issue") or "").split()).strip()
        fix = str(issue.get("fix") or "").strip()
        if not original or not label or not fix:
            continue
        grammar_issues.append({"original": original, "issue": label, "fix": fix})

    formatting_notes = [
        " ".join(str(note or "").split()).strip()
        for note in (parsed.get("formatting_notes") or [])
        if " ".join(str(note or "").split()).strip()
    ]

    thematic_fit = parsed.get("thematic_fit") if isinstance(parsed.get("thematic_fit"), dict) else {}
    score = str(thematic_fit.get("score") or "moderate")
    notes = " ".join(str(thematic_fit.get("notes") or "").split()).strip() or fallback["thematic_fit"]["notes"]
    overall_verdict = " ".join(str(parsed.get("overall_verdict") or "").split()).strip() or fallback["overall_verdict"]

    return {
        "continuity_issues": continuity_issues,
        "insertion_opportunities": insertion_opportunities,
        "grammar_issues": grammar_issues,
        "formatting_notes": formatting_notes,
        "thematic_fit": {"score": score, "notes": notes},
        "overall_verdict": overall_verdict,
    }


def normalize_synopsis_result(raw: str, spoiler_level: str) -> dict:
    fallback = {
        "spoiler_level": spoiler_level,
        "synopsis": "Synopsis could not be generated yet.",
        "focus_points": ["premise", "tone", "main conflict"],
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        fallback["synopsis"] = raw[:600] or fallback["synopsis"]
        return fallback

    synopsis = " ".join(str(parsed.get("synopsis") or "").split()).strip() or fallback["synopsis"]
    points = [
        " ".join(str(item or "").split()).strip()
        for item in (parsed.get("focus_points") or [])
        if " ".join(str(item or "").split()).strip()
    ][:5]
    return {
        "spoiler_level": str(parsed.get("spoiler_level") or spoiler_level),
        "synopsis": synopsis,
        "focus_points": points or fallback["focus_points"],
    }


def normalize_prose_tighten_result(raw: str, original_text: str) -> dict:
    fallback = {
        "tightened_text": original_text.strip(),
        "rationale": ["LoreVia could not safely tighten this selection yet."],
        "changed": False,
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return fallback

    tightened_text = str(parsed.get("tightened_text") or "").strip()
    rationale = [
        " ".join(str(item or "").split()).strip()
        for item in (parsed.get("rationale") or [])
        if " ".join(str(item or "").split()).strip()
    ][:4]
    if not tightened_text:
        return fallback
    return {
        "tightened_text": tightened_text,
        "rationale": rationale or ["Trimmed repetition and sharpened sentence flow."],
        "changed": tightened_text != original_text.strip(),
    }


def normalize_proactive_scan_result(raw: str) -> dict:
    fallback = {
        "findings": [],
        "overall_note": "Proactive continuity scan could not be parsed.",
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        fallback["overall_note"] = raw[:400] or fallback["overall_note"]
        return fallback

    findings: list[dict[str, Any]] = []
    for item in parsed.get("findings") or []:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title") or "").split()).strip()
        description = " ".join(str(item.get("description") or "").split()).strip()
        action_label = " ".join(str(item.get("action_label") or "").split()).strip()
        ask_prompt = " ".join(str(item.get("ask_prompt") or "").split()).strip()
        if not title or not description or not action_label or not ask_prompt:
            continue
        chapter_ref = item.get("chapter_ref")
        findings.append({
            "severity": str(item.get("severity") or "info"),
            "type": str(item.get("type") or "future_direction"),
            "title": title,
            "description": description,
            "chapter_ref": chapter_ref if isinstance(chapter_ref, int) and chapter_ref > 0 else None,
            "action_label": action_label,
            "ask_prompt": ask_prompt,
        })

    overall_note = " ".join(str(parsed.get("overall_note") or "").split()).strip() or fallback["overall_note"]
    return {"findings": findings[:4], "overall_note": overall_note}


def build_fallback_advisor_suggestions(
    *,
    book_title: str,
    total_chapters: int,
    character_count: int,
    open_thread_count: int,
    focus_thread: dict | None = None,
) -> list[dict]:
    """Return evergreen scan cards so the continuity scan never feels empty."""
    suggestions: list[dict] = [
        {
            "id": "fallback-manuscript-checkpoint",
            "type": "manuscript_checkpoint",
            "severity": "info",
            "title": "Manuscript checkpoint",
            "description": (
                f"{book_title} currently has {total_chapters} chapter"
                f"{'' if total_chapters == 1 else 's'}, {character_count} extracted character"
                f"{'' if character_count == 1 else 's'}, and {open_thread_count} unresolved plot thread"
                f"{'' if open_thread_count == 1 else 's'}. Even when nothing is obviously broken, this is a good moment to pressure-test continuity drift, pacing drag, and missing payoff."
            ),
            "chapter_ref": total_chapters if total_chapters > 0 else None,
            "action_label": "Run a manuscript check-in",
            "ask_prompt": (
                "Give me a proactive continuity and direction check-in. "
                "What feels structurally fragile or underdeveloped right now?"
            ),
        },
        {
            "id": "fallback-editorial-focus",
            "type": "editorial_focus",
            "severity": "opportunity",
            "title": "Editorial focus pass",
            "description": (
                "Use the scan as a planning prompt, not only a bug list. "
                "A focused pass can uncover weak setup, underused foreshadowing, or endings that need stronger early planting before those problems become visible in later chapters."
            ),
            "chapter_ref": total_chapters if total_chapters > 0 else None,
            "action_label": "Find the best pressure point",
            "ask_prompt": (
                "If you were doing a proactive editorial pass, where would you focus first: "
                "continuity, foreshadowing, pacing, or arc resolution?"
            ),
        },
    ]

    if focus_thread:
        thread_title = str(focus_thread.get("title") or "current arc").strip() or "current arc"
        introduced_at = focus_thread.get("introduced_at")
        description = str(focus_thread.get("description") or "").strip()
        suggestions.append({
            "id": "fallback-focus-thread",
            "type": "future_direction",
            "severity": "direction",
            "title": f"Pressure-test the \"{thread_title}\" thread",
            "description": (
                f"This looks like one of the main unresolved engines in the book"
                + (f", running since chapter {introduced_at}" if introduced_at else "")
                + ". Even without a visible contradiction, it is worth checking whether the eventual payoff is clear enough and whether the earlier setup is doing enough work."
                + (f" {description[:180]}" if description else "")
            ),
            "chapter_ref": introduced_at if isinstance(introduced_at, int) else None,
            "action_label": "Stress-test this arc",
            "ask_prompt": (
                f"Help me pressure-test the \"{thread_title}\" thread. "
                "What ending paths fit best, and what setup might still be missing?"
            ),
        })
    else:
        suggestions.append({
            "id": "fallback-foreshadowing-sweep",
            "type": "unresolved_clue",
            "severity": "opportunity",
            "title": "Run a foreshadowing sweep",
            "description": (
                "No urgent structural problems were flagged from extracted data, which usually means the highest-value next step is looking for underlined moments that could carry more future payoff."
            ),
            "chapter_ref": total_chapters if total_chapters > 0 else None,
            "action_label": "Look for payoff gaps",
            "ask_prompt": (
                "What foreshadowing or payoff opportunities am I most likely missing right now?"
            ),
        })

    return suggestions


async def build_advisor_suggestions_payload(
    *,
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    skip_llm: bool = False,
) -> dict[str, Any]:
    """Run the full heuristic + optional LLM advisor scan and return the result dict."""
    book_id = book.id
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
    if not skip_llm and heuristic_count < 3 and (recent_summaries or open_threads or world_rows):
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
        proactive_result = await get_proactive_scan_cache(str(book.id), proactive_cache_key)
        if proactive_result is None:
            if settings.OPENAI_API_KEY and settings.OPENAI_INTEL_MODEL:
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                try:
                    response = await create_tracked_chat_completion(
                        client=client,
                        feature="advisor_proactive_scan",
                        model=settings.OPENAI_INTEL_MODEL,
                        db=db,
                        user_id=user_id,
                        book_id=book.id,
                        temperature=0.2,
                        max_tokens=900,
                        response_format={"type": "json_object"},
                        messages=[
                            {
                                "role": "system",
                                "content": PROACTIVE_SCAN_SYSTEM.format(
                                    title=safe_prompt_str(book.title),
                                    story_context=safe_prompt_str(story_context),
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
                    await set_proactive_scan_cache(str(book.id), proactive_cache_key, proactive_result)
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


# ─── Continuity report builders ───────────────────────────────────────────────

def build_continuity_report_markdown(
    *,
    title: str,
    chapter_num: int | None,
    review: dict,
    retrieved_passages: list[dict],
    open_threads: list[dict],
) -> str:
    lines = [
        "# LoreVia Continuity Review Report",
        "",
        f"- Manuscript: {title}",
        f"- Chapter under review: {chapter_num if chapter_num is not None else 'Not specified'}",
        "- Document type: Editorial continuity assessment",
        "",
        "## Executive Summary",
        "",
        str(review.get("overall_verdict") or "No verdict generated."),
        "",
        "## Thematic Fit",
        "",
        f"- Rating: {review.get('thematic_fit', {}).get('score', 'unknown')}",
        f"- Notes: {review.get('thematic_fit', {}).get('notes', 'No notes provided.')}",
        "",
        "## Continuity Findings",
        "",
    ]

    issues = review.get("continuity_issues") or []
    if issues:
        for issue in issues:
            lines.extend([
                f"### {issue.get('title', 'Untitled issue')}",
                f"- Severity: {issue.get('severity', 'unknown')}",
                f"- Type: {issue.get('type', 'unknown')}",
                f"- Finding: {issue.get('description', 'No description provided.')}",
                f"- Recommended action: {issue.get('suggestion', 'No recommendation provided.')}",
                "",
            ])
    else:
        lines.extend(["No continuity conflicts were identified.", ""])

    insertions = review.get("insertion_opportunities") or []
    lines.extend(["## Insertion Opportunities", ""])
    if insertions:
        for item in insertions:
            lines.extend([
                f"### {item.get('title', 'Untitled opportunity')}",
                f"- Target chapter: {item.get('target_chapter', '-')}",
                f"- Problem addressed: {item.get('problem', 'No problem stated.')}",
                f"- Add: {item.get('what_to_add', 'No suggestion provided.')}",
                f"- Why here: {item.get('why_here', 'No reasoning provided.')}",
                "",
            ])
    else:
        lines.extend(["No insertion opportunities were identified.", ""])

    lines.extend(["## Grammar And Formatting", ""])
    grammar = review.get("grammar_issues") or []
    if grammar:
        for issue in grammar:
            lines.append(f"- {issue.get('issue', 'Grammar issue')}: \"{issue.get('original', '')}\" -> \"{issue.get('fix', '')}\"")
    else:
        lines.append("- No grammar issues recorded.")
    lines.append("")

    formatting = review.get("formatting_notes") or []
    if formatting:
        lines.extend(["Formatting notes:"] + [f"- {note}" for note in formatting] + [""])

    lines.extend(["## Forgotten Threads And Follow-Up Watchlist", ""])
    if open_threads:
        for item in open_threads:
            lines.append(f"- {item.get('title', 'Untitled')}: {item.get('description', 'No detail recorded.')}")
    else:
        lines.append("- No forgotten-thread warnings were active for this manuscript state.")
    lines.append("")

    lines.extend(["## Supporting Passages", ""])
    if retrieved_passages:
        for passage in retrieved_passages:
            chapter_label = f"Chapter {passage.get('chapter_num')}"
            if passage.get("chapter_title"):
                chapter_label += f" — {passage.get('chapter_title')}"
            lines.append(f"- {chapter_label}: {passage.get('excerpt', '')}")
    else:
        lines.append("- No passages were attached to this review.")

    return "\n".join(lines) + "\n"


def build_continuity_report_pdf(markdown: str, *, title: str, chapter_num: int | None) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    heading = styles["Heading1"]
    subheading = styles["Heading2"]
    body = styles["BodyText"]
    body.leading = 14
    body.textColor = colors.black
    story = [
        Paragraph("LoreVia Continuity Review Report", heading),
        Spacer(1, 0.16 * inch),
        Paragraph(f"Manuscript: {title}", body),
        Paragraph(f"Chapter under review: {chapter_num if chapter_num is not None else 'Not specified'}", body),
        Spacer(1, 0.18 * inch),
    ]

    for line in markdown.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            story.append(Spacer(1, 0.12 * inch))
            story.append(Paragraph(line[3:], subheading))
            continue
        if line.startswith("### "):
            story.append(Spacer(1, 0.08 * inch))
            story.append(Paragraph(line[4:], body))
            continue
        if not line.strip():
            story.append(Spacer(1, 0.08 * inch))
            continue
        if line.startswith("- "):
            story.append(Paragraph(f"• {line[2:]}", body))
        else:
            story.append(Paragraph(line, body))

    doc.build(story)
    return buffer.getvalue()


# ─── Series advisor prompts ───────────────────────────────────────────────────

SERIES_ADVISOR_SYSTEM = """\
You are a Story Advisor for the book series "{series_name}". You are talking directly with the author.

You have structured story data extracted from MULTIPLE books in this series.
Each book's characters, plot threads, and themes are labelled by book title.

Core responsibilities:
- ANSWER questions that span the whole series.
- Flag continuity breaks BETWEEN books (a character trait, event, or world rule that changes between volumes without explanation).
- Surface cross-book foreshadowing opportunities and missed connections.
- NEVER say "I have no context" — you always have series-level story data.

Format cross-book contradictions EXACTLY as:
⚠️ Cross-Book Contradiction: [what clashes — name the books]
Book A says: "[direct quote or close paraphrase]"
Book B says: "[direct quote or close paraphrase]"
Tradeoff: [what breaks if you proceed]
Suggestion: [a concrete fix]

Tone: direct, specific, like a smart developmental editor who has read every volume.
Length: 3–5 paragraphs max. Always name characters, book titles, and chapter numbers.

--- SERIES STORY DATA ---
{story_context}
-------------------------
"""

SERIES_CONTINUITY_SYSTEM = """\
You are a developmental editor and continuity guardian for the book series "{series_name}".
The author is submitting a passage from "{new_book_title}" and wants to know if it is
consistent with the EARLIER books in the series.

Return JSON only with this exact shape:
{{
  "continuity_issues": [
    {{
      "type": "character_personality" | "character_trait" | "event_conflict" | "theme_drift" | "timeline" | "cross_book_conflict",
      "severity": "critical" | "moderate" | "minor",
      "title": "short label",
      "source_book": "which earlier book this conflicts with",
      "description": "clear explanation — cite character name, book title, chapter",
      "suggestion": "concrete fix"
    }}
  ],
  "cross_book_opportunities": [
    {{
      "title": "short label",
      "description": "foreshadowing or connection opportunity between books",
      "earlier_book": "earlier book title",
      "what_to_add": "brief suggestion"
    }}
  ],
  "thematic_fit": {{
    "score": "strong" | "moderate" | "weak",
    "notes": "2-3 sentences on series tone and theme fit"
  }},
  "overall_verdict": "1-2 sentence summary"
}}

Rules:
- Only flag cross-book issues, not within-book issues already caught by the single-book editor.
- Cross-book opportunities should surface callbacks and echoes that connect the new book to earlier volumes.
- Name the earlier book and chapter when citing evidence.

--- SERIES KNOWLEDGE (earlier books) ---
{story_context}
----------------------------------------
"""


# ─── Series story context builder ────────────────────────────────────────────

async def build_series_story_context(
    db: AsyncSession,
    book_ids: list[uuid.UUID],
    book_titles: dict[uuid.UUID, str],
    max_chars_per_book: int = 8,
    max_threads_per_book: int = 5,
) -> str:
    """Build a merged story context from multiple books for series-level queries.

    Each book section is labelled with the book title so the LLM can distinguish
    between volumes.  Capped to keep prompt size cost-efficient.
    """
    series_key_parts = [
        f"{book_id}:{book_titles.get(book_id, str(book_id))}"
        for book_id in book_ids
    ]
    series_key = hashlib.sha256("||".join(series_key_parts).encode("utf-8")).hexdigest()
    version = 0
    for book_id in book_ids:
        version = max(version, await get_book_cache_version(str(book_id)))
        series_rows = (
            await db.execute(select(SeriesBook.series_id).where(SeriesBook.book_id == book_id))
        ).all()
        for row in series_rows:
            version = max(version, await get_series_cache_version(str(row.series_id)))
    cached = await get_series_story_context_cache(series_key, version)
    if cached is not None:
        return cached

    lines: list[str] = []

    for book_id in book_ids:
        title = book_titles.get(book_id, str(book_id))
        lines.append(f"\n=== Book: {title} ===")

        chars = (
            await db.execute(
                select(
                    Character.name, Character.role, Character.arc_summary,
                    Character.first_chapter, Character.archetype,
                    Character.personality_tags, Character.motivations,
                    Character.trait_state,
                )
                .where(Character.book_id == book_id)
                .order_by(Character.first_chapter)
                .limit(max_chars_per_book)
            )
        ).all()

        if chars:
            lines.append("Characters:")
            for c in chars:
                role_str = f"[{c.role}]" if c.role else ""
                arc = (c.arc_summary[:100] + "...") if c.arc_summary and len(c.arc_summary) > 100 else (c.arc_summary or "")
                tags = ", ".join((c.personality_tags or [])[:3])
                motives = "; ".join((c.motivations or [])[:2])
                lines.append(
                    f"  • {c.name} {role_str} — first ch.{c.first_chapter}. "
                    + (f"Arc: {arc} " if arc else "")
                    + (f"Personality: {tags}. " if tags else "")
                    + (f"Drives: {motives}." if motives else "")
                )

        threads = (
            await db.execute(
                select(PlotThread.title, PlotThread.status, PlotThread.introduced_at, PlotThread.description)
                .where(PlotThread.book_id == book_id)
                .order_by(PlotThread.importance.desc())
                .limit(max_threads_per_book)
            )
        ).all()

        if threads:
            lines.append("Plot threads:")
            for t in threads:
                desc = (t.description[:80] + "...") if t.description and len(t.description) > 80 else (t.description or "")
                lines.append(f"  • [{t.status}] {t.title} (ch.{t.introduced_at}). {desc}")

    payload = "\n".join(lines)
    await set_series_story_context_cache(series_key, version, payload)
    return payload


def normalize_series_continuity_result(raw: str) -> dict:
    """Normalize the cross-series continuity JSON from the LLM."""
    fallback = {
        "continuity_issues": [],
        "cross_book_opportunities": [],
        "thematic_fit": {"score": "moderate", "notes": "Unable to parse result."},
        "overall_verdict": "Cross-series continuity review could not be parsed.",
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        fallback["overall_verdict"] = raw[:400] or fallback["overall_verdict"]
        return fallback

    issues = []
    for issue in parsed.get("continuity_issues") or []:
        if not isinstance(issue, dict):
            continue
        title = " ".join(str(issue.get("title") or "").split()).strip()
        description = " ".join(str(issue.get("description") or "").split()).strip()
        if not title or not description:
            continue
        issues.append({
            "type": str(issue.get("type") or "cross_book_conflict"),
            "severity": str(issue.get("severity") or "moderate"),
            "title": title,
            "source_book": " ".join(str(issue.get("source_book") or "").split()).strip(),
            "description": description,
            "suggestion": " ".join(str(issue.get("suggestion") or "").split()).strip(),
        })

    opportunities = []
    for opp in parsed.get("cross_book_opportunities") or []:
        if not isinstance(opp, dict):
            continue
        title = " ".join(str(opp.get("title") or "").split()).strip()
        if not title:
            continue
        opportunities.append({
            "title": title,
            "description": " ".join(str(opp.get("description") or "").split()).strip(),
            "earlier_book": " ".join(str(opp.get("earlier_book") or "").split()).strip(),
            "what_to_add": " ".join(str(opp.get("what_to_add") or "").split()).strip(),
        })

    thematic_fit = parsed.get("thematic_fit") if isinstance(parsed.get("thematic_fit"), dict) else {}
    overall_verdict = " ".join(str(parsed.get("overall_verdict") or "").split()).strip() or fallback["overall_verdict"]

    return {
        "continuity_issues": issues,
        "cross_book_opportunities": opportunities,
        "thematic_fit": {
            "score": str(thematic_fit.get("score") or "moderate"),
            "notes": " ".join(str(thematic_fit.get("notes") or "").split()).strip() or fallback["thematic_fit"]["notes"],
        },
        "overall_verdict": overall_verdict,
    }
