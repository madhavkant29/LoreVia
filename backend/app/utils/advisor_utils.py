"""
Advisor utility helpers — LLM intent/response classifiers, story context
builder, and continuity report renderers extracted from the advisor route.
"""
from __future__ import annotations

import json
import re
import uuid

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, PlotThread

# ─── System / prompt templates ────────────────────────────────────────────────

ADVISOR_SYSTEM = """\
You are a Story Advisor for the novel "{title}". You are talking directly with the author.

You have two sources of knowledge about this book:
1. STORY KNOWLEDGE — structured data extracted from the full manuscript (characters, plot threads, chapter count)
2. RETRIEVED PASSAGES — specific text excerpts most relevant to the author's question

Core responsibilities:
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
You are generating a spoiler-light synopsis for the novel "{title}".

You have:
- STORY KNOWLEDGE about the manuscript
- EARLY CHAPTER CONTEXT from the beginning of the book

Return JSON only:
{{
  "spoiler_level": "none" | "minimal",
  "synopsis": "2-4 paragraphs",
  "focus_points": ["hook", "tone", "premise"]
}}

Rules:
- Keep spoilers at {spoiler_level} level.
- Prefer premise, tone, main dramatic situation, and early character dynamics.
- Do not reveal major twists, endings, betrayals, secret identities, or late-book resolutions.
- If uncertain, stay vaguer rather than spoil.
- Write like jacket-copy plus author-facing grounding, not marketing fluff.

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


# ─── LLM classifiers ─────────────────────────────────────────────────────────

async def classify_intent(client: AsyncOpenAI, message: str) -> str:
    try:
        r = await client.chat.completions.create(
            model="gpt-4o-mini",
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
    if reply.startswith("⚠️") or "⚠️ Contradiction" in reply[:200]:
        return "warning"
    if reply.startswith("✨") or "✨ Opportunity" in reply[:200]:
        return "opportunity"
    if "🔀 Option" in reply[:400]:
        return "tradeoff"
    try:
        r = await client.chat.completions.create(
            model="gpt-4o-mini",
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
                latest_growth = next((item for item in reversed(c.growth_events) if isinstance(item, dict) and item.get("event")), None)
                if latest_growth:
                    growth = f"Recent growth beat: {latest_growth.get('event')}."
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
