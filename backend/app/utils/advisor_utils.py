"""
Advisor utility helpers — LLM intent/response classifiers, story context
builder, and continuity report renderers extracted from the advisor route.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections import OrderedDict
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, PlotThread, WorldElement
from app.utils.world_building_utils import build_world_logic_response, classify_world_intent


# ─── Advisor response cache ───────────────────────────────────────────────────
# Simple TTL-based LRU in-process cache keyed on sha256(book_id + last_msg).
# No external dependency — expires automatically in CACHE_TTL_SECONDS.

CACHE_TTL_SECONDS = 600   # 10 minutes
_CACHE_MAX_SIZE = 512


class _TTLCache:
    """OrderedDict-backed LRU cache with per-entry TTL."""

    def __init__(self, maxsize: int = _CACHE_MAX_SIZE) -> None:
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: float = CACHE_TTL_SECONDS) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.monotonic() + ttl)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)


advisor_response_cache = _TTLCache()


def make_advisor_cache_key(book_id: str | uuid.UUID, last_user_message: str) -> str:
    """SHA-256 key for the (book, message) pair."""
    payload = f"{book_id}||{last_user_message.strip()}"
    return hashlib.sha256(payload.encode()).hexdigest()


def make_editorial_cache_key(book_id: str | uuid.UUID, text: str, chapter_num: int | None) -> str:
    """SHA-256 key for editorial review (book, text, chapter)."""
    payload = f"{book_id}||{text.strip()[:500]}||{chapter_num or 0}"
    return hashlib.sha256(payload.encode()).hexdigest()

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


async def build_advisor_world_analysis(
    db: AsyncSession,
    book: Book,
    query: str,
    mode: str,
) -> dict[str, Any]:
    """Run the world-building analyzer for advisor chat questions."""
    return await build_world_logic_response(db, book, query, mode)


RESPONSE_TYPE_PROMPT = """\
Given this Story Advisor reply, classify the PRIMARY response type into ONE of:
  standard | warning | opportunity | tradeoff

- warning: reply leads with ⚠️ Contradiction or contradicts the author's plan
- opportunity: reply leads with ✨ Opportunity or surfaces unused story potential
- tradeoff: reply uses 🔀 Option A/B or debates story direction choices
- standard: informational answer, analysis, or general advice

Reply text (first 400 chars): {reply}

Reply with just the label, nothing else."""

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
- If nothing is off, return an empty issues array and say the voices feel consistent.

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

async def classify_intent(client: AsyncOpenAI, message: str) -> str:
    from app.core.config import settings
    try:
        r = await client.chat.completions.create(
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
    """Fast rule-based check first, then LLM fallback."""
    from app.core.config import settings
    if reply.startswith("⚠️") or "⚠️ Contradiction" in reply[:200]:
        return "warning"
    if reply.startswith("✨") or "✨ Opportunity" in reply[:200]:
        return "opportunity"
    if "🔀 Option" in reply[:400]:
        return "tradeoff"
    try:
        r = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
            max_tokens=10,
            temperature=0,
            messages=[
                {"role": "user", "content": RESPONSE_TYPE_PROMPT.format(reply=reply[:400])},
            ],
        )
        label = (r.choices[0].message.content or "").strip().lower()
        return label if label in ("standard", "warning", "opportunity", "tradeoff") else "standard"
    except Exception:
        return "standard"


# ─── Story context builder ────────────────────────────────────────────────────

async def build_story_context(db: AsyncSession, book_id: uuid.UUID, total_ch: int) -> str:
    """Pulls structured story data — characters + plot threads — to give the advisor
    grounding even when passage retrieval returns nothing."""
    lines: list[str] = [f"Total chapters processed: {total_ch}"]

    chars = (
        await db.execute(
            select(Character.name, Character.role, Character.arc_summary, Character.first_chapter,
                   Character.archetype, Character.personality_tags, Character.motivations,
                   Character.trait_state, Character.growth_events)
            .where(Character.book_id == book_id)
            .order_by(Character.first_chapter)
            .limit(20)
        )
    ).all()

    if chars:
        lines.append("\nCHARACTERS (extracted from manuscript):")
        for c in chars:
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

    threads = (
        await db.execute(
            select(PlotThread.title, PlotThread.status, PlotThread.importance,
                   PlotThread.introduced_at, PlotThread.description)
            .where(PlotThread.book_id == book_id)
            .order_by(PlotThread.importance.desc())
            .limit(12)
        )
    ).all()

    if threads:
        lines.append("\nPLOT THREADS (extracted from manuscript):")
        for t in threads:
            desc = (t.description[:100] + "...") if t.description and len(t.description) > 100 else (t.description or "")
            lines.append(
                f"  • [{t.status.upper()}] {t.title} (importance {t.importance}/10, "
                f"introduced ch.{t.introduced_at}). {desc}"
            )

    world_reference_rows = (
        await db.execute(
            select(WorldElement.name, WorldElement.element_type, WorldElement.description)
            .where(WorldElement.book_id == book_id, WorldElement.source_scope == "worldbuilding")
            .order_by(WorldElement.usage_count.desc(), WorldElement.name.asc())
            .limit(10)
        )
    ).all()
    if world_reference_rows:
        lines.append("\nWORLD REFERENCE CORPUS (author-supplied lore):")
        for name, element_type, description in world_reference_rows:
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

    world_rows = (
        await db.execute(
            select(WorldElement.name, WorldElement.element_type, WorldElement.description, WorldElement.usage_count)
            .where(WorldElement.book_id == book_id)
            .order_by(WorldElement.usage_count.desc(), WorldElement.created_at.desc())
            .limit(12)
        )
    ).all()
    if world_rows:
        lines.append("\nWORLD ELEMENTS (extracted from manuscript):")
        for row in world_rows:
            desc = " ".join(str(row.description or "").split()).strip()
            if len(desc) > 100:
                desc = desc[:100] + "..."
            lines.append(f"  - {row.name} [{row.element_type}] usage={row.usage_count}. {desc}")

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

    return "\n".join(lines)


def identify_character_mentions(
    text: str,
    character_rows: list[dict],
    limit: int = 5,
) -> list[dict]:
    stripped_text = re.sub(r'\\s+', ' ', text.casefold()).strip()
    normalized_text = f" {stripped_text} "
    matches: list[tuple[int, dict]] = []

    for row in character_rows:
        score = 0
        for candidate in [row.get("name"), *(row.get("aliases") or [])]:
            cleaned = " ".join(str(candidate or "").split()).strip()
            if not cleaned:
                continue
            if f" {cleaned.casefold()} " in normalized_text:
                score += max(1, len(cleaned.split()))
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

    return "\n".join(lines)


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
