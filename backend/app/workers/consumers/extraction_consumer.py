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
from app.core.redis import (
    INFLIGHT_BOOK_TTL_SECONDS,
    cache_del,
    cache_delete_if_owner,
    cache_set_if_absent,
    key_extraction_inflight,
    key_extraction_inflight_book,
)
from app.core.storage import download_book, upload_binary
from app.engine.character.deduplicator import (
    character_name_keys,
    find_similar,
    is_valid_alias,
    names_equivalent,
    resolve_character_match_id,
    resolve_character_match_ids,
)
from app.engine.character.entity_filters import CharacterPersistenceDecision, character_persistence_decision
from app.engine.character.extractor import extract_characters_and_relationships, fallback_character_mentions
from app.engine.character.profile_builder import build_character_profile, update_profile
from app.engine.embeddings.embedder import build_character_embedding_text, build_chunk_embedding_text, embed_batch
from app.models.book import Book, Chapter, ChapterMedia
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.intelligence import BookChunk, CharacterRelationship
from app.models.user import User
from app.parsers.chunker import ChunkingConfig, chunk_text, count_tokens
from app.services.email_service import send_processing_complete_with_stats
from app.utils.billing_utils import has_paid_reading_access
from app.utils.book_utils import parse_book_upload_for_ingestion, refresh_screenplay_scene_rows
from app.utils.character_utils import (
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
    CHARACTER_VISIBILITY_VISIBLE,
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_CANDIDATE_SUPPRESSED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED,
    build_character_mention_cluster_key,
    build_character_dossier_summary,
    can_auto_persist_character_candidate,
    cluster_character_entities,
    decide_character_candidate_disposition,
    decide_relationship_candidate_disposition,
    build_character_roster_snapshot,
    find_earliest_character_mention_chapters,
    is_cast_visible_character,
    is_role_only_character_name,
    normalize_character_name,
    record_character_candidate,
    record_character_mention,
    record_relationship_candidate,
    refresh_character_duplicate_suggestions,
    resolve_character_reference_from_roster,
)
from app.utils.compliance.copyright_check import evaluate_document_copyright
from app.utils.ingestion_utils import (
    apply_chapter_number_strategy,
    build_analysis_chapter_state,
    build_source_integrity_state,
    build_chapter_dispatch_plan,
    chunked,
    current_parser_diagnostics,
    elapsed_ms,
    EXTRACTION_INFLIGHT_TTL_SECONDS,
    get_processing_started_at,
    is_book_hidden,
    mark_book_processing_cancelled,
    persist_chapter_payloads,
    processing_state_for_completed_extraction,
    update_book_processing_state,
)
from app.utils.intelligence_utils import (
    compute_voice_metrics,
    extract_dialogue_samples_by_character,
    merge_voice_profile_metrics,
)
from app.utils.notification_utils import collect_book_ready_stats, upsert_book_ready_notification
from app.utils.queue_utils import queue_for_user
from app.utils.relationship_utils import (
    canonical_relationship_pair_key,
    relationship_state_signature,
    upsert_relationship_timeline_state,
)

log = logging.getLogger("lorevia.extraction")
AUTO_SAVE_CONFIDENCE = 0.78
SINGLE_MENTION_SAVE_CONFIDENCE = 0.90
MIN_EXISTING_UPDATE_CONFIDENCE = 0.55


def _relationship_signature(
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
    rel_type: str,
    sentiment: float | None,
    from_chapter: int,
    description: str | None,
) -> tuple[str, str, str, float | None, str, int]:
    left_id, right_id = canonical_relationship_pair_key(character_a_id, character_b_id)
    normalized_type, normalized_sentiment, normalized_description = relationship_state_signature(
        rel_type=rel_type or "neutral",
        sentiment=sentiment,
        description=description,
    )
    return left_id, right_id, normalized_type, normalized_sentiment, normalized_description, int(from_chapter or 0)


def _relationship_resolution_candidates(
    chars: list[Character],
    name: str | None,
    *,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
    context_text: str | None = None,
) -> list[uuid.UUID]:
    candidate = " ".join(str(name or "").split()).strip()
    if not candidate:
        return []
    matched = _find_character_ids_in_cache(chars, candidate, [], key_cache=key_cache)
    if matched:
        return matched
    resolved = resolve_character_reference_from_roster(chars, candidate, context_text=context_text)
    return [resolved.id] if resolved is not None else []


def _relationship_evidence_payload(
    rel: dict[str, Any],
    *,
    chapter_number: int,
    counterpart_name: str | None,
    counterpart_character_id: uuid.UUID | None,
    unresolved_side: str,
    resolution: str,
) -> dict[str, Any]:
    pair_key: list[str] | None = None
    if rel.get("matched_character_a_id") and rel.get("matched_character_b_id"):
        pair_key = list(
            canonical_relationship_pair_key(
                uuid.UUID(str(rel["matched_character_a_id"])),
                uuid.UUID(str(rel["matched_character_b_id"])),
            )
        )
    return {
        "relationship": {
            "character_a": " ".join(str(rel.get("character_a") or "").split()).strip(),
            "character_b": " ".join(str(rel.get("character_b") or "").split()).strip(),
            "type": " ".join(str(rel.get("type") or "neutral").split()).strip() or "neutral",
            "description": " ".join(str(rel.get("description") or "").split()).strip(),
            "chapter_number": int(chapter_number or 0),
            "source_batch_key": rel.get("source_batch_key"),
        },
        "review_kind": "relationship_resolution",
        "unresolved_side": unresolved_side,
        "resolution": resolution,
        "counterpart_name": counterpart_name,
        "counterpart_character_id": str(counterpart_character_id) if counterpart_character_id else None,
        "pair_key": pair_key,
        "character_a_matches": [str(item) for item in rel.get("character_a_matches", [])[:3]],
        "character_b_matches": [str(item) for item in rel.get("character_b_matches", [])[:3]],
    }


async def _record_relationship_review_candidates(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    rel: dict[str, Any],
    left_matches: list[uuid.UUID],
    right_matches: list[uuid.UUID],
) -> int:
    created = 0
    left_name = " ".join(str(rel.get("character_a") or "").split()).strip()
    right_name = " ".join(str(rel.get("character_b") or "").split()).strip()
    relationship_key = str(rel.get("source_batch_key") or f"{book_id}:{chapter_number}")
    left_resolution = "resolved" if len(left_matches) == 1 else ("ambiguous" if len(left_matches) > 1 else "missing")
    right_resolution = "resolved" if len(right_matches) == 1 else ("ambiguous" if len(right_matches) > 1 else "missing")

    if left_name and right_name and (len(left_matches) != 1 or len(right_matches) != 1):
        reason_codes = [
            "relationship_unresolved",
            f"character_a_{left_resolution}",
            f"character_b_{right_resolution}",
        ]
        evidence = _relationship_evidence_payload(
            rel,
            chapter_number=chapter_number,
            counterpart_name=right_name or left_name or None,
            counterpart_character_id=right_matches[0] if len(right_matches) == 1 else left_matches[0] if len(left_matches) == 1 else None,
            unresolved_side="both" if len(left_matches) != 1 and len(right_matches) != 1 else ("character_a" if len(left_matches) != 1 else "character_b"),
            resolution=f"{left_resolution}:{right_resolution}",
        )
        disposition = decide_relationship_candidate_disposition(
            raw_character_a=left_name,
            raw_character_b=right_name,
            left_resolved=len(left_matches) == 1,
            right_resolved=len(right_matches) == 1,
            reason_codes=reason_codes,
            evidence=evidence,
        )
        candidate = await record_relationship_candidate(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            raw_character_a=left_name,
            raw_character_b=right_name,
            matched_character_a_id=left_matches[0] if len(left_matches) == 1 else None,
            matched_character_b_id=right_matches[0] if len(right_matches) == 1 else None,
            rel_type=str(rel.get("rel_type") or rel.get("type") or rel.get("relationship") or "connection").strip() or None,
            sentiment=rel.get("sentiment"),
            description=str(rel.get("description") or "").strip() or None,
            status=disposition.status,
            reason_codes=disposition.reason_codes,
            evidence=disposition.evidence,
            source_batch_key=f"{relationship_key}:relationship",
        )
        if candidate is not None and candidate.status == CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
            created += 1

    return created


async def _persist_relationship_records(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    existing_characters: list[Character],
    relationships: list[dict[str, Any]],
    key_cache: dict[uuid.UUID, set[str]],
    persisted_signatures: set[tuple[str, str, str, float | None, str, int]],
) -> tuple[int, list[dict[str, Any]], int]:
    persisted = 0
    unresolved: list[dict[str, Any]] = []
    review_candidate_count = 0

    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        left_name = " ".join(str(rel.get("character_a") or "").split()).strip()
        right_name = " ".join(str(rel.get("character_b") or "").split()).strip()
        if not left_name or not right_name:
            continue

        context_text = " ".join(
            part
            for part in [left_name, right_name, " ".join(str(rel.get("description") or "").split()).strip()]
            if part
        )
        left_matches = _relationship_resolution_candidates(existing_characters, left_name, key_cache=key_cache, context_text=context_text)
        right_matches = _relationship_resolution_candidates(existing_characters, right_name, key_cache=key_cache, context_text=context_text)
        if len(left_matches) == 1 and len(right_matches) == 1 and left_matches[0] != right_matches[0]:
            signature = _relationship_signature(
                left_matches[0],
                right_matches[0],
                str(rel.get("type") or "neutral"),
                rel.get("sentiment"),
                chapter_number,
                str(rel.get("description") or ""),
            )
            relationship, created = await upsert_relationship_timeline_state(
                db,
                book_id=book_id,
                character_a_id=left_matches[0],
                character_b_id=right_matches[0],
                rel_type=str(rel.get("type") or "neutral"),
                sentiment=rel.get("sentiment"),
                description=str(rel.get("description") or ""),
                from_chapter=chapter_number,
            )
            if created:
                persisted_signatures.add(signature)
                persisted += 1
            continue

        unresolved_entry = {
            "character_a": left_name,
            "character_b": right_name,
            "type": str(rel.get("type") or "neutral"),
            "description": " ".join(str(rel.get("description") or "").split()).strip(),
            "source_batch_key": rel.get("source_batch_key"),
            "chapter_number": chapter_number,
            "character_a_matches": [str(item) for item in left_matches[:3]],
            "character_b_matches": [str(item) for item in right_matches[:3]],
            "matched_character_a_id": str(left_matches[0]) if len(left_matches) == 1 else None,
            "matched_character_b_id": str(right_matches[0]) if len(right_matches) == 1 else None,
        }
        unresolved.append(unresolved_entry)
        review_candidate_count += await _record_relationship_review_candidates(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            rel=unresolved_entry,
            left_matches=left_matches,
            right_matches=right_matches,
        )

    return persisted, unresolved, review_candidate_count


async def process_book(book_id: str, queue_wait_ms: int | None = None, task_id: str | None = None) -> dict:
    inflight_key = key_extraction_inflight_book(book_id)
    owner_token = task_id or "unknown"
    if not await cache_set_if_absent(inflight_key, owner_token, INFLIGHT_BOOK_TTL_SECONDS):
        log.info("book_processing_already_inflight book_id=%s", book_id)
        return {"skipped": "already_inflight"}

    try:
        return await _process_book_impl(book_id, queue_wait_ms=queue_wait_ms)
    finally:
        await cache_delete_if_owner(inflight_key, owner_token)


async def _process_book_impl(book_id: str, queue_wait_ms: int | None = None) -> dict:
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

        copyright_info = await evaluate_document_copyright(
            format_name=book.format,
            raw=raw,
            existing_isbn=book.isbn,
        )
        if copyright_info.get("isbn"):
            book.isbn = str(copyright_info["isbn"])
        book.copyright_warning = bool(copyright_info.get("copyright_warning", False))
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

        existing_chapters = (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id)
            )
        ).scalars().all()
        existing_chapter_map: dict[int, Chapter] = {
            ch.number: ch for ch in existing_chapters if ch.number is not None
        }
        for ch_data in all_chapters:
            await _ensure_chapter_stub(
                db,
                book,
                ch_data,
                s3_key=stored_chapter_keys.get(int(ch_data["number"]), ""),
                existing_chapter_map=existing_chapter_map,
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

    if getattr(book, "is_editor_project", False):
        from app.services.editor_project_service import get_rebuild_run_id

        rebuild_id = get_rebuild_run_id(book)
        if not rebuild_id:
            log.info("Skipping stale editor-project extraction book_id=%s", book.id)
            return

    chapter_number = int(ch_data["number"])
    inflight_key = key_extraction_inflight(str(book.id), chapter_number)
    if not await cache_set_if_absent(
        inflight_key,
        {"book_id": str(book.id), "chapter_number": chapter_number},
        EXTRACTION_INFLIGHT_TTL_SECONDS,
    ):
        log.info("Skipping duplicate extraction in-flight book_id=%s chapter=%s", book.id, chapter_number)
        return

    try:
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

        chapter.analysis_state = build_analysis_chapter_state(
            chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
            status="pending",
            source_integrity=build_source_integrity_state(
                text_present=bool(str(ch_data.get("text") or "").strip()),
                media_marker_count=len(re.findall(r"\[\[IMAGE:[^\]]+\]\]", str(ch_data.get("text") or ""))),
                stored_media_count=len(ch_data.get("images") or []),
                recovery_status="ok",
            ),
        )
        await db.flush()

        assert chapter is not None
        await db.execute(delete(BookChunk).where(BookChunk.chapter_id == chapter.id))
        await db.execute(
            delete(CharacterMention).where(
                CharacterMention.book_id == book.id,
                CharacterMention.chapter_number == chapter_number,
            )
        )
        await db.execute(
            delete(CharacterCandidate).where(
                CharacterCandidate.book_id == book.id,
                CharacterCandidate.chapter_number == chapter_number,
                CharacterCandidate.status.in_((CHARACTER_CANDIDATE_PENDING, CHARACTER_CANDIDATE_SUPPRESSED)),
            )
        )
        await db.execute(
            delete(CharacterRelationshipCandidate).where(
                CharacterRelationshipCandidate.book_id == book.id,
                CharacterRelationshipCandidate.chapter_number == chapter_number,
                CharacterRelationshipCandidate.status.in_(
                    (CHARACTER_RELATIONSHIP_CANDIDATE_PENDING, CHARACTER_RELATIONSHIP_CANDIDATE_SUPPRESSED)
                ),
            )
        )

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
        chunk_embedding_inputs = [
            build_chunk_embedding_text(
                chapter_number=chapter_number,
                chapter_title=chapter.title or ch_data.get("title"),
                text=chunk,
            )
            for chunk in chunks
        ]
        chunk_batches = chunked(chunk_embedding_inputs, settings.EXTRACTION_EMBED_BATCH_SIZE)
        embed_semaphore = asyncio.Semaphore(
            max(1, min(settings.EXTRACTION_EMBED_CONCURRENCY, len(chunk_batches) or 1))
        )

        async def _embed_with_limit(batch: list[str]) -> list[list[float]]:
            async with embed_semaphore:
                return await embed_batch(
                    batch,
                    db=db,
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
        character_key_cache: dict[uuid.UUID, set[str]] = {
            char.id: character_name_keys(char.name, char.aliases or [])
            for char in existing_characters
            if char.id is not None
        }
        roster_snapshot = build_character_roster_snapshot(existing_characters)

        llm_started = time.perf_counter()
        extraction_batches = _group_chunks_for_extraction(chunks)
        extraction_batch_texts = ["\n\n".join(chunk_batch) for chunk_batch in extraction_batches]
        extraction_results = await asyncio.gather(
            *(
                extract_characters_and_relationships(
                    batch_text,
                    user_id=book.user_id,
                    book_id=book.id,
                    known_characters=roster_snapshot,
                    usage_db=db,
                )
                for batch_text in extraction_batch_texts
            ),
            return_exceptions=True,
        )
        extraction_failed_batches = 0
        extraction_fallback_batches = 0
        extraction_fallback_character_count = 0
        extraction_rejected_characters: list[dict[str, Any]] = []
        unresolved_relationships: list[dict[str, Any]] = []
        pending_relationships: list[dict[str, Any]] = []
        pending_first_chapter_candidates: dict[uuid.UUID, list[str]] = {}
        pending_first_chapter_updates: dict[uuid.UUID, Character] = {}
        saved_character_count = 0
        quarantined_candidate_count = 0
        ambiguous_entity_count = 0
        strict_hold_count = 0
        relationship_review_candidate_count = 0
        chapter_media_count = len(ch_data.get("images") or [])
        media_marker_count = len(re.findall(r"\[\[IMAGE:[^\]]+\]\]", str(ch_data.get("text") or "")))
        existing_relationship_rows = (
            await db.execute(
                select(
                    CharacterRelationship.character_a_id,
                    CharacterRelationship.character_b_id,
                    CharacterRelationship.rel_type,
                    CharacterRelationship.sentiment,
                    CharacterRelationship.from_chapter,
                    CharacterRelationship.description,
                ).where(
                    CharacterRelationship.book_id == book.id,
                    CharacterRelationship.from_chapter == chapter_number,
                )
            )
        ).all()
        persisted_relationship_signatures: set[tuple[str, str, str, float | None, str, int]] = {
            _relationship_signature(
                row.character_a_id,
                row.character_b_id,
                row.rel_type,
                row.sentiment,
                row.from_chapter,
                row.description,
            )
            for row in existing_relationship_rows
        }

        raw_character_entities: list[dict[str, Any]] = []
        for batch_index, (batch_text, result) in enumerate(zip(extraction_batch_texts, extraction_results), start=1):
            source_batch_key = f"{book.id}:{chapter_number}:{batch_index}"
            if isinstance(result, Exception):
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
                    usage_db=db,
                )
                extraction_fallback_batches += 1
                extraction_fallback_character_count += len(result.get("characters", []))
            result = cast(dict[str, Any], result)
            _append_rejected_character_reports(extraction_rejected_characters, result.get("rejected_characters"))

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

        aggregated_entities = cluster_character_entities(raw_character_entities)
        pending_new_entities: list[tuple[dict[str, Any], set[uuid.UUID], str | None]] = []
        for entity in aggregated_entities:
            cluster_members = entity.get("cluster_members") if isinstance(entity.get("cluster_members"), list) else []
            entity_source_batch_key = next(
                (
                    str(member.get("source_batch_key") or "")
                    for member in cluster_members
                    if str(member.get("source_batch_key") or "").strip()
                ),
                None,
            )
            context_text = "\n\n".join(
                str(member.get("source_text") or "").strip()
                for member in cluster_members[:3]
                if str(member.get("source_text") or "").strip()
            )
            blocked_ids = _blocked_character_ids(existing_characters, entity, key_cache=character_key_cache)
            matching_ids = _find_character_ids_in_cache(
                existing_characters,
                str(entity.get("name") or ""),
                entity.get("aliases", []),
                blocked_ids=blocked_ids,
                key_cache=character_key_cache,
            )
            if len(matching_ids) != 1 and context_text:
                resolver_match = resolve_character_reference_from_roster(
                    [char for char in existing_characters if char.id not in blocked_ids],
                    str(entity.get("name") or ""),
                    context_text=context_text,
                )
                if resolver_match is not None:
                    matching_ids = [resolver_match.id]

            existing_id = matching_ids[0] if len(matching_ids) == 1 else None
            decision = _character_save_decision(entity)
            manual_review_reason = _entity_requires_manual_review(entity)
            existing_match = next((item for item in existing_characters if item.id == existing_id), None) if existing_id is not None else None

            if len(matching_ids) > 1:
                ambiguous_entity_count += 1
                quarantined_candidate_count += 1
                status, reasons, _evidence = await _record_character_disposition_candidate(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=None,
                    reason_codes=["ambiguous_roster_match"],
                    source_batch_key=entity_source_batch_key,
                )
                await _record_cluster_member_candidates(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=None,
                    reason_code="ambiguous_roster_match",
                    status=status,
                )
                await _record_entity_cluster_mentions(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=None,
                    resolver_status="suppressed" if status == CHARACTER_CANDIDATE_SUPPRESSED else "ambiguous",
                    resolver_reasons=reasons,
                )
                continue

            if existing_id is not None:
                if existing_match is not None and not is_cast_visible_character(existing_match):
                    reasons = ["matched_quarantined_character", *list(decision.reasons or [])]
                    quarantined_candidate_count += 1
                    status, resolved_reasons, _evidence = await _record_character_disposition_candidate(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        reason_codes=reasons,
                        source_batch_key=entity_source_batch_key,
                    )
                    await _record_entity_cluster_mentions(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        resolver_status="suppressed" if status == CHARACTER_CANDIDATE_SUPPRESSED else "matched_needs_review",
                        resolver_reasons=resolved_reasons,
                    )
                    continue
                if not decision.allowed or not _should_update_existing_character(entity):
                    reasons = list(decision.reasons or []) or ["existing_match_needs_review"]
                    if manual_review_reason and manual_review_reason not in reasons:
                        reasons.append(manual_review_reason)
                    if manual_review_reason:
                        strict_hold_count += 1
                    quarantined_candidate_count += 1
                    status, resolved_reasons, _evidence = await _record_character_disposition_candidate(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        reason_codes=reasons,
                        source_batch_key=entity_source_batch_key,
                    )
                    await _record_entity_cluster_mentions(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        resolver_status="suppressed" if status == CHARACTER_CANDIDATE_SUPPRESSED else "matched_needs_review",
                        resolver_reasons=resolved_reasons,
                    )
                    continue

                accepted = await _accept_existing_character_match(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    existing_id=existing_id,
                    existing_characters=existing_characters,
                    character_key_cache=character_key_cache,
                    pending_first_chapter_candidates=pending_first_chapter_candidates,
                    pending_first_chapter_updates=pending_first_chapter_updates,
                    reason_code="matched_existing_character",
                    source_batch_key=entity_source_batch_key,
                )
                if accepted:
                    saved_character_count += 1
                    await _record_entity_cluster_mentions(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        resolver_status="matched_existing",
                        resolver_reasons=["matched_existing_character"],
                    )
                    await _record_cluster_member_candidates(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        reason_code="matched_existing_character",
                    )
                continue

            if not decision.allowed or manual_review_reason or not _can_auto_save_character(entity):
                reasons = list(decision.reasons or []) or ["low_confidence_needs_review"]
                if manual_review_reason and manual_review_reason not in reasons:
                    reasons.append(manual_review_reason)
                if manual_review_reason:
                    strict_hold_count += 1
                quarantined_candidate_count += 1
                status, resolved_reasons, _evidence = await _record_character_disposition_candidate(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=None,
                    reason_codes=reasons,
                    source_batch_key=entity_source_batch_key,
                )
                await _record_cluster_member_candidates(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=None,
                    reason_code=resolved_reasons[0] if resolved_reasons else reasons[0],
                    status=status,
                )
                await _record_entity_cluster_mentions(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=None,
                    resolver_status="suppressed" if status == CHARACTER_CANDIDATE_SUPPRESSED else "held_for_review",
                    resolver_reasons=resolved_reasons,
                )
                continue

            pending_new_entities.append((entity, blocked_ids, entity_source_batch_key))

        new_entity_embeddings = await _embed_new_character_candidates(
            [(entity, blocked_ids) for entity, blocked_ids, _source_batch_key in pending_new_entities],
            db=db,
            user_id=book.user_id,
            book_id=book.id,
        )
        for (entity, blocked_ids, entity_source_batch_key), emb in zip(pending_new_entities, new_entity_embeddings):
            if not emb:
                continue
            matching_ids = _find_character_ids_in_cache(
                existing_characters,
                str(entity.get("name") or ""),
                entity.get("aliases", []),
                blocked_ids=blocked_ids,
                key_cache=character_key_cache,
            )
            if len(matching_ids) > 1:
                ambiguous_entity_count += 1
                quarantined_candidate_count += 1
                status, reasons, _evidence = await _record_character_disposition_candidate(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=None,
                    reason_codes=["ambiguous_roster_match_after_cluster"],
                    source_batch_key=entity_source_batch_key,
                )
                await _record_entity_cluster_mentions(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=None,
                    resolver_status="suppressed" if status == CHARACTER_CANDIDATE_SUPPRESSED else "ambiguous",
                    resolver_reasons=reasons,
                )
                continue
            if len(matching_ids) == 1:
                existing_id = matching_ids[0]
                accepted = await _accept_existing_character_match(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    existing_id=existing_id,
                    existing_characters=existing_characters,
                    character_key_cache=character_key_cache,
                    pending_first_chapter_candidates=pending_first_chapter_candidates,
                    pending_first_chapter_updates=pending_first_chapter_updates,
                    reason_code="matched_existing_character_after_cluster",
                    source_batch_key=entity_source_batch_key,
                )
                if accepted:
                    saved_character_count += 1
                    await _record_entity_cluster_mentions(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        resolver_status="matched_existing",
                        resolver_reasons=["matched_existing_character_after_cluster"],
                    )
                    await _record_cluster_member_candidates(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        reason_code="matched_existing_character_after_cluster",
                    )
                continue

            existing_id = await find_similar(
                db,
                book.id,
                emb,
                settings.DEDUP_SIMILARITY_THRESHOLD,
                excluded_ids=blocked_ids,
            )
            if existing_id:
                accepted = await _accept_existing_character_match(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    existing_id=existing_id,
                    existing_characters=existing_characters,
                    character_key_cache=character_key_cache,
                    pending_first_chapter_candidates=pending_first_chapter_candidates,
                    pending_first_chapter_updates=pending_first_chapter_updates,
                    reason_code="embedding_matched_existing_character",
                    source_batch_key=entity_source_batch_key,
                )
                if accepted:
                    saved_character_count += 1
                    await _record_entity_cluster_mentions(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        resolver_status="embedding_matched_existing",
                        resolver_reasons=["embedding_matched_existing_character"],
                    )
                    await _record_cluster_member_candidates(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=existing_id,
                        reason_code="embedding_matched_existing_character",
                    )
                continue

            promoted = await _promote_new_character_from_entity(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                embedding=emb,
                existing_characters=existing_characters,
                character_key_cache=character_key_cache,
                pending_first_chapter_candidates=pending_first_chapter_candidates,
                pending_first_chapter_updates=pending_first_chapter_updates,
                source_batch_key=entity_source_batch_key,
            )
            saved_character_count += 1
            await _record_entity_cluster_mentions(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=promoted.id,
                resolver_status="promoted",
                resolver_reasons=["new_character_promoted"],
            )
            await _record_cluster_member_candidates(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=promoted.id,
                reason_code="matched_cluster_member",
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
        persisted_relationship_count, unresolved_relationships, relationship_review_candidate_count = await _persist_relationship_records(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
            existing_characters=existing_characters,
            relationships=pending_relationships,
            key_cache=character_key_cache,
            persisted_signatures=persisted_relationship_signatures,
        )
        duplicate_suggestions = await refresh_character_duplicate_suggestions(db, book_id=book.id, characters=existing_characters)
        if pending_first_chapter_candidates:
            earliest_started = time.perf_counter()
            earliest_mentions = await find_earliest_character_mention_chapters(
                db,
                book_id=book.id,
                candidates_by_key=pending_first_chapter_candidates,
                upto_chapter=chapter_number,
            )
            for character_id, earliest_chapter in earliest_mentions.items():
                char = pending_first_chapter_updates.get(character_id)
                if char is None:
                    continue
                if earliest_chapter < int(char.first_chapter or chapter_number):
                    char.first_chapter = earliest_chapter
                current_last_seen = int(char.last_seen_chapter or char.first_chapter or earliest_chapter)
                char.last_seen_chapter = max(current_last_seen, char.first_chapter or earliest_chapter)
            log.info(
                "ingestion_timing stage=first_chapter_backfill book_id=%s chapter=%s elapsed_ms=%s characters=%s",
                book.id,
                chapter_number,
                elapsed_ms(earliest_started),
                len(pending_first_chapter_candidates),
            )
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
            "saved_characters": saved_character_count,
            "quarantined_candidates": quarantined_candidate_count,
            "ambiguity_rate": round(ambiguous_entity_count / max(1, len(aggregated_entities)), 3),
            "strict_hold_rate": round(strict_hold_count / max(1, len(aggregated_entities)), 3),
            "mention_to_promotion_rate": round(saved_character_count / max(1, len(raw_character_entities)), 3),
            "rejected_entities": len(extraction_rejected_characters),
            "unresolved_relationships_count": len(unresolved_relationships),
            "relationship_review_candidates": relationship_review_candidate_count,
            "relationships_persisted": persisted_relationship_count,
            "duplicate_suggestions": sum(1 for item in duplicate_suggestions if str(item.status or "") == "pending"),
            "chapter_media_count": chapter_media_count,
            "media_marker_count": media_marker_count,
            "cover_available": bool(book.cover_s3_key),
        }
        if extraction_rejected_characters:
            chapter_character_diagnostics["rejected_characters"] = _summarize_rejected_character_reports(
                extraction_rejected_characters
            )
        if unresolved_relationships:
            chapter_character_diagnostics["unresolved_relationships"] = unresolved_relationships[:20]
        extraction_diagnostics["character_extraction"] = {
            **chapter_character_diagnostics,
            "totals": {
                "saved_characters": int(previous_totals.get("saved_characters") or 0) + saved_character_count,
                "quarantined_candidates": int(previous_totals.get("quarantined_candidates") or 0) + quarantined_candidate_count,
                "rejected_entities": int(previous_totals.get("rejected_entities") or 0) + len(extraction_rejected_characters),
                "relationships_persisted": int(previous_totals.get("relationships_persisted") or 0) + persisted_relationship_count,
                "unresolved_relationships_count": int(previous_totals.get("unresolved_relationships_count") or 0) + len(unresolved_relationships),
                "relationship_review_candidates": int(previous_totals.get("relationship_review_candidates") or 0) + relationship_review_candidate_count,
            },
        }

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
            parser_diagnostics=extraction_diagnostics,
        )
        await db.commit()
        from app.utils.advisor_utils import invalidate_advisor_caches_for_book

        await invalidate_advisor_caches_for_book(db, book_id=book.id)
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

        if await _book_processing_complete(db, book.id):
            ready_stats = await collect_book_ready_stats(db, book)
            book.status = "ready"
            processing_status, processing_stage = processing_state_for_completed_extraction(
                analysis_complete=ready_stats.analysis_complete,
            )
            book.writer_workspace = update_book_processing_state(
                book,
                status=processing_status,
                stage=processing_stage,
                total_chapters=processing_total,
                completed_chapters=processed_count,
                started_at=get_processing_started_at(book),
                queue_wait_ms=queue_wait_ms,
                chapter_number=chapter_number,
                chapter_title=chapter.title,
                parser_diagnostics=extraction_diagnostics,
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

            _, created_ready_notification = await upsert_book_ready_notification(db, book, ready_stats)

            await db.commit()

            user = await db.get(User, book.user_id)
            if user and user.email and created_ready_notification and ready_stats.analysis_complete:
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
    finally:
        await cache_del(inflight_key)


async def _ensure_chapter_stub(db, book, ch_data: dict, *, s3_key: str, existing_chapter_map: dict[int, Chapter] | None = None):
    if existing_chapter_map is not None:
        existing = existing_chapter_map.get(int(ch_data["number"]))
    else:
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
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> uuid.UUID | None:
    roster = [
        (char.id, char.name, char.aliases or [])
        for char in chars
        if not blocked_ids or char.id not in blocked_ids
    ]
    return resolve_character_match_id(name, aliases or [], roster, blocked_ids=blocked_ids)


def _find_character_ids_in_cache(
    chars: list[Character],
    name: str,
    aliases: list[str] | None,
    blocked_ids: set[uuid.UUID] | None = None,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> list[uuid.UUID]:
    roster = [
        (char.id, char.name, char.aliases or [])
        for char in chars
        if not blocked_ids or char.id not in blocked_ids
    ]
    return resolve_character_match_ids(name, aliases or [], roster, blocked_ids=blocked_ids)


def _find_character_in_cache(
    chars: list[Character],
    name: str,
    *,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> Character | None:
    match_id = _find_character_id_in_cache(chars, name, [], key_cache=key_cache)
    if not match_id:
        return None
    return next((char for char in chars if char.id == match_id), None)


def _find_character_by_id(chars: list[Character], character_id: uuid.UUID) -> Character | None:
    return next((char for char in chars if char.id == character_id), None)


async def _accept_existing_character_match(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    existing_id: uuid.UUID,
    existing_characters: list[Character],
    character_key_cache: dict[uuid.UUID, set[str]],
    pending_first_chapter_candidates: dict[uuid.UUID, list[str]],
    pending_first_chapter_updates: dict[uuid.UUID, Character],
    reason_code: str,
    source_batch_key: str | None,
) -> bool:
    char = _find_character_by_id(existing_characters, existing_id)
    if char is None:
        return False
    updated = update_profile(char, {**entity, "first_chapter": chapter_number})
    changed = _changed(char.trait_state or {}, updated["trait_state"])
    _apply_character_update(char, updated)
    _refresh_character_key_cache(character_key_cache, char)
    pending_first_chapter_candidates[existing_id] = _first_chapter_lookup_candidates(
        char.name,
        updated.get("aliases") or char.aliases or [],
    )
    pending_first_chapter_updates[existing_id] = char
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
    await record_character_candidate(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        raw_name=str(entity.get("name") or ""),
        proposed_name=str(entity.get("name") or ""),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        matched_character_id=existing_id,
        status="accepted",
        confidence=entity.get("confidence"),
        reason_codes=[reason_code],
        evidence=_candidate_record_evidence(entity),
        source_batch_key=source_batch_key,
    )
    _merge_alias_in_memory(char, entity["name"] if char else None)
    return True


async def _promote_new_character_from_entity(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    embedding: list[float],
    existing_characters: list[Character],
    character_key_cache: dict[uuid.UUID, set[str]],
    pending_first_chapter_candidates: dict[uuid.UUID, list[str]],
    pending_first_chapter_updates: dict[uuid.UUID, Character],
    source_batch_key: str | None,
) -> Character:
    dossier_summary = _entity_dossier_summary(entity)
    entity["visibility_state"] = CHARACTER_VISIBILITY_VISIBLE
    entity["approval_state"] = CHARACTER_APPROVAL_APPROVED
    entity["approval_source"] = CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO
    entity["approval_reason_codes"] = [
        "deterministic_auto_promotion",
        *[
            str(reason).strip()
            for reason in (dossier_summary.get("summary_reason_codes") or [])
            if str(reason).strip()
        ],
    ]
    entity["dossier_summary"] = dossier_summary
    profile = build_character_profile(entity, book_id, chapter_number)
    char = Character(**profile, embedding=embedding)
    db.add(char)
    await db.flush()
    existing_characters.append(char)
    _refresh_character_key_cache(character_key_cache, char)
    await record_character_candidate(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        raw_name=str(entity.get("name") or ""),
        proposed_name=str(entity.get("name") or ""),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        matched_character_id=char.id,
        status="promoted",
        confidence=entity.get("confidence"),
        reason_codes=["new_character_promoted"],
        evidence=_candidate_record_evidence(entity),
        source_batch_key=source_batch_key,
    )
    pending_first_chapter_candidates[char.id] = _first_chapter_lookup_candidates(
        profile["name"],
        profile["aliases"],
    )
    pending_first_chapter_updates[char.id] = char
    return char


def _apply_character_update(char: Character, updated: dict[str, Any]) -> None:
    for key, value in updated.items():
        setattr(char, key, value)


async def _record_entity_cluster_mentions(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    matched_character_id: uuid.UUID | None,
    resolver_status: str,
    resolver_reasons: list[str],
) -> None:
    cluster_key = build_character_mention_cluster_key(
        str(entity.get("name") or ""),
        entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
    )
    members = entity.get("cluster_members") if isinstance(entity.get("cluster_members"), list) else []
    if not members:
        members = [{
            "name": entity.get("name"),
            "aliases": entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
            "source_batch_key": entity.get("_source_batch_key"),
            "source_text": entity.get("_source_text"),
            "evidence": _entity_evidence(entity),
        }]

    for member in members:
        raw_name = " ".join(str(member.get("name") or "").split()).strip()
        normalized_name = normalize_character_name(raw_name)
        if not raw_name or not normalized_name:
            continue
        await record_character_mention(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            raw_name=raw_name,
            normalized_name=normalized_name,
            source_batch_key=str(member.get("source_batch_key") or "") or None,
            cluster_key=cluster_key or normalized_name,
            mention_text=str(member.get("source_text") or "")[:1800] or None,
            matched_character_id=matched_character_id,
            resolver_status=resolver_status,
            resolver_reasons=resolver_reasons,
            evidence=member.get("evidence") if isinstance(member.get("evidence"), dict) else {},
        )


async def _record_cluster_member_candidates(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    matched_character_id: uuid.UUID | None,
    reason_code: str,
    status: str = "accepted",
) -> None:
    members = entity.get("cluster_members") if isinstance(entity.get("cluster_members"), list) else []
    if not members:
        return

    primary_name = normalize_character_name(str(entity.get("name") or ""))
    seen: set[tuple[str, str | None]] = set()
    for member in members:
        raw_name = " ".join(str(member.get("name") or "").split()).strip()
        normalized_name = normalize_character_name(raw_name)
        source_batch_key = str(member.get("source_batch_key") or "") or None
        if not raw_name or not normalized_name:
            continue
        if normalized_name == primary_name:
            continue
        dedupe_key = (normalized_name, source_batch_key)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        await record_character_candidate(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            raw_name=raw_name,
            proposed_name=raw_name,
            aliases=member.get("aliases") if isinstance(member.get("aliases"), list) else [],
            matched_character_id=matched_character_id,
            status=status,
            confidence=entity.get("confidence"),
            reason_codes=[reason_code],
            evidence={
                **(member.get("evidence") if isinstance(member.get("evidence"), dict) else {}),
                "entity": {
                    "name": raw_name,
                    "canonical_name": entity.get("name"),
                    "aliases": member.get("aliases") if isinstance(member.get("aliases"), list) else [],
                    "confidence": entity.get("confidence"),
                },
            },
            source_batch_key=source_batch_key,
        )


def _merge_alias_in_memory(char: Character | None, alias: str | None) -> None:
    if char is None or not is_valid_alias(alias):
        return
    cleaned_alias = str(alias or "").strip()
    if not cleaned_alias or cleaned_alias.casefold() == str(char.name or "").strip().casefold():
        return
    aliases = list(char.aliases or [])
    if any(existing.casefold() == cleaned_alias.casefold() for existing in aliases):
        return
    char.aliases = [*aliases, cleaned_alias]


def _character_keys_for_cache(
    char: Character,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> set[str]:
    if key_cache is not None and char.id in key_cache:
        return key_cache[char.id]
    keys = character_name_keys(char.name, char.aliases or [])
    if key_cache is not None and char.id is not None:
        key_cache[char.id] = keys
    return keys


def _refresh_character_key_cache(key_cache: dict[uuid.UUID, set[str]], char: Character) -> None:
    if char.id is None:
        return
    key_cache[char.id] = character_name_keys(char.name, char.aliases or [])


def _entity_evidence(entity: dict) -> dict:
    evidence = entity.get("evidence")
    return evidence if isinstance(evidence, dict) else {}


def _entity_dossier_summary(entity: dict) -> dict[str, Any]:
    evidence = _entity_evidence(entity)
    verifier = evidence.get("verifier") if isinstance(evidence.get("verifier"), dict) else {}
    final = verifier.get("final") if isinstance(verifier, dict) and isinstance(verifier.get("final"), dict) else {}
    return build_character_dossier_summary(
        name=entity.get("name"),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        evidence=evidence,
        reason_codes=[
            *(
                final.get("reasons")
                if isinstance(final.get("reasons"), list)
                else []
            ),
            *(
                evidence.get("resolver_reasons")
                if isinstance(evidence.get("resolver_reasons"), list)
                else []
            ),
        ],
    )


def _candidate_record_evidence(entity: dict) -> dict[str, Any]:
    evidence = dict(_entity_evidence(entity))
    evidence["dossier_summary"] = _entity_dossier_summary(entity)
    evidence["entity"] = {
        "name": entity.get("name"),
        "canonical_name": entity.get("canonical_name"),
        "aliases": entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        "role": entity.get("role"),
        "traits": entity.get("traits") if isinstance(entity.get("traits"), dict) else {},
        "personality_tags": entity.get("personality_tags") if isinstance(entity.get("personality_tags"), list) else [],
        "motivations": entity.get("motivations") if isinstance(entity.get("motivations"), list) else [],
        "fears": entity.get("fears") if isinstance(entity.get("fears"), list) else [],
        "goal": entity.get("goal"),
        "lie_they_believe": entity.get("lie_they_believe"),
        "backstory_wound": entity.get("backstory_wound"),
        "arc_type": entity.get("arc_type"),
        "arc_summary": entity.get("arc_summary"),
        "archetype": entity.get("archetype"),
        "growth_event": entity.get("growth_event") if isinstance(entity.get("growth_event"), dict) else None,
        "confidence": entity.get("confidence"),
    }
    return evidence


async def _record_character_disposition_candidate(
    db,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    entity: dict[str, Any],
    matched_character_id: uuid.UUID | None,
    reason_codes: list[str],
    source_batch_key: str | None,
) -> tuple[str, list[str], dict[str, Any]]:
    evidence = _candidate_record_evidence(entity)
    disposition = decide_character_candidate_disposition(
        name=str(entity.get("name") or ""),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        confidence=entity.get("confidence"),
        reason_codes=reason_codes,
        evidence=evidence,
        matched_character_id=matched_character_id,
    )
    await record_character_candidate(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        raw_name=str(entity.get("name") or ""),
        proposed_name=str(entity.get("name") or ""),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
        matched_character_id=matched_character_id,
        status=disposition.status,
        confidence=entity.get("confidence"),
        reason_codes=disposition.reason_codes,
        evidence=disposition.evidence,
        source_batch_key=source_batch_key,
    )
    return disposition.status, list(disposition.reason_codes), disposition.evidence


def _blocked_character_ids(
    chars: list[Character],
    entity: dict,
    *,
    key_cache: dict[uuid.UUID, set[str]] | None = None,
) -> set[uuid.UUID]:
    blocked_ids: set[uuid.UUID] = set()
    blocked_names = [name for name in (entity.get("anti_merge_names") or []) if isinstance(name, str) and name.strip()]
    if not blocked_names:
        return blocked_ids

    for blocked_name in blocked_names:
        blocked_keys = character_name_keys(blocked_name, [])
        for char in chars:
            char_keys = _character_keys_for_cache(char, key_cache)
            if blocked_keys & char_keys:
                blocked_ids.add(char.id)
                continue
            if names_equivalent(blocked_name, [], char.name, char.aliases or []):
                blocked_ids.add(char.id)
    return blocked_ids


def _entity_verifier_summary(entity: dict) -> dict[str, Any]:
    evidence = _entity_evidence(entity)
    verifier = evidence.get("verifier") if isinstance(evidence.get("verifier"), dict) else {}
    final = verifier.get("final") if isinstance(verifier, dict) else {}
    return final if isinstance(final, dict) else {}


def _entity_verifier_band(entity: dict) -> str | None:
    final = _entity_verifier_summary(entity)
    band = str(final.get("confidence_band") or "").strip()
    return band or None


def _should_update_existing_character(entity: dict) -> bool:
    verifier_band = _entity_verifier_band(entity)
    if verifier_band == "reject":
        return False
    if verifier_band == "review":
        return False
    dossier_summary = _entity_dossier_summary(entity)
    if dossier_summary.get("resolver_ambiguity_count") or dossier_summary.get("conflict_signal_count"):
        return False
    if verifier_band == "accept":
        return bool(
            dossier_summary.get("strict_auto_eligible")
            or (
                not dossier_summary.get("single_token")
                and dossier_summary.get("person_ner_support", 0) >= 1
                and (
                    _entity_evidence(entity).get("has_dialogue_or_action")
                    or _has_character_profile_signal(entity)
                )
            )
        )
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
    if any(
        str(entity.get(field) or "").strip()
        for field in ("goal", "lie_they_believe", "backstory_wound", "arc_type", "archetype")
    ):
        return True
    if any(entity.get(field) for field in ("personality_tags", "motivations", "fears")):
        return True
    arc_summary = str(entity.get("arc_summary") or "").strip().casefold()
    if arc_summary and arc_summary not in {
        "appearance not yet described",
        "background character",
        "is a character",
        "mysterious figure",
        "normal character",
        "plain character",
        "supporting character",
        "this character is a character",
        "protagonist",
        "antagonist",
        "puppet master",
        "tragic figure",
        "unknown character",
    }:
        return True
    growth_event = entity.get("growth_event")
    return isinstance(growth_event, dict) and bool(str(growth_event.get("event") or "").strip())


def _entity_requires_manual_review(entity: dict) -> str | None:
    verifier_band = _entity_verifier_band(entity)
    if verifier_band == "review":
        return "mention_verifier_review"
    if verifier_band == "reject":
        return "mention_verifier_rejected"

    evidence = _entity_evidence(entity)
    cluster_names = [
        str(item).strip()
        for item in (evidence.get("cluster_names") or [])
        if str(item).strip()
    ]
    confidence = float(entity.get("confidence") or 0.0)
    if is_role_only_character_name(entity.get("name")) and not any(
        not is_role_only_character_name(name) for name in cluster_names
    ):
        return "role_only_reference_requires_review"

    mention_count = int(evidence.get("mention_count") or 0)
    strong_mentions = int(evidence.get("strong_mention_count") or 0)
    confidence = float(entity.get("confidence") or 0.0)
    if (
        mention_count <= 1
        and strong_mentions >= 1
        and confidence >= 0.9
        and (
            evidence.get("has_dialogue_or_action")
            or evidence.get("has_physical_description")
        )
    ):
        return None
    if confidence < 0.45 and strong_mentions <= 1:
        return "low_confidence_requires_review"
    if mention_count <= 1 and strong_mentions <= 1 and not _has_character_profile_signal(entity):
        return "single_mention_requires_review"
    return None


def _can_auto_save_character(entity: dict) -> bool:
    if _entity_verifier_band(entity) != "accept":
        return False
    if _entity_requires_manual_review(entity):
        return False
    return _character_save_decision(entity).allowed


def _character_save_decision(entity: dict):
    evidence = _entity_evidence(entity)
    traits = entity.get("traits")
    trait_state = traits if isinstance(traits, dict) else {}
    decision = character_persistence_decision(
        entity.get("name"),
        role=entity.get("role"),
        aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else None,
        personality_tags=entity.get("personality_tags") if isinstance(entity.get("personality_tags"), list) else None,
        motivations=entity.get("motivations") if isinstance(entity.get("motivations"), list) else None,
        fears=entity.get("fears") if isinstance(entity.get("fears"), list) else None,
        archetype=entity.get("archetype"),
        trait_state=trait_state,
        relationship_count=int(entity.get("relationship_count") or 0),
        arc_summary=entity.get("arc_summary"),
        evidence=evidence,
        entity_type=str(entity.get("entity_type") or "person"),
    )
    verifier_band = _entity_verifier_band(entity)
    verifier_reasons = [
        str(reason).strip()
        for reason in (_entity_verifier_summary(entity).get("reasons") or [])
        if str(reason).strip()
    ]
    dossier_summary = _entity_dossier_summary(entity)
    if verifier_band == "reject":
        return CharacterPersistenceDecision(
            allowed=False,
            score=decision.score,
            reasons=tuple(["mention_verifier_rejected", *verifier_reasons]),
        )
    if verifier_band == "review":
        return CharacterPersistenceDecision(
            allowed=False,
            score=decision.score,
            reasons=tuple(["mention_verifier_review", *verifier_reasons]),
        )
    if verifier_band == "accept":
        if not dossier_summary.get("strict_auto_eligible"):
            return CharacterPersistenceDecision(
                allowed=False,
                score=decision.score,
                reasons=tuple([
                    "candidate_dossier_needs_review",
                    *[
                        str(reason).strip()
                        for reason in (dossier_summary.get("strict_auto_reason_codes") or [])
                        if str(reason).strip()
                    ],
                    *decision.reasons,
                ]),
            )
        if not can_auto_persist_character_candidate(
            name=entity.get("name"),
            aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
            evidence=evidence,
        ):
            return CharacterPersistenceDecision(
                allowed=False,
                score=decision.score,
                reasons=tuple([
                    "initial_auto_persist_requires_stronger_grounding",
                    *[
                        str(reason).strip()
                        for reason in (dossier_summary.get("strict_auto_reason_codes") or [])
                        if str(reason).strip()
                    ],
                    *decision.reasons,
                ]),
            )
        return CharacterPersistenceDecision(
            allowed=decision.allowed,
            score=decision.score,
            reasons=tuple(decision.reasons),
        )
    confidence = float(entity.get("confidence") or 0.0)
    if confidence >= AUTO_SAVE_CONFIDENCE and not dossier_summary.get("strict_auto_eligible"):
        return CharacterPersistenceDecision(
            allowed=False,
            score=decision.score,
            reasons=tuple([
                "candidate_dossier_needs_review",
                *[
                    str(reason).strip()
                    for reason in (dossier_summary.get("strict_auto_reason_codes") or [])
                    if str(reason).strip()
                ],
                *decision.reasons,
            ]),
        )
    return decision


def _append_rejected_character_reports(target: list[dict[str, Any]], entries: list[dict[str, Any]] | None) -> None:
    if not entries:
        return
    seen = {
        (
            str(item.get("name") or "").casefold(),
            str(item.get("stage") or "").casefold(),
            str(item.get("reason") or "").casefold(),
        )
        for item in target
    }
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = (
            str(entry.get("name") or "").casefold(),
            str(entry.get("stage") or "").casefold(),
            str(entry.get("reason") or "").casefold(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        target.append({
            "name": str(entry.get("name") or ""),
            "stage": str(entry.get("stage") or ""),
            "reason": str(entry.get("reason") or ""),
            "confidence": entry.get("confidence"),
            "evidence": entry.get("evidence") or {},
        })


def _summarize_rejected_character_reports(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return entries[:40]


def _first_chapter_lookup_candidates(name: str | None, aliases: list[str] | None) -> list[str]:
    candidates = [str(name or "").strip(), *[str(alias).strip() for alias in aliases or []]]
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def _character_dedup_embedding_text(name: str, traits: dict[str, Any] | None) -> str:
    return build_character_embedding_text(name=name, traits=traits)


async def _embed_new_character_candidates(
    pending_new_entities: list[tuple[dict[str, Any], set[uuid.UUID]]],
    *,
    db,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
) -> list[list[float]]:
    if not pending_new_entities:
        return []

    embedding_inputs = [
        build_character_embedding_text(
            name=str(entity.get("name") or ""),
            traits=entity.get("traits") if isinstance(entity.get("traits"), dict) else {},
            aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
            role=str(entity.get("role") or "").strip() or None,
            arc_summary=str(entity.get("arc_summary") or "").strip() or None,
            evidence_snippets=[
                str(item).strip()
                for item in ((_entity_evidence(entity).get("snippets") or []) if isinstance(_entity_evidence(entity).get("snippets"), list) else [])
                if str(item).strip()
            ],
        )
        for entity, _blocked_ids in pending_new_entities
    ]
    return await embed_batch(
        embedding_inputs,
        db=db,
        user_id=user_id,
        book_id=book_id,
        feature="character_embedding",
    )


async def _book_processing_complete(db, book_id: uuid.UUID) -> bool:
    remaining_count: int | None = await db.scalar(
        select(func.count()).select_from(Chapter).where(Chapter.book_id == book_id, Chapter.processed.is_(False))
    )
    return (remaining_count or 0) == 0


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
