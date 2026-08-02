from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, cast

from app.core.config import settings
from app.engine.character.extractor import (
    extract_characters_and_relationships,
    fallback_character_mentions,
)
from app.services.extraction_character_reporting_service import (
    _append_rejected_character_reports,
)
from app.services.extraction_processing_flow_service import _group_chunks_for_extraction
from app.utils.characters.serialization import build_character_roster_snapshot
from app.utils.llm_usage_utils import is_llm_call_error

log = logging.getLogger("lorevia.extraction")


@dataclass(slots=True)
class ChapterLlmExtractionResult:
    extraction_batch_texts: list[str]
    extraction_failed_batches: int
    extraction_fallback_batches: int
    extraction_fallback_character_count: int
    extraction_rejected_characters: list[dict[str, Any]]
    pending_relationships: list[dict[str, Any]]
    raw_character_entities: list[dict[str, Any]]

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
) -> ChapterLlmExtractionResult:
    """Run batched LLM extraction and return normalized chapter-level candidates."""
    roster_snapshot = build_character_roster_snapshot(existing_characters)
    extraction_batches = _group_chunks_for_extraction(chunks)
    extraction_batch_texts = ["\n\n".join(chunk_batch) for chunk_batch in extraction_batches]
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
            )

    extraction_results = await asyncio.gather(
        *(_extract_with_limit(batch_text) for batch_text in extraction_batch_texts),
        return_exceptions=True,
    )

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
        if isinstance(result, Exception):
            # A provider/control failure is not a signal to make another paid
            # call through the fallback path. All concurrent batches have
            # settled at this point, so it is safe for the caller to close DB.
            if is_llm_call_error(result):
                raise result
            extraction_failed_batches += 1
            log.warning(
                "character_extraction_batch_failed book_id=%s chapter=%s batch=%s",
                book.id,
                chapter_number,
                batch_index,
                exc_info=result,
            )
            result = await fallback_character_mentions(
                batch_text,
                user_id=book.user_id,
                book_id=book.id,
                usage_db=None,
                language=book.language,
            )
            extraction_fallback_batches += 1
            extraction_fallback_character_count += len(result.get("characters", []))

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
            entity_copy["_source_text"] = batch_text[:2200]
            raw_character_entities.append(entity_copy)

        for rel in result.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            if not rel.get("character_a") or not rel.get("character_b"):
                continue
            pending_relationships.append(
                {
                    **rel,
                    "source_batch_key": source_batch_key,
                }
            )

    return ChapterLlmExtractionResult(
        extraction_batch_texts=extraction_batch_texts,
        extraction_failed_batches=extraction_failed_batches,
        extraction_fallback_batches=extraction_fallback_batches,
        extraction_fallback_character_count=extraction_fallback_character_count,
        extraction_rejected_characters=extraction_rejected_characters,
        pending_relationships=pending_relationships,
        raw_character_entities=raw_character_entities,
    )
