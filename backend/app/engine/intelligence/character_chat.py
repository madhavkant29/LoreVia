"""
Character chat: in-character responses grounded in story context.
"""
from typing import Any, cast

from app.core.config import settings
from app.core.llm import complete_with_fallback
from app.models.character import Character


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


def _format_relationship_memory(character: Character) -> str:
    direct_summaries = getattr(character, "relationship_summaries", None)
    if isinstance(direct_summaries, list):
        cleaned = [str(item).strip() for item in direct_summaries if str(item).strip()]
        if cleaned:
            return "; ".join(cleaned[:4])

    summaries: list[str] = []
    for attr_name, counterpart_attr in (
        ("relationships_as_a", "character_b"),
        ("relationships_as_b", "character_a"),
    ):
        relationships = character.__dict__.get(attr_name)
        if not isinstance(relationships, list):
            continue
        for rel in relationships[:4]:
            counterpart = getattr(rel, counterpart_attr, None)
            counterpart_name = str(getattr(counterpart, "name", "") or "").strip() or "someone"
            description = str(getattr(rel, "description", "") or "").strip()
            rel_type = str(getattr(rel, "rel_type", "") or "connection").replace("_", " ").strip() or "connection"
            summaries.append(description or f"{rel_type.capitalize()} connection with {counterpart_name}.")

    cleaned = [summary for summary in summaries if summary]
    return "; ".join(cleaned[:4]) if cleaned else "no relationship evidence extracted yet"


async def chat_as_character(
    character: Character,
    book_title: str,
    current_chapter: int,
    context_summary: str,
    search_context: str,
    messages: list[dict],
) -> str:
    from app.engine.character.profile_builder import build_description

    trait_state = character.trait_state if isinstance(character.trait_state, dict) else {}
    system = CHAR_SYSTEM.format(
        name=character.name,
        title=book_title,
        personality=_join_values(character.personality_tags),
        motivations=_join_values(character.motivations),
        fears=_join_values(character.fears),
        arc_summary=character.arc_summary or "story ongoing",
        description=build_description(trait_state, character.archetype),
        relationships=_format_relationship_memory(character),
        growth_events=_format_growth_events(character.growth_events),
        chapter=current_chapter,
        context=("\n".join(filter(None, [context_summary or "", search_context or ""])))[:1300],
    )

    recent = messages[-10:]
    user_prompt = "\n".join(
        f"{str(message.get('role', 'user')).upper()}: {str(message.get('content', '')).strip()}"
        for message in recent
        if str(message.get("content", "")).strip()
    )

    reply = await complete_with_fallback(
        system=system,
        user=user_prompt or "USER: Say something in character.",
        openai_model=settings.OPENAI_INTEL_MODEL,
        gemini_model=None,
        temperature=0.7,
        max_tokens=220,
    )
    cleaned_reply = cast(str, reply).strip()
    if cleaned_reply:
        return cleaned_reply
    return "I don't know how to answer that just yet."
