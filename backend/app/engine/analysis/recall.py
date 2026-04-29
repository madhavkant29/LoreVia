"""
Memory recall - generates a grounded recap for returning readers.
"""

from app.core.config import settings
from app.core.llm import complete_with_fallback

RECALL_PROMPT = """You are helping a reader resume a book after a break.
They last read up to chapter {last_chapter} of "{title}" and are about to continue.

Write a grounded recap in natural prose.

Rules:
- Keep it to 2-3 sentences.
- Use concrete names and events when they are available.
- Preserve uncertainty when the source context is thin.
- Never include spoilers past chapter {last_chapter}.
- Avoid list formatting, headers, and quotation marks unless the source requires them.
- Mention at most one unresolved question near the end.
"""


async def generate_recall(
    title: str,
    last_chapter: int,
    recent_summary: str,
    active_characters: list[str],
    open_threads: list[str],
) -> str:
    context = (
        f"Recent events:\n{recent_summary}\n\n"
        f"Active characters:\n{', '.join(active_characters[:5]) or 'Unknown'}\n\n"
        f"Open threads:\n{', '.join(open_threads[:3]) or 'Unknown'}"
    )
    prompt = RECALL_PROMPT.format(title=title, last_chapter=last_chapter)
    content = await complete_with_fallback(
        system=prompt,
        user=context,
        openai_model=settings.OPENAI_EXTRACT_MODEL,
        gemini_model=settings.GEMINI_EXTRACT_MODEL,
        temperature=0.25,
        max_tokens=220,
    )
    return _polish_recall(content)


def _polish_recall(text: str) -> str:
    cleaned = " ".join((text or "").split())
    cleaned = cleaned.removeprefix("Previously on:").removeprefix("Previously on").strip(" :-")
    replacements = {
        "As we dive back in,": "",
        "Meanwhile,": "",
        "the overarching themes of": "",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned.strip()
