from __future__ import annotations

from typing import Any, Sequence

from app.models.intelligence import CharacterRelationship, WorldElement


def build_relationship_drift_suggestions(
    relationship_rows: Sequence[CharacterRelationship],
    character_names: dict[Any, str],
) -> list[dict[str, Any]]:
    relationship_groups: dict[tuple[str, str], list[CharacterRelationship]] = {}
    for rel in relationship_rows:
        key = tuple(sorted([str(rel.character_a_id), str(rel.character_b_id)]))
        relationship_groups.setdefault(key, []).append(rel)

    suggestions: list[dict[str, Any]] = []
    for pair_key, rel_items in relationship_groups.items():
        if len(rel_items) < 2:
            continue
        first = rel_items[0]
        last = rel_items[-1]
        rel_names = (
            " / ".join(
                name
                for name in [
                    character_names.get(first.character_a_id),
                    character_names.get(first.character_b_id),
                ]
                if name
            )
            or "Character relationship"
        )
        type_changed = first.rel_type != last.rel_type
        sentiment_changed = (
            first.sentiment is not None
            and last.sentiment is not None
            and abs(first.sentiment - last.sentiment) >= 1.1
        )
        if not type_changed and not sentiment_changed:
            continue
        suggestions.append(
            {
                "id": f"relationship-{pair_key[0]}-{pair_key[1]}",
                "type": "relationship_flip",
                "severity": "warning" if type_changed else "info",
                "title": f"Relationship drift: {rel_names}",
                "description": (
                    f"This relationship shifts from {first.rel_type.replace('_', ' ')} in chapter {first.from_chapter} "
                    f"to {last.rel_type.replace('_', ' ')} in chapter {last.from_chapter}."
                    if type_changed
                    else f"The emotional tone around {rel_names} swings sharply between chapter {first.from_chapter} and chapter {last.from_chapter}."
                )
                + (f" {last.description}" if last.description else ""),
                "chapter_ref": last.from_chapter,
                "action_label": "Check the relationship arc",
                "ask_prompt": f"Is the shift in the {rel_names} relationship earned on page, or am I skipping a transition?",
                "source": "heuristic",
            }
        )
    return suggestions


def build_world_drift_suggestions(world_rows: Sequence[WorldElement]) -> list[dict[str, Any]]:
    world_groups: dict[tuple[str, str], list[WorldElement]] = {}
    for element in world_rows:
        group_key = (
            " ".join(str(element.element_type or "").split()).strip().lower(),
            " ".join(str(element.name or "").split()).strip().lower(),
        )
        world_groups.setdefault(group_key, []).append(element)

    suggestions: list[dict[str, Any]] = []
    for (element_type, element_name), items in world_groups.items():
        descriptions = [
            " ".join(str(item.description or "").split()).strip()
            for item in items
            if " ".join(str(item.description or "").split()).strip()
        ]
        normalized = list(dict.fromkeys(description.lower() for description in descriptions))
        if len(items) < 2 or len(normalized) < 2:
            continue
        if all(
            a in b or b in a for index, a in enumerate(normalized) for b in normalized[index + 1 :]
        ):
            continue
        if element_type in {"place", "location"}:
            issue_type = "location_conflict"
            title = f"Location details drift: {items[0].name}"
            prompt = f"Check the canon for {items[0].name}. Do these location details contradict each other?"
        elif element_type in {"item", "artifact", "object"}:
            issue_type = "object_continuity"
            title = f"Object continuity drift: {items[0].name}"
            prompt = f"Check the continuity of {items[0].name}. Am I describing or handling it inconsistently?"
        elif element_type in {"concept", "rule", "magic", "system"}:
            issue_type = "world_rule_conflict"
            title = f"World-rule conflict: {items[0].name}"
            prompt = f"Check the canon for {items[0].name}. Do my world rules now conflict?"
        else:
            continue
        suggestions.append(
            {
                "id": f"world-{issue_type}-{element_name}",
                "type": issue_type,
                "severity": "warning",
                "title": title,
                "description": (
                    f"Multiple canon descriptions for {items[0].name} now diverge across extracted world elements. "
                    f"Example one: {descriptions[0][:120]} Example two: {descriptions[1][:120]}"
                ),
                "chapter_ref": None,
                "action_label": "Reconcile the canon",
                "ask_prompt": prompt,
                "source": "heuristic",
            }
        )
    return suggestions
