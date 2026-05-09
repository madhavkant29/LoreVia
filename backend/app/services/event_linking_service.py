from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Chapter
from app.models.character import Character


def _clean_name(value: str | None) -> str:
    return " ".join((value or "").split()).strip().lower()


def _normalize_major_event(raw_event: dict, *, chapter_number: int, character_ids: list[str], character_names: list[str]) -> dict:
    title = " ".join(str(raw_event.get("event_title") or raw_event.get("event") or "").split()).strip()
    description = " ".join(str(raw_event.get("description") or raw_event.get("impact") or "").split()).strip()
    importance_raw = raw_event.get("importance")
    if isinstance(importance_raw, int):
        importance = importance_raw
    else:
        try:
            importance = int(importance_raw if importance_raw is not None else 5)
        except Exception:
            importance = 5
    return {
        "chapter_number": chapter_number,
        "event_title": title or f"Chapter {chapter_number} event",
        "description": description or "",
        "importance": max(1, min(importance, 10)),
        "involved_characters": character_ids,
        "involved_character_names": character_names,
        "event_type": raw_event.get("event_type"),
    }


def _normalize_character_event(raw_event: dict, *, chapter_number: int, character: Character) -> dict:
    title = " ".join(str(raw_event.get("event_title") or raw_event.get("event") or "").split()).strip()
    description = " ".join(str(raw_event.get("description") or raw_event.get("impact") or "").split()).strip()
    impact_score = raw_event.get("impact_score", raw_event.get("importance", 5))
    try:
        impact_score = int(impact_score)
    except Exception:
        impact_score = 5
    growth_magnitude = raw_event.get("growth_magnitude", impact_score)
    try:
        growth_magnitude = int(growth_magnitude)
    except Exception:
        growth_magnitude = impact_score
    return {
        "chapter_number": chapter_number,
        "event_title": title or f"Chapter {chapter_number} event",
        "description": description or "",
        "impact_score": max(1, min(impact_score, 10)),
        "role": raw_event.get("role") or character.role,
        "accomplishments": [str(item).strip() for item in (raw_event.get("accomplishments") or []) if str(item).strip()],
        "growth_direction": str(raw_event.get("growth_direction") or "neutral"),
        "growth_magnitude": max(0, min(growth_magnitude, 10)),
        "is_major": bool(raw_event.get("is_major", impact_score >= 7)),
    }


async def link_summary_events(
    db: AsyncSession,
    *,
    chapter: Chapter,
    key_events: list[dict] | None,
    char_changes: list[dict] | None,
) -> dict[str, list[dict]]:
    character_rows = (
        await db.execute(select(Character).where(Character.book_id == chapter.book_id))
    ).scalars().all()
    by_lookup: dict[str, Character] = {}
    for character in character_rows:
        by_lookup[_clean_name(character.name)] = character
        for alias in character.aliases or []:
            alias_key = _clean_name(alias)
            if alias_key:
                by_lookup.setdefault(alias_key, character)

    linked_major_events: list[dict] = []
    updated_character_events: list[dict] = []

    for raw_event in key_events or []:
        if not isinstance(raw_event, dict):
            continue
        involved = raw_event.get("involved_characters") or []
        matched_characters: list[Character] = []
        for item in involved:
            candidate = by_lookup.get(_clean_name(str(item)))
            if candidate and candidate not in matched_characters:
                matched_characters.append(candidate)

        major_event = _normalize_major_event(
            raw_event,
            chapter_number=chapter.number,
            character_ids=[str(character.id) for character in matched_characters],
            character_names=[character.name for character in matched_characters],
        )
        linked_major_events.append(major_event)

        for character in matched_characters:
            event_payload = _normalize_character_event(raw_event, chapter_number=chapter.number, character=character)
            _append_unique_character_event(character, event_payload)
            updated_character_events.append(
                {
                    "character_id": str(character.id),
                    "character_name": character.name,
                    **event_payload,
                }
            )

    for raw_change in char_changes or []:
        if not isinstance(raw_change, dict):
            continue
        character = by_lookup.get(_clean_name(str(raw_change.get("character"))))
        if character is None:
            continue
        event_payload = _normalize_character_event(
            {
                "event_title": raw_change.get("event_title") or raw_change.get("change") or f"{character.name} changes",
                "description": raw_change.get("description") or raw_change.get("change") or raw_change.get("evidence") or "",
                "impact_score": raw_change.get("impact_score") or 5,
                "role": raw_change.get("role") or character.role,
                "growth_direction": raw_change.get("growth_direction") or "neutral",
                "growth_magnitude": raw_change.get("growth_magnitude") or 5,
                "accomplishments": raw_change.get("accomplishments") or [],
                "is_major": raw_change.get("is_major", False),
            },
            chapter_number=chapter.number,
            character=character,
        )
        _append_unique_character_event(character, event_payload)
        updated_character_events.append(
            {
                "character_id": str(character.id),
                "character_name": character.name,
                **event_payload,
            }
        )

    return {"major_events": linked_major_events, "character_events": updated_character_events}


def _append_unique_character_event(character: Character, event_payload: dict) -> None:
    events = list(character.growth_events or [])
    identity = (
        int(event_payload.get("chapter_number") or 0),
        _clean_name(str(event_payload.get("event_title") or "")),
    )
    for existing in events:
        if not isinstance(existing, dict):
            continue
        existing_identity = (
            int(existing.get("chapter_number") or 0),
            _clean_name(str(existing.get("event_title") or existing.get("event") or "")),
        )
        if existing_identity == identity:
            existing.update(event_payload)
            character.growth_events = events
            return
    events.append(event_payload)
    events.sort(key=lambda item: (int(item.get("chapter_number") or 0), str(item.get("event_title") or "").lower()))
    character.growth_events = events
