"""
Full book processing: parse -> chunk -> extract characters + relationships -> embed.
Lazy: first N chapters immediately, rest queued.
"""
import asyncio
import logging
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy import update as sa_update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.storage import download_book, upload_binary
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.deduplicator import (
    character_name_keys,
    embed_for_dedup,
    find_similar,
    merge_alias,
    names_equivalent,
)
from app.engine.character.extractor import extract_characters_and_relationships
from app.engine.character.profile_builder import build_character_profile, update_profile
from app.engine.embeddings.embedder import embed_batch
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import BookChunk, CharacterRelationship, Notification
from app.models.user import User
from app.parsers.chunker import ChunkingConfig, chunk_text, count_tokens
from app.services.email_service import send_processing_complete_with_stats
from app.utils.billing_utils import has_paid_reading_access
from app.utils.book_utils import parse_book_upload_for_ingestion, refresh_screenplay_scene_rows
from app.utils.character_utils import find_earliest_character_mention_chapter
from app.utils.compliance.copyright_check import check_isbn
from app.utils.external.isbn_lookup import extract_isbn_from_pdf
from app.utils.ingestion_utils import (
    apply_chapter_number_strategy,
    build_chapter_dispatch_plan,
    chunked,
    elapsed_ms,
    get_processing_started_at,
    is_book_hidden,
    mark_book_processing_cancelled,
    persist_chapter_payloads,
    update_book_processing_state,
)
from app.utils.intelligence_utils import (
    compute_voice_metrics,
    extract_dialogue_samples_by_character,
    merge_voice_profile_metrics,
)
from app.utils.notification_utils import build_book_ready_notification, collect_book_ready_stats
from app.utils.queue_utils import queue_for_user

log = logging.getLogger("lorevia.extraction")
AUTO_SAVE_CONFIDENCE = 0.78
SINGLE_MENTION_SAVE_CONFIDENCE = 0.90
MIN_EXISTING_UPDATE_CONFIDENCE = 0.55


async def process_book(book_id: str, queue_wait_ms: int | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        started_at = time.perf_counter()
        processing_started_at = datetime.now(UTC)
        book = await db.get(Book, uuid.UUID(book_id))
        if not book:
            return {"error": "not found"}

        if book.hidden_at is not None:
            log.info("Skipping processing for hidden book %s", book_id)
            return {"skipped": "book_hidden"}

        book.status = "processing"
        book.writer_workspace = update_book_processing_state(
            book,
            status="processing",
            stage="queued",
            total_chapters=book.total_chapters,
            completed_chapters=0,
            started_at=processing_started_at,
            queue_wait_ms=queue_wait_ms,
        )
        await db.commit()

        download_started = time.perf_counter()
        raw = await asyncio.to_thread(download_book, book.s3_key)
        log.info(
            "ingestion_timing stage=download book_id=%s elapsed_ms=%s queue_wait_ms=%s",
            book_id,
            elapsed_ms(download_started),
            queue_wait_ms,
        )

        if book.format == "pdf" and not book.cover_s3_key:
            from app.parsers.pdf_parser import extract_first_page_cover

            try:
                cover = await asyncio.to_thread(extract_first_page_cover, raw)
                if cover:
                    cover_bytes, content_type = cover
                    book.cover_s3_key = await asyncio.to_thread(
                        upload_binary,
                        f"covers/{book.user_id}/{uuid.uuid4()}.png",
                        cover_bytes,
                        content_type,
                    )
            except Exception:
                log.warning("cover_extraction_upload_failed book_id=%s", book_id, exc_info=True)

        if book.is_public and book.format == "pdf" and not book.isbn:
            detected_isbn = extract_isbn_from_pdf(raw)
            if detected_isbn:
                book.isbn = detected_isbn
        if book.is_public and book.isbn:
            copyright_info = await check_isbn(book.isbn)
            book.copyright_warning = bool(copyright_info.get("found", False))
        await db.commit()

        parse_started = time.perf_counter()
        parsed_payload = await parse_book_upload_for_ingestion(
            format_name=book.format,
            work_type=book.work_type,
            raw=raw,
            preserve_chapter_numbers=book.preserve_chapter_numbers,
            preserve_source_chapters=book.preserve_source_chapters,
        )
        chapters = cast(list[dict[str, Any]], parsed_payload["chapters"])
        screenplay_payload = cast(dict[str, Any] | None, parsed_payload.get("screenplay_payload"))
        parser_diagnostics = cast(dict[str, Any] | None, parsed_payload.get("parser_diagnostics"))
        all_chapters = apply_chapter_number_strategy(
            chapters,
            preserve_chapter_numbers=(book.preserve_chapter_numbers or book.preserve_source_chapters) and book.work_type != "screenplay",
            generic_titles=book.work_type != "screenplay" and not (book.preserve_chapter_numbers or book.preserve_source_chapters),
        )
        log.info(
            "ingestion_timing stage=parse book_id=%s elapsed_ms=%s chapters=%s",
            book_id,
            elapsed_ms(parse_started),
            len(all_chapters),
        )

        if await is_book_hidden(db, book.id):
            await mark_book_processing_cancelled(
                db,
                book,
                stage="parse",
                queue_wait_ms=queue_wait_ms,
                last_error="Book was removed while processing.",
            )
            return {"skipped": "book_hidden"}

        user = await db.get(User, book.user_id)

        full_tokens = sum(count_tokens(ch["text"]) for ch in all_chapters)
        processed_tokens = full_tokens
        was_truncated = False
        ai_chapters = all_chapters

        if user and not has_paid_reading_access(user):
            result = await db.execute(
                select(func.sum(Book.total_tokens))
                .where(Book.user_id == user.id, Book.id != book.id, Book.status != "error")
            )
            used_so_far = result.scalar() or 0
            remaining_budget = max(0, settings.FREE_TOTAL_TOKEN_BUDGET - used_so_far)

            if remaining_budget == 0:
                log.warning("User %s has exhausted free token budget: %s used.", book.user_id, used_so_far)
                await db.execute(sa_update(Book).where(Book.id == book.id).values(status="error", total_tokens=0))
                await db.commit()
                return {"error": "budget_exhausted"}

            partial_chapters: list[dict] = []
            current_sum = 0
            for ch in all_chapters:
                ch_toks = count_tokens(ch["text"])
                if current_sum + ch_toks <= remaining_budget:
                    partial_chapters.append(ch)
                    current_sum += ch_toks
                else:
                    was_truncated = True
                    break

            if not partial_chapters:
                log.warning("Remaining budget (%s) too small for even first chapter.", remaining_budget)
                await db.execute(sa_update(Book).where(Book.id == book.id).values(status="error", total_tokens=0))
                await db.commit()
                return {"error": "insufficient_remaining_budget"}

            ai_chapters = partial_chapters
            processed_tokens = current_sum

        await db.execute(
            sa_update(Book)
            .where(Book.id == book.id)
            .values(
                total_chapters=len(all_chapters),
                total_tokens=processed_tokens,
                is_truncated=was_truncated,
                writer_workspace=update_book_processing_state(
                    book,
                    status="processing",
                    stage="parsed",
                    total_chapters=len(all_chapters),
                    completed_chapters=0,
                    started_at=processing_started_at,
                    queue_wait_ms=queue_wait_ms,
                    parser_diagnostics=parser_diagnostics,
                ),
            )
        )
        await db.commit()

        stage_started = time.perf_counter()
        stored_chapter_keys = await persist_chapter_payloads(
            book.id,
            all_chapters,
            concurrency=settings.INGESTION_CHAPTER_UPLOAD_CONCURRENCY,
        )

        if await is_book_hidden(db, book.id):
            await mark_book_processing_cancelled(
                db,
                book,
                stage="staged",
                queue_wait_ms=queue_wait_ms,
                last_error="Book was removed while processing.",
            )
            return {"skipped": "book_hidden"}

        for ch_data in all_chapters:
            await _ensure_chapter_stub(
                db,
                book,
                ch_data,
                s3_key=stored_chapter_keys.get(int(ch_data["number"]), ""),
            )
        if screenplay_payload is not None:
            await refresh_screenplay_scene_rows(
                db,
                book=book,
                parsed_scenes=cast(list[Any], screenplay_payload["scenes"]),
            )
        await db.commit()
        log.info(
            "ingestion_timing stage=stage_chapters book_id=%s elapsed_ms=%s stored=%s",
            book_id,
            elapsed_ms(stage_started),
            len(stored_chapter_keys),
        )

        if await is_book_hidden(db, book.id):
            await mark_book_processing_cancelled(
                db,
                book,
                stage="staged",
                rollback=True,
                queue_wait_ms=queue_wait_ms,
                last_error="Book was removed while processing.",
            )
            return {"skipped": "book_hidden"}

        from app.workers.tasks.extraction_tasks import process_chapter_task

        dispatch_plan = build_chapter_dispatch_plan(
            [int(ch_data["number"]) for ch_data in ai_chapters],
            eager_limit=settings.LAZY_PROCESS_INITIAL_CHAPTERS,
            dispatch_window=settings.INGESTION_CHAPTER_DISPATCH_WINDOW,
            dispatch_delay_seconds=settings.INGESTION_CHAPTER_DISPATCH_DELAY_SECONDS,
        )
        queue_started = time.perf_counter()
        for dispatch in dispatch_plan:
            if await is_book_hidden(db, book.id):
                await mark_book_processing_cancelled(
                    db,
                    book,
                    stage="queue_chapters",
                    queue_wait_ms=queue_wait_ms,
                    last_error="Book was removed while processing.",
                )
                return {"skipped": "book_hidden"}
            process_chapter_task.apply_async(
                args=[str(book.id), dispatch.chapter_number],
                queue=queue_for_user(user, "extraction") if user else "extraction",
                countdown=dispatch.countdown,
            )
        log.info(
            "ingestion_timing stage=queue_chapters book_id=%s elapsed_ms=%s queued=%s",
            book_id,
            elapsed_ms(queue_started),
            len(dispatch_plan),
        )

        if await is_book_hidden(db, book.id):
            await mark_book_processing_cancelled(
                db,
                book,
                stage="queue_complete",
                queue_wait_ms=queue_wait_ms,
                last_error="Book was removed while processing.",
            )
            return {"skipped": "book_hidden"}

        if was_truncated:
            book.status = "ready"
            await db.commit()

        if settings.DEBUG:
            log.info("book_processed %s chapters=%s", book_id, len(all_chapters))
        log.info(
            "ingestion_timing stage=process_book_total book_id=%s elapsed_ms=%s processed_chapters=%s truncated=%s",
            book_id,
            elapsed_ms(started_at),
            len(ai_chapters),
            was_truncated,
        )
        return {"book_id": book_id, "chapters": len(all_chapters)}


async def _process_chapter(db, book, ch_data: dict, queue_wait_ms: int | None = None):
    """Extract characters, relationships, store chunks for one chapter."""
    if book.hidden_at is not None:
        log.info("Skipping chapter processing for hidden book %s", book.id)
        return

    chapter_number = int(ch_data["number"])
    started_at = time.perf_counter()
    user = await db.get(User, book.user_id)
    db_load_started = time.perf_counter()
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar()
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

    s3_key = chapter.s3_key if chapter is not None else ""
    if chapter is None:
        chapter = Chapter(
            book_id=book.id,
            number=chapter_number,
            content_version=int(ch_data.get("content_version") or 1),
            title=ch_data.get("title"),
            description=ch_data.get("description"),
            s3_key=s3_key,
            word_count=_count_words(ch_data.get("text", "")),
            processed=True,
        )
        db.add(chapter)
        await db.flush()
        await _sync_chapter_media(db, book, chapter, ch_data)
    else:
        chapter_changed = False
        if ch_data.get("title") and chapter.title != ch_data["title"]:
            chapter.title = ch_data["title"]
            chapter_changed = True
        if ch_data.get("description") and chapter.description != ch_data["description"]:
            chapter.description = ch_data["description"]
            chapter_changed = True
        if not chapter.processed:
            chapter.processed = True
            chapter_changed = True
        next_word_count = _count_words(ch_data.get("text", ""))
        if next_word_count and chapter.word_count != next_word_count:
            chapter.word_count = next_word_count
            chapter_changed = True
        next_content_version = ch_data.get("content_version")
        if next_content_version is not None and int(chapter.content_version or 1) != int(next_content_version):
            chapter.content_version = int(next_content_version)
            chapter_changed = True
        if chapter_changed:
            await db.flush()
        await _sync_chapter_media(db, book, chapter, ch_data)

    assert chapter is not None
    await db.execute(delete(BookChunk).where(BookChunk.chapter_id == chapter.id))

    chunk_started = time.perf_counter()
    chunks = chunk_text(
        ch_data["text"],
        config=ChunkingConfig(
            target_tokens=settings.CHUNK_TARGET_TOKENS,
            max_tokens=settings.CHUNK_MAX_TOKENS,
            min_tokens=settings.CHUNK_MIN_TOKENS,
            overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
            overlap_ratio=settings.CHUNK_OVERLAP_RATIO,
        ),
    )
    log.info(
        "ingestion_timing stage=chunk book_id=%s chapter=%s elapsed_ms=%s chunks=%s",
        book.id,
        chapter_number,
        elapsed_ms(chunk_started),
        len(chunks),
    )

    embed_started = time.perf_counter()
    chunk_batches = chunked(chunks, settings.EXTRACTION_EMBED_BATCH_SIZE)
    embed_semaphore = asyncio.Semaphore(
        max(1, min(settings.EXTRACTION_EMBED_CONCURRENCY, len(chunk_batches) or 1))
    )

    async def _embed_with_limit(batch: list[str]) -> list[list[float]]:
        async with embed_semaphore:
            return await embed_batch(
                batch,
                user_id=book.user_id,
                book_id=book.id,
                feature="chapter_chunk_embedding",
            )

    embedded_batches = await asyncio.gather(*(_embed_with_limit(batch) for batch in chunk_batches))
    chunk_embeddings = [embedding for batch in embedded_batches for embedding in batch]
    log.info(
        "ingestion_timing stage=embed book_id=%s chapter=%s elapsed_ms=%s batches=%s",
        book.id,
        chapter_number,
        elapsed_ms(embed_started),
        len(chunk_batches),
    )

    for index, (chunk_text_val, emb) in enumerate(zip(chunks, chunk_embeddings)):
        db.add(
            BookChunk(
                book_id=book.id,
                chapter_id=chapter.id,
                chunk_index=index,
                text=chunk_text_val,
                embedding=emb,
                token_count=len(chunk_text_val.split()),
            )
        )

    existing_characters = (
        await db.execute(
            select(Character).where(Character.book_id == book.id).order_by(Character.first_chapter, Character.created_at)
        )
    ).scalars().all()

    llm_started = time.perf_counter()
    extraction_batches = _group_chunks_for_extraction(chunks)
    extraction_results = await asyncio.gather(
        *(
            extract_characters_and_relationships(
                "\n\n".join(chunk_batch),
                user_id=book.user_id,
                book_id=book.id,
            )
            for chunk_batch in extraction_batches
        ),
        return_exceptions=True,
    )

    for result in extraction_results:
        if isinstance(result, Exception):
            continue
        result = cast(dict[str, Any], result)

        character_entities = [
            entity
            for entity in result.get("characters", [])
            if isinstance(entity, dict) and entity.get("name")
        ]
        for entity in character_entities:
            blocked_ids = _blocked_character_ids(existing_characters, entity)
            existing_id = _find_character_id_in_cache(
                existing_characters,
                entity["name"],
                entity.get("aliases", []),
                blocked_ids=blocked_ids,
            )

            if existing_id:
                if not _should_update_existing_character(entity):
                    continue
                char = await db.get(Character, existing_id)
                if char:
                    updated = update_profile(char, {**entity, "first_chapter": chapter_number})
                    earliest_chapter = await find_earliest_character_mention_chapter(
                        db,
                        book_id=book.id,
                        name=char.name,
                        aliases=updated.get("aliases") or char.aliases or [],
                        upto_chapter=chapter_number,
                    )
                    if earliest_chapter is not None:
                        updated["first_chapter"] = min(updated["first_chapter"], earliest_chapter)
                    changed = _changed(char.trait_state or {}, updated["trait_state"])
                    await db.execute(sa_update(Character).where(Character.id == existing_id).values(**updated))
                    if changed:
                        growth_event = entity.get("growth_event")
                        if isinstance(growth_event, dict):
                            growth_event = {**growth_event, "chapter": chapter_number}
                        db.add(
                            CharacterState(
                                character_id=existing_id,
                                at_chapter=chapter_number,
                                trait_snapshot=updated["trait_state"],
                                motivations_snapshot=updated.get("motivations") or [],
                                fears_snapshot=updated.get("fears") or [],
                                prompt_delta=_diff(char.trait_state or {}, updated["trait_state"]),
                                arc_note=entity.get("arc_summary"),
                                growth_event=growth_event if isinstance(growth_event, dict) else None,
                            )
                        )
                await merge_alias(db, existing_id, entity["name"])
            else:
                if not _can_auto_save_character(entity):
                    log.info(
                        "Rejected new character '%s' at save gate: confidence=%s evidence=%s",
                        entity.get("name"),
                        entity.get("confidence"),
                        entity.get("evidence"),
                    )
                    continue
                emb = await embed_for_dedup(entity["name"], entity.get("traits", {}))
                if not emb:
                    continue
                existing_id = await find_similar(
                    db,
                    book.id,
                    emb,
                    settings.DEDUP_SIMILARITY_THRESHOLD,
                    excluded_ids=blocked_ids,
                )
                if existing_id:
                    char = await db.get(Character, existing_id)
                    if char and _should_update_existing_character(entity):
                        updated = update_profile(char, {**entity, "first_chapter": chapter_number})
                        earliest_chapter = await find_earliest_character_mention_chapter(
                            db,
                            book_id=book.id,
                            name=char.name,
                            aliases=updated.get("aliases") or char.aliases or [],
                            upto_chapter=chapter_number,
                        )
                        if earliest_chapter is not None:
                            updated["first_chapter"] = min(updated["first_chapter"], earliest_chapter)
                        changed = _changed(char.trait_state or {}, updated["trait_state"])
                        await db.execute(sa_update(Character).where(Character.id == existing_id).values(**updated))
                        if changed:
                            growth_event = entity.get("growth_event")
                            if isinstance(growth_event, dict):
                                growth_event = {**growth_event, "chapter": chapter_number}
                            db.add(
                                CharacterState(
                                    character_id=existing_id,
                                    at_chapter=chapter_number,
                                    trait_snapshot=updated["trait_state"],
                                    motivations_snapshot=updated.get("motivations") or [],
                                    fears_snapshot=updated.get("fears") or [],
                                    prompt_delta=_diff(char.trait_state or {}, updated["trait_state"]),
                                    arc_note=entity.get("arc_summary"),
                                    growth_event=growth_event if isinstance(growth_event, dict) else None,
                                )
                            )
                    await merge_alias(db, existing_id, entity["name"])
                    continue
                profile = build_character_profile(entity, book.id, chapter_number)
                earliest_chapter = await find_earliest_character_mention_chapter(
                    db,
                    book_id=book.id,
                    name=profile["name"],
                    aliases=profile["aliases"],
                    upto_chapter=chapter_number,
                )
                if earliest_chapter is not None:
                    profile["first_chapter"] = min(profile["first_chapter"], earliest_chapter)
                char = Character(**profile, embedding=emb)
                db.add(char)
                await db.flush()
                existing_characters.append(char)

        for rel in result.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            if not rel.get("character_a") or not rel.get("character_b"):
                continue
            char_a = _find_character_in_cache(existing_characters, rel["character_a"])
            char_b = _find_character_in_cache(existing_characters, rel["character_b"])
            if char_a and char_b:
                db.add(
                    CharacterRelationship(
                        book_id=book.id,
                        character_a_id=char_a.id,
                        character_b_id=char_b.id,
                        rel_type=rel.get("type", "neutral"),
                        sentiment=rel.get("sentiment"),
                        description=rel.get("description"),
                        from_chapter=chapter_number,
                    )
                )

    dialogue_samples = extract_dialogue_samples_by_character(
        str(ch_data.get("text") or ""),
        [{"id": str(char.id), "name": char.name, "aliases": char.aliases or []} for char in existing_characters if char.name],
    )
    if dialogue_samples:
        existing_voice_profiles = (
            await db.execute(
                select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id)
            )
        ).scalars().all()
        profiles_by_character_id = {profile.character_id: profile for profile in existing_voice_profiles}
        for char in existing_characters:
            samples = dialogue_samples.get(char.name)
            if not samples:
                continue
            metrics = compute_voice_metrics(samples)
            if int(metrics.get("sample_dialogue_count") or 0) <= 0:
                continue
            current_profile = profiles_by_character_id.get(char.id)
            merged_metrics = merge_voice_profile_metrics(
                {
                    "sample_dialogue_count": current_profile.sample_dialogue_count if current_profile else 0,
                    "sample_word_count": current_profile.sample_word_count if current_profile else 0,
                    "avg_sentence_length": current_profile.avg_sentence_length if current_profile else 0,
                    "avg_word_length_x100": current_profile.avg_word_length_x100 if current_profile else 0,
                    "contraction_rate_x1000": current_profile.contraction_rate_x1000 if current_profile else 0,
                    "question_rate_x1000": current_profile.question_rate_x1000 if current_profile else 0,
                    "exclamation_rate_x1000": current_profile.exclamation_rate_x1000 if current_profile else 0,
                    "ellipsis_rate_x1000": current_profile.ellipsis_rate_x1000 if current_profile else 0,
                    "dash_rate_x1000": current_profile.dash_rate_x1000 if current_profile else 0,
                    "uppercase_rate_x1000": current_profile.uppercase_rate_x1000 if current_profile else 0,
                    "formality_score_x1000": current_profile.formality_score_x1000 if current_profile else 0,
                    "lexical_complexity_x1000": current_profile.lexical_complexity_x1000 if current_profile else 0,
                    "emotional_intensity_x1000": current_profile.emotional_intensity_x1000 if current_profile else 0,
                    "dominant_markers": current_profile.dominant_markers if current_profile else {},
                    "signature_phrases": current_profile.signature_phrases if current_profile else [],
                } if current_profile else None,
                metrics,
            )
            if current_profile is None:
                db.add(
                    CharacterVoiceProfile(
                        book_id=book.id,
                        character_id=char.id,
                        **merged_metrics,
                    )
                )
            else:
                for key, value in merged_metrics.items():
                    setattr(current_profile, key, value)

    log.info(
        "ingestion_timing stage=llm_extract book_id=%s chapter=%s elapsed_ms=%s batches=%s",
        book.id,
        chapter_number,
        elapsed_ms(llm_started),
        len(extraction_batches),
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

    processed_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Chapter).where(
                    Chapter.book_id == book.id,
                    Chapter.processed.is_(True),
                )
            )
        ).scalar_one()
    )
    processing_total = int(book.total_chapters or processed_count or 0) or None
    book.writer_workspace = update_book_processing_state(
        book,
        status="processing",
        stage="chapter_complete",
        total_chapters=processing_total,
        completed_chapters=processed_count,
        started_at=get_processing_started_at(book),
        queue_wait_ms=queue_wait_ms,
        chapter_number=chapter_number,
        chapter_title=chapter.title,
    )
    await db.commit()
    processing_state = book.writer_workspace.get("processing") if isinstance(book.writer_workspace, dict) else None
    log.info(
        "ingestion_progress book_id=%s chapter=%s completed=%s total=%s progress_pct=%s eta_seconds=%s queue_wait_ms=%s",
        book.id,
        chapter_number,
        processed_count,
        processing_total,
        (processing_state or {}).get("progress_pct") if isinstance(processing_state, dict) else None,
        (processing_state or {}).get("eta_seconds") if isinstance(processing_state, dict) else None,
        queue_wait_ms,
    )

    if await _should_consolidate_after_chapter(db, book, chapter.number):
        await consolidate_characters(db, book.id, up_to_chapter=chapter_number)
        await db.commit()

    if await _book_processing_complete(db, book.id):
        book.status = "ready"
        book.writer_workspace = update_book_processing_state(
            book,
            status="ready",
            stage="complete",
            total_chapters=processing_total,
            completed_chapters=processed_count,
            started_at=get_processing_started_at(book),
            queue_wait_ms=queue_wait_ms,
            chapter_number=chapter_number,
            chapter_title=chapter.title,
        )

        if book.mode == "author" and book.total_chapters:
            from app.models.progress import ReadingProgress

            progress_result = await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.user_id == book.user_id,
                    ReadingProgress.book_id == book.id,
                )
            )
            progress = progress_result.scalar()

            chapters_read = list(range(1, book.total_chapters + 1))
            if progress is None:
                progress = ReadingProgress(
                    user_id=book.user_id,
                    book_id=book.id,
                    current_chapter=book.total_chapters,
                    scroll_pct=1.0,
                    chapters_read=chapters_read,
                )
                db.add(progress)
            else:
                progress.current_chapter = book.total_chapters
                progress.scroll_pct = 1.0
                progress.chapters_read = chapters_read

        existing_ready_notification = (
            await db.execute(
                select(Notification).where(
                    Notification.book_id == book.id,
                    Notification.user_id == book.user_id,
                    Notification.kind == "book_ready",
                )
            )
        ).scalar()
        ready_stats = await collect_book_ready_stats(db, book)
        if existing_ready_notification is None:
            db.add(build_book_ready_notification(book, ready_stats))

        await db.commit()

        user = await db.get(User, book.user_id)
        if user and user.email and existing_ready_notification is None:
            await send_processing_complete_with_stats(
                user.email,
                book_title=book.title,
                character_count=ready_stats.character_count,
                relationship_count=ready_stats.relationship_count,
                plot_thread_count=ready_stats.plot_thread_count,
                continuity_issue_count=ready_stats.continuity_issue_count,
            )

    from app.workers.tasks.analysis_tasks import analyse_chapter_task

    analyse_chapter_task.apply_async(
        args=[str(chapter.id), ch_data["text"], ch_data.get("title") or ""],
        queue=queue_for_user(user, "analysis") if user else "analysis",
    )

    log.info(
        "ingestion_timing stage=chapter_total book_id=%s chapter=%s elapsed_ms=%s",
        book.id,
        chapter_number,
        elapsed_ms(started_at),
    )


async def _ensure_chapter_stub(db, book, ch_data: dict, *, s3_key: str):
    existing = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == ch_data["number"])
        )
    ).scalar()

    if existing is None:
        db.add(
            Chapter(
                book_id=book.id,
                number=ch_data["number"],
                title=ch_data.get("title"),
                description=ch_data.get("description"),
                s3_key=s3_key,
                token_count=count_tokens(ch_data["text"]),
                word_count=_count_words(ch_data.get("text", "")),
                processed=False,
            )
        )
        await db.flush()
        return

    changed = False
    if ch_data.get("title") and (not existing.title or not existing.title.strip()):
        existing.title = ch_data["title"]
        changed = True
    if ch_data.get("description") and (not existing.description or not existing.description.strip()):
        existing.description = ch_data["description"]
        changed = True
    if ch_data.get("text") and not existing.token_count:
        existing.token_count = count_tokens(ch_data["text"])
        changed = True
    if s3_key and existing.s3_key != s3_key:
        existing.s3_key = s3_key
        changed = True
    next_word_count = _count_words(ch_data.get("text", ""))
    if next_word_count and existing.word_count != next_word_count:
        existing.word_count = next_word_count
        changed = True
    if changed:
        await db.flush()


def _find_character_id_in_cache(
    chars: list[Character],
    name: str,
    aliases: list[str] | None,
    blocked_ids: set[uuid.UUID] | None = None,
) -> uuid.UUID | None:
    candidate_keys = character_name_keys(name, aliases or [])
    if not candidate_keys:
        return None

    for char in chars:
        if blocked_ids and char.id in blocked_ids:
            continue
        if candidate_keys & character_name_keys(char.name, char.aliases or []):
            return char.id
        if names_equivalent(name, aliases or [], char.name, char.aliases or []):
            return char.id
    return None


def _find_character_in_cache(chars: list[Character], name: str) -> Character | None:
    match_id = _find_character_id_in_cache(chars, name, [])
    if not match_id:
        return None
    return next((char for char in chars if char.id == match_id), None)


def _entity_evidence(entity: dict) -> dict:
    evidence = entity.get("evidence")
    return evidence if isinstance(evidence, dict) else {}


def _blocked_character_ids(chars: list[Character], entity: dict) -> set[uuid.UUID]:
    blocked_ids: set[uuid.UUID] = set()
    blocked_names = [name for name in (entity.get("anti_merge_names") or []) if isinstance(name, str) and name.strip()]
    if not blocked_names:
        return blocked_ids

    for blocked_name in blocked_names:
        blocked_keys = character_name_keys(blocked_name, [])
        for char in chars:
            if blocked_keys & character_name_keys(char.name, char.aliases or []):
                blocked_ids.add(char.id)
                continue
            if names_equivalent(blocked_name, [], char.name, char.aliases or []):
                blocked_ids.add(char.id)
    return blocked_ids


def _should_update_existing_character(entity: dict) -> bool:
    confidence = float(entity.get("confidence") or 0.0)
    if confidence >= AUTO_SAVE_CONFIDENCE:
        return True
    evidence = _entity_evidence(entity)
    return bool(confidence >= MIN_EXISTING_UPDATE_CONFIDENCE and (
        evidence.get("has_dialogue_or_action")
        or evidence.get("has_physical_description")
        or evidence.get("appears_multiple_times")
        or _has_character_profile_signal(entity)
    ))


def _has_character_profile_signal(entity: dict) -> bool:
    traits = entity.get("traits")
    if isinstance(traits, dict) and any(
        isinstance(value, dict) and str(value.get("value") or "").strip()
        for value in traits.values()
    ):
        return True
    if any(str(entity.get(field) or "").strip() for field in ("goal", "lie_they_believe", "backstory_wound", "arc_type", "arc_summary", "archetype")):
        return True
    if any(entity.get(field) for field in ("personality_tags", "motivations", "fears")):
        return True
    growth_event = entity.get("growth_event")
    return isinstance(growth_event, dict) and bool(str(growth_event.get("event") or "").strip())


def _can_auto_save_character(entity: dict) -> bool:
    entity_type = str(entity.get("entity_type") or "person").casefold()
    if entity_type not in {"person", "alias"}:
        return False

    confidence = float(entity.get("confidence") or 0.0)
    if confidence < AUTO_SAVE_CONFIDENCE:
        return False

    evidence = _entity_evidence(entity)
    mention_count = int(entity.get("mention_count") or evidence.get("mention_count") or 0)
    has_dialogue_or_action = bool(evidence.get("has_dialogue_or_action"))
    has_physical_description = bool(evidence.get("has_physical_description"))
    appears_multiple_times = bool(evidence.get("appears_multiple_times")) or mention_count >= 2
    has_profile_signal = _has_character_profile_signal(entity)

    if not (has_dialogue_or_action or has_physical_description or appears_multiple_times or has_profile_signal):
        return False

    if mention_count < 2 and not (
        confidence >= SINGLE_MENTION_SAVE_CONFIDENCE
        and (has_dialogue_or_action or has_physical_description or has_profile_signal)
    ):
        return False

    return True


async def _book_processing_complete(db, book_id: uuid.UUID) -> bool:
    remaining_count: int | None = await db.scalar(
        select(func.count()).select_from(Chapter).where(Chapter.book_id == book_id, Chapter.processed.is_(False))
    )
    return (remaining_count or 0) == 0


async def _should_consolidate_after_chapter(db, book: Book, chapter_number: int) -> bool:
    if chapter_number <= settings.LAZY_PROCESS_INITIAL_CHAPTERS:
        return True
    return await _book_processing_complete(db, book.id)


def _changed(old: dict, new: dict, delta: float = 0.15) -> bool:
    for key, value in new.items():
        if not isinstance(value, dict):
            continue
        old_conf = old.get(key, {}).get("confidence", 0) if isinstance(old.get(key), dict) else 0
        if value.get("confidence", 0) - old_conf >= delta:
            return True
    return False


def _diff(old: dict, new: dict) -> str:
    changes = []
    for key, value in new.items():
        if not isinstance(value, dict):
            continue
        old_v = old.get(key, {}).get("value") if isinstance(old.get(key), dict) else None
        new_v = value.get("value")
        if old_v and new_v and old_v != new_v:
            changes.append(f"{key}: {old_v}->{new_v}")
        elif not old_v and new_v:
            changes.append(f"+{key}: {new_v}")
    return "; ".join(changes[:5]) or "minor update"


def _group_chunks_for_extraction(chunks: list[str]) -> list[list[str]]:
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for chunk in chunks:
        chunk_tokens = count_tokens(chunk)
        exceeds_token_budget = current_tokens + chunk_tokens > settings.EXTRACTION_BATCH_MAX_TOKENS
        exceeds_chunk_budget = len(current_batch) >= settings.EXTRACTION_BATCH_MAX_CHUNKS

        if current_batch and (exceeds_token_budget or exceeds_chunk_budget):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(chunk)
        current_tokens += chunk_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def _count_words(text: str) -> int:
    cleaned = re.sub(r"\[\[IMAGE:[^\]]+\]\]", " ", text or "")
    return len(re.findall(r"\b[\w']+\b", cleaned))


async def _sync_chapter_media(db, book: Book, chapter: Chapter, ch_data: dict) -> None:
    images = ch_data.get("images") or []
    await db.execute(delete(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id))
    if not images:
        return

    for index, image in enumerate(images):
        raw = image.get("bytes")
        marker = image.get("marker")
        if not raw or not marker:
            continue
        filename = image.get("filename") or f"{uuid.uuid4().hex}.bin"
        storage_key = f"chapter-media/{book.id}/{chapter.number}/{index}-{filename}"
        await asyncio.to_thread(upload_binary, storage_key, raw, image.get("content_type"))
        db.add(
            ChapterMedia(
                book_id=book.id,
                chapter_id=chapter.id,
                marker=marker,
                asset_type="image",
                content_type=image.get("content_type"),
                storage_key=storage_key,
                caption=None,
                sort_order=index,
            )
        )
