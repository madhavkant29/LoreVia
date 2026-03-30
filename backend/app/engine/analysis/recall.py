"""
Memory recall - generates "Previously on..." summary for returning readers.
"""
from openai import AsyncOpenAI

from app.core.config import settings


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

RECALL_PROMPT = """The user is returning to read after a break.
They last read up to chapter {last_chapter} of "{title}".
They are about to continue reading.

Based on the story so far, generate a brief "Previously on..." recap:

Recent events (last 3 important things that happened)
Key characters active (3 most relevant right now)
Open thread (1 unresolved mystery or question)

Keep it brief, friendly, and spoiler-free (nothing past chapter {last_chapter}).
No headers - just natural flowing text, like a friend reminding you."""


async def generate_recall(
    title: str,
    last_chapter: int,
    recent_summary: str,
    active_characters: list[str],
    open_threads: list[str],
) -> str:
    client = get_client()
    try:
        context = (
            f"Recent events: {recent_summary}\n"
            f"Active characters: {', '.join(active_characters[:5])}\n"
            f"Open threads: {', '.join(open_threads[:3])}"
        )
        prompt = RECALL_PROMPT.format(title=title, last_chapter=last_chapter)

        r = await client.chat.completions.create(
            model=settings.OPENAI_EXTRACT_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
            ],
            temperature=0.4,
            max_tokens=300,
        )
        return r.choices[0].message.content.strip()
    finally:
        await client.close()
