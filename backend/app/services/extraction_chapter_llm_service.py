from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from app.core.config import settings
from app.engine.character.extractor import (
    ambiguous_full_name_fragments,
    extract_characters_and_relationships,
)
from app.parsers.chunker import count_tokens
from app.services.extraction_character_profile_service import enrich_chapter_character_profiles
from app.services.extraction_character_reporting_service import (
    _append_rejected_character_reports,
)
from app.services.extraction_processing_flow_service import _group_chunks_for_extraction
from app.utils.characters.extraction import cluster_character_entities
from app.utils.characters.profile_evidence import profile_evidence_packets
from app.utils.characters.relationship_evidence import grounded_relationship_evidence
from app.utils.characters.serialization import build_character_roster_snapshot
from app.utils.characters.text import (
    extraction_source_coverage,
    source_excerpt_range_around_name,
    source_excerpt_ranges_around_names,
    source_mention_spans_in_batch,
)

log = logging.getLogger("lorevia.extraction")


@dataclass(slots=True)
class ChapterLlmExtractionResult:
    extraction_batch_texts: list[str]
    source_coverage: dict[str, Any]
    extraction_failed_batches: int
    extraction_fallback_batches: int
    extraction_fallback_character_count: int
    extraction_rejected_characters: list[dict[str, Any]]
    pending_relationships: list[dict[str, Any]]
    raw_character_entities: list[dict[str, Any]]
    aggregated_character_entities: list[dict[str, Any]]

    @property
    def batch_count(self) -> int:
        return len(self.extraction_batch_texts)


async def collect_chapter_llm_extraction(
    _db,
    *,
    book,
    chapter_number: int,
    chunks: list[str],
    existing_characters: list[Any],
    on_incomplete_batch: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> ChapterLlmExtractionResult:
    """Run batched LLM extraction and return normalized chapter-level candidates."""
    roster_snapshot = build_character_roster_snapshot(existing_characters)
    extraction_batches = _group_chunks_for_extraction(chunks)
    source_coverage = extraction_source_coverage(
        chunks,
        extraction_batches,
        max_tokens=settings.EXTRACTION_BATCH_MAX_TOKENS,
        count_tokens=count_tokens,
    )
    if not any(chunk.strip() for chunk in chunks):
        source_coverage["complete"] = False
        source_coverage["failure_stage"] = "character_source_empty"
        source_coverage["batch_outcomes"] = []
        if on_incomplete_batch is not None:
            await on_incomplete_batch(source_coverage)
        raise ValueError("character_extraction_empty_source")
    extraction_batch_texts = ["\n\n".join(chunk_batch) for chunk_batch in extraction_batches]
    source_ranges_by_batch: dict[int, list[dict[str, int]]] = {}
    for source_range in source_coverage["ranges"]:
        source_ranges_by_batch.setdefault(source_range["batch_index"], []).append(source_range)
    extraction_semaphore = asyncio.Semaphore(
        max(1, min(settings.LLM_MAX_CONCURRENT_CALLS_PER_USER, len(extraction_batch_texts) or 1))
    )

    async def _extract_with_limit(batch_text: str) -> dict:
        async with extraction_semaphore:
            return await extract_characters_and_relationships(
                batch_text,
                user_id=book.user_id,
                book_id=book.id,
                known_characters=roster_snapshot,
                # Usage control owns an independent short-lived session.
                usage_db=None,
                language=book.language,
                discovery_only=True,
            )

    extraction_results = await asyncio.gather(
        *(_extract_with_limit(batch_text) for batch_text in extraction_batch_texts),
        return_exceptions=True,
    )
    cancelled = next(
        (result for result in extraction_results if isinstance(result, asyncio.CancelledError)),
        None,
    )
    if cancelled is not None:
        raise cancelled
    source_coverage["batch_outcomes"] = [
        {
            "batch_index": batch_index,
            "status": "failed" if isinstance(result, Exception) else "succeeded",
            **({"error_type": type(result).__name__} if isinstance(result, Exception) else {}),
        }
        for batch_index, result in enumerate(extraction_results, start=1)
    ]
    failed_batches = [result for result in extraction_results if isinstance(result, Exception)]
    if failed_batches:
        source_coverage["complete"] = False
        source_coverage["failure_stage"] = "character_discovery"
        if on_incomplete_batch is not None:
            await on_incomplete_batch(source_coverage)
        for batch_index, result in enumerate(extraction_results, start=1):
            if isinstance(result, Exception):
                log.warning(
                    "character_extraction_batch_incomplete book_id=%s chapter=%s batch=%s error_type=%s",
                    book.id,
                    chapter_number,
                    batch_index,
                    type(result).__name__,
                )
        raise failed_batches[0]

    extraction_failed_batches = 0
    extraction_fallback_batches = 0
    extraction_fallback_character_count = 0
    extraction_rejected_characters: list[dict[str, Any]] = []
    pending_relationships: list[dict[str, Any]] = []
    raw_character_entities: list[dict[str, Any]] = []

    for batch_index, (batch_text, result) in enumerate(
        zip(extraction_batch_texts, extraction_results), start=1
    ):
        source_batch_key = f"{book.id}:{chapter_number}:{batch_index}"
        result = cast(dict[str, Any], result)
        _append_rejected_character_reports(
            extraction_rejected_characters, result.get("rejected_characters")
        )

        character_entities = [
            entity
            for entity in result.get("characters", [])
            if isinstance(entity, dict) and entity.get("name")
        ]
        for entity in character_entities:
            entity_copy = dict(entity)
            entity_copy["_source_batch_key"] = source_batch_key
            source_names = [str(entity_copy["name"]), *(entity_copy.get("aliases") or [])]
            entity_copy["_source_windows"] = [
                {"start": start, "text": batch_text[start:end]}
                for start, end in source_excerpt_ranges_around_names(
                    batch_text,
                    source_names,
                )
            ]
            if entity_copy["_source_windows"]:
                excerpt_start, excerpt_end = source_excerpt_range_around_name(
                    batch_text, source_names
                )
                entity_copy["_source_start"] = excerpt_start
                entity_copy["_source_text"] = batch_text[excerpt_start:excerpt_end]
            else:
                entity_copy["_source_start"] = None
                entity_copy["_source_text"] = ""
            entity_copy["_source_mentions"] = source_mention_spans_in_batch(
                batch_text,
                source_names,
                source_ranges_by_batch[batch_index],
            )
            raw_character_entities.append(entity_copy)

        for rel in result.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            if not rel.get("character_a") or not rel.get("character_b"):
                continue
            relationship_evidence = grounded_relationship_evidence(rel, batch_text)
            pending_relationships.append(
                {
                    **rel,
                    "label_evidence": relationship_evidence or {},
                    "source_quote_verified": relationship_evidence is not None,
                    "source_batch_key": source_batch_key,
                }
            )

    aggregated_character_entities = cluster_character_entities(raw_character_entities)
    ambiguous_fragments = ambiguous_full_name_fragments(
        [
            *extraction_batch_texts,
            *(
                str(name)
                for character in roster_snapshot
                for name in [character.get("name"), *(character.get("aliases") or [])]
                if name
            ),
        ]
    )
    for entity in aggregated_character_entities:
        if str(entity.get("name") or "").casefold() in ambiguous_fragments:
            evidence = dict(entity.get("evidence") or {})
            evidence["ambiguous_full_name_fragment"] = True
            entity["evidence"] = evidence
    try:
        aggregated_character_entities = await enrich_chapter_character_profiles(
            aggregated_character_entities,
            user_id=book.user_id,
            book_id=book.id,
            language=book.language,
        )
    except Exception as exc:
        source_coverage["complete"] = False
        source_coverage["failure_stage"] = "character_profile_enrichment"
        source_coverage["profile_enrichment"] = {
            "status": "failed",
            "error_type": type(exc).__name__,
        }
        if on_incomplete_batch is not None:
            await on_incomplete_batch(source_coverage)
        log.warning(
            "character_profile_enrichment_incomplete book_id=%s chapter=%s error_type=%s",
            book.id,
            chapter_number,
            type(exc).__name__,
        )
        raise
    unanchored_profiles = sum(
        entity.get("evidence", {}).get("profile_enrichment_status") == "unanchored_reference"
        for entity in aggregated_character_entities
    )
    invalid_response_batches = sum(
        int(entity.get("evidence", {}).get("profile_enrichment_invalid_batches") or 0)
        for entity in aggregated_character_entities
    )
    profile_enrichment = {
        "status": "partial" if unanchored_profiles or invalid_response_batches else "complete",
        "identity_clusters": len(aggregated_character_entities),
        "evidence_passages": sum(
            len(profile_evidence_packets(entity)) for entity in aggregated_character_entities
        ),
        "unanchored_references": unanchored_profiles,
    }
    if invalid_response_batches:
        profile_enrichment["invalid_response_batches"] = invalid_response_batches
    source_coverage["profile_enrichment"] = profile_enrichment

    return ChapterLlmExtractionResult(
        extraction_batch_texts=extraction_batch_texts,
        source_coverage=source_coverage,
        extraction_failed_batches=extraction_failed_batches,
        extraction_fallback_batches=extraction_fallback_batches,
        extraction_fallback_character_count=extraction_fallback_character_count,
        extraction_rejected_characters=extraction_rejected_characters,
        pending_relationships=pending_relationships,
        raw_character_entities=raw_character_entities,
        aggregated_character_entities=aggregated_character_entities,
    )
