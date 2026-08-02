"""
Chapter summary generation - 3 modes.
Generated once, cached in Redis + stored in DB forever.
"""

import json
import re
import uuid
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.llm import complete_with_fallback

PROMPTS = {
    "short": (
        "Summarise this chapter in 3-4 sentences. Key events only. "
        "No spoilers beyond what is shown. Be concise and factual."
    ),
    "detailed": """Analyse this chapter and return JSON only:
{
  "summary": "4-6 paragraph summary with concrete detail and cause-effect continuity",
  "key_events": [{
    "event_title": "...",
    "description": "...",
    "importance": 1-10,
    "impact": "...",
    "involved_characters": ["Character Name"],
    "event_type": "plot_twist|climax|resolution|setup",
    "continuity_facts": [{
      "subject": "specific character, object, relationship, or world rule",
      "subject_type": "character|object|relationship|world_rule",
      "predicate": "character.location|character.age|character.injury|character.ability|character.possession|knowledge.acquired|knowledge.used|object.state|object.owner|object.location|object.properties|relationship.type|world.rule",
      "value": "one precise canonical fact",
      "fact_key": "short stable wording reused for the same knowledge fact",
      "evidence": "short exact excerpt from this chapter",
      "has_transition_evidence": false,
      "perspective": "narrator or viewpoint character, if relevant",
      "unreliable_narration": false
    }]
  }],
  "char_changes": [{
    "character": "...",
    "change": "...",
    "evidence": "...",
    "event_title": "...",
    "description": "...",
    "impact_score": 1-10,
    "role": "protagonist|supporting|antagonist|ally",
    "accomplishments": ["..."],
    "growth_direction": "positive|negative|neutral",
    "growth_magnitude": 1-10,
    "is_major": true
  }],
  "clues": [{"clue": "...", "foreshadows": "...", "why_it_matters": "..."}],
  "themes": [{"theme": "...", "signal": "explicit|subtext", "evidence": "...", "depth": "surface|complex"}],
  "open_questions": ["..."]
}
Rules:
- Return raw JSON only. No markdown fences.
- Use concrete names, motivations, and turning points from the text.
- The summary should feel rich enough for a reader who forgot the chapter, not like a compressed blurb.
- Preserve chronology and explain why the chapter matters.
- Add continuity_facts only for facts explicitly stated or used in this chapter.
- For knowledge.used, record a fact only when the character acts on, states, or relies on it.
- Reuse the same short fact_key for semantically identical knowledge facts.
- Mark has_transition_evidence when the passage explicitly explains a change, transfer, injury, recovery, disguise, transformation, travel, or relationship shift.
- Mark unreliable_narration when the passage itself signals an unreliable, mistaken, deceptive, dream, or disguised viewpoint.
- Evidence must be a short exact excerpt, never a paraphrase.
- Include both obvious and philosophical themes when grounded in the text, such as false altruism, self-hatred, moral injury, denial, obsession, unreliable narration, or identity fracture.
- If there are no character changes or clues, return empty arrays.
- Do not include any text before or after the JSON.""",
    "key_points": (
        "List exactly 5 key things that happen in this chapter. "
        "Numbered. One sentence each. Most important first."
    ),
}


async def generate_summary(
    chapter_text: str,
    mode: str,
    title: str = "",
    *,
    openai_client: AsyncOpenAI | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
) -> dict:
    system = f"You are analysing chapter: {title}. " + PROMPTS[mode]
    passages = _analysis_passages(chapter_text, max_chars=8500)
    payloads: list[dict[str, Any]] = []
    plain_results: list[str] = []
    for part_index, passage in enumerate(passages, start=1):
        part_system = system
        if len(passages) > 1:
            part_system = (
                f"{system}\nThis is part {part_index} of {len(passages)}. "
                "Only report evidence contained in this part and preserve its local chronology."
            )
        usage_metadata: dict[str, Any] = {"chapter_title": title[:160]}
        if len(passages) > 1:
            usage_metadata.update({"part_index": part_index, "part_count": len(passages)})
        content = await complete_with_fallback(
            system=part_system,
            user=passage,
            openai_model=settings.OPENAI_EXTRACT_MODEL,
            gemini_model=settings.GEMINI_EXTRACT_MODEL,
            temperature=0.2,
            max_tokens=2200,
            response_format={"type": "json_object"} if mode == "detailed" else None,
            openai_client=openai_client,
            usage_feature=f"chapter_summary_{mode}",
            usage_user_id=user_id,
            usage_book_id=book_id,
            usage_metadata=usage_metadata,
        )
        if mode == "detailed":
            try:
                data = json.loads(_strip_json_fence(content))
                payloads.append(_normalize_summary_payload(data, fallback=content))
                continue
            except json.JSONDecodeError:
                pass
        plain_results.append(content)

    if mode == "detailed" and payloads:
        return _merge_detailed_summary_payloads(payloads)
    content = "\n\n".join(plain_results).strip()
    return {
        "content": content,
        "key_events": None,
        "char_changes": None,
        "clues": None,
        "themes": None,
    }


def _analysis_passages(text: str, *, max_chars: int) -> list[str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return [""]
    if len(cleaned) <= max_chars:
        return [cleaned]

    passages: list[str] = []
    current: list[str] = []
    current_length = 0
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()]
    for paragraph in paragraphs:
        pieces = (
            [paragraph]
            if len(paragraph) <= max_chars
            else [
                paragraph[index : index + max_chars]
                for index in range(0, len(paragraph), max_chars)
            ]
        )
        for piece in pieces:
            projected = current_length + len(piece) + (2 if current else 0)
            if current and projected > max_chars:
                passages.append("\n\n".join(current))
                current = []
                current_length = 0
            current.append(piece)
            current_length += len(piece) + (2 if current_length else 0)
    if current:
        passages.append("\n\n".join(current))
    return passages or [cleaned]


def _merge_detailed_summary_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    def unique_dicts(items: list[dict[str, Any]], *keys: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for item in items:
            identity = "|".join(
                " ".join(str(item.get(key) or "").split()).strip().casefold() for key in keys
            )
            if not identity or identity in seen:
                continue
            seen.add(identity)
            result.append(item)
        return result

    contents = [
        " ".join(str(payload.get("content") or "").split()).strip()
        for payload in payloads
        if str(payload.get("content") or "").strip()
    ]
    return {
        "content": "\n\n".join(contents),
        "key_events": unique_dicts(
            [
                item
                for payload in payloads
                for item in (payload.get("key_events") or [])
                if isinstance(item, dict)
            ],
            "event_title",
            "description",
        ),
        "char_changes": unique_dicts(
            [
                item
                for payload in payloads
                for item in (payload.get("char_changes") or [])
                if isinstance(item, dict)
            ],
            "character",
            "change",
        ),
        "clues": unique_dicts(
            [
                item
                for payload in payloads
                for item in (payload.get("clues") or [])
                if isinstance(item, dict)
            ],
            "clue",
            "why_it_matters",
        ),
        "themes": unique_dicts(
            [
                item
                for payload in payloads
                for item in (payload.get("themes") or [])
                if isinstance(item, dict)
            ],
            "theme",
            "evidence",
        ),
    }


def derive_summary_modes_from_detailed(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    detailed_content = " ".join(str(payload.get("content") or "").split()).strip()
    key_events = [item for item in (payload.get("key_events") or []) if isinstance(item, dict)]

    short_sentences = _split_sentences(detailed_content)[:3]
    short_content = " ".join(short_sentences).strip() or detailed_content

    key_points: list[str] = []
    for index, item in enumerate(key_events[:5], start=1):
        title = " ".join(str(item.get("event_title") or item.get("event") or "").split()).strip()
        description = " ".join(
            str(item.get("description") or item.get("impact") or "").split()
        ).strip()
        sentence = description or title
        if title and description and not description.lower().startswith(title.lower()):
            sentence = f"{title}: {description}"
        cleaned_sentence = sentence.rstrip(". ")
        if cleaned_sentence:
            key_points.append(f"{index}. {cleaned_sentence}.")

    if not key_points:
        fallback_sentences = _split_sentences(detailed_content)[:5]
        key_points = [
            f"{index}. {sentence.rstrip('. ')}."
            for index, sentence in enumerate(fallback_sentences, start=1)
            if sentence
        ]

    return {
        "short": {
            "content": short_content,
            "key_events": None,
            "char_changes": None,
            "clues": None,
            "themes": None,
        },
        "key_points": {
            "content": "\n".join(key_points).strip(),
            "key_events": None,
            "char_changes": None,
            "clues": None,
            "themes": None,
        },
    }


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
    key_events = []
    for item in data.get("key_events") or []:
        if isinstance(item, dict):
            key_events.append(
                {
                    "event_title": item.get("event_title") or item.get("event") or "",
                    "event": item.get("event") or item.get("event_title") or "",
                    "description": item.get("description") or item.get("impact") or "",
                    "importance": item.get("importance") or 5,
                    "impact": item.get("impact") or item.get("description") or "",
                    "involved_characters": item.get("involved_characters") or [],
                    "event_type": item.get("event_type"),
                    "continuity_facts": _normalize_continuity_facts(item.get("continuity_facts")),
                }
            )
        elif isinstance(item, str) and item.strip():
            key_events.append(
                {
                    "event_title": item.strip(),
                    "event": item.strip(),
                    "description": "",
                    "importance": 5,
                    "impact": "",
                    "involved_characters": [],
                    "continuity_facts": [],
                }
            )

    char_changes = []
    for item in data.get("char_changes") or []:
        if not isinstance(item, dict):
            continue
        char_changes.append(
            {
                "character": item.get("character") or "",
                "change": item.get("change") or item.get("description") or "",
                "evidence": item.get("evidence") or "",
                "event_title": item.get("event_title") or item.get("change") or "",
                "description": item.get("description") or item.get("change") or "",
                "impact_score": item.get("impact_score") or 5,
                "role": item.get("role"),
                "accomplishments": item.get("accomplishments") or [],
                "growth_direction": item.get("growth_direction") or "neutral",
                "growth_magnitude": item.get("growth_magnitude") or item.get("impact_score") or 5,
                "is_major": bool(item.get("is_major", False)),
            }
        )
    return {
        "content": data.get("summary", fallback),
        "key_events": key_events,
        "char_changes": char_changes,
        "clues": data.get("clues") or [],
        "themes": data.get("themes") or [],
    }


def _normalize_continuity_facts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    facts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        subject = " ".join(str(item.get("subject") or "").split()).strip()
        predicate = " ".join(str(item.get("predicate") or "").split()).strip().casefold()
        fact_value = " ".join(str(item.get("value") or "").split()).strip()
        evidence = " ".join(str(item.get("evidence") or "").split()).strip()
        if not subject or not predicate or not fact_value or not evidence:
            continue
        facts.append(
            {
                "subject": subject,
                "subject_type": " ".join(str(item.get("subject_type") or "").split())
                .strip()
                .casefold(),
                "predicate": predicate,
                "value": fact_value,
                "fact_key": " ".join(str(item.get("fact_key") or "").split()).strip(),
                "evidence": evidence[:600],
                "has_transition_evidence": bool(item.get("has_transition_evidence")),
                "perspective": " ".join(str(item.get("perspective") or "").split()).strip(),
                "unreliable_narration": bool(item.get("unreliable_narration")),
            }
        )
    return facts


def _split_sentences(content: str) -> list[str]:
    if not content:
        return []
    segments = [
        segment.strip() for segment in re.split(r"(?<=[.!?])\s+", content) if segment.strip()
    ]
    return segments
