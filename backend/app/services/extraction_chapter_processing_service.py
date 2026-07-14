"""
Full book processing: parse -> chunk -> extract characters + relationships -> embed.
Lazy: first N chapters immediately, rest queued.
"""

import logging
import re
import time
import uuid

from sqlalchemy import select

from app.core.redis import (
    cache_del,
    cache_set_if_absent,
    key_extraction_inflight,
)
from app.engine.character.deduplicator import character_name_keys
from app.models.character import Character
from app.models.user import User
from app.services.character_identity.resolver import reconcile_pending_first_name_alias_candidates
from app.services.extraction_chapter_diagnostics_flow_service import (
    build_post_llm_chapter_diagnostics,
)
from app.services.extraction_chapter_embedding_service import (
    persist_chapter_chunks_with_embeddings,
)
from app.services.extraction_chapter_llm_service import collect_chapter_llm_extraction
from app.services.extraction_chapter_progress_service import update_chapter_processing_progress
from app.services.extraction_chapter_record_service import stage_chapter_for_extraction
from app.services.extraction_chapter_content_service import (
    _prepare_chapter_rich_content,
)
from app.services.extraction_chapter_analysis_dispatch_service import (
    dispatch_chapter_analysis_after_extraction,
)
from app.services.extraction_character_resolution_service import (
    resolve_chapter_character_entities,
)
from app.services.extraction_processing_flow_service import (
    finalize_book_completion_after_chapter,
)
from app.services.extraction_relationship_service import (
    load_persisted_relationship_signatures,
)
from app.utils.ingestion_utils import (
    EXTRACTION_INFLIGHT_TTL_SECONDS,
    elapsed_ms,
    is_book_hidden,
    mark_book_processing_cancelled,
)

log = logging.getLogger("lorevia.extraction")


async def _process_chapter(
    db,
    book,
    ch_data: dict,
    queue_wait_ms: int | None = None,
    rebuild_run_id: str | None = None,
    manual_reprocess: bool = False,
):
    """Extract characters, relationships, store chunks for one chapter."""
    if await is_book_hidden(db, book.id):
        log.info("Skipping chapter processing for unavailable book %s", book.id)
        return

    from app.services.editor_project_service import get_rebuild_run_id

    active_rebuild_run_id = get_rebuild_run_id(book)
    if rebuild_run_id is not None and active_rebuild_run_id != rebuild_run_id:
        log.info("Skipping stale rebuild extraction book_id=%s", book.id)
        return
    if (
        getattr(book, "is_editor_project", False)
        and not active_rebuild_run_id
        and not manual_reprocess
    ):
        log.info("Skipping stale editor-project extraction book_id=%s", book.id)
        return

    ch_data = _prepare_chapter_rich_content(ch_data)
    chapter_number = int(ch_data["number"])
    inflight_key = key_extraction_inflight(str(book.id), chapter_number)
    if not await cache_set_if_absent(
        inflight_key,
        {"book_id": str(book.id), "chapter_number": chapter_number},
        EXTRACTION_INFLIGHT_TTL_SECONDS,
    ):
        log.info(
            "Skipping duplicate extraction in-flight book_id=%s chapter=%s", book.id, chapter_number
        )
        return

    try:
        started_at = time.perf_counter()
        user = await db.get(User, book.user_id)
        db_load_started = time.perf_counter()
        chapter = await stage_chapter_for_extraction(db, book, ch_data, chapter_number)
        log.info(
            "ingestion_timing stage=chapter_db_load book_id=%s chapter=%s elapsed_ms=%s",
            book.id,
            chapter_number,
            elapsed_ms(db_load_started),
        )
        log.info(
            "ingestion_timing stage=chapter_queue_wait book_id=%s chapter=%s queue_wait_ms=%s",
            book.id,
            chapter_number,
            queue_wait_ms,
        )

        chunks = await persist_chapter_chunks_with_embeddings(
            db,
            book=book,
            chapter=chapter,
            chapter_number=chapter_number,
            ch_data=ch_data,
        )

        existing_characters = (
            (
                await db.execute(
                    select(Character)
                    .where(Character.book_id == book.id)
                    .order_by(Character.first_chapter, Character.created_at)
                )
            )
            .scalars()
            .all()
        )
        character_key_cache: dict[uuid.UUID, set[str]] = {
            char.id: character_name_keys(char.name, char.aliases or [])
            for char in existing_characters
            if char.id is not None
        }

        llm_started = time.perf_counter()
        llm_extraction = await collect_chapter_llm_extraction(
            db,
            book=book,
            chapter_number=chapter_number,
            chunks=chunks,
            existing_characters=existing_characters,
        )
        pending_relationships = llm_extraction.pending_relationships
        reconciled_first_name_alias_count = 0
        chapter_media_count = len(ch_data.get("images") or [])
        media_marker_count = len(
            re.findall(r"\[\[IMAGE:[^\]]+\]\]", str(ch_data.get("text") or ""))
        )
        persisted_relationship_signatures = await load_persisted_relationship_signatures(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
        )

        raw_character_entities = llm_extraction.raw_character_entities
        character_resolution = await resolve_chapter_character_entities(
            db,
            book=book,
            chapter_number=chapter_number,
            existing_characters=existing_characters,
            character_key_cache=character_key_cache,
            raw_character_entities=raw_character_entities,
        )
        aggregated_entities = character_resolution.aggregated_entities
        pending_first_chapter_candidates = (
            character_resolution.pending_first_chapter_candidates
        )
        pending_first_chapter_updates = character_resolution.pending_first_chapter_updates
        saved_character_count = character_resolution.saved_character_count
        quarantined_candidate_count = character_resolution.quarantined_candidate_count
        ambiguous_entity_count = character_resolution.ambiguous_entity_count
        strict_hold_count = character_resolution.strict_hold_count

        reconciled_first_name_alias_count = await reconcile_pending_first_name_alias_candidates(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
        )

        extraction_diagnostics = await build_post_llm_chapter_diagnostics(
            db,
            book=book,
            ch_data=ch_data,
            chapter_number=chapter_number,
            existing_characters=existing_characters,
            llm_extraction=llm_extraction,
            llm_started=llm_started,
            pending_relationships=pending_relationships,
            character_key_cache=character_key_cache,
            persisted_relationship_signatures=persisted_relationship_signatures,
            pending_first_chapter_candidates=pending_first_chapter_candidates,
            pending_first_chapter_updates=pending_first_chapter_updates,
            raw_character_entities=raw_character_entities,
            aggregated_entities=aggregated_entities,
            saved_character_count=saved_character_count,
            quarantined_candidate_count=quarantined_candidate_count,
            ambiguous_entity_count=ambiguous_entity_count,
            strict_hold_count=strict_hold_count,
            reconciled_first_name_alias_count=reconciled_first_name_alias_count,
            chapter_media_count=chapter_media_count,
            media_marker_count=media_marker_count,
        )

        if await is_book_hidden(db, book.id):
            await mark_book_processing_cancelled(
                db,
                book,
                stage="chapter_extract",
                rollback=True,
                queue_wait_ms=queue_wait_ms,
                chapter_number=chapter_number,
                chapter_title=chapter.title,
                last_error="Book was removed while processing.",
            )
            return

        commit_started = time.perf_counter()
        await db.commit()
        log.info(
            "ingestion_timing stage=chapter_db_commit book_id=%s chapter=%s elapsed_ms=%s",
            book.id,
            chapter_number,
            elapsed_ms(commit_started),
        )

        processed_count, processing_total = await update_chapter_processing_progress(
            db,
            book=book,
            chapter=chapter,
            chapter_number=chapter_number,
            queue_wait_ms=queue_wait_ms,
            extraction_diagnostics=extraction_diagnostics,
        )

        await finalize_book_completion_after_chapter(
            db,
            book=book,
            chapter=chapter,
            chapter_number=chapter_number,
            processed_count=processed_count,
            processing_total=processing_total,
            queue_wait_ms=queue_wait_ms,
            extraction_diagnostics=extraction_diagnostics,
        )

        await dispatch_chapter_analysis_after_extraction(
            db,
            book=book,
            chapter=chapter,
            chapter_number=chapter_number,
            rebuild_run_id=rebuild_run_id,
            manual_reprocess=manual_reprocess,
        )

        log.info(
            "ingestion_timing stage=chapter_total book_id=%s chapter=%s elapsed_ms=%s",
            book.id,
            chapter_number,
            elapsed_ms(started_at),
        )
    finally:
        await cache_del(inflight_key)
