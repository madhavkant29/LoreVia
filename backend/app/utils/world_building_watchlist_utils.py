from __future__ import annotations

from app.engine.world.gap_detector import detect_gap_categories
from app.utils.characters.similarity import name_similarity
from app.utils.world_building_conflict_utils import (
    _normalize_world_name,
    _should_surface_world_item,
    _world_names_equivalent,
)


def _find_matching_item(
    name: str, items_by_name: dict[str, dict], *, aliases: list[str] | None = None
) -> dict | None:
    query_names = [str(name or "").strip(), *[str(alias).strip() for alias in (aliases or [])]]
    query_names = [query_name for query_name in query_names if query_name]
    normalized_keys = {_normalize_world_name(query_name) for query_name in query_names}
    normalized_keys.discard("")
    if not normalized_keys:
        return None

    for key in normalized_keys:
        exact_match = items_by_name.get(key)
        if exact_match is not None:
            return exact_match

    best_match: dict | None = None
    best_score = 0.0
    for candidate in items_by_name.values():
        candidate_names = [
            str(candidate.get("canonical_name") or candidate.get("name") or "").strip(),
            *[str(alias).strip() for alias in (candidate.get("aliases") or [])],
        ]
        candidate_names = [candidate_name for candidate_name in candidate_names if candidate_name]
        if not candidate_names:
            continue
        if any(
            _normalize_world_name(candidate_name) in normalized_keys
            for candidate_name in candidate_names
        ):
            return candidate
        score = max(
            (
                name_similarity(query_name, candidate_name)
                for query_name in query_names
                for candidate_name in candidate_names
                if _world_names_equivalent(query_name, candidate_name)
            ),
            default=0.0,
        )
        if score >= best_score:
            best_score = score
            best_match = candidate
    return best_match if best_score >= 0.84 else None


def _build_gap_item(
    *,
    category: str,
    severity: str,
    title: str,
    description: str,
    suggested_fix: str,
    priority: int,
    world_item: dict | None = None,
    story_item: dict | None = None,
    world_evidence: str | None = None,
    story_evidence: str | None = None,
) -> dict:
    if world_item is not None:
        item_name = str(world_item.get("name") or "")
        resolved_world_evidence = (
            world_evidence or str(world_item.get("description") or "").strip() or None
        )
        world_document_id = str(world_item.get("world_document_id") or "") or None
        world_document_title = str(world_item.get("world_document_title") or "").strip() or None
    else:
        item_name = str(story_item.get("name") or "") if story_item else ""
        resolved_world_evidence = world_evidence
        world_document_id = None
        world_document_title = None
    if story_item is not None:
        resolved_story_evidence = (
            story_evidence or str(story_item.get("description") or "").strip() or None
        )
        story_chapter_number = int(story_item.get("chapter_number") or 0) or None
        story_chapter_title = str(story_item.get("chapter_title") or "").strip() or None
    else:
        resolved_story_evidence = story_evidence
        story_chapter_number = None
        story_chapter_title = None
    return {
        "id": f"{category}-{item_name.lower().replace(' ', '-')}",
        "category": category,
        "severity": severity,
        "title": title,
        "description": description,
        "suggested_fix": suggested_fix,
        "world_evidence": resolved_world_evidence,
        "story_evidence": resolved_story_evidence,
        "world_document_id": world_document_id,
        "world_document_title": world_document_title,
        "story_chapter_number": story_chapter_number,
        "story_chapter_title": story_chapter_title,
        "character_name": None,
        "priority": priority,
        "entity_type": str((world_item or story_item or {}).get("element_type") or ""),
        "canonical_name": str((world_item or story_item or {}).get("canonical_name") or item_name),
        "confidence": max(
            float((world_item or {}).get("confidence") or 0.0),
            float((story_item or {}).get("confidence") or 0.0),
        ),
        "provenance": {
            "world": list((world_item or {}).get("provenance") or [])[:2],
            "story": list((story_item or {}).get("provenance") or [])[:2],
        },
    }


def _build_coverage_watchlist_items(
    *,
    story_by_name: dict[str, dict],
    world_by_name: dict[str, dict],
    characters: list[dict],
    limit: int,
    existing_items: list[dict],
) -> list[dict]:
    if limit <= 0:
        return []

    existing_ids = {str(item.get("id") or "") for item in existing_items}
    existing_titles = {str(item.get("title") or "").strip().lower() for item in existing_items}
    supplemental: list[dict] = []

    def add_candidate(item: dict | None) -> None:
        if item is None:
            return
        item_id = str(item.get("id") or "")
        item_title = str(item.get("title") or "").strip().lower()
        if not item_id or item_id in existing_ids or item_title in existing_titles:
            return
        existing_ids.add(item_id)
        existing_titles.add(item_title)
        supplemental.append(item)

    for world_item in sorted(
        world_by_name.values(),
        key=lambda item: (
            int(item.get("usage_count") or 0),
            float(item.get("confidence") or 0.0),
            str(item.get("name") or "").lower(),
        ),
        reverse=True,
    ):
        if len(supplemental) >= limit:
            break
        if not _should_surface_world_item(world_item):
            continue
        description = str(world_item.get("description") or "").strip()
        claims = list(world_item.get("claims") or [])
        provenance = list(world_item.get("provenance") or [])
        story_match = _find_matching_item(
            world_item["name"], story_by_name, aliases=world_item.get("aliases") or []
        )
        if len(description) < 90 or (not claims and len(provenance) < 2):
            add_candidate(
                _build_gap_item(
                    category="coverage_watchlist",
                    severity="low",
                    title=f"{world_item['name']} needs a clearer canon note",
                    description="This lore is present in the active world corpus, but the canon detail is still thin for continuity checks and later retrieval.",
                    suggested_fix=f"Expand {world_item['name']} with stable facts, limits, relationships, and consequences so later chapters can reuse the same canon cleanly.",
                    world_item=world_item,
                    story_item=story_match,
                    priority=4,
                )
            )
        if len(supplemental) >= limit:
            break
        if story_match is not None:
            chapter_count = int(
                story_match.get("chapter_count") or len(story_match.get("chapter_numbers") or [])
            )
            presence_score = float(story_match.get("presence_score") or 0.0)
            if chapter_count <= 1 or presence_score < 0.75:
                add_candidate(
                    _build_gap_item(
                        category="coverage_watchlist",
                        severity="low",
                        title=f"{world_item['name']} needs one more story anchor",
                        description="The canon exists, but the manuscript still gives readers only light runway for this world element.",
                        suggested_fix=f"Reinforce {world_item['name']} in one earlier scene, summary beat, or dialogue exchange so readers can track it before later payoff.",
                        world_item=world_item,
                        story_item=story_match,
                        priority=4,
                    )
                )

    for story_item in sorted(
        story_by_name.values(),
        key=lambda item: (
            int(item.get("usage_count") or 0),
            float(item.get("presence_score") or 0.0),
            str(item.get("name") or "").lower(),
        ),
        reverse=True,
    ):
        if len(supplemental) >= limit:
            break
        if (
            _find_matching_item(
                story_item["name"], world_by_name, aliases=story_item.get("aliases") or []
            )
            is not None
        ):
            continue
        if (
            int(story_item.get("usage_count") or 0) < 2
            and float(story_item.get("confidence") or 0.0) < 0.55
        ):
            continue
        add_candidate(
            _build_gap_item(
                category="coverage_watchlist",
                severity="medium",
                title=f"{story_item['name']} deserves a world note",
                description="This lore is active enough in the manuscript that it is worth pinning down in the canon workspace, even before it becomes a hard contradiction.",
                suggested_fix=f"Create a short worldbuilding note for {story_item['name']} with a stable definition, affected characters, and any rules readers need to remember.",
                story_item=story_item,
                priority=5,
            )
        )

    for character in characters:
        if len(supplemental) >= limit:
            break
        if not character.get("should_watch"):
            continue
        world_match = _find_matching_item(
            str(character.get("name") or ""),
            world_by_name,
            aliases=list(character.get("aliases") or []),
        )
        if world_match is not None:
            continue
        add_candidate(
            {
                "id": f"coverage-watch-character-{character['id']}",
                "category": "coverage_watchlist",
                "severity": "medium",
                "title": f"{character['name']} needs a canon-facing reference note",
                "description": "This character is carrying enough story weight that the worldbuilding workspace should track how lore, factions, or rules interact with them.",
                "suggested_fix": f"Add a concise canon note for {character['name']} covering role, affiliations, pressures, and any world rules tied to their arc.",
                "world_evidence": None,
                "story_evidence": character.get("story_evidence"),
                "world_document_id": None,
                "world_document_title": None,
                "story_chapter_number": character.get("chapter_number"),
                "story_chapter_title": None,
                "character_name": character.get("name"),
                "priority": 4,
                "entity_type": "character",
                "canonical_name": character.get("name"),
                "confidence": 0.0,
                "provenance": {"world": [], "story": []},
            }
        )

    if len(supplemental) < limit:
        baseline_candidates = detect_gap_categories(
            [*world_by_name.values(), *story_by_name.values()]
        )
        for category, items in baseline_candidates.items():
            if len(supplemental) >= limit:
                break
            for item in items:
                if len(supplemental) >= limit:
                    break
                add_candidate(
                    {
                        "id": f"coverage-watch-{category}",
                        "category": "coverage_watchlist",
                        "severity": "low",
                        "title": str(
                            item.get("title") or f"Missing {category.replace('_', ' ')} coverage"
                        ),
                        "description": f"LoreVia could not find a stable {category.replace('_', ' ')} reference layer in the extracted canon, which makes future continuity checks thinner.",
                        "suggested_fix": f"Add or expand notes that clarify the story's {category.replace('_', ' ')} frame, even if the answer is intentionally minimal.",
                        "world_evidence": None,
                        "story_evidence": None,
                        "world_document_id": None,
                        "world_document_title": None,
                        "story_chapter_number": None,
                        "story_chapter_title": None,
                        "character_name": None,
                        "priority": 3,
                        "entity_type": category,
                        "canonical_name": None,
                        "confidence": 0.0,
                        "provenance": {"world": [], "story": []},
                    }
                )

    return supplemental[:limit]
