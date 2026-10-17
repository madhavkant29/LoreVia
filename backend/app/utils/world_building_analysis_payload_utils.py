from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.world.dependency_graph import build_dependency_graph
from app.engine.world.gap_detector import detect_consistency_flags
from app.models.intelligence import WorldBuildingDocument, WorldElement
from app.utils.world_building_analysis_persistence_utils import upsert_world_analysis
from app.utils.world_building_candidate_utils import WORLD_HIGH_SIGNAL_TYPES
from app.utils.world_building_conflict_utils import (
    _build_cross_source_conflict_detail,
    _detect_internal_candidate_conflicts,
    _is_underintegrated_story_match,
    _normalize_world_name,
    _should_surface_story_item,
    _should_surface_world_item,
    _world_text_mentions_name,
)
from app.utils.world_building_serialization_utils import (
    serialize_world_document,
    serialize_world_element,
)
from app.utils.world_building_story_utils import (
    apply_gap_scores,
    apply_integration_scores,
    collapse_elements,
)
from app.utils.world_building_watchlist_utils import (
    _build_coverage_watchlist_items,
    _build_gap_item,
    _find_matching_item,
)

GAP_GROUP_META: dict[str, tuple[str, str]] = {
    "story_conflicts": (
        "Story conflicts",
        "The manuscript and the world corpus disagree about the same lore element.",
    ),
    "missing_in_story": (
        "Missing in story",
        "The world corpus documents lore that barely appears in the story manuscript.",
    ),
    "missing_in_world": (
        "Missing in world corpus",
        "Story-facing lore appears in chapters but is not captured in the world-building workspace.",
    ),
    "character_gaps": (
        "Character reference gaps",
        "Core character facts are active in the story but absent from the world corpus.",
    ),
    "timeline_gaps": (
        "Timeline watchlist",
        "Lore only appears late or too lightly in the manuscript to feel grounded.",
    ),
    "coverage_watchlist": (
        "Coverage watchlist",
        "LoreVia keeps a short queue of under-specified canon areas so there are always concrete worldbuilding review targets to tighten.",
    ),
}
MIN_WORLD_REVIEW_TARGETS = 3


def empty_gap_analysis_payload(mode: str) -> dict:
    return {
        "mode": mode,
        "generated_at": None,
        "gap_categories": {},
        "gap_groups": [],
        "priority_gaps": [],
        "consistency_flags": [],
        "world_elements": [],
        "world_documents": [],
    }


def empty_integration_analysis_payload(mode: str) -> dict:
    return {
        "mode": mode,
        "generated_at": None,
        "integration_opportunities": [],
        "consistency_flags": [],
        "world_elements": [],
        "world_documents": [],
        "dependency_graph": [],
    }


def _conflict_item_name(item: dict) -> str:
    return _normalize_world_name(
        str(item.get("canonical_name") or item.get("name") or item.get("title") or "")
    )


def _detect_cross_source_candidate_conflicts(
    *,
    world_candidate_records: list[dict],
    story_candidate_records: list[dict],
) -> list[dict]:
    if not world_candidate_records or not story_candidate_records:
        return []
    world_by_name = collapse_elements(world_candidate_records)
    story_by_name = collapse_elements(story_candidate_records)
    items: list[dict] = []
    for world_item in world_by_name.values():
        story_match = _find_matching_item(
            str(world_item.get("name") or ""),
            story_by_name,
            aliases=list(world_item.get("aliases") or []),
        )
        if story_match is None:
            continue
        conflict_detail = _build_cross_source_conflict_detail(world_item, story_match)
        if conflict_detail is None:
            continue
        items.append(
            _build_gap_item(
                category="story_conflicts",
                severity="critical",
                title=conflict_detail["title"],
                description=conflict_detail["description"],
                suggested_fix=conflict_detail["suggested_fix"],
                world_item=world_item,
                story_item=story_match,
                priority=10,
                world_evidence=conflict_detail.get("world_evidence"),
                story_evidence=conflict_detail.get("story_evidence"),
            )
        )
    return items


def build_gap_groups(grouped_items: dict[str, list[dict]]) -> tuple[list[dict], dict]:
    gap_groups = []
    for key, items in grouped_items.items():
        label, description = GAP_GROUP_META.get(key, (key.replace("_", " ").title(), None))
        ordered_items = sorted(
            items, key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or ""))
        )
        gap_groups.append(
            {
                "key": key,
                "label": label,
                "description": description,
                "items": ordered_items,
            }
        )
    gap_groups.sort(
        key=lambda item: max(
            (int(entry.get("priority") or 0) for entry in item["items"]), default=0
        ),
        reverse=True,
    )
    return gap_groups, {group["key"]: group["items"] for group in gap_groups}


async def build_world_gap_analysis_payload(
    db: AsyncSession,
    *,
    book_id: uuid.UUID | None,
    series_id: uuid.UUID | None,
    mode: str,
    documents: list[WorldBuildingDocument],
    document_elements: list[WorldElement],
    story_elements: list[WorldElement],
    characters: list[dict],
    story_candidate_records: list[dict] | None = None,
    world_candidate_records: list[dict] | None = None,
    consistency_elements: list[WorldElement] | None = None,
    persist: bool = True,
) -> dict:
    story_by_name = collapse_elements([serialize_world_element(item) for item in story_elements])
    world_by_name = collapse_elements([serialize_world_element(item) for item in document_elements])
    world_corpus_text = "\n".join(
        f"{item.get('canonical_name') or item.get('name') or ''} {' '.join(item.get('aliases') or [])} {item.get('description') or ''}"
        for item in world_by_name.values()
    ).lower()

    grouped_items: dict[str, list[dict]] = defaultdict(list)
    story_conflict_names: set[str] = set()
    for item in _detect_internal_candidate_conflicts(
        world_candidate_records or [], source_kind="world"
    ):
        grouped_items["story_conflicts"].append(item)
        story_conflict_names.add(_conflict_item_name(item))
    for item in _detect_internal_candidate_conflicts(
        story_candidate_records or [], source_kind="story"
    ):
        grouped_items["story_conflicts"].append(item)
        story_conflict_names.add(_conflict_item_name(item))
    for item in _detect_cross_source_candidate_conflicts(
        world_candidate_records=world_candidate_records or [],
        story_candidate_records=story_candidate_records or [],
    ):
        conflict_name = _conflict_item_name(item)
        if conflict_name in story_conflict_names:
            continue
        grouped_items["story_conflicts"].append(item)
        story_conflict_names.add(conflict_name)

    for key, world_item in world_by_name.items():
        if not _should_surface_world_item(world_item):
            continue
        story_match = _find_matching_item(
            world_item["name"], story_by_name, aliases=world_item.get("aliases") or []
        )
        if story_match is None:
            grouped_items["missing_in_story"].append(
                _build_gap_item(
                    category="missing_in_story",
                    severity="high",
                    title=f"{world_item['name']} is missing from the story manuscript",
                    description="This lore item is documented in the world-building corpus but does not appear in the current story manuscript.",
                    suggested_fix=f"Seed {world_item['name']} into a chapter scene, summary beat, or character conversation so the manuscript reflects the reference lore.",
                    world_item=world_item,
                    priority=8
                    if str(world_item.get("element_type") or "") in WORLD_HIGH_SIGNAL_TYPES
                    else 6,
                )
            )
            continue

        conflict_detail = _build_cross_source_conflict_detail(world_item, story_match)
        if conflict_detail is not None:
            conflict_name = _normalize_world_name(str(world_item.get("name") or ""))
            if conflict_name in story_conflict_names:
                continue
            grouped_items["story_conflicts"].append(
                _build_gap_item(
                    category="story_conflicts",
                    severity="critical",
                    title=conflict_detail["title"],
                    description=conflict_detail["description"],
                    suggested_fix=conflict_detail["suggested_fix"],
                    world_item=world_item,
                    story_item=story_match,
                    priority=10,
                    world_evidence=conflict_detail.get("world_evidence"),
                    story_evidence=conflict_detail.get("story_evidence"),
                )
            )
            story_conflict_names.add(conflict_name)
            continue

        if _is_underintegrated_story_match(story_match):
            grouped_items["timeline_gaps"].append(
                _build_gap_item(
                    category="timeline_gaps",
                    severity="medium",
                    title=f"{world_item['name']} only lands lightly in the manuscript",
                    description="The lore exists in the world corpus, but it only surfaces once or very late in the story material.",
                    suggested_fix=f"Foreshadow {world_item['name']} earlier or reinforce it across multiple chapters so readers can track it before payoff moments.",
                    world_item=world_item,
                    story_item=story_match,
                    priority=6,
                )
            )

    for key, story_item in story_by_name.items():
        if _find_matching_item(
            story_item["name"], world_by_name, aliases=story_item.get("aliases") or []
        ) is not None or not _should_surface_story_item(story_item):
            continue
        grouped_items["missing_in_world"].append(
            _build_gap_item(
                category="missing_in_world",
                severity="medium",
                title=f"{story_item['name']} appears in the story but not in the world corpus",
                description="Readers can encounter this lore in the manuscript, but it is not captured in the reference documents yet.",
                suggested_fix=f"Add a worldbuilding entry for {story_item['name']} so the reference corpus stays aligned with the manuscript.",
                story_item=story_item,
                priority=5,
            )
        )

    for character in characters:
        if not character["should_watch"]:
            continue
        character_aliases = list(character.get("aliases") or [])
        if (
            _world_text_mentions_name(world_corpus_text, character["name"])
            or any(
                _world_text_mentions_name(world_corpus_text, alias) for alias in character_aliases
            )
            or _find_matching_item(character["name"], world_by_name, aliases=character_aliases)
            is not None
        ):
            continue
        grouped_items["character_gaps"].append(
            {
                "id": f"character-gap-{character['id']}",
                "category": "character_gaps",
                "severity": "medium",
                "title": f"{character['name']} is active in the story but absent from world notes",
                "description": "This character has meaningful story presence, but the world-building corpus does not mention them.",
                "suggested_fix": f"Add a worldbuilding note for {character['name']} covering role, affiliations, and any lore rules that affect them.",
                "world_evidence": None,
                "story_evidence": character["story_evidence"],
                "world_document_id": None,
                "world_document_title": None,
                "story_chapter_number": character["chapter_number"],
                "story_chapter_title": None,
                "character_name": character["name"],
                "priority": 5,
            }
        )

    gap_groups, gap_categories = build_gap_groups(grouped_items)
    priority_gaps = [item for group in gap_groups for item in group["items"]]
    priority_gaps.sort(
        key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or ""))
    )
    consistency_inputs = [
        serialize_world_element(item) for item in (consistency_elements or document_elements)
    ]
    consistency_inputs.extend(world_candidate_records or [])
    consistency_inputs.extend(story_candidate_records or [])
    consistency_flags_by_id: dict[str, dict] = {}
    for flag in detect_consistency_flags(consistency_inputs):
        consistency_flags_by_id.setdefault(str(flag.get("id") or flag.get("title") or ""), flag)
    consistency_flags = list(consistency_flags_by_id.values())
    supplemental_needed = max(
        0, MIN_WORLD_REVIEW_TARGETS - (len(priority_gaps) + len(consistency_flags))
    )
    if supplemental_needed:
        supplemental_items = _build_coverage_watchlist_items(
            story_by_name=story_by_name,
            world_by_name=world_by_name,
            characters=characters,
            limit=supplemental_needed,
            existing_items=priority_gaps,
        )
        if supplemental_items:
            grouped_items["coverage_watchlist"].extend(supplemental_items)
            gap_groups, gap_categories = build_gap_groups(grouped_items)
            priority_gaps = [item for group in gap_groups for item in group["items"]]
            priority_gaps.sort(
                key=lambda item: (-int(item.get("priority") or 0), str(item.get("title") or ""))
            )
    priority_gaps = priority_gaps[:12]

    generated_at = datetime.now(UTC)
    if persist:
        analysis = await upsert_world_analysis(
            db,
            book_id=book_id,
            series_id=series_id,
            mode=mode,
            gap_categories=gap_categories,
            priority_gaps=priority_gaps,
            integration_opportunities=[],
            consistency_flags=consistency_flags,
        )
        generated_at = analysis.generated_at
    apply_gap_scores(document_elements, priority_gaps)

    return {
        "mode": mode,
        "generated_at": generated_at,
        "gap_categories": gap_categories,
        "gap_groups": gap_groups,
        "priority_gaps": priority_gaps,
        "consistency_flags": consistency_flags,
        "world_elements": [serialize_world_element(element) for element in document_elements],
        "world_documents": [serialize_world_document(document) for document in documents],
    }


async def build_integration_analysis_payload(
    db: AsyncSession,
    *,
    book_id: uuid.UUID | None,
    series_id: uuid.UUID | None,
    mode: str,
    documents: list[WorldBuildingDocument],
    document_elements: list[WorldElement],
    story_elements: list[WorldElement],
    consistency_elements: list[WorldElement] | None = None,
    persist: bool = True,
) -> dict:
    story_by_name = collapse_elements([serialize_world_element(item) for item in story_elements])
    integration_opportunities: list[dict] = []

    for element in document_elements:
        serialized_element = serialize_world_element(element)
        if not _should_surface_world_item(serialized_element):
            continue
        metadata = element.analysis_metadata or {}
        story_match = _find_matching_item(
            element.name,
            story_by_name,
            aliases=metadata.get("aliases") or [],
        )
        story_match_data = story_match or {}
        presence_score = float(story_match_data.get("presence_score") or 0.0)
        usage_count = int(story_match_data.get("usage_count") or 0)
        if presence_score >= 0.62 or usage_count >= 3:
            continue
        target_chapter = story_match_data.get("chapter_number")
        integration_opportunities.append(
            {
                "id": f"integration-{str(element.id)}",
                "element_name": element.name,
                "element_type": element.element_type,
                "description": f"{element.name} is present in the world corpus but underused in the manuscript.",
                "suggestions": [
                    f"Introduce {element.name} in a character-facing scene before it becomes plot-critical.",
                    f"Reference {element.name} in chapter summaries, dialogue, or setting description so it feels lived-in.",
                ],
                "target_chapter": target_chapter,
                "target_chapter_title": story_match_data.get("chapter_title"),
                "priority": 8 if usage_count == 0 else (7 if presence_score < 0.35 else 6),
                "world_document_id": str(element.world_document_id)
                if element.world_document_id
                else None,
                "world_document_title": metadata.get("world_document_title"),
                "confidence": float(serialized_element.get("confidence") or 0.0),
                "canonical_name": serialized_element.get("canonical_name") or element.name,
            }
        )

    integration_opportunities.sort(
        key=lambda item: (-int(item.get("priority") or 0), item["element_name"].lower())
    )
    consistency_flags = detect_consistency_flags(
        [serialize_world_element(item) for item in (consistency_elements or document_elements)]
    )
    generated_at = datetime.now(UTC)
    if persist:
        analysis = await upsert_world_analysis(
            db,
            book_id=book_id,
            series_id=series_id,
            mode=mode,
            gap_categories={},
            priority_gaps=[],
            integration_opportunities=integration_opportunities,
            consistency_flags=consistency_flags,
        )
        generated_at = analysis.generated_at
    apply_integration_scores(document_elements, integration_opportunities)
    return {
        "mode": mode,
        "generated_at": generated_at,
        "integration_opportunities": integration_opportunities,
        "consistency_flags": consistency_flags,
        "world_elements": [serialize_world_element(element) for element in document_elements],
        "world_documents": [serialize_world_document(document) for document in documents],
        "dependency_graph": build_dependency_graph(
            [serialize_world_element(element) for element in document_elements]
        ),
    }
