"""
Character chat — in-character responses grounded in story context.
Phase 3 feature. Uses GPT-4o-mini for quality.
"""
from typing import Any, cast

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.character import Character


def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

CHAR_SYSTEM = """You are {name} from "{title}".

About you:
- Personality: {personality}
- Motivations: {motivations}
- Fears: {fears}
- Arc so far: {arc_summary}
- Physical: {description}

What you know (up to chapter {chapter}):
{context}

RULES:
- Stay completely in character. Speak as {name} would.
- Only reference events up to chapter {chapter}.
- Never break the fourth wall or mention you are an AI.
- If asked about something you don't know yet, react in character to the uncertainty.
- Keep responses concise — 2–4 sentences unless the question warrants more."""


async def chat_as_character(
    character: Character,
    book_title: str,
    current_chapter: int,
    context_summary: str,
    search_context: str,
    messages: list[dict],  # conversation history: [{"role": "user"/"assistant", "content": "..."}]
) -> str:
    client = get_client()
    try:
        from app.engine.character.profile_builder import build_description

        system = CHAR_SYSTEM.format(
            name=character.name,
            title=book_title,
            personality=", ".join(character.personality_tags or []) or "unknown",
            motivations=", ".join(character.motivations or []) or "unknown",
            fears=", ".join(character.fears or []) or "unknown",
            arc_summary=character.arc_summary or "story ongoing",
            description=build_description(character.trait_state or {}, character.archetype),
            chapter=current_chapter,
            context=("\n".join(filter(None, [context_summary or "", search_context or ""])))[:1300],
        )

        # Keep last 10 turns to manage context window
        recent = messages[-10:]
        chat_messages = cast(Any, [{"role": "system", "content": system}] + recent)

        r = await client.chat.completions.create(
            model=settings.OPENAI_INTEL_MODEL,
            messages=chat_messages,
            temperature=0.7,
            max_tokens=220,
        )
        return (r.choices[0].message.content or "").strip()
    finally:
        await client.close()
