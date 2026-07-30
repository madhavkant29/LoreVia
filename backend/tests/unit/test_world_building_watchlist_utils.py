from app.utils.world_building_watchlist_utils import (
    _build_coverage_watchlist_items,
    _build_gap_item,
    _find_matching_item,
)


def test_find_matching_item_matches_aliases():
    item = {
        "name": "The Glass Harbor",
        "canonical_name": "Glass Harbor",
        "aliases": ["Harbor of Glass"],
    }

    assert (
        _find_matching_item(
            "Harbor of Glass",
            {"glass harbor": item},
            aliases=["The Glass Port"],
        )
        is item
    )


def test_build_gap_item_preserves_world_and_story_evidence():
    gap = _build_gap_item(
        category="missing_in_story",
        severity="medium",
        title="Glass Harbor needs story support",
        description="The world note exists but the manuscript barely uses it.",
        suggested_fix="Add an early scene beat.",
        priority=5,
        world_item={
            "name": "Glass Harbor",
            "description": "A port made from storm-glass.",
            "world_document_id": "doc-1",
            "world_document_title": "Atlas",
            "element_type": "location",
            "confidence": 0.8,
            "provenance": ["world"],
        },
        story_item={
            "name": "Glass Harbor",
            "description": "A port briefly mentioned in passing.",
            "chapter_number": 4,
            "chapter_title": "Arrival",
            "element_type": "location",
            "confidence": 0.6,
            "provenance": ["story"],
        },
    )

    assert gap["id"] == "missing_in_story-glass-harbor"
    assert gap["world_document_id"] == "doc-1"
    assert gap["story_chapter_number"] == 4
    assert gap["confidence"] == 0.8
    assert gap["provenance"] == {"world": ["world"], "story": ["story"]}


def test_build_coverage_watchlist_items_adds_thin_world_notes():
    items = _build_coverage_watchlist_items(
        story_by_name={},
        world_by_name={
            "glass harbor": {
                "name": "Glass Harbor",
                "canonical_name": "Glass Harbor",
                "aliases": [],
                "element_type": "place",
                "description": "A port.",
                "usage_count": 3,
                "confidence": 0.9,
                "claims": [],
                "provenance": ["world"],
            }
        },
        characters=[],
        limit=3,
        existing_items=[],
    )

    assert any(item["title"] == "Glass Harbor needs a clearer canon note" for item in items)
    assert all(item["category"] == "coverage_watchlist" for item in items)


def test_build_coverage_watchlist_items_skips_existing_titles():
    items = _build_coverage_watchlist_items(
        story_by_name={},
        world_by_name={
            "glass harbor": {
                "name": "Glass Harbor",
                "canonical_name": "Glass Harbor",
                "aliases": [],
                "element_type": "place",
                "description": "A port.",
                "usage_count": 3,
                "confidence": 0.9,
                "claims": [],
                "provenance": ["world"],
            }
        },
        characters=[],
        limit=3,
        existing_items=[{"id": "old", "title": "Glass Harbor needs a clearer canon note"}],
    )

    assert all(item["title"] != "Glass Harbor needs a clearer canon note" for item in items)
