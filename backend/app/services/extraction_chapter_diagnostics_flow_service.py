import logging
from typing import Any

from app.services.character_identity.repair import CharacterIdentityRepairJob
from app.services.extraction_chapter_diagnostics_service import (
    build_chapter_character_extraction_diagnostics,
)
from app.services.extraction_first_chapter_service import backfill_pending_first_chapter_mentions
from app.services.extraction_relationship_service import _persist_relationship_records
from app.services.extraction_voice_profile_service import refresh_chapter_voice_profiles
from app.utils.characters.duplicates import refresh_character_duplicate_suggestions
from app.utils.ingestion_utils import elapsed_ms

log = logging.getLogger("lorevia.extraction")


async def build_post_llm_chapter_diagnostics(
    db,
    *,
    book,
    ch_data: dict,
    chapter_number: int,
    existing_characters: list[Any],
    llm_extraction: Any,
    llm_started: float,
    pending_relationships: list[dict[str, Any]],
    character_key_cache: dict[Any, set[str]],
    persisted_relationship_signatures: set[Any],
    pending_first_chapter_candidates: dict[Any, list[str]],
    pending_first_chapter_updates: dict[Any, Any],
    raw_character_entities: list[dict[str, Any]],
    aggregated_entities: list[dict[str, Any]],
    saved_character_count: int,
    quarantined_candidate_count: int,
    ambiguous_entity_count: int,
    strict_hold_count: int,
    reconciled_first_name_alias_count: int,
    chapter_media_count: int,
    media_marker_count: int,
) -> Any:
    await refresh_chapter_voice_profiles(
        db,
        book=book,
        chapter_text=str(ch_data.get("text") or ""),
        existing_characters=existing_characters,
    )

    log.info(
        "ingestion_timing stage=llm_extract book_id=%s chapter=%s elapsed_ms=%s batches=%s",
        book.id,
        chapter_number,
        elapsed_ms(llm_started),
        llm_extraction.batch_count,
    )
    (
        persisted_relationship_count,
        unresolved_relationships,
        relationship_review_candidate_count,
    ) = await _persist_relationship_records(
        db,
        book_id=book.id,
        chapter_number=chapter_number,
        existing_characters=existing_characters,
        relationships=pending_relationships,
        key_cache=character_key_cache,
        persisted_signatures=persisted_relationship_signatures,
    )
    repair_result = await CharacterIdentityRepairJob(db, book_id=book.id).apply()
    duplicate_suggestions = await refresh_character_duplicate_suggestions(
        db, book_id=book.id, characters=existing_characters
    )
    await backfill_pending_first_chapter_mentions(
        db,
        book_id=book.id,
        chapter_number=chapter_number,
        pending_first_chapter_candidates=pending_first_chapter_candidates,
        pending_first_chapter_updates=pending_first_chapter_updates,
    )
    return await build_chapter_character_extraction_diagnostics(
        db,
        book,
        chapter_number=chapter_number,
        extraction_batch_texts=llm_extraction.extraction_batch_texts,
        extraction_failed_batches=llm_extraction.extraction_failed_batches,
        extraction_fallback_batches=llm_extraction.extraction_fallback_batches,
        extraction_fallback_character_count=llm_extraction.extraction_fallback_character_count,
        raw_character_entities=raw_character_entities,
        aggregated_entities=aggregated_entities,
        saved_character_count=saved_character_count,
        quarantined_candidate_count=quarantined_candidate_count,
        ambiguous_entity_count=ambiguous_entity_count,
        strict_hold_count=strict_hold_count,
        extraction_rejected_characters=llm_extraction.extraction_rejected_characters,
        unresolved_relationships=unresolved_relationships,
        relationship_review_candidate_count=relationship_review_candidate_count,
        persisted_relationship_count=persisted_relationship_count,
        duplicate_suggestions=duplicate_suggestions,
        repair_result=repair_result,
        reconciled_first_name_alias_count=reconciled_first_name_alias_count,
        chapter_media_count=chapter_media_count,
        media_marker_count=media_marker_count,
    )
