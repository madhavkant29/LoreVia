from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from sqlalchemy import select

from app.models.book import Book
from app.models.character import CharacterCandidate
from app.services.extraction_character_reporting_service import (
    _summarize_rejected_character_reports,
)
from app.utils.ingestion_utils import current_parser_diagnostics


async def build_chapter_character_extraction_diagnostics(
    db,
    book: Book,
    *,
    chapter_number: int,
    extraction_batch_texts: Sequence[str],
    extraction_failed_batches: int,
    extraction_fallback_batches: int,
    extraction_fallback_character_count: int,
    raw_character_entities: Sequence[dict[str, Any]],
    aggregated_entities: Sequence[dict[str, Any]],
    saved_character_count: int,
    quarantined_candidate_count: int,
    ambiguous_entity_count: int,
    strict_hold_count: int,
    extraction_rejected_characters: list[dict[str, Any]],
    unresolved_relationships: list[dict[str, Any]],
    relationship_review_candidate_count: int,
    persisted_relationship_count: int,
    duplicate_suggestions: Sequence[Any],
    repair_result: Any,
    reconciled_first_name_alias_count: int,
    chapter_media_count: int,
    media_marker_count: int,
) -> dict[str, Any]:
    adjudication_status_rows = (
        (
            await db.execute(
                select(CharacterCandidate.adjudication_status).where(
                    CharacterCandidate.book_id == book.id,
                    CharacterCandidate.chapter_number == chapter_number,
                )
            )
        )
        .scalars()
        .all()
    )
    adjudication_counts = Counter(str(status or "unknown") for status in adjudication_status_rows)
    extraction_diagnostics = dict(current_parser_diagnostics(book) or {})
    previous_character_diagnostics = (
        extraction_diagnostics.get("character_extraction")
        if isinstance(extraction_diagnostics.get("character_extraction"), dict)
        else {}
    )
    previous_totals = (
        previous_character_diagnostics.get("totals")
        if isinstance(previous_character_diagnostics.get("totals"), dict)
        else {}
    )
    chapter_character_diagnostics = {
        "total_batches": len(extraction_batch_texts),
        "failed_batches": extraction_failed_batches,
        "fallback_batches": extraction_fallback_batches,
        "fallback_character_count": extraction_fallback_character_count,
        "raw_mentions": len(raw_character_entities),
        "candidate_clusters": len(aggregated_entities),
        "extracted_candidates": sum(adjudication_counts.values()),
        "saved_characters": saved_character_count,
        "quarantined_candidates": quarantined_candidate_count,
        "adjudicated_promoted_characters": int(adjudication_counts.get("promoted_character", 0)),
        "adjudicated_quarantined_candidates": int(adjudication_counts.get("quarantined", 0)),
        "adjudicated_rejected_noise": int(adjudication_counts.get("rejected", 0)),
        "adjudicated_place_entities": int(adjudication_counts.get("place", 0)),
        "adjudicated_alias_merges": int(adjudication_counts.get("merged_alias", 0)),
        "ambiguous_llm_adjudications": 0,
        "ambiguity_rate": round(ambiguous_entity_count / max(1, len(aggregated_entities)), 3),
        "strict_hold_rate": round(strict_hold_count / max(1, len(aggregated_entities)), 3),
        "mention_to_promotion_rate": round(
            saved_character_count / max(1, len(raw_character_entities)), 3
        ),
        "rejected_entities": len(extraction_rejected_characters),
        "unresolved_relationships_count": len(unresolved_relationships),
        "relationship_review_candidates": relationship_review_candidate_count,
        "relationships_persisted": persisted_relationship_count,
        "duplicate_suggestions": sum(
            1 for item in duplicate_suggestions if str(item.status or "") == "pending"
        ),
        "identity_auto_merged": repair_result.auto_merged,
        "identity_auto_aliases": repair_result.auto_aliases + reconciled_first_name_alias_count,
        "identity_auto_suppressed": repair_result.auto_suppressed,
        "identity_blocked_suggestions": repair_result.blocked_suggestions,
        "chapter_media_count": chapter_media_count,
        "media_marker_count": media_marker_count,
        "cover_available": bool(book.cover_s3_key),
    }
    if extraction_rejected_characters:
        chapter_character_diagnostics["rejected_characters"] = (
            _summarize_rejected_character_reports(extraction_rejected_characters)
        )
    if unresolved_relationships:
        chapter_character_diagnostics["unresolved_relationships"] = unresolved_relationships[:20]

    extraction_diagnostics["character_extraction"] = {
        **chapter_character_diagnostics,
        "totals": {
            "saved_characters": int(previous_totals.get("saved_characters") or 0)
            + saved_character_count,
            "quarantined_candidates": int(previous_totals.get("quarantined_candidates") or 0)
            + quarantined_candidate_count,
            "adjudicated_promoted_characters": int(
                previous_totals.get("adjudicated_promoted_characters") or 0
            )
            + int(adjudication_counts.get("promoted_character", 0)),
            "adjudicated_quarantined_candidates": int(
                previous_totals.get("adjudicated_quarantined_candidates") or 0
            )
            + int(adjudication_counts.get("quarantined", 0)),
            "adjudicated_rejected_noise": int(
                previous_totals.get("adjudicated_rejected_noise") or 0
            )
            + int(adjudication_counts.get("rejected", 0)),
            "adjudicated_place_entities": int(
                previous_totals.get("adjudicated_place_entities") or 0
            )
            + int(adjudication_counts.get("place", 0)),
            "adjudicated_alias_merges": int(
                previous_totals.get("adjudicated_alias_merges") or 0
            )
            + int(adjudication_counts.get("merged_alias", 0)),
            "ambiguous_llm_adjudications": int(
                previous_totals.get("ambiguous_llm_adjudications") or 0
            ),
            "rejected_entities": int(previous_totals.get("rejected_entities") or 0)
            + len(extraction_rejected_characters),
            "relationships_persisted": int(previous_totals.get("relationships_persisted") or 0)
            + persisted_relationship_count,
            "unresolved_relationships_count": int(
                previous_totals.get("unresolved_relationships_count") or 0
            )
            + len(unresolved_relationships),
            "relationship_review_candidates": int(
                previous_totals.get("relationship_review_candidates") or 0
            )
            + relationship_review_candidate_count,
        },
    }
    return extraction_diagnostics
