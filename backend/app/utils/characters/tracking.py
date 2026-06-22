"""Focused character tracking helpers."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import CharacterRelationship
from app.utils.characters.presentation import dedupe_preserve_order


def build_character_arc_tracker(
    character: Character,
    *,
    states: list[CharacterState],
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
    voice_profile: CharacterVoiceProfile | None,
    total_chapters: int | None = None,
) -> dict[str, Any]:
    sorted_states = sorted(states, key=lambda row: row.at_chapter)
    raw_events = [event for event in (character.growth_events or []) if isinstance(event, dict)]
    raw_events.sort(
        key=lambda event: (
            _event_chapter(event, character.first_chapter),
            _clean_tracker_text(event.get("event_title") or event.get("event")) or "",
        )
    )

    turning_points: list[dict[str, Any]] = []
    arc_timeline: list[str] = []
    for event in raw_events:
        chapter_number = _event_chapter(event, character.first_chapter)
        if chapter_number <= 0:
            continue
        title = (
            _clean_tracker_text(event.get("event_title") or event.get("event"))
            or f"Shift in chapter {chapter_number}"
        )
        description = _clean_tracker_text(event.get("description") or event.get("impact"))
        turning_points.append(
            {
                "chapter_number": chapter_number,
                "title": title,
                "description": description,
                "impact_score": event.get("impact_score") or event.get("importance"),
                "growth_direction": _clean_tracker_text(
                    event.get("growth_direction") or event.get("tone")
                ),
                "is_major": bool(event.get("is_major", False)),
            }
        )
        arc_timeline.append(
            f"Chapter {chapter_number}: {title}" + (f" - {description}" if description else "")
        )

    relationship_changes = build_relationship_change_entries(
        character, relationships, counterpart_names
    )
    physical_history = build_physical_description_history(sorted_states)
    contradictions = build_character_contradictions(character, sorted_states, physical_history)
    voice_markers = _dominant_marker_lines(voice_profile)

    diagnostics: list[str] = []
    last_change_chapter = max(
        [character.first_chapter, *[item["chapter_number"] for item in turning_points]],
        default=character.first_chapter,
    )
    last_seen = character.last_seen_chapter or character.first_chapter
    if last_seen - last_change_chapter >= 14:
        diagnostics.append("Character has not changed meaningfully in 14 chapters.")

    previous_motivations: list[str] | None = None
    for state in sorted_states:
        current_motivations = [
            item for item in (state.motivations_snapshot or []) if _clean_tracker_text(item)
        ]
        if (
            previous_motivations
            and current_motivations
            and previous_motivations != current_motivations
        ):
            explained = any(
                abs(item["chapter_number"] - state.at_chapter) <= 1 for item in turning_points
            )
            if not explained:
                diagnostics.append("Motivation changed, but no scene explains why.")
                break
        if current_motivations:
            previous_motivations = current_motivations

    pair_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in relationship_changes:
        pair_history[item["counterpart_name"]].append(item)
    for counterpart_name, items in pair_history.items():
        ordered = sorted(items, key=lambda row: row["chapter_number"])
        for previous, current in zip(ordered, ordered[1:]):
            previous_negative = (previous.get("sentiment") or 0) <= -0.35 or str(
                previous.get("type") or ""
            ).lower() in {"enemy", "rival", "hostile"}
            current_positive = (current.get("sentiment") or 0) >= 0.35 or str(
                current.get("type") or ""
            ).lower() in {"ally", "friend", "romantic", "family", "mentor"}
            if (
                previous_negative
                and current_positive
                and (current["chapter_number"] - previous["chapter_number"]) <= 2
            ):
                diagnostics.append(
                    f"Relationship with {counterpart_name} shifts from hostile to trusting too abruptly."
                )
                break
        if diagnostics and diagnostics[-1].endswith("too abruptly."):
            break

    if (
        total_chapters
        and character.last_seen_chapter
        and total_chapters - character.last_seen_chapter >= 25
    ):
        diagnostics.append(
            f"Character is absent for {total_chapters - character.last_seen_chapter} chapters after the latest appearance."
        )

    latest_description = _clean_tracker_text(
        character.description if hasattr(character, "description") else None
    )
    return {
        "goal": _clean_tracker_text(getattr(character, "goal", None))
        or (character.motivations or [None])[0],
        "motivation": (character.motivations or [None])[0],
        "motivations": character.motivations or [],
        "fear": (character.fears or [None])[0],
        "fears": character.fears or [],
        "lie_they_believe": _clean_tracker_text(getattr(character, "lie_they_believe", None)),
        "wound_backstory": _clean_tracker_text(getattr(character, "backstory_wound", None)),
        "arc_type": _clean_tracker_text(
            getattr(character, "arc_type", None) or character.archetype
        ),
        "first_appearance": character.first_chapter,
        "major_turning_points": turning_points,
        "relationship_changes": relationship_changes,
        "contradictions": contradictions,
        "voice_markers": voice_markers,
        "physical_description_history": physical_history,
        "arc_timeline": arc_timeline,
        "diagnostics": dedupe_preserve_order(diagnostics),
        "latest_arc_note": _clean_tracker_text(sorted_states[-1].arc_note)
        if sorted_states
        else character.arc_summary,
        "summary": _clean_tracker_text(character.arc_summary) or latest_description,
    }


def _clean_tracker_text(value: object | None) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or None


def _event_chapter(event: dict[str, Any], fallback: int) -> int:
    raw = event.get("chapter_number") or event.get("chapter") or fallback
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return fallback


def _trait_value_for_history(raw: object) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("value")
        return _clean_tracker_text(value)
    return _clean_tracker_text(raw)


def _dominant_marker_lines(profile: CharacterVoiceProfile | None) -> list[str]:
    if profile is None:
        return []
    markers: list[str] = []
    for key, value in (profile.dominant_markers or {}).items():
        cleaned_key = _clean_tracker_text(key)
        cleaned_value = _clean_tracker_text(value)
        if cleaned_key and cleaned_value:
            markers.append(f"{cleaned_key.replace('_', ' ').title()}: {cleaned_value}")
        elif cleaned_key:
            markers.append(cleaned_key.replace("_", " ").title())
    for phrase in profile.signature_phrases or []:
        cleaned_phrase = _clean_tracker_text(phrase)
        if cleaned_phrase:
            markers.append(f'Signature phrase: "{cleaned_phrase}"')
    return dedupe_preserve_order(markers)


def _trait_label(trait_key: str) -> str:
    labels = {
        "hair": "Hair",
        "eyes": "Eyes",
        "build": "Build",
        "age": "Age",
        "face": "Face",
        "distinguishing": "Distinguishing details",
        "manual_description": "Description",
    }
    return labels.get(trait_key, trait_key.replace("_", " ").title())


def build_physical_description_history(states: list[CharacterState]) -> list[dict[str, Any]]:
    tracked_keys = ("hair", "eyes", "build", "age", "face", "distinguishing", "manual_description")
    history: list[dict[str, Any]] = []
    previous_values: dict[str, str] = {}
    for state in sorted(states, key=lambda row: row.at_chapter):
        snapshot = state.trait_snapshot or {}
        for trait_key in tracked_keys:
            current_value = _trait_value_for_history(snapshot.get(trait_key))
            if not current_value:
                continue
            if previous_values.get(trait_key, "").casefold() == current_value.casefold():
                continue
            history.append(
                {
                    "chapter_number": state.at_chapter,
                    "trait": trait_key,
                    "label": _trait_label(trait_key),
                    "value": current_value,
                    "previous_value": previous_values.get(trait_key),
                }
            )
            previous_values[trait_key] = current_value
    return history


def build_relationship_change_entries(
    character: Character,
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in sorted(
        relationships,
        key=lambda item: (item.from_chapter or 0, item.to_chapter or 10**6, str(item.id)),
    ):
        counterpart_id = (
            rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        )
        rows.append(
            {
                "counterpart_id": str(counterpart_id),
                "counterpart_name": counterpart_names.get(counterpart_id, "Unknown character"),
                "chapter_number": rel.from_chapter or character.first_chapter,
                "to_chapter": rel.to_chapter,
                "type": rel.rel_type or "connection",
                "sentiment": rel.sentiment,
                "description": _clean_tracker_text(rel.description),
            }
        )
    return rows


def build_character_contradictions(
    character: Character,
    states: list[CharacterState],
    physical_history: list[dict[str, Any]],
) -> list[str]:
    contradictions: list[str] = []
    for item in physical_history:
        previous_value = _clean_tracker_text(item.get("previous_value"))
        current_value = _clean_tracker_text(item.get("value"))
        label = _clean_tracker_text(item.get("label"))
        chapter_number = item.get("chapter_number")
        if previous_value and current_value and label:
            contradictions.append(
                f"{label} shifts from {previous_value} to {current_value} by chapter {chapter_number}."
            )

    previous_motivations: list[str] | None = None
    previous_fears: list[str] | None = None
    for state in sorted(states, key=lambda row: row.at_chapter):
        current_motivations = [
            item for item in (state.motivations_snapshot or []) if _clean_tracker_text(item)
        ]
        current_fears = [item for item in (state.fears_snapshot or []) if _clean_tracker_text(item)]
        if (
            previous_motivations
            and current_motivations
            and previous_motivations != current_motivations
        ):
            contradictions.append(
                f"Motivation profile changes by chapter {state.at_chapter}: {', '.join(previous_motivations[:2])} -> {', '.join(current_motivations[:2])}."
            )
        if previous_fears and current_fears and previous_fears != current_fears:
            contradictions.append(
                f"Fear profile changes by chapter {state.at_chapter}: {', '.join(previous_fears[:2])} -> {', '.join(current_fears[:2])}."
            )
        if current_motivations:
            previous_motivations = current_motivations
        if current_fears:
            previous_fears = current_fears
    return dedupe_preserve_order(contradictions)[:10]
