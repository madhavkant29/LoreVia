"""
Plot thread extraction and status tracking.
"""
import json
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

PLOT_SYSTEM = """Analyse this chapter for plot threads. Return JSON only:
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
Focus on meaningful story threads, not minor events. Return [] if nothing significant."""


async def extract_plot_threads(chapter_text: str, chapter_num: int) -> list[dict]:
    r = await client.chat.completions.create(
        model=settings.OPENAI_EXTRACT_MODEL,
        messages=[
            {"role": "system", "content": PLOT_SYSTEM},
            {"role": "user", "content": chapter_text[:5000]},
        ],
        temperature=0.1,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(r.choices[0].message.content)
        threads = data.get("threads", [])
        for t in threads:
            t["introduced_at"] = chapter_num
        return threads
    except Exception:
        return []
