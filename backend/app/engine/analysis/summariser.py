"""
Chapter summary generation - 3 modes.
Generated once, cached in Redis + stored in DB forever.
"""
import json

from openai import AsyncOpenAI

from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

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
}""",
    "key_points": (
        "List exactly 5 key things that happen in this chapter. "
        "Numbered. One sentence each. Most important first."
    ),
}


async def generate_summary(chapter_text: str, mode: str, title: str = "") -> dict:
    system = f"You are analysing chapter: {title}. " + PROMPTS[mode]
    response = await client.chat.completions.create(
        model=settings.OPENAI_EXTRACT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": chapter_text[:6000]},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    content = response.choices[0].message.content.strip()

    if mode == "detailed":
        try:
            data = json.loads(content)
            return {
                "content": data.get("summary", content),
                "key_events": data.get("key_events"),
                "char_changes": data.get("char_changes"),
                "clues": data.get("clues"),
            }
        except json.JSONDecodeError:
            pass
    return {"content": content, "key_events": None, "char_changes": None, "clues": None}
