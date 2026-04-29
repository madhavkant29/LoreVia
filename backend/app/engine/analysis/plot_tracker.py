"""
Plot thread extraction and status tracking.
"""
import json

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.llm import complete_with_fallback

PLOT_SYSTEM = """Analyse this chapter for meaningful plot threads. Return JSON only:
{
  "threads": [
    {
      "title": "short title e.g. The revenge arc",
      "type": "main|sub|mystery|romance|political",
      "status": "introduced|ongoing|resolved|abandoned|unknown",
      "description": "1 sentence",
      "characters_involved": ["name1", "name2"],
      "importance": 1-10
    }
  ]
}
Rules:
- Focus on meaningful story threads, not minor events.
- Use specific titles grounded in the text, not generic labels.
- Only emit a thread if it has clear stakes or ongoing narrative importance.
- Track psychological and philosophical tensions when they meaningfully drive the plot, including false altruism, self-hatred, denial, obsession, moral injury, or unreliable narration.
- Return raw JSON only. No markdown fences.
- Return [] if nothing significant."""


async def extract_plot_threads(
    chapter_text: str,
    chapter_num: int,
    *,
    openai_client: AsyncOpenAI | None = None,
) -> list[dict]:
    try:
        content = await complete_with_fallback(
            system=PLOT_SYSTEM,
            user=chapter_text[:5000],
            openai_model=settings.OPENAI_EXTRACT_MODEL,
            gemini_model=settings.GEMINI_EXTRACT_MODEL,
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
            openai_client=openai_client,
        )
        try:
            data = json.loads(_strip_json_fence(content))
            threads = data.get("threads", [])
            for t in threads:
                t["introduced_at"] = chapter_num
            return threads
        except Exception:
            return []
    except Exception:
        return []


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    elif stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    return stripped.strip()
