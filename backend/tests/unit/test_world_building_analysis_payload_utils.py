from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.utils.world_building_analysis_payload_utils import (
    build_integration_analysis_payload,
    build_world_gap_analysis_payload,
    empty_gap_analysis_payload,
    empty_integration_analysis_payload,
)


def _element(**overrides):
    now = datetime.now(UTC)
    values = {
        "id": uuid.uuid4(),
        "book_id": uuid.uuid4(),
        "series_id": None,
        "world_document_id": uuid.uuid4(),
        "source_scope": "world",
        "element_type": "place",
        "name": "Glass Harbor",
        "description": "A port city powered by mirror beacons.",
        "parent_element_id": None,
        "dependencies": [],
        "usage_count": 0,
        "gap_score": None,
        "integration_score": None,
        "suggestions": [],
        "edited_by_author": False,
        "is_series_canonical": False,
        "created_at": now,
        "updated_at": now,
        "analysis_metadata": {
            "canonical_name": "Glass Harbor",
            "aliases": ["Mirror Port"],
            "confidence": 0.92,
            "grounding_passage_count": 2,
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _document(**overrides):
    now = datetime.now(UTC)
    values = {
        "id": uuid.uuid4(),
        "book_id": uuid.uuid4(),
        "title": "Atlas notes",
        "source_name": "atlas.md",
        "word_count": 120,
        "is_active": True,
        "archived_at": None,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_empty_payload_helpers_return_stable_shapes():
    gap_payload = empty_gap_analysis_payload("gap_detection")
    integration_payload = empty_integration_analysis_payload("story_integration")

    assert gap_payload["mode"] == "gap_detection"
    assert gap_payload["gap_groups"] == []
    assert gap_payload["priority_gaps"] == []
    assert integration_payload["mode"] == "story_integration"
    assert integration_payload["integration_opportunities"] == []
    assert integration_payload["dependency_graph"] == []


@pytest.mark.asyncio
async def test_build_world_gap_analysis_payload_surfaces_missing_world_lore_without_persisting():
    document = _document()
    world_element = _element(book_id=document.book_id)

    payload = await build_world_gap_analysis_payload(
        SimpleNamespace(),
        book_id=document.book_id,
        series_id=None,
        mode="gap_detection",
        documents=[document],
        document_elements=[world_element],
        story_elements=[],
        characters=[],
        persist=False,
    )

    assert payload["mode"] == "gap_detection"
    assert payload["world_documents"][0]["title"] == "Atlas notes"
    assert payload["gap_categories"]["missing_in_story"][0]["title"].startswith("Glass Harbor")
    assert world_element.gap_score is not None


@pytest.mark.asyncio
async def test_build_integration_analysis_payload_surfaces_underused_world_lore_without_persisting():
    document = _document()
    world_element = _element(book_id=document.book_id)

    payload = await build_integration_analysis_payload(
        SimpleNamespace(),
        book_id=document.book_id,
        series_id=None,
        mode="story_integration",
        documents=[document],
        document_elements=[world_element],
        story_elements=[],
        persist=False,
    )

    assert payload["mode"] == "story_integration"
    assert payload["integration_opportunities"][0]["element_name"] == "Glass Harbor"
    assert payload["world_elements"][0]["name"] == "Glass Harbor"
    assert world_element.integration_score is not None
