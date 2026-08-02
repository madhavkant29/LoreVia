"""
Plot thread extraction and status tracking.
"""

import json
import uuid
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.llm import LLM_PROVIDER_EXCEPTIONS, complete_with_fallback
from app.engine.analysis.summariser import _analysis_passages

PLOT_SYSTEM = """Analyse this chapter for meaningful plot threads. Return JSON only:
{
  "threads": [
    {
      "title": "short title e.g. Joren promised to return the amulet",
      "type": "promise|mystery|conflict|prophecy|goal|object|clue|relationship_tension|open_question|subplot|political|romance|main",
      "status": "introduced|developing|paused|resolved|contradicted|abandoned|unknown",
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
- Track promises, mysteries, conflicts, prophecies, goals, objects, clues, relationship tensions, and open questions when they carry reader expectation.
- Track psychological and philosophical tensions when they meaningfully drive the plot, including false altruism, self-hatred, denial, obsession, moral injury, or unreliable narration.
- Use "paused" when a thread is intentionally quiet in this chapter, "contradicted" when the chapter undermines prior setup, and "abandoned" only when the text strongly implies the thread is being dropped.
- Return raw JSON only. No markdown fences.
- Return [] if nothing significant."""


async def extract_plot_threads(
    chapter_text: str,
    chapter_num: int,
    *,
    openai_client: AsyncOpenAI | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
) -> list[dict]:
    threads_by_key: dict[str, dict[str, Any]] = {}
    passages = _analysis_passages(chapter_text, max_chars=5000)
    for part_index, passage in enumerate(passages, start=1):
        try:
            usage_metadata: dict[str, Any] = {"chapter_number": chapter_num}
            if len(passages) > 1:
                usage_metadata.update({"part_index": part_index, "part_count": len(passages)})
            content = await complete_with_fallback(
                system=(
                    PLOT_SYSTEM
                    if len(passages) == 1
                    else (
                        f"{PLOT_SYSTEM}\nThis is part {part_index} of {len(passages)}. "
                        "Only report threads evidenced in this part."
                    )
                ),
                user=passage,
                openai_model=settings.OPENAI_EXTRACT_MODEL,
                gemini_model=settings.GEMINI_EXTRACT_MODEL,
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"},
                openai_client=openai_client,
                usage_feature="plot_thread_extraction",
                usage_user_id=user_id,
                usage_book_id=book_id,
                usage_metadata=usage_metadata,
            )
            data = json.loads(_strip_json_fence(content))
            for thread in data.get("threads", []):
                if not isinstance(thread, dict):
                    continue
                title = " ".join(str(thread.get("title") or "").split()).strip()
                if not title:
                    continue
                key = title.casefold()
                thread["introduced_at"] = chapter_num
                existing = threads_by_key.get(key)
                if existing is None:
                    threads_by_key[key] = thread
                    continue
                existing["importance"] = max(
                    int(existing.get("importance") or 5),
                    int(thread.get("importance") or 5),
                )
                existing["characters_involved"] = list(
                    dict.fromkeys(
                        [
                            *(existing.get("characters_involved") or []),
                            *(thread.get("characters_involved") or []),
                        ]
                    )
                )
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
        except LLM_PROVIDER_EXCEPTIONS:
            continue
    return list(threads_by_key.values())


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    elif stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    return stripped.strip()
