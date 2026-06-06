"""Editor-project service: rebuild orchestration for empty-origin books.

Rebuild resets all generated intelligence and re-runs extraction + analysis
from saved editor chapters. Curated (author-edited) data is preserved.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import (
    mark_book_cache_dirty,
    mark_user_dashboard_cache_dirty,
)
from app.models.book import Book, Chapter
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    WikiEntry,
    WorldGapAnalysis,
    WorldElement,
)
from app.models.tag import CustomTag
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.ingestion_utils import build_chapter_dispatch_plan

log = logging.getLogger("lorevia.editor_project")

CHARACTER_CANDIDATE_PENDING = "pending"
CHARACTER_CANDIDATE_SUPPRESSED = "suppressed"
AUTO_FIRST_REPROCESS_WORD_THRESHOLD = 2000


def _reprocess_metadata(book: Book) -> dict[str, Any]:
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    metadata = workspace.get("reprocess") if isinstance(workspace.get("reprocess"), dict) else {}
    return dict(metadata)


def auto_reprocess_enabled(book: Book) -> bool:
    metadata = _reprocess_metadata(book)
    return bool(metadata.get("auto_reprocess_enabled", True))


def update_reprocess_metadata(
    book: Book,
    *,
    auto_reprocess_enabled: bool | None = None,
    add_pending_chapters: list[int] | None = None,
    clear_pending_chapters: list[int] | None = None,
    last_manual_chapter_number: int | None = None,
) -> None:
    from app.utils.book_utils import normalize_reprocess_metadata, normalize_writer_workspace

    workspace = normalize_writer_workspace(book.writer_workspace if isinstance(book.writer_workspace, dict) else None)
    metadata = normalize_reprocess_metadata(workspace.get("reprocess") if isinstance(workspace.get("reprocess"), dict) else None)
    now = datetime.now(UTC).isoformat()
    if auto_reprocess_enabled is not None:
        metadata["auto_reprocess_enabled"] = bool(auto_reprocess_enabled)
        metadata["last_mode_changed_at"] = now
    pending = {
        int(item)
        for item in (metadata.get("pending_chapters") or [])
        if isinstance(item, (int, float)) and int(item) > 0
    }
    for chapter_number in add_pending_chapters or []:
        if isinstance(chapter_number, int) and chapter_number > 0:
            pending.add(chapter_number)
    for chapter_number in clear_pending_chapters or []:
        if isinstance(chapter_number, int) and chapter_number > 0:
            pending.discard(chapter_number)
    metadata["pending_chapters"] = sorted(pending)
    if last_manual_chapter_number is not None:
        metadata["last_manual_chapter_started_at"] = now
        metadata["last_manual_chapter_number"] = int(last_manual_chapter_number)
    workspace["reprocess"] = metadata
    book.writer_workspace = workspace


async def purge_manual_chapter_reprocess_content(
    db: AsyncSession,
    *,
    book: Book,
    chapter: Chapter,
) -> None:
    await db.execute(delete(BookChunk).where(BookChunk.chapter_id == chapter.id))
    await db.execute(delete(ChapterSummary).where(ChapterSummary.chapter_id == chapter.id))
    await db.execute(
        delete(CharacterMention).where(
            CharacterMention.book_id == book.id,
            CharacterMention.chapter_number == chapter.number,
        )
    )
    await db.execute(
        delete(CharacterCandidate).where(
            CharacterCandidate.book_id == book.id,
            CharacterCandidate.chapter_number == chapter.number,
            CharacterCandidate.status.in_((CHARACTER_CANDIDATE_PENDING, CHARACTER_CANDIDATE_SUPPRESSED)),
        )
    )
    await db.execute(
        delete(CharacterRelationshipCandidate).where(
            CharacterRelationshipCandidate.book_id == book.id,
            CharacterRelationshipCandidate.chapter_number == chapter.number,
        )
    )
    await db.execute(
        delete(CharacterRelationship).where(
            CharacterRelationship.book_id == book.id,
            CharacterRelationship.from_chapter == chapter.number,
            CharacterRelationship.edited_by_author == False,
        )
    )
    await db.execute(
        delete(CharacterState).where(
            CharacterState.character_id.in_(
                select(Character.id).where(Character.book_id == book.id)
            ),
            CharacterState.at_chapter == chapter.number,
        )
    )
    chapter.processed = False
    chapter.analysis_state = {}
    await db.flush()


def has_reprocess_started(book: Book) -> bool:
    metadata = _reprocess_metadata(book)
    return bool(
        metadata.get("last_started_at")
        or metadata.get("auto_first_started_at")
        or metadata.get("manual_started_at")
    )


async def reset_generated_data(db: AsyncSession, book: Book) -> dict[str, int]:
    """Delete all generated intelligence rows for a book.

    PRESERVES: chapters, novel scenes, versions, notes, annotations,
    world-building documents, canon overrides, world notes, curated world
    elements, curated relationships, curated plot threads, anchor characters
    (manual or referenced by curated data), and authored custom tags.
    """
    from app.utils.character_utils import CHARACTER_CANDIDATE_PENDING, CHARACTER_CANDIDATE_SUPPRESSED

    counts: dict[str, int] = {}

    _book_id = book.id
    chapter_ids_result = await db.execute(
        select(Chapter.id).where(Chapter.book_id == _book_id)
    )
    chapter_ids = [row[0] for row in chapter_ids_result.all()]

    # --- Delete generated rows that are never curated ---

    result = await db.execute(delete(BookChunk).where(BookChunk.book_id == _book_id))
    counts["book_chunks"] = result.rowcount

    if chapter_ids:
        result = await db.execute(
            delete(ChapterSummary).where(ChapterSummary.chapter_id.in_(chapter_ids))
        )
        counts["chapter_summaries"] = result.rowcount
        chapters = (
            await db.execute(select(Chapter).where(Chapter.book_id == _book_id))
        ).scalars().all()
        for chapter in chapters:
            chapter.processed = not bool(chapter.word_count and chapter.word_count > 0)
            chapter.analysis_state = {}
        counts["chapters_reset"] = len(chapters)

    result = await db.execute(delete(WikiEntry).where(WikiEntry.book_id == _book_id))
    counts["wiki_entries"] = result.rowcount

    result = await db.execute(delete(WorldGapAnalysis).where(WorldGapAnalysis.book_id == _book_id))
    counts["world_gap_analyses"] = result.rowcount

    result = await db.execute(
        delete(CharacterCandidate).where(
            CharacterCandidate.book_id == _book_id,
            CharacterCandidate.status.in_(
                (CHARACTER_CANDIDATE_PENDING, CHARACTER_CANDIDATE_SUPPRESSED)
            ),
        )
    )
    counts["character_candidates"] = result.rowcount

    result = await db.execute(
        delete(CharacterMention).where(CharacterMention.book_id == _book_id)
    )
    counts["character_mentions"] = result.rowcount

    result = await db.execute(
        delete(CharacterDuplicateSuggestion).where(
            CharacterDuplicateSuggestion.book_id == _book_id
        )
    )
    counts["duplicate_suggestions"] = result.rowcount

    result = await db.execute(
        delete(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == _book_id)
    )
    counts["voice_profiles"] = result.rowcount

    # --- Delete generated world elements, preserve curated ---

    result = await db.execute(
        delete(WorldElement).where(
            WorldElement.book_id == _book_id,
            WorldElement.edited_by_author == False,
        )
    )
    counts["world_elements"] = result.rowcount

    # --- Delete non-curated relationships, preserve curated ---

    result = await db.execute(
        delete(CharacterRelationship).where(
            CharacterRelationship.book_id == _book_id,
            CharacterRelationship.edited_by_author == False,
        )
    )
    counts["relationships"] = result.rowcount

    # --- Delete non-curated plot threads, preserve curated ---

    result = await db.execute(
        delete(PlotThread).where(
            PlotThread.book_id == _book_id,
            PlotThread.edited_by_author == False,
        )
    )
    counts["plot_threads"] = result.rowcount

    # --- Handle characters: preserve anchors, delete rest ---

    character_counts = await _reset_characters_for_book(db, _book_id)
    counts.update(character_counts)

    # --- Delete CharacterState for remaining (anchor) characters ---

    anchor_ids_result = await db.execute(
        select(Character.id).where(Character.book_id == _book_id)
    )
    anchor_ids = [row[0] for row in anchor_ids_result.all()]
    if anchor_ids:
        result = await db.execute(
            delete(CharacterState).where(CharacterState.character_id.in_(anchor_ids))
        )
        counts["character_states"] = result.rowcount

    await db.flush()
    return counts


async def _reset_characters_for_book(db: AsyncSession, book_id: uuid.UUID) -> dict[str, int]:
    """Delete generated characters, reset counters on anchor characters."""
    counts: dict[str, int] = {}

    anchor_ids = await _resolve_character_anchor_ids(db, book_id)

    all_chars_result = await db.execute(
        select(Character.id, Character.is_manual).where(Character.book_id == book_id)
    )
    all_chars = all_chars_result.all()

    deleted = 0
    for char_id, is_manual in all_chars:
        if char_id in anchor_ids:
            await db.execute(
                select(Character).where(Character.id == char_id)
            )
            char_result = await db.execute(
                select(Character).where(Character.id == char_id)
            )
            char = char_result.scalar_one_or_none()
            if char is not None:
                char.mention_count = 0
                char.last_seen_chapter = None
                char.analysis_metadata = {}
                char.growth_events = []
        else:
            await db.execute(delete(Character).where(Character.id == char_id))
            deleted += 1

    counts["characters_deleted"] = deleted
    counts["characters_preserved"] = len(anchor_ids)
    return counts


async def _resolve_character_anchor_ids(db: AsyncSession, book_id: uuid.UUID) -> set[uuid.UUID]:
    """Find character IDs that should be preserved as extraction anchors.

    Anchors are characters that are:
      - manually created (is_manual == True), OR
      - referenced by a curated relationship (edited_by_author == True), OR
      - have authored custom tags (entity_type == "character")
    """
    anchors: set[uuid.UUID] = set()

    manual_result = await db.execute(
        select(Character.id).where(
            Character.book_id == book_id,
            Character.is_manual == True,
        )
    )
    anchors.update(row[0] for row in manual_result.all())

    curated_rel_a = await db.execute(
        select(CharacterRelationship.character_a_id).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.edited_by_author == True,
        )
    )
    curated_rel_b = await db.execute(
        select(CharacterRelationship.character_b_id).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.edited_by_author == True,
        )
    )
    anchors.update(row[0] for row in curated_rel_a.all())
    anchors.update(row[0] for row in curated_rel_b.all())

    tagged_char_ids = await db.execute(
        select(CustomTag.entity_id).where(
            CustomTag.book_id == book_id,
            CustomTag.entity_type == "character",
        )
    )
    anchors.update(row[0] for row in tagged_char_ids.all())

    return anchors


async def prepare_rebuild(
    db: AsyncSession,
    book: Book,
    *,
    reason: str = "manual_reprocess",
    auto_first_threshold_words: int | None = None,
) -> str:
    """Reset generated data and mark the book as processing with a new run ID.

    Returns the new rebuild_run_id string.
    """
    rebuild_run_id = uuid.uuid4().hex
    counts = await reset_generated_data(db, book)

    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    from app.utils.book_utils import normalize_writer_workspace

    workspace = normalize_writer_workspace(workspace)
    now = datetime.now(UTC)
    reprocess_metadata = dict(workspace.get("reprocess") if isinstance(workspace.get("reprocess"), dict) else {})
    reprocess_metadata["last_started_at"] = now.isoformat()
    reprocess_metadata["last_reason"] = reason
    reprocess_metadata["last_rebuild_run_id"] = rebuild_run_id
    if reason == "auto_first_2000_words":
        reprocess_metadata["auto_first_started_at"] = now.isoformat()
        reprocess_metadata["auto_first_threshold_words"] = int(auto_first_threshold_words or AUTO_FIRST_REPROCESS_WORD_THRESHOLD)
    elif reason == "manual_reprocess":
        reprocess_metadata["manual_started_at"] = now.isoformat()
    workspace["reprocess"] = reprocess_metadata
    workspace["processing"] = {
        "status": "processing",
        "stage": "extraction",
        "rebuild_run_id": rebuild_run_id,
        "chapters_completed": 0,
        "chapters_total": book.total_chapters,
        "started_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    book.writer_workspace = workspace
    book.status = "processing"

    await db.commit()
    await db.refresh(book)

    await mark_book_cache_dirty(str(book.id))
    await mark_user_dashboard_cache_dirty(book.user_id)
    await invalidate_advisor_caches_for_book(db, book_id=book.id)

    log.info(
        "editor_rebuild_prepared book_id=%s rebuild_run_id=%s counts=%s",
        book.id,
        rebuild_run_id,
        counts,
    )
    return rebuild_run_id


async def dispatch_rebuild(db: AsyncSession, book: Book) -> tuple[int, int]:
    """Queue chapter processing tasks for rebuild.

    Returns (chapters_queued, total_words).
    """
    from app.utils.queue_utils import queue_for_user
    from app.workers.tasks.extraction_tasks import process_chapter_task
    from app.models.user import User
    from app.utils.billing_utils import has_paid_reading_access

    user = await db.get(User, book.user_id)
    rebuild_run_id = get_rebuild_run_id(book)

    if user and not has_paid_reading_access(user):
        result = await db.execute(
            select(func.sum(Book.total_tokens))
            .where(Book.user_id == user.id, Book.id != book.id, Book.status != "error")
        )
        used_so_far = result.scalar() or 0
        remaining_budget = max(0, settings.FREE_TOTAL_TOKEN_BUDGET - used_so_far)
        if remaining_budget == 0:
            await fail_rebuild_if_active(
                db,
                book,
                expected_rebuild_run_id=rebuild_run_id,
                error="token_budget_exhausted",
            )
            book.status = "error"
            book.total_tokens = 0
            await db.commit()
            return 0, 0
    if not rebuild_run_id:
        raise RuntimeError("active_rebuild_run_required")

    chapters_result = await db.execute(
        select(Chapter)
        .where(Chapter.book_id == book.id)
        .order_by(Chapter.number.asc())
    )
    chapters = chapters_result.scalars().all()

    total_words = 0
    chapter_numbers: list[int] = []
    for ch in chapters:
        wc = ch.word_count or 0
        total_words += wc
        if wc > 0:
            chapter_numbers.append(ch.number)

    if not chapter_numbers:
        await _transition_to_ready(db, book)
        return 0, 0

    book.total_chapters = len(chapter_numbers)
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    if isinstance(workspace.get("processing"), dict):
        workspace["processing"]["chapters_total"] = len(chapter_numbers)
        workspace["processing"]["status"] = "processing"
        workspace["processing"]["stage"] = "extraction"
    book.writer_workspace = workspace
    await db.commit()

    dispatch_plan = build_chapter_dispatch_plan(
        chapter_numbers,
        eager_limit=settings.LAZY_PROCESS_INITIAL_CHAPTERS,
        dispatch_window=settings.INGESTION_CHAPTER_DISPATCH_WINDOW,
        dispatch_delay_seconds=settings.INGESTION_CHAPTER_DISPATCH_DELAY_SECONDS,
    )

    try:
        for dispatch in dispatch_plan:
            process_chapter_task.apply_async(
                args=[str(book.id), dispatch.chapter_number],
                kwargs={"rebuild_run_id": rebuild_run_id},
                queue=queue_for_user(user, "extraction") if user else "extraction",
                countdown=dispatch.countdown,
            )
    except Exception as exc:
        await fail_rebuild_if_active(
            db,
            book,
            expected_rebuild_run_id=rebuild_run_id,
            error=str(exc),
        )
        await db.commit()
        raise

    log.info(
        "editor_rebuild_dispatched book_id=%s chapters=%s total_words=%s",
        book.id,
        len(dispatch_plan),
        total_words,
    )
    return len(dispatch_plan), total_words


async def maybe_auto_reprocess_editor_project(db: AsyncSession, book: Book) -> tuple[bool, int, int]:
    """Start the free first rebuild for editor projects once they cross the word threshold."""
    if not getattr(book, "is_editor_project", False):
        return False, 0, 0
    if not auto_reprocess_enabled(book):
        return False, 0, 0
    if get_rebuild_run_id(book) is not None or has_reprocess_started(book):
        return False, 0, 0
    total_words = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                    Chapter.book_id == book.id,
                    Chapter.word_count > 0,
                )
            )
        ).scalar()
        or 0
    )
    if total_words < AUTO_FIRST_REPROCESS_WORD_THRESHOLD:
        return False, 0, total_words

    await prepare_rebuild(
        db,
        book,
        reason="auto_first_2000_words",
        auto_first_threshold_words=AUTO_FIRST_REPROCESS_WORD_THRESHOLD,
    )
    chapters_queued, rebuilt_words = await dispatch_rebuild(db, book)
    return True, chapters_queued, rebuilt_words


async def _transition_to_ready(db: AsyncSession, book: Book) -> None:
    """Mark a zero-chapter editor project as ready."""
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = dict(workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {})
    processing["status"] = "ready"
    processing["stage"] = "complete"
    processing["is_fully_ready"] = True
    workspace["processing"] = processing
    book.writer_workspace = workspace
    book.status = "ready"
    await complete_rebuild_if_ready(db, book)
    await db.commit()


async def complete_rebuild_if_ready(db: AsyncSession, book: Book) -> bool:
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace.get("processing"), dict) else None
    if not processing or not processing.get("rebuild_run_id"):
        return False
    processing = await reconcile_editor_rebuild_processing_state(db, book, processing=processing)
    workspace["processing"] = processing
    book.writer_workspace = workspace
    if not processing.get("is_fully_ready"):
        return False
    now = datetime.now(UTC)
    reprocess_metadata = dict(workspace.get("reprocess") if isinstance(workspace.get("reprocess"), dict) else {})
    reprocess_metadata["last_completed_at"] = now.isoformat()
    reprocess_metadata["last_completed_rebuild_run_id"] = processing.get("rebuild_run_id")
    workspace["reprocess"] = reprocess_metadata
    processing.pop("rebuild_run_id", None)
    processing["status"] = "ready"
    processing["stage"] = "complete"
    processing["completed_at"] = now.isoformat()
    workspace["processing"] = processing
    book.writer_workspace = workspace
    if book.status == "processing":
        book.status = "ready"
    await db.flush()
    return True


async def reconcile_editor_rebuild_processing_state(
    db: AsyncSession,
    book: Book,
    *,
    processing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bring editor rebuild processing state back in sync with persisted chapter rows."""
    from app.models.intelligence import ChapterSummary
    from app.utils.ingestion_utils import merge_processing_pipeline

    next_processing = dict(processing if isinstance(processing, dict) else {})
    chapter_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Chapter).where(
                    Chapter.book_id == book.id,
                    Chapter.word_count > 0,
                )
            )
        ).scalar_one()
    )
    processed_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Chapter).where(
                    Chapter.book_id == book.id,
                    Chapter.word_count > 0,
                    Chapter.processed.is_(True),
                )
            )
        ).scalar_one()
    )
    analyzed_count = int(
        (
            await db.execute(
                select(func.count(func.distinct(ChapterSummary.chapter_id)))
                .select_from(ChapterSummary)
                .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.word_count > 0,
                    Chapter.processed.is_(True),
                    ChapterSummary.mode == "detailed",
                )
            )
        ).scalar_one()
    )
    now = datetime.now(UTC).isoformat()
    if chapter_count == 0:
        extraction_status = "succeeded"
        analysis_status = "succeeded"
    else:
        extraction_status = "succeeded" if processed_count >= chapter_count else "running"
        analysis_status = "succeeded" if analyzed_count >= chapter_count else "running"

    next_processing["chapters_completed"] = processed_count
    next_processing["chapters_total"] = chapter_count
    if chapter_count > 0:
        next_processing["progress_pct"] = round((processed_count / chapter_count) * 100, 1)

    return merge_processing_pipeline(
        next_processing,
        extraction={
            "status": extraction_status,
            "completed_chapters": processed_count,
            "total_chapters": chapter_count,
            "updated_at": now,
        },
        analysis={
            "status": analysis_status,
            "completed_chapters": analyzed_count,
            "total_chapters": chapter_count,
            "updated_at": now,
        },
    )


async def fail_rebuild_if_active(
    db: AsyncSession,
    book: Book,
    *,
    expected_rebuild_run_id: str | None = None,
    error: str | None = None,
) -> bool:
    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace.get("processing"), dict) else None
    if not processing or not processing.get("rebuild_run_id"):
        return False
    if expected_rebuild_run_id is not None and processing.get("rebuild_run_id") != expected_rebuild_run_id:
        return False
    now = datetime.now(UTC)
    reprocess_metadata = dict(workspace.get("reprocess") if isinstance(workspace.get("reprocess"), dict) else {})
    reprocess_metadata["last_failed_at"] = now.isoformat()
    reprocess_metadata["last_failed_rebuild_run_id"] = processing.get("rebuild_run_id")
    if error:
        reprocess_metadata["last_error"] = " ".join(str(error).split()).strip()
    workspace["reprocess"] = reprocess_metadata
    processing.pop("rebuild_run_id", None)
    processing["status"] = "failed"
    processing["stage"] = "failed"
    processing["failed_at"] = now.isoformat()
    workspace["processing"] = processing
    book.writer_workspace = workspace
    book.status = "failed"
    await db.flush()
    return True


async def fail_rebuild_run(
    db: AsyncSession,
    book_id: uuid.UUID,
    *,
    expected_rebuild_run_id: str | None = None,
    error: str | None = None,
) -> bool:
    book = await db.get(Book, book_id)
    if book is None:
        return False
    return await fail_rebuild_if_active(
        db,
        book,
        expected_rebuild_run_id=expected_rebuild_run_id,
        error=error,
    )


async def cancel_rebuild_for_manual_edit(
    db: AsyncSession,
    book: Book,
    *,
    reason: str,
) -> bool:
    """Cancel an active editor rebuild because the saved manuscript changed."""
    if not getattr(book, "is_editor_project", False):
        return False

    workspace = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
    processing = dict(workspace.get("processing") if isinstance(workspace.get("processing"), dict) else {})
    rebuild_run_id = processing.get("rebuild_run_id")
    if not rebuild_run_id:
        return False

    now = datetime.now(UTC)
    reprocess_metadata = dict(workspace.get("reprocess") if isinstance(workspace.get("reprocess"), dict) else {})
    reprocess_metadata["last_cancelled_at"] = now.isoformat()
    reprocess_metadata["last_cancelled_rebuild_run_id"] = rebuild_run_id
    reprocess_metadata["last_cancelled_reason"] = reason

    processing.pop("rebuild_run_id", None)
    processing["status"] = "cancelled"
    processing["stage"] = "cancelled"
    processing["cancelled_at"] = now.isoformat()
    processing["last_error"] = reason

    workspace["reprocess"] = reprocess_metadata
    workspace["processing"] = processing
    book.writer_workspace = workspace
    book.status = "ready"
    await db.flush()
    return True


def get_rebuild_run_id(book: Book) -> str | None:
    """Extract the current rebuild_run_id from the book's processing state."""
    workspace = book.writer_workspace if isinstance(book.writer_workspace, dict) else {}
    processing = workspace.get("processing") if isinstance(workspace, dict) else None
    if not processing:
        return None
    return processing.get("rebuild_run_id")


def is_editor_project_processing(book: Book) -> bool:
    """Check if an editor project is currently rebuilding."""
    if not getattr(book, "is_editor_project", False):
        return False
    rebuild_id = get_rebuild_run_id(book)
    return rebuild_id is not None
