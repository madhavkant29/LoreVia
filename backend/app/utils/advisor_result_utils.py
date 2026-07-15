from __future__ import annotations

import json
import re
from typing import Any

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
        cleaned_issues.append(
            {
                "character_name": character_name,
                "severity": str(issue.get("severity") or "moderate"),
                "title": title,
                "description": description,
                "evidence": " ".join(str(issue.get("evidence") or "").split()).strip(),
                "suggestion": " ".join(str(issue.get("suggestion") or "").split()).strip(),
                "intentionality_prompt": " ".join(
                    str(issue.get("intentionality_prompt") or "").split()
                ).strip(),
            }
        )

    overall_verdict = (
        " ".join(str(parsed.get("overall_verdict") or "").split()).strip()
        or fallback["overall_verdict"]
    )
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
        continuity_issues.append(
            {
                "type": str(issue.get("type") or "event_conflict"),
                "severity": str(issue.get("severity") or "moderate"),
                "title": title,
                "description": description,
                "suggestion": " ".join(str(issue.get("suggestion") or "").split()).strip(),
            }
        )

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
        insertion_opportunities.append(
            {
                "title": title,
                "problem": problem,
                "target_chapter": target_chapter,
                "target_chapter_title": " ".join(
                    str(item.get("target_chapter_title") or "").split()
                ).strip()
                or None,
                "anchor_excerpt": " ".join(str(item.get("anchor_excerpt") or "").split()).strip(),
                "what_to_add": what_to_add,
                "why_here": why_here,
                "purpose": str(item.get("purpose") or "foreshadowing"),
            }
        )

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

    thematic_fit = (
        parsed.get("thematic_fit") if isinstance(parsed.get("thematic_fit"), dict) else {}
    )
    score = str(thematic_fit.get("score") or "moderate")
    notes = (
        " ".join(str(thematic_fit.get("notes") or "").split()).strip()
        or fallback["thematic_fit"]["notes"]
    )
    overall_verdict = (
        " ".join(str(parsed.get("overall_verdict") or "").split()).strip()
        or fallback["overall_verdict"]
    )

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
        findings.append(
            {
                "severity": str(item.get("severity") or "info"),
                "type": str(item.get("type") or "future_direction"),
                "title": title,
                "description": description,
                "chapter_ref": chapter_ref
                if isinstance(chapter_ref, int) and chapter_ref > 0
                else None,
                "action_label": action_label,
                "ask_prompt": ask_prompt,
            }
        )

    overall_note = (
        " ".join(str(parsed.get("overall_note") or "").split()).strip() or fallback["overall_note"]
    )
    return {"findings": findings[:4], "overall_note": overall_note}


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
        issues.append(
            {
                "type": str(issue.get("type") or "cross_book_conflict"),
                "severity": str(issue.get("severity") or "moderate"),
                "title": title,
                "source_book": " ".join(str(issue.get("source_book") or "").split()).strip(),
                "description": description,
                "suggestion": " ".join(str(issue.get("suggestion") or "").split()).strip(),
            }
        )

    opportunities = []
    for opp in parsed.get("cross_book_opportunities") or []:
        if not isinstance(opp, dict):
            continue
        title = " ".join(str(opp.get("title") or "").split()).strip()
        if not title:
            continue
        opportunities.append(
            {
                "title": title,
                "description": " ".join(str(opp.get("description") or "").split()).strip(),
                "earlier_book": " ".join(str(opp.get("earlier_book") or "").split()).strip(),
                "what_to_add": " ".join(str(opp.get("what_to_add") or "").split()).strip(),
            }
        )

    thematic_fit = (
        parsed.get("thematic_fit") if isinstance(parsed.get("thematic_fit"), dict) else {}
    )
    overall_verdict = (
        " ".join(str(parsed.get("overall_verdict") or "").split()).strip()
        or fallback["overall_verdict"]
    )

    return {
        "continuity_issues": issues,
        "cross_book_opportunities": opportunities,
        "thematic_fit": {
            "score": str(thematic_fit.get("score") or "moderate"),
            "notes": " ".join(str(thematic_fit.get("notes") or "").split()).strip()
            or fallback["thematic_fit"]["notes"],
        },
        "overall_verdict": overall_verdict,
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
        suggestions.append(
            {
                "id": "fallback-focus-thread",
                "type": "future_direction",
                "severity": "direction",
                "title": f'Pressure-test the "{thread_title}" thread',
                "description": (
                    "This looks like one of the main unresolved engines in the book"
                    + (f", running since chapter {introduced_at}" if introduced_at else "")
                    + ". Even without a visible contradiction, it is worth checking whether the eventual payoff is clear enough and whether the earlier setup is doing enough work."
                    + (f" {description[:180]}" if description else "")
                ),
                "chapter_ref": introduced_at if isinstance(introduced_at, int) else None,
                "action_label": "Stress-test this arc",
                "ask_prompt": (
                    f'Help me pressure-test the "{thread_title}" thread. '
                    "What ending paths fit best, and what setup might still be missing?"
                ),
            }
        )
    else:
        suggestions.append(
            {
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
            }
        )

    return suggestions
