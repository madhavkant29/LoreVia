"""
Chapter summary generation - 3 modes.
Generated once, cached in Redis + stored in DB forever.
"""
import json

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
  "key_events": [{"event": "...", "importance": 1-10, "impact": "..."}],
  "char_changes": [{"character": "...", "change": "...", "evidence": "..."}],
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


async def generate_summary(chapter_text: str, mode: str, title: str = "") -> dict:
    system = f"You are analysing chapter: {title}. " + PROMPTS[mode]
    content = await complete_with_fallback(
        system=system,
        user=chapter_text[:9000],
        openai_model=settings.OPENAI_EXTRACT_MODEL,
        gemini_model=settings.GEMINI_EXTRACT_MODEL,
        temperature=0.2,
        max_tokens=2200,
        response_format={"type": "json_object"} if mode == "detailed" else None,
    )

    if mode == "detailed":
        try:
            data = json.loads(_strip_json_fence(content))
            return _normalize_summary_payload(data, fallback=content)
        except json.JSONDecodeError:
            pass
    return {"content": content, "key_events": None, "char_changes": None, "clues": None, "themes": None}


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
    return {
        "content": data.get("summary", fallback),
        "key_events": data.get("key_events") or [],
        "char_changes": data.get("char_changes") or [],
        "clues": data.get("clues") or [],
        "themes": data.get("themes") or [],
    }
