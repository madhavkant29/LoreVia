"""
Chapter summary generation - 3 modes.
Generated once, cached in Redis + stored in DB forever.
"""
import json

from openai import AsyncOpenAI

from app.core.config import settings


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

PROMPTS = {
    "short": (
        "Summarise this chapter in 3-4 sentences. Key events only. "
        "No spoilers beyond what is shown. Be concise and factual."
    ),
    "detailed": """Analyse this chapter and return JSON only:
{
  "summary": "2-3 paragraph summary",
  "key_events": [{"event": "...", "importance": 1-10}],
  "char_changes": [{"character": "...", "change": "..."}],
  "clues": [{"clue": "...", "foreshadows": "..."}],
  "open_questions": ["..."]
}
Rules:
- Return raw JSON only. No markdown fences.
- Use concrete names from the text.
- If there are no character changes or clues, return empty arrays.
- Do not include any text before or after the JSON.""",
    "key_points": (
        "List exactly 5 key things that happen in this chapter. "
        "Numbered. One sentence each. Most important first."
    ),
}


async def generate_summary(chapter_text: str, mode: str, title: str = "") -> dict:
    client = get_client()
    try:
        system = f"You are analysing chapter: {title}. " + PROMPTS[mode]
        request_kwargs = {
            "model": settings.OPENAI_EXTRACT_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": chapter_text[:6000]},
            ],
            "temperature": 0.2,
            "max_tokens": 1500,
        }
        if mode == "detailed":
            request_kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**request_kwargs)
        content = response.choices[0].message.content.strip()

        if mode == "detailed":
            try:
                data = json.loads(_strip_json_fence(content))
                return _normalize_summary_payload(data, fallback=content)
            except json.JSONDecodeError:
                pass
        return {"content": content, "key_events": None, "char_changes": None, "clues": None}
    finally:
        await client.close()


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
    }
