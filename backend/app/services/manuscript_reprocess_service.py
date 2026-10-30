from __future__ import annotations

import hashlib
import json
import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.models.book import Book, Chapter
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterIdentityConstraint,
    CharacterRelationshipCandidate,
    VoiceReviewDecision,
)
from app.models.operations import TaskExecution
from app.schemas.books import (
    ManuscriptReprocessBody,
    ManuscriptReprocessOut,
    ManuscriptReprocessPreflightOut,
)
from app.services.book_section_service import filter_analysis_eligible_chapters
from app.services.processing_allowance_service import (
    MANUAL_REPROCESS_USAGE_KIND,
    ProcessingReservationRequest,
    ensure_project_writable,
    manual_reprocess_source_prefix,
    release_processing_reservations_for_source_prefix,
    reserve_processing_word_batch,
    reserve_processing_words,
)
from app.services.task_execution_service import (
    dispatch_pending_extraction_tasks,
    ensure_task_execution,
    get_or_create_processing_run,
)
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book
from app.utils.exception_boundaries import BEST_EFFORT_CLEANUP_EXCEPTIONS
from app.utils.ingestion_utils import (
    build_analysis_chapter_state,
    load_processing_chapter_payload,
)
from app.utils.llm_usage_utils import (
    assert_manual_reprocess_token_capacity,
    estimate_manual_reprocess_tokens,
)

log = logging.getLogger(__name__)
MANUAL_REPROCESS_FINALIZATION_ERRORS = BEST_EFFORT_CLEANUP_EXCEPTIONS
MANUAL_REPROCESS_CLEANUP_ERRORS = BEST_EFFORT_CLEANUP_EXCEPTIONS


async def _lock_book_reprocessing(db: AsyncSession, book_id: uuid.UUID) -> None:
    await db.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"manual_reprocess:{book_id}")))
    )


async def _chapter_extraction_is_active(
    db: AsyncSession,
    book_id: uuid.UUID,
) -> bool:
    execution_id = await db.scalar(
        select(TaskExecution.id)
        .where(
            TaskExecution.book_id == book_id,
            TaskExecution.task_name == "extraction_tasks.process_chapter",
            TaskExecution.status.in_(("pending_dispatch", "queued", "running", "paused")),
        )
        .limit(1)
    )
    return execution_id is not None


async def preview_manual_manuscript_reprocess(
    *, db: AsyncSession, current_user, book_id: uuid.UUID
) -> ManuscriptReprocessPreflightOut:
    """Inspect stored sources and replacement scope without reserving or changing data."""
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await ensure_project_writable(db, book)
    state = await _load_manual_reprocess_state(db, book)
    await db.commit()
    return await _build_manual_reprocess_preflight(book.id, state)


async def _load_manual_reprocess_state(db: AsyncSession, book: Book) -> dict:
    from app.services.editor_project_service import (
        _resolve_character_anchor_ids,
        get_rebuild_run_id,
    )

    chapters = list(
        (
            await db.execute(
                select(Chapter)
                .where(Chapter.book_id == book.id, Chapter.word_count > 0)
                .order_by(Chapter.number)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    chapters = await filter_analysis_eligible_chapters(db, book.id, chapters)
    character_ids = set(
        (await db.execute(select(Character.id).where(Character.book_id == book.id))).scalars().all()
    )
    protected_ids = character_ids & await _resolve_character_anchor_ids(db, book.id)
    protected_characters = (
        (
            await db.execute(
                select(Character)
                .where(Character.id.in_(protected_ids))
                .order_by(Character.id)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
        if protected_ids
        else []
    )
    review_decisions = (
        await db.execute(
            select(
                VoiceReviewDecision.user_id,
                VoiceReviewDecision.finding_key,
                VoiceReviewDecision.decision,
                VoiceReviewDecision.note,
            )
            .where(VoiceReviewDecision.book_id == book.id)
            .order_by(VoiceReviewDecision.user_id, VoiceReviewDecision.finding_key)
        )
    ).all()
    candidate_reviews = (
        await db.execute(
            select(
                CharacterCandidate.id,
                CharacterCandidate.generation_id,
                CharacterCandidate.status,
                CharacterCandidate.reason_codes,
                CharacterCandidate.rejection_reason,
                CharacterCandidate.matched_character_id,
                CharacterCandidate.source_batch_key,
            )
            .where(CharacterCandidate.book_id == book.id)
            .order_by(CharacterCandidate.id)
        )
    ).all()
    relationship_candidate_reviews = (
        await db.execute(
            select(
                CharacterRelationshipCandidate.id,
                CharacterRelationshipCandidate.generation_id,
                CharacterRelationshipCandidate.status,
                CharacterRelationshipCandidate.reason_codes,
                CharacterRelationshipCandidate.matched_character_a_id,
                CharacterRelationshipCandidate.matched_character_b_id,
            )
            .where(CharacterRelationshipCandidate.book_id == book.id)
            .order_by(CharacterRelationshipCandidate.id)
        )
    ).all()
    manual_identity_constraints = (
        await db.execute(
            select(
                CharacterIdentityConstraint.id,
                CharacterIdentityConstraint.left_character_id,
                CharacterIdentityConstraint.right_character_id,
                CharacterIdentityConstraint.constraint_type,
                CharacterIdentityConstraint.reason,
            )
            .where(
                CharacterIdentityConstraint.book_id == book.id,
                CharacterIdentityConstraint.source == "manual",
            )
            .order_by(CharacterIdentityConstraint.id)
        )
    ).all()
    return {
        "book_id": str(book.id),
        "chapters": [
            {
                "chapter_id": str(chapter.id),
                "chapter_number": chapter.number,
                "content_version": str(chapter.content_version or ""),
                "word_count": int(chapter.word_count or 0),
                "title": str(chapter.title or ""),
                "s3_key": str(chapter.s3_key or ""),
            }
            for chapter in chapters
        ],
        "protected_character_ids": sorted(map(str, protected_ids)),
        "replaceable_character_ids": sorted(map(str, character_ids - protected_ids)),
        "protected_character_reviews": [
            {
                "id": str(character.id),
                "name": character.name,
                "aliases": character.aliases,
                "role": character.role,
                "trait_state": character.trait_state,
                "personality_tags": character.personality_tags,
                "motivations": character.motivations,
                "fears": character.fears,
                "goal": character.goal,
                "arc_summary": character.arc_summary,
                "analysis_metadata": character.analysis_metadata,
                "visibility_state": character.visibility_state,
                "approval_state": character.approval_state,
                "approval_source": character.approval_source,
                "approval_reason_codes": character.approval_reason_codes,
            }
            for character in protected_characters
        ],
        "voice_review_decisions": [
            [str(user_id), finding_key, decision, note]
            for user_id, finding_key, decision, note in review_decisions
        ],
        "character_candidate_reviews": [
            [str(value) if isinstance(value, uuid.UUID) else value for value in row]
            for row in candidate_reviews
        ],
        "relationship_candidate_reviews": [
            [str(value) if isinstance(value, uuid.UUID) else value for value in row]
            for row in relationship_candidate_reviews
        ],
        "manual_identity_constraints": [
            [str(value) if isinstance(value, uuid.UUID) else value for value in row]
            for row in manual_identity_constraints
        ],
        "rebuild_run_id": str(get_rebuild_run_id(book) or ""),
        "chapter_extraction_active": await _chapter_extraction_is_active(db, book.id),
    }


async def _build_manual_reprocess_preflight(
    book_id: uuid.UUID, state: dict
) -> ManuscriptReprocessPreflightOut:
    chapters = state["chapters"]
    source_parts: list[dict[str, str | int]] = []
    missing_chapters: list[int] = []
    for chapter in chapters:
        payload = await load_processing_chapter_payload(
            book_id,
            chapter["chapter_number"],
            chapter_s3_key=chapter["s3_key"],
            chapter_title=chapter["title"],
        )
        if payload is None:
            missing_chapters.append(chapter["chapter_number"])
            continue
        source_parts.append(
            {
                **chapter,
                "source_sha256": hashlib.sha256(
                    json.dumps(
                        {"text": payload["text"], "html": payload.get("html")},
                        sort_keys=True,
                        default=str,
                    ).encode()
                ).hexdigest(),
            }
        )
    blockers: list[str] = []
    if not chapters:
        blockers.append("No saved chapters are eligible for reprocessing.")
    if missing_chapters:
        blockers.append("Stored source text is unavailable for one or more chapters.")
    if state["rebuild_run_id"] or state["chapter_extraction_active"]:
        blockers.append("Chapter processing or a rebuild is already in progress.")
    fingerprint = None
    if not blockers:
        snapshot = {
            "book_id": state["book_id"],
            "sources": source_parts,
            "protected_character_ids": state["protected_character_ids"],
            "replaceable_character_ids": state["replaceable_character_ids"],
            "protected_character_reviews": state["protected_character_reviews"],
            "voice_review_decisions": state["voice_review_decisions"],
            "character_candidate_reviews": state["character_candidate_reviews"],
            "relationship_candidate_reviews": state["relationship_candidate_reviews"],
            "manual_identity_constraints": state["manual_identity_constraints"],
        }
        fingerprint = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
    return ManuscriptReprocessPreflightOut(
        book_id=str(book_id),
        ready=not blockers,
        chapters_total=len(chapters),
        processed_words_to_reserve=sum(chapter["word_count"] for chapter in chapters),
        protected_characters=len(state["protected_character_ids"]),
        replaceable_characters=len(state["replaceable_character_ids"]),
        missing_source_chapters=missing_chapters,
        blockers=blockers,
        preview_fingerprint=fingerprint,
    )


async def start_manual_manuscript_reprocess(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    body: ManuscriptReprocessBody,
) -> ManuscriptReprocessOut:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await ensure_project_writable(db, book)
    user_id = current_user.id
    resolved_book_id = book.id

    if not (body.confirm_processing_words or body.confirm_upload_charge):
        raise HTTPException(
            400,
            "Confirm that reprocessing will consume processed-word allowance before continuing.",
        )

    from app.services.editor_project_service import (
        dispatch_rebuild,
        fail_rebuild_if_active,
        get_rebuild_run_id,
        prepare_rebuild,
    )

    state = await _load_manual_reprocess_state(db, book)
    state_snapshot = json.dumps(state, sort_keys=True, default=str)
    await db.commit()
    preflight = await _build_manual_reprocess_preflight(resolved_book_id, state)
    if not preflight.chapters_total:
        raise HTTPException(400, "Save at least one chapter before reprocessing")
    if not preflight.ready:
        raise HTTPException(409, "Stored-source preflight is no longer ready. Refresh it.")
    if not body.preview_fingerprint:
        raise HTTPException(409, "A reprocess preview is required. Refresh the preflight.")
    if preflight.preview_fingerprint != body.preview_fingerprint:
        raise HTTPException(
            409, "The manuscript or review decisions changed. Refresh the preflight."
        )

    await _lock_book_reprocessing(db, resolved_book_id)
    await db.refresh(book)
    if book.user_id != user_id:
        raise HTTPException(404, "Book not found")
    await db.refresh(current_user)
    require_author_access(current_user)
    await ensure_project_writable(db, book)
    if get_rebuild_run_id(book) is not None:
        raise HTTPException(409, "A rebuild is already in progress for this project")
    if await _chapter_extraction_is_active(db, book.id):
        raise HTTPException(409, "Chapter processing is already in progress for this project")
    locked_state = await _load_manual_reprocess_state(db, book)
    if json.dumps(locked_state, sort_keys=True, default=str) != state_snapshot:
        raise HTTPException(
            409, "The manuscript or review decisions changed. Refresh the preflight."
        )

    chapters = (
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id, Chapter.word_count > 0)
            )
        )
        .scalars()
        .all()
    )
    chapters = await filter_analysis_eligible_chapters(db, book.id, list(chapters))

    if not chapters:
        raise HTTPException(400, "Save at least one chapter before reprocessing")

    requested_words = sum(int(chapter.word_count or 0) for chapter in chapters)
    rebuild_run_id = uuid.uuid4().hex
    source_prefix = manual_reprocess_source_prefix(rebuild_run_id)
    reservations, allowance = await reserve_processing_word_batch(
        db,
        current_user,
        book_id=book.id,
        usage_kind=MANUAL_REPROCESS_USAGE_KIND,
        requests=[
            ProcessingReservationRequest(
                source_id=f"{source_prefix}{chapter.id}:{chapter.content_version}",
                word_count=int(chapter.word_count or 0),
            )
            for chapter in chapters
        ],
    )
    reservation_ids_by_chapter_id = {
        chapter.id: reservation.id
        for chapter, reservation in zip(chapters, reservations, strict=True)
    }
    try:
        await prepare_rebuild(
            db,
            book,
            reason="manual_reprocess",
            rebuild_run_id=rebuild_run_id,
        )
        chapters_queued, total_words = await dispatch_rebuild(
            db,
            book,
            reservation_ids_by_chapter_id=reservation_ids_by_chapter_id,
            manual_reprocess=True,
            run_kind="manual_reprocess",
        )
        await db.commit()
    except MANUAL_REPROCESS_FINALIZATION_ERRORS as exc:
        log.exception(
            "manual_reprocess_allowance_failed book_id=%s rebuild_run_id=%s",
            resolved_book_id,
            rebuild_run_id,
        )
        await db.rollback()
        try:
            await release_processing_reservations_for_source_prefix(
                db,
                user_id=user_id,
                book_id=resolved_book_id,
                usage_kind=MANUAL_REPROCESS_USAGE_KIND,
                source_prefix=source_prefix,
            )
            await db.refresh(book)
            await fail_rebuild_if_active(
                db,
                book,
                expected_rebuild_run_id=rebuild_run_id,
                error="Unable to dispatch the manual reprocess.",
            )
            await db.commit()
        except MANUAL_REPROCESS_CLEANUP_ERRORS:
            await db.rollback()
            log.exception(
                "manual_reprocess_allowance_cleanup_failed book_id=%s rebuild_run_id=%s",
                resolved_book_id,
                rebuild_run_id,
            )
        raise HTTPException(
            503,
            "Unable to start the reprocess. Unused processed-word reservations were released.",
        ) from exc

    return ManuscriptReprocessOut(
        book_id=str(resolved_book_id),
        status="processing",
        chapters_queued=chapters_queued,
        total_words=total_words,
        upload_charge_consumed=False,
        charge_kind=None,
        processed_words_reserved=requested_words,
        processed_words_remaining=allowance.monthly_processed_words_remaining,
    )


async def start_manual_chapter_reprocess(
    *,
    db: AsyncSession,
    current_user,
    book_id: uuid.UUID,
    chapter_number: int,
) -> ManuscriptReprocessOut:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await ensure_project_writable(db, book)

    chapter = (
        await db.execute(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.number == chapter_number)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(404, "Chapter not found")
    if not chapter.word_count or chapter.word_count <= 0:
        raise HTTPException(400, "Save chapter content before reprocessing")
    source_identity = (
        chapter.id,
        chapter.content_version,
        chapter.s3_key,
        chapter.title,
        chapter.word_count,
    )
    source_key = chapter.s3_key
    source_title = chapter.title
    await db.commit()
    chapter_payload = await load_processing_chapter_payload(
        book.id,
        chapter_number,
        chapter_s3_key=source_key,
        chapter_title=source_title,
    )
    if chapter_payload is None:
        raise HTTPException(400, "Save chapter content before reprocessing")

    await _lock_book_reprocessing(db, book.id)
    await db.refresh(book)
    if book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    await db.refresh(current_user)
    require_author_access(current_user)
    await ensure_project_writable(db, book)

    from app.services.editor_project_service import (
        get_rebuild_run_id,
        update_reprocess_metadata,
    )

    if get_rebuild_run_id(book) is not None:
        raise HTTPException(409, "A rebuild is already in progress for this project")
    if await _chapter_extraction_is_active(db, book.id):
        raise HTTPException(409, "Chapter processing is already in progress for this project")
    chapter = (
        await db.execute(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.number == chapter_number)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if (
        chapter is None
        or (
            chapter.id,
            chapter.content_version,
            chapter.s3_key,
            chapter.title,
            chapter.word_count,
        )
        != source_identity
    ):
        raise HTTPException(409, "The chapter changed while loading its source. Retry.")

    estimated_tokens = estimate_manual_reprocess_tokens(str(chapter_payload.get("text") or ""))
    await assert_manual_reprocess_token_capacity(
        db,
        current_user,
        estimated_tokens=estimated_tokens,
    )
    reservation, allowance = await reserve_processing_words(
        db,
        current_user,
        book_id=book.id,
        usage_kind="chapter_reprocess",
        source_id=f"{book.id}:{chapter_number}:{chapter.content_version}:{uuid.uuid4().hex}",
        word_count=int(chapter.word_count or 0),
    )

    chapter.analysis_state = build_analysis_chapter_state(
        chapter.analysis_state if isinstance(chapter.analysis_state, dict) else None,
        status="queued",
        increment_attempt=True,
    )
    update_reprocess_metadata(
        book,
        clear_pending_chapters=[chapter_number],
        last_manual_chapter_number=chapter_number,
    )
    processing_run = await get_or_create_processing_run(
        db,
        user_id=current_user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        chapters_total=1,
        reuse_active=False,
    )
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=processing_run,
        chapter_id=chapter.id,
        chapter_number=chapter_number,
        arguments={
            "book_id": str(book.id),
            "chapter_number": chapter_number,
            "processing_run_id": str(processing_run.id),
            "processing_reservation_id": str(reservation.id),
            "manual_reprocess": True,
        },
        identity_suffix=reservation.id,
    )
    reservation.task_id = str(execution.id)
    await db.commit()
    await db.refresh(book)
    await invalidate_advisor_caches_for_book(db, book_id=book.id)
    await mark_book_cache_dirty(str(book.id))

    await dispatch_pending_extraction_tasks(db)

    return ManuscriptReprocessOut(
        book_id=str(book.id),
        status="processing",
        chapters_queued=1,
        total_words=int(chapter.word_count or 0),
        upload_charge_consumed=False,
        charge_kind=None,
        processed_words_reserved=int(chapter.word_count or 0),
        processed_words_remaining=allowance.monthly_processed_words_remaining,
    )
