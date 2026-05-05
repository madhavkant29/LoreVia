"""
Character chat: in-character responses grounded in story context.
"""
from typing import Any, cast

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.character import Character


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


CHAR_SYSTEM = """You are {name} from "{title}".

Manuscript-derived profile:
- Personality: {personality}
- Motivations: {motivations}
- Fears: {fears}
- Arc so far: {arc_summary}
- Physical: {description}
- Relationship memory: {relationships}
- Growth evidence: {growth_events}

What you know (up to chapter {chapter}):
{context}

RULES:
- Stay completely in character. Speak as {name} would.
- Only reference events up to chapter {chapter}.
- Never break the fourth wall or mention you are an AI.
- If asked about something you don't know yet, react in character to the uncertainty.
- Keep responses concise: 2-4 sentences unless the question warrants more."""


def _join_values(values: list[str] | None, fallback: str = "unknown") -> str:
    cleaned = [value.strip() for value in values or [] if value and value.strip()]
    return ", ".join(cleaned) if cleaned else fallback


def _format_growth_events(events: object) -> str:
    if not isinstance(events, list):
        return "no growth evidence extracted yet"
    lines: list[str] = []
    for item in events[:5]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("event_title") or item.get("event") or "story beat").strip()
        description = str(item.get("description") or item.get("impact") or "").strip()
        chapter = item.get("chapter_number") or item.get("chapter")
        prefix = f"chapter {chapter}: " if chapter else ""
        lines.append(f"{prefix}{title}{f' - {description}' if description else ''}")
    return "; ".join(lines) if lines else "no growth evidence extracted yet"


async def chat_as_character(
    character: Character,
    book_title: str,
    current_chapter: int,
    context_summary: str,
    search_context: str,
    messages: list[dict],
) -> str:
    client = get_client()
    try:
        from app.engine.character.profile_builder import build_description

        system = CHAR_SYSTEM.format(
            name=character.name,
            title=book_title,
            personality=_join_values(character.personality_tags),
            motivations=_join_values(character.motivations),
            fears=_join_values(character.fears),
            arc_summary=character.arc_summary or "story ongoing",
            description=build_description(character.trait_state or {}, character.archetype),
            relationships=_join_values(character.relationship_summaries, "no relationship evidence extracted yet"),
            growth_events=_format_growth_events(character.growth_events),
            chapter=current_chapter,
            context=("\n".join(filter(None, [context_summary or "", search_context or ""])))[:1300],
        )

        recent = messages[-10:]
        chat_messages = cast(Any, [{"role": "system", "content": system}] + recent)

        response = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
            messages=chat_messages,
            temperature=0.7,
            max_tokens=220,
        )
        return (response.choices[0].message.content or "").strip()
    finally:
        await client.close()
