"""
Character utility helpers â€” shared across route modules.
Covers display filtering, status derivation, relationship summaries,
and text-sanitization helpers used on character data.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import inspect

from app.models.character import (
    Character,
    CharacterAlias,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.intelligence import (
    CharacterRelationship,
)
from app.utils.characters.candidates import build_character_analysis_payload
from app.utils.characters.constants import CHARACTER_APPROVAL_PROTECTED
from app.utils.characters.governance import character_governance, character_status
from app.utils.characters.graph import get_graph_visibility_override
from app.utils.characters.presentation import compose_character_description, dedupe_preserve_order
from app.utils.characters.text import clean_optional_text, clean_string_list
from app.utils.characters.tracking import build_character_arc_tracker


def is_protected_character(char: Character | None) -> bool:
    if char is None:
        return False
    _visibility_state, approval_state, _approval_source, _reason_codes = character_governance(char)
    if approval_state == CHARACTER_APPROVAL_PROTECTED:
        return True
    metadata = dict(getattr(char, "analysis_metadata", None) or {})
    return bool(getattr(char, "is_manual", False) or metadata.get("protected_from_repair"))


def serialize_character_alias_record(alias: CharacterAlias) -> dict[str, Any]:
    return {
        "id": str(alias.id),
        "book_id": str(alias.book_id),
        "character_id": str(alias.character_id),
        "alias_text": alias.alias_text,
        "normalized_alias": alias.normalized_alias,
        "alias_kind": alias.alias_kind,
        "source": alias.source,
        "confidence": float(alias.confidence or 0.0),
        "created_at": alias.created_at,
    }


def serialize_character_alias_records(char: Character) -> list[dict[str, Any]]:
    try:
        if "alias_records" in inspect(char).unloaded:
            return []
    except Exception:
        return []
    records = getattr(char, "alias_records", None) or []
    return [
        serialize_character_alias_record(alias)
        for alias in sorted(
            records,
            key=lambda item: (str(item.alias_kind or ""), str(item.alias_text or "").casefold()),
        )
    ]


def serialize_character_detail(
    char: Character, *, skip_analysis_metadata: bool = False
) -> dict[str, Any]:
    visibility_state, approval_state, approval_source, approval_reason_codes = character_governance(
        char
    )
    return {
        "id": char.id,
        "book_id": char.book_id,
        "name": char.name,
        "aliases": getattr(char, "aliases", None) or [],
        "alias_records": serialize_character_alias_records(char),
        "role": getattr(char, "role", None),
        "first_chapter": getattr(char, "first_chapter", 0),
        "trait_state": getattr(char, "trait_state", None) or {},
        "hair": getattr(char, "hair", None),
        "eyes": getattr(char, "eyes", None),
        "build": getattr(char, "build", None),
        "age_descriptor": getattr(char, "age_descriptor", None),
        "distinguishing": getattr(char, "distinguishing", None),
        "personality_tags": getattr(char, "personality_tags", None) or [],
        "motivations": getattr(char, "motivations", None) or [],
        "fears": getattr(char, "fears", None) or [],
        "archetype": getattr(char, "archetype", None),
        "arc_summary": getattr(char, "arc_summary", None),
        "last_seen_chapter": getattr(char, "last_seen_chapter", None),
        "mention_count": getattr(char, "mention_count", None) or 0,
        "growth_events": getattr(char, "growth_events", None) or [],
        "character_type": getattr(char, "character_type", None),
        "character_type_score": getattr(char, "character_type_score", None),
        "subtype_scores": getattr(char, "subtype_scores", None) or {},
        "analysis_metadata": None
        if skip_analysis_metadata
        else build_character_analysis_payload(char),
        "visibility_state": visibility_state,
        "approval_state": approval_state,
        "approval_source": approval_source,
        "approval_reason_codes": approval_reason_codes,
        "approval_updated_at": getattr(char, "approval_updated_at", None),
        "is_manual": getattr(char, "is_manual", False),
        "created_at": getattr(char, "created_at"),
    }


def serialize_book_character(
    char: Character,
    *,
    rel_summaries: dict[str, list[str]],
    states: list[CharacterState],
    relationships: list[CharacterRelationship],
    counterpart_names: dict[uuid.UUID, str],
    voice_profile: CharacterVoiceProfile | None,
    total_chapters: int | None,
    tags: list[str] | None = None,
    skip_arc_tracker: bool = False,
    skip_analysis_metadata: bool = False,
    skip_tags: bool = False,
) -> dict[str, Any]:
    relationship_summaries = dedupe_preserve_order(rel_summaries.get(str(char.id), []))
    visibility_state, approval_state, approval_source, approval_reason_codes = character_governance(
        char
    )
    result: dict[str, Any] = {
        "id": str(char.id),
        "book_id": str(char.book_id),
        "name": char.name,
        "aliases": char.aliases or [],
        "alias_records": serialize_character_alias_records(char),
        "role": char.role,
        "first_chapter": char.first_chapter,
        "last_seen_chapter": char.last_seen_chapter,
        "mention_count": char.mention_count or 0,
        "status": character_status(char),
        "trait_state": char.trait_state or {},
        "hair": char.hair,
        "eyes": char.eyes,
        "build": char.build,
        "age_descriptor": char.age_descriptor,
        "distinguishing": char.distinguishing,
        "description": compose_character_description(
            trait_state=char.trait_state or {},
            archetype=char.archetype,
            arc_summary=char.arc_summary,
            personality_tags=char.personality_tags or [],
            motivations=char.motivations or [],
            relationship_summaries=relationship_summaries,
        ),
        "personality_tags": char.personality_tags or [],
        "goal": char.goal,
        "motivations": char.motivations or [],
        "fears": char.fears or [],
        "lie_they_believe": char.lie_they_believe,
        "backstory_wound": char.backstory_wound,
        "arc_type": char.arc_type,
        "archetype": char.archetype,
        "arc_summary": char.arc_summary,
        "growth_events": char.growth_events or [],
        "relationship_summaries": relationship_summaries,
        "character_type": char.character_type,
        "character_type_score": char.character_type_score,
        "subtype_scores": char.subtype_scores or {},
        "visibility_state": visibility_state,
        "approval_state": approval_state,
        "approval_source": approval_source,
        "approval_reason_codes": approval_reason_codes,
        "approval_updated_at": getattr(char, "approval_updated_at", None),
        "is_manual": getattr(char, "is_manual", False),
        "graph_visibility_override": get_graph_visibility_override(char),
    }
    if skip_analysis_metadata:
        result["analysis_metadata"] = None
    else:
        result["analysis_metadata"] = build_character_analysis_payload(char)
    result["tags"] = [] if skip_tags else (tags or [])
    if skip_arc_tracker:
        result["arc_tracker"] = None
    else:
        result["arc_tracker"] = build_character_arc_tracker(
            char,
            states=states,
            relationships=relationships,
            counterpart_names=counterpart_names,
            voice_profile=voice_profile,
            total_chapters=total_chapters,
        )
    return result


def serialize_reader_character(
    char: Character,
    *,
    trait_snapshot: dict[str, Any] | None = None,
    relationship_summaries: list[str] | None = None,
) -> dict[str, Any]:
    resolved_traits = dict(cast(dict[str, Any], trait_snapshot or char.trait_state or {}))
    visibility_state, approval_state, approval_source, approval_reason_codes = character_governance(
        char
    )
    return {
        "id": str(char.id),
        "name": char.name,
        "aliases": char.aliases or [],
        "alias_records": serialize_character_alias_records(char),
        "role": char.role,
        "first_chapter": char.first_chapter,
        "last_seen_chapter": char.last_seen_chapter,
        "status": character_status(char),
        "description": compose_character_description(
            trait_state=resolved_traits,
            archetype=char.archetype,
            arc_summary=char.arc_summary,
            personality_tags=char.personality_tags or [],
            motivations=char.motivations or [],
            relationship_summaries=relationship_summaries or [],
        ),
        "trait_state": resolved_traits,
        "personality_tags": char.personality_tags or [],
        "motivations": char.motivations or [],
        "fears": char.fears or [],
        "archetype": char.archetype,
        "arc_summary": char.arc_summary,
        "mention_count": char.mention_count or 0,
        "is_manual": getattr(char, "is_manual", False),
        "analysis_metadata": build_character_analysis_payload(char),
        "visibility_state": visibility_state,
        "approval_state": approval_state,
        "approval_source": approval_source,
        "approval_reason_codes": approval_reason_codes,
        "approval_updated_at": getattr(char, "approval_updated_at", None),
        "goal": char.goal,
        "lie_they_believe": char.lie_they_believe,
        "backstory_wound": char.backstory_wound,
        "arc_type": char.arc_type,
        "growth_events": char.growth_events or [],
        "graph_visibility_override": get_graph_visibility_override(char),
        "relationship_summaries": clean_string_list(relationship_summaries or []),
    }


def build_character_roster_snapshot(characters: Sequence[Character]) -> list[dict[str, Any]]:
    roster: list[dict[str, Any]] = []
    for character in characters:
        roster.append(
            {
                "id": str(character.id),
                "name": character.name,
                "aliases": clean_string_list(character.aliases or []),
                "role": character.role,
                "summary": clean_optional_text(
                    compose_character_description(
                        trait_state=character.trait_state or {},
                        archetype=character.archetype,
                        arc_summary=character.arc_summary,
                        personality_tags=character.personality_tags or [],
                        motivations=character.motivations or [],
                    )
                ),
                "is_manual": bool(getattr(character, "is_manual", False)),
            }
        )
    return roster
