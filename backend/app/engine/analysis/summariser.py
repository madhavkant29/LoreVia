"""
Chapter summary generation - 3 modes.
Generated once, cached in Redis + stored in DB forever.
"""
import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.llm import complete_with_fallback

PROMPTS = {
    "short": (
        "Summarise this chapter in 3-4 sentences. Key events only. "
        "No spoilers beyond what is shown. Be concise and factual."
    ),
    "detailed": """Analyse this chapter and return JSON only:
{
  "summary": "4-6 paragraph summary with concrete detail and cause-effect continuity",
  "key_events": [{
    "event_title": "...",
    "description": "...",
    "importance": 1-10,
    "impact": "...",
    "involved_characters": ["Character Name"],
    "event_type": "plot_twist|climax|resolution|setup"
  }],
  "char_changes": [{
    "character": "...",
    "change": "...",
    "evidence": "...",
    "event_title": "...",
    "description": "...",
    "impact_score": 1-10,
    "role": "protagonist|supporting|antagonist|ally",
    "accomplishments": ["..."],
    "growth_direction": "positive|negative|neutral",
    "growth_magnitude": 1-10,
    "is_major": true
  }],
  "clues": [{"clue": "...", "foreshadows": "...", "why_it_matters": "..."}],
  "themes": [{"theme": "...", "signal": "explicit|subtext", "evidence": "...", "depth": "surface|complex"}],
  "open_questions": ["..."]
}
Rules:
- Return raw JSON only. No markdown fences.
- Use concrete names, motivations, and turning points from the text.
- The summary should feel rich enough for a reader who forgot the chapter, not like a compressed blurb.
- Preserve chronology and explain why the chapter matters.
- Include both obvious and philosophical themes when grounded in the text, such as false altruism, self-hatred, moral injury, denial, obsession, unreliable narration, or identity fracture.
- If there are no character changes or clues, return empty arrays.
- Do not include any text before or after the JSON.""",
    "key_points": (
        "List exactly 5 key things that happen in this chapter. "
        "Numbered. One sentence each. Most important first."
    ),
}


async def generate_summary(
    chapter_text: str,
    mode: str,
    title: str = "",
    *,
    openai_client: AsyncOpenAI | None = None,
) -> dict:
    system = f"You are analysing chapter: {title}. " + PROMPTS[mode]
    content = await complete_with_fallback(
        system=system,
        user=chapter_text[:9000],
        openai_model=settings.OPENAI_EXTRACT_MODEL,
        gemini_model=settings.GEMINI_EXTRACT_MODEL,
        temperature=0.2,
        max_tokens=2200,
        response_format={"type": "json_object"} if mode == "detailed" else None,
        openai_client=openai_client,
    )

    if mode == "detailed":
        try:
            data = json.loads(_strip_json_fence(content))
            return _normalize_summary_payload(data, fallback=content)
        except json.JSONDecodeError:
            pass
    return {"content": content, "key_events": None, "char_changes": None, "clues": None, "themes": None}


def derive_summary_modes_from_detailed(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    detailed_content = " ".join(str(payload.get("content") or "").split()).strip()
    key_events = [item for item in (payload.get("key_events") or []) if isinstance(item, dict)]

    short_sentences = _split_sentences(detailed_content)[:3]
    short_content = " ".join(short_sentences).strip() or detailed_content

    key_points: list[str] = []
    for index, item in enumerate(key_events[:5], start=1):
        title = " ".join(str(item.get("event_title") or item.get("event") or "").split()).strip()
        description = " ".join(str(item.get("description") or item.get("impact") or "").split()).strip()
        sentence = description or title
        if title and description and not description.lower().startswith(title.lower()):
            sentence = f"{title}: {description}"
        cleaned_sentence = sentence.rstrip(". ")
        if cleaned_sentence:
            key_points.append(f"{index}. {cleaned_sentence}.")

    if not key_points:
        fallback_sentences = _split_sentences(detailed_content)[:5]
        key_points = [f"{index}. {sentence.rstrip('. ')}." for index, sentence in enumerate(fallback_sentences, start=1) if sentence]

    return {
        "short": {
            "content": short_content,
            "key_events": None,
            "char_changes": None,
            "clues": None,
            "themes": None,
        },
        "key_points": {
            "content": "\n".join(key_points).strip(),
            "key_events": None,
            "char_changes": None,
            "clues": None,
            "themes": None,
        },
    }


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    elif stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    return stripped.strip()


def _normalize_summary_payload(data: dict, fallback: str) -> dict:
    key_events = []
    for item in data.get("key_events") or []:
        if isinstance(item, dict):
            key_events.append(
                {
                    "event_title": item.get("event_title") or item.get("event") or "",
                    "event": item.get("event") or item.get("event_title") or "",
                    "description": item.get("description") or item.get("impact") or "",
                    "importance": item.get("importance") or 5,
                    "impact": item.get("impact") or item.get("description") or "",
                    "involved_characters": item.get("involved_characters") or [],
                    "event_type": item.get("event_type"),
                }
            )
        elif isinstance(item, str) and item.strip():
            key_events.append({"event_title": item.strip(), "event": item.strip(), "description": "", "importance": 5, "impact": "", "involved_characters": []})

    char_changes = []
    for item in data.get("char_changes") or []:
        if not isinstance(item, dict):
            continue
        char_changes.append(
            {
                "character": item.get("character") or "",
                "change": item.get("change") or item.get("description") or "",
                "evidence": item.get("evidence") or "",
                "event_title": item.get("event_title") or item.get("change") or "",
                "description": item.get("description") or item.get("change") or "",
                "impact_score": item.get("impact_score") or 5,
                "role": item.get("role"),
                "accomplishments": item.get("accomplishments") or [],
                "growth_direction": item.get("growth_direction") or "neutral",
                "growth_magnitude": item.get("growth_magnitude") or item.get("impact_score") or 5,
                "is_major": bool(item.get("is_major", False)),
            }
        )
    return {
        "content": data.get("summary", fallback),
        "key_events": key_events,
        "char_changes": char_changes,
        "clues": data.get("clues") or [],
        "themes": data.get("themes") or [],
    }


def _split_sentences(content: str) -> list[str]:
    if not content:
        return []
    segments = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", content) if segment.strip()]
    return segments
