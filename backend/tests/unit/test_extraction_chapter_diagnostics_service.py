import uuid
from types import SimpleNamespace

import pytest

from app.services.extraction_chapter_diagnostics_service import (
    build_chapter_character_extraction_diagnostics,
)


class _FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _FakeExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _FakeScalarResult(self._values)


class _FakeDb:
    def __init__(self, values):
        self._values = values

    async def execute(self, _statement):
        return _FakeExecuteResult(self._values)


@pytest.mark.asyncio
async def test_build_chapter_character_extraction_diagnostics_accumulates_totals():
    book = SimpleNamespace(
        id=uuid.uuid4(),
        cover_s3_key="covers/book.png",
        writer_workspace={
            "processing": {
                "parser_diagnostics": {
                    "character_extraction": {
                        "totals": {
                            "invalid_profile_batches": 1,
                            "saved_characters": 2,
                            "quarantined_candidates": 1,
                            "adjudicated_promoted_characters": 3,
                            "adjudicated_quarantined_candidates": 4,
                            "adjudicated_rejected_noise": 5,
                            "adjudicated_place_entities": 6,
                            "adjudicated_alias_merges": 7,
                            "ambiguous_llm_adjudications": 8,
                            "rejected_entities": 9,
                            "relationships_persisted": 10,
                            "unresolved_relationships_count": 11,
                            "relationship_review_candidates": 12,
                        }
                    }
                }
            }
        },
    )

    diagnostics = await build_chapter_character_extraction_diagnostics(
        _FakeDb(["promoted_character", "quarantined", "rejected", "place", "merged_alias"]),
        book,
        chapter_number=3,
        extraction_batch_texts=["a", "b"],
        source_coverage={
            "complete": True,
            "source_characters": 2,
            "profile_enrichment": {"status": "partial", "invalid_response_batches": 2},
        },
        extraction_failed_batches=1,
        extraction_fallback_batches=1,
        extraction_fallback_character_count=2,
        raw_character_entities=[{"name": "A"}, {"name": "B"}, {"name": "C"}],
        aggregated_entities=[{"name": "A"}, {"name": "B"}],
        saved_character_count=2,
        quarantined_candidate_count=1,
        ambiguous_entity_count=1,
        strict_hold_count=1,
        extraction_rejected_characters=[{"name": "Noise", "stage": "extract"}],
        unresolved_relationships=[{"source": "A", "target": "B"}],
        relationship_review_candidate_count=2,
        persisted_relationship_count=3,
        duplicate_suggestions=[SimpleNamespace(status="pending"), SimpleNamespace(status="done")],
        repair_result=SimpleNamespace(
            auto_merged=1,
            auto_aliases=2,
            auto_suppressed=3,
            blocked_suggestions=4,
        ),
        reconciled_first_name_alias_count=5,
        chapter_media_count=6,
        media_marker_count=7,
    )

    character_diagnostics = diagnostics["character_extraction"]

    assert character_diagnostics["total_batches"] == 2
    assert character_diagnostics["source_coverage"] == {
        "complete": True,
        "source_characters": 2,
        "profile_enrichment": {"status": "partial", "invalid_response_batches": 2},
    }
    assert character_diagnostics["invalid_profile_batches"] == 2
    assert character_diagnostics["totals"]["invalid_profile_batches"] == 3
    assert character_diagnostics["extracted_candidates"] == 5
    assert character_diagnostics["duplicate_suggestions"] == 1
    assert character_diagnostics["identity_auto_aliases"] == 7
    assert character_diagnostics["cover_available"] is True
    assert character_diagnostics["totals"]["saved_characters"] == 4
    assert character_diagnostics["totals"]["quarantined_candidates"] == 2
    assert character_diagnostics["totals"]["adjudicated_promoted_characters"] == 4
    assert character_diagnostics["totals"]["relationships_persisted"] == 13
    assert character_diagnostics["totals"]["unresolved_relationships_count"] == 12
    assert character_diagnostics["rejected_characters"] == [{"name": "Noise", "stage": "extract"}]
    assert character_diagnostics["unresolved_relationships"] == [{"source": "A", "target": "B"}]
