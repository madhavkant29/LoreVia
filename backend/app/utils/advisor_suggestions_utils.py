from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Any

from app.models.intelligence import CharacterRelationship, PlotThread, WorldElement
from app.utils.characters.relationship_evidence import relationship_quote_anchors_participants


def proactive_advisor_finding_id(finding: dict[str, Any]) -> str:
    """Keep a supported check stable across evidence-group and wording changes."""
    evidence = " ".join(str(finding.get("evidence_excerpt") or "").split()).casefold()
    if not evidence:
        raise ValueError("advisor_finding_missing_evidence")
    finding_type = str(finding.get("type") or "").strip().casefold()
    chapter = finding.get("chapter_ref")
    chapter_key = str(chapter) if isinstance(chapter, int) and not isinstance(chapter, bool) else ""
    identity = f"{finding_type}\x1f{chapter_key}\x1f{evidence}"
    return f"proactive-{hashlib.sha256(identity.encode()).hexdigest()[:24]}"


def advisor_clue_evidence(clues: object) -> list[str]:
    """Keep the structured clue and payoff context from detailed summaries."""
    if isinstance(clues, list):
        values = clues
    elif isinstance(clues, dict):
        values = (
            [clues]
            if "clue" in clues
            else [
                {"clue": key, **(value if isinstance(value, dict) else {"why_it_matters": value})}
                for key, value in clues.items()
            ]
        )
    else:
        return []
    evidence: list[str] = []
    for item in values:
        if isinstance(item, str):
            line = item.strip()
        elif isinstance(item, dict):
            if not isinstance(item.get("clue"), str) or not item["clue"].strip():
                continue
            line = " | ".join(
                value.strip()
                for field in ("clue", "foreshadows", "why_it_matters")
                if isinstance(value := item.get(field), str) and value.strip()
            )
        else:
            continue
        if line:
            evidence.append(line)
    return evidence


def build_advisor_chapter_evidence_blocks(
    *,
    chapter_number: int,
    chapter_title: str | None,
    content: str | None,
    key_events: object,
    clues: object = None,
    max_chars: int = 850,
    overlap: int = 100,
) -> list[str]:
    """Keep every summary detail in bounded blocks with a source chapter label."""
    if max_chars < 1 or overlap < 0 or overlap >= max_chars:
        raise ValueError("invalid_advisor_summary_section_size")
    event_lines: list[str] = []
    if isinstance(key_events, list):
        for event in key_events:
            if isinstance(event, str):
                if event.strip():
                    event_lines.append(event.strip())
                continue
            if not isinstance(event, dict):
                continue
            details = list(
                dict.fromkeys(
                    value
                    for value in (
                        str(event.get("event_title") or event.get("event") or "").strip(),
                        str(event.get("description") or "").strip(),
                        str(event.get("impact") or "").strip(),
                    )
                    if value
                )
            )
            characters = event.get("involved_characters")
            if isinstance(characters, list):
                names = ", ".join(str(name).strip() for name in characters if str(name).strip())
                if names:
                    details.append(f"Involved: {names}")
            facts = event.get("continuity_facts")
            if isinstance(facts, list):
                for fact in facts:
                    if not isinstance(fact, dict):
                        continue
                    statement = " ".join(
                        str(fact.get(field) or "").strip()
                        for field in ("subject", "predicate", "value")
                    ).strip()
                    evidence = str(fact.get("evidence") or "").strip()
                    if statement or evidence:
                        details.append(
                            "Continuity fact: "
                            + statement
                            + (f" (evidence: {evidence})" if evidence else "")
                        )
            if details:
                event_lines.append(" | ".join(details))
    summary = str(content or "").strip()
    body = summary + ("\nKey events:\n" + "\n".join(event_lines) if event_lines else "")
    clue_lines = advisor_clue_evidence(clues)
    if clue_lines:
        body += "\nClues:\n" + "\n".join(clue_lines)
    if not body:
        return []
    prefix = f"Chapter {chapter_number} ({chapter_title or 'Untitled'}): "
    blocks: list[str] = []
    start = 0
    while start < len(body):
        end = min(start + max_chars, len(body))
        if end < len(body):
            boundary = body.rfind(" ", start + max_chars // 2, end)
            if boundary > start + overlap:
                end = boundary + 1
        blocks.append(prefix + body[start:end])
        if end == len(body):
            break
        start = end - overlap
    return blocks


def build_advisor_item_evidence_blocks(
    prefix: str,
    detail: str | None,
    *,
    separator: str = ". ",
    max_chars: int = 600,
    overlap: int = 80,
) -> list[str]:
    """Preserve an entire structured item while repeating its source label on each block."""
    if max_chars < 1 or overlap < 0 or overlap >= max_chars:
        raise ValueError("invalid_advisor_item_section_size")
    header = prefix.strip()
    if not header:
        return []
    body = str(detail or "").strip()
    if not body:
        return [header]
    blocks: list[str] = []
    start = 0
    while start < len(body):
        end = min(start + max_chars, len(body))
        if end < len(body):
            boundary = body.rfind(" ", start + max_chars // 2, end)
            if boundary > start + overlap:
                end = boundary + 1
        blocks.append(header + separator + body[start:end])
        if end == len(body):
            break
        start = end - overlap
    return blocks


def partition_advisor_scan_evidence(
    *,
    summaries: Sequence[str],
    threads: Sequence[str],
    relationships: Sequence[str],
    world_elements: Sequence[str],
) -> list[dict[str, list[str]]]:
    """Scan every item in bounded groups with adjacent and chapter-matched context."""
    categories = {
        "summaries": (summaries, 4),
        "threads": (threads, 8),
        "relationships": (relationships, 5),
        "world_elements": (world_elements, 6),
    }
    group_count = max((len(items) + size - 1) // size for items, size in categories.values())
    summaries_by_chapter: dict[int, list[str]] = {}
    for block in summaries:
        match = re.match(r"Chapter\s+(\d+)\b", block, flags=re.IGNORECASE)
        if match:
            summaries_by_chapter.setdefault(int(match.group(1)), []).append(block)
    groups: list[dict[str, list[str]]] = []
    for index in range(group_count):
        group: dict[str, list[str]] = {}
        for name, (items, size) in categories.items():
            current = list(items[index * size : (index + 1) * size])
            if current and index > 0:
                # The last item of the previous group lets the audit compare
                # evidence that straddles a bounded group boundary.
                current.insert(0, items[index * size - 1])
            if name == "summaries" and not current and summaries:
                related = [
                    *threads[index * 8 : (index + 1) * 8],
                    *relationships[index * 5 : (index + 1) * 5],
                ]
                chapter_refs = dict.fromkeys(
                    int(match.group(1))
                    for block in related
                    if (
                        match := re.search(
                            r"\b(?:introduced\s+ch\.|at\s+chapter\s+)(\d+)\b",
                            block,
                            flags=re.IGNORECASE,
                        )
                    )
                )
                for chapter_ref in chapter_refs:
                    matching = summaries_by_chapter.get(chapter_ref, [])
                    if matching:
                        current.append(matching[index % len(matching)])
                    if len(current) == 4:
                        break
                if not current:
                    current.append(summaries[index % len(summaries)])
            group[name] = current
        groups.append(group)
    return groups


def advisor_scan_output_token_budget(source_block_count: int) -> int:
    """Leave room for multiple source-backed findings without unbounded output."""
    if source_block_count < 0:
        raise ValueError("invalid_advisor_source_block_count")
    return min(8192, max(2048, 1024 + 256 * source_block_count))


def build_open_thread_review_suggestions(
    threads: Sequence[PlotThread],
    statuses: dict[Any, str],
    *,
    total_chapters: int,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Offer reviewable, source-attributed open threads without claiming a contradiction."""
    suggestions: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for thread in threads:
        if len(suggestions) >= limit:
            break
        title = " ".join(str(thread.title or "").split()).strip()
        normalized_title = title.casefold()
        chapter = thread.last_mentioned_at or thread.introduced_at
        if (
            not title
            or normalized_title in seen_titles
            or statuses.get(thread.id)
            not in {"introduced", "developing", "paused", "possibly_abandoned", "forgotten"}
            or int(thread.importance or 0) < 6
            or int(getattr(thread, "mention_count", 0) or 0) < 2
            or not isinstance(chapter, int)
            or not 1 <= chapter <= total_chapters
        ):
            continue
        seen_titles.add(normalized_title)
        suggestions.append(
            {
                "id": f"thread-review-{thread.id}",
                "type": "future_direction",
                "severity": "direction",
                "title": f'Review open thread: "{title}"',
                "description": (
                    f"This tracked thread was last mentioned in chapter {chapter} and remains open. "
                    "Check whether its next step or payoff is intentional."
                    + (
                        f" Recorded context: {' '.join(thread.description.split())[:180]}"
                        if thread.description
                        else ""
                    )
                ),
                "chapter_ref": chapter,
                "action_label": "Review thread evidence",
                "ask_prompt": f'What does the manuscript actually establish about "{title}", and does it need a later payoff?',
                "source": "heuristic",
            }
        )
    return suggestions


def advisor_supported_relationship(
    relationship: CharacterRelationship, character_names: dict[Any, str]
) -> bool:
    """Include author-reviewed ties or generated ties with verified participant evidence."""
    if relationship.edited_by_author:
        return True
    evidence = relationship.label_evidence if isinstance(relationship.label_evidence, dict) else {}
    start = evidence.get("source_start")
    end = evidence.get("source_end")
    return bool(
        isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and end > start >= 0
        and relationship_quote_anchors_participants(
            evidence.get("quote"),
            character_names.get(relationship.character_a_id),
            character_names.get(relationship.character_b_id),
        )
    )


def build_relationship_drift_suggestions(
    relationship_rows: Sequence[CharacterRelationship],
    character_names: dict[Any, str],
) -> list[dict[str, Any]]:
    relationship_groups: dict[tuple[str, str], list[CharacterRelationship]] = {}
    for rel in relationship_rows:
        if not advisor_supported_relationship(rel, character_names):
            continue
        key = tuple(sorted([str(rel.character_a_id), str(rel.character_b_id)]))
        relationship_groups.setdefault(key, []).append(rel)

    suggestions: list[dict[str, Any]] = []
    for pair_key, rel_items in relationship_groups.items():
        if len(rel_items) < 2:
            continue
        rel_items = sorted(rel_items, key=lambda item: item.from_chapter)
        if rel_items[0].from_chapter == rel_items[-1].from_chapter:
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
        type_aliases = {
            "friends": "friend",
            "friendship": "friend",
            "allies": "ally",
            "enemies": "enemy",
        }
        situational_types = {
            "relationship",
            "sits_with",
            "sitting_next_to",
            "supportive",
            "indifference",
        }
        first_type = str(first.rel_type or "").strip().casefold().replace(" ", "_")
        last_type = str(last.rel_type or "").strip().casefold().replace(" ", "_")
        if first_type in situational_types or last_type in situational_types:
            continue
        type_changed = type_aliases.get(first_type, first_type) != type_aliases.get(
            last_type, last_type
        )
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
