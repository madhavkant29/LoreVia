"""
Full book processing: parse -> chunk -> extract characters + relationships -> embed.
Lazy: first N chapters immediately, rest queued.
"""

import logging
import re
import time
import uuid
from typing import Any

from sqlalchemy import select

from app.core.redis import (
    cache_del,
    cache_set_if_absent,
    key_extraction_inflight,
)
from app.engine.character.deduplicator import character_name_keys
from app.models.character import Character
from app.services.book_freeze_service import book_is_frozen, is_book_frozen
from app.services.character_identity.resolver import (
    reconcile_pending_first_name_alias_candidates,
)
from app.services.extraction_chapter_analysis_dispatch_service import (
    dispatch_chapter_analysis_after_extraction,
)
from app.services.extraction_chapter_content_service import (
    _prepare_chapter_rich_content,
)
from app.services.extraction_chapter_diagnostics_flow_service import (
    build_post_llm_chapter_diagnostics,
)
from app.services.extraction_chapter_embedding_service import (
    prepare_chapter_chunks_with_embeddings,
    replace_chapter_chunks,
)
from app.services.extraction_chapter_llm_service import collect_chapter_llm_extraction
from app.services.extraction_chapter_progress_service import (
    update_chapter_processing_progress,
)
from app.services.extraction_chapter_record_service import (
    replace_chapter_extraction_records,
    stage_chapter_for_extraction,
)
from app.services.extraction_character_mention_count_service import (
    reconcile_character_mention_counts,
)
from app.services.extraction_character_reporting_service import (
    precompute_chapter_character_embeddings,
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
    record_extraction_coverage_in_analysis_state,
    record_incomplete_extraction_attempt_in_analysis_state,
)

log = logging.getLogger("lorevia.extraction")


async def _process_chapter(
    db,
    book,
    ch_data: dict,
    queue_wait_ms: int | None = None,
    rebuild_run_id: str | None = None,
    manual_reprocess: bool = False,
    dispatch_analysis: bool = True,
    check_book_completion: bool = True,
) -> bool:
    from app.services.data_generation_service import generation_scope

    with generation_scope(rebuild_run_id):
        return await _process_chapter_in_generation(
            db,
            book,
            ch_data,
            queue_wait_ms=queue_wait_ms,
            rebuild_run_id=rebuild_run_id,
            manual_reprocess=manual_reprocess,
            dispatch_analysis=dispatch_analysis,
            check_book_completion=check_book_completion,
        )


async def _process_chapter_in_generation(
    db,
    book,
    ch_data: dict,
    queue_wait_ms: int | None = None,
    rebuild_run_id: str | None = None,
    manual_reprocess: bool = False,
    dispatch_analysis: bool = True,
    check_book_completion: bool = True,
) -> bool:
    """Extract characters, relationships, store chunks for one chapter."""
    if await is_book_hidden(db, book.id):
        log.info("Skipping chapter processing for unavailable book %s", book.id)
        return False
    if is_book_frozen(book):
        log.info("Skipping chapter processing for frozen book %s", book.id)
        return False

    from app.services.editor_project_service import get_rebuild_run_id

    active_rebuild_run_id = get_rebuild_run_id(book)
    if rebuild_run_id is not None and active_rebuild_run_id != rebuild_run_id:
        log.info("Skipping stale rebuild extraction book_id=%s", book.id)
        return False
    if (
        getattr(book, "is_editor_project", False)
        and not active_rebuild_run_id
        and not manual_reprocess
    ):
        log.info("Skipping stale editor-project extraction book_id=%s", book.id)
        return False

    ch_data = _prepare_chapter_rich_content(ch_data)
    chapter_number = int(ch_data["number"])
    inflight_key = key_extraction_inflight(str(book.id), chapter_number)
    if not await cache_set_if_absent(
        inflight_key,
        {"book_id": str(book.id), "chapter_number": chapter_number},
        EXTRACTION_INFLIGHT_TTL_SECONDS,
    ):
        log.info(
            "Skipping duplicate extraction in-flight book_id=%s chapter=%s",
            book.id,
            chapter_number,
        )
        return False

    try:
        started_at = time.perf_counter()
        db_load_started = time.perf_counter()
        chapter = await stage_chapter_for_extraction(
            db,
            book,
            ch_data,
            chapter_number,
            rebuild_existing_chapter=bool(rebuild_run_id),
        )
        # Stage/reset the chapter in a short transaction. Provider calls below
        # must not hold a checked-out connection or chapter locks.
        await db.commit()
        frozen_before_embedding = await book_is_frozen(db, book.id)
        await db.commit()
        if frozen_before_embedding:
            log.info(
                "Aborting frozen chapter extraction book_id=%s chapter=%s",
                book.id,
                chapter_number,
            )
            return False
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

        prepared_chunks = await prepare_chapter_chunks_with_embeddings(
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
        # The roster is safe to use after commit because worker sessions use
        # expire_on_commit=False. Release the read transaction before LLM I/O.
        await db.commit()
        character_key_cache: dict[uuid.UUID, set[str]] = {
            char.id: character_name_keys(char.name, char.aliases or [])
            for char in existing_characters
            if char.id is not None
        }

        llm_started = time.perf_counter()
        frozen_before_extraction = await book_is_frozen(db, book.id)
        await db.commit()
        if frozen_before_extraction:
            log.info(
                "Aborting frozen chapter extraction before LLM book_id=%s chapter=%s",
                book.id,
                chapter_number,
            )
            return False

        async def record_incomplete_batch(coverage: dict[str, Any]) -> None:
            try:
                chapter.analysis_state = record_incomplete_extraction_attempt_in_analysis_state(
                    chapter.analysis_state, coverage
                )
                await db.commit()
            except Exception as persistence_error:
                try:
                    await db.rollback()
                except Exception as rollback_error:
                    log.warning(
                        "character_extraction_failure_diagnostics_rollback_unavailable book_id=%s chapter=%s error_type=%s",
                        book.id,
                        chapter_number,
                        type(rollback_error).__name__,
                    )
                log.warning(
                    "character_extraction_failure_diagnostics_unavailable book_id=%s chapter=%s error_type=%s",
                    book.id,
                    chapter_number,
                    type(persistence_error).__name__,
                )

        llm_extraction = await collect_chapter_llm_extraction(
            db,
            book=book,
            chapter_number=chapter_number,
            # Embedding chunks may normalize whitespace; extraction provenance
            # must cover the stored chapter source itself, character for character.
            chunks=[str(ch_data.get("text") or "")],
            existing_characters=existing_characters,
            on_incomplete_batch=record_incomplete_batch,
        )
        frozen_before_character_embedding = await book_is_frozen(db, book.id)
        await db.commit()
        if frozen_before_character_embedding:
            log.info(
                "Aborting frozen chapter extraction before character embeddings book_id=%s chapter=%s",
                book.id,
                chapter_number,
            )
            return False
        # Embedding can wait on the provider. Prepare every proposed identity
        # before replacing source records so no chapter transaction stays open
        # across that wait. Resolution still decides which identities to save.
        precomputed_character_embeddings = await precompute_chapter_character_embeddings(
            llm_extraction.aggregated_character_entities,
            user_id=book.user_id,
            book_id=book.id,
        )
        frozen_after_character_embedding = await book_is_frozen(db, book.id)
        await db.commit()
        if frozen_after_character_embedding:
            log.info(
                "Aborting frozen chapter extraction after character embeddings book_id=%s chapter=%s",
                book.id,
                chapter_number,
            )
            return False
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
        await replace_chapter_chunks(
            db,
            prepared_chunks,
            chapter_id=chapter.id,
        )
        previous_mention_character_ids = await replace_chapter_extraction_records(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
            replace_generated_intelligence=manual_reprocess,
        )

        raw_character_entities = llm_extraction.raw_character_entities
        if await book_is_frozen(db, book.id):
            await db.rollback()
            log.info(
                "Aborting frozen chapter extraction before resolution book_id=%s chapter=%s",
                book.id,
                chapter_number,
            )
            return False
        character_resolution = await resolve_chapter_character_entities(
            db,
            book=book,
            chapter_number=chapter_number,
            existing_characters=existing_characters,
            character_key_cache=character_key_cache,
            raw_character_entities=raw_character_entities,
            aggregated_entities=llm_extraction.aggregated_character_entities,
            precomputed_embeddings=precomputed_character_embeddings,
        )
        aggregated_entities = character_resolution.aggregated_entities
        pending_first_chapter_candidates = character_resolution.pending_first_chapter_candidates
        pending_first_chapter_updates = character_resolution.pending_first_chapter_updates
        saved_character_count = character_resolution.saved_character_count
        quarantined_candidate_count = character_resolution.quarantined_candidate_count
        ambiguous_entity_count = character_resolution.ambiguous_entity_count
        strict_hold_count = character_resolution.strict_hold_count

        await reconcile_character_mention_counts(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
            previous_character_ids=previous_mention_character_ids,
            characters=existing_characters,
        )

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
            return False

        # Only expose the chapter as processed once all provider-backed
        # extraction and its database writes have succeeded. The staging
        # transaction deliberately leaves this false so another chapter
        # cannot finalize the book while this task is still running.
        chapter.analysis_state = record_extraction_coverage_in_analysis_state(
            chapter.analysis_state, llm_extraction.source_coverage
        )
        chapter.processed = True
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

        if check_book_completion:
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

        if dispatch_analysis:
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
        return True
    finally:
        await cache_del(inflight_key)
