"""Guarded, zero-AI repair of an existing PDF book's chapter boundaries."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import uuid

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal
from app.core.redis import mark_book_cache_dirty, mark_user_dashboard_cache_dirty
from app.models.book import (
    Book,
    BookNote,
    BookSection,
    Chapter,
    ChapterMedia,
    ChapterVersion,
    ManuscriptAnnotation,
    NovelScene,
)
from app.models.generation import BookDataGeneration
from app.models.operations import BookProcessingRun, ManuscriptImportJob
from app.models.progress import ReadingProgress, ReadingSession
from app.services.book_section_service import persist_book_sections
from app.services.editor_project_service import update_reprocess_metadata
from app.utils.advisor_utils import invalidate_advisor_caches_for_book
from app.utils.books.chapter_versions import snapshot_chapter_version_reference
from app.utils.books.manuscript import (
    apply_staged_editor_chapter_content,
    stage_editor_chapter_content,
)
from app.utils.storage_utils import delete_storage_keys_best_effort
from scripts.plan_saved_chapter_structure import build_plan

log = logging.getLogger(__name__)


async def _check_locked_state(
    db, book: Book, plan: dict
) -> tuple[list[Chapter], list[ReadingProgress]]:
    """Reject writes made since the source-bound plan was constructed."""
    identity = plan["_identity"]
    if book.format != "pdf" or book.s3_key != identity["source_key"]:
        raise ValueError("saved_pdf_source_changed")
    if (book.import_structure or {}).get("source_sha256") != identity["source_sha256"]:
        raise ValueError("saved_pdf_source_hash_changed")
    if book.is_public or book.public_status == "published":
        raise ValueError("published_book_requires_separate_review")
    generation_id = await db.scalar(
        select(BookDataGeneration.id).where(
            BookDataGeneration.book_id == book.id,
            BookDataGeneration.status == "active",
        )
    )
    if str(generation_id) != identity["generation_id"]:
        raise ValueError("active_generation_changed")
    busy_runs = await db.scalar(
        select(func.count())
        .select_from(BookProcessingRun)
        .where(
            BookProcessingRun.book_id == book.id,
            BookProcessingRun.status.in_(["queued", "running", "paused", "cancel_requested"]),
        )
    )
    busy_imports = await db.scalar(
        select(func.count())
        .select_from(ManuscriptImportJob)
        .where(
            ManuscriptImportJob.book_id == book.id,
            ManuscriptImportJob.status.in_(["queued", "running", "cancel_requested"]),
        )
    )
    if busy_runs or busy_imports:
        raise ValueError("book_processing_in_progress")
    chapters = (
        (
            await db.execute(
                select(Chapter)
                .where(Chapter.book_id == book.id)
                .order_by(Chapter.number)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    observed = [
        {
            "number": row.number,
            "id": str(row.id),
            "content_version": row.content_version,
            "title": row.title,
            "s3_key": row.s3_key,
        }
        for row in chapters
    ]
    expected = [
        {key: row[key] for key in ("number", "id", "content_version", "title", "s3_key")}
        for row in identity["saved_chapters"]
    ]
    if observed != expected:
        raise ValueError("saved_chapters_changed")
    counts = {}
    for label, model in (
        ("saved_scenes", NovelScene),
        ("chapter_versions", ChapterVersion),
        ("manuscript_annotations", ManuscriptAnnotation),
        ("book_sections", BookSection),
        ("chapter_media", ChapterMedia),
        ("reading_sessions", ReadingSession),
    ):
        counts[label] = int(
            await db.scalar(select(func.count()).select_from(model).where(model.book_id == book.id))
            or 0
        )
    counts["chapter_notes"] = int(
        await db.scalar(
            select(func.count())
            .select_from(BookNote)
            .where(BookNote.book_id == book.id, BookNote.chapter_number.is_not(None))
        )
        or 0
    )
    progress = (
        (
            await db.execute(
                select(ReadingProgress)
                .where(ReadingProgress.book_id == book.id)
                .order_by(ReadingProgress.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    counts["reading_progress"] = len(progress)
    if counts != identity["record_counts"]:
        raise ValueError("related_records_changed")
    if any(counts[label] for label in counts if label not in {"book_sections", "reading_progress"}):
        raise ValueError("related_records_require_manual_mapping")
    section_ids = [
        str(value)
        for value in (
            await db.execute(
                select(BookSection.id)
                .where(BookSection.book_id == book.id)
                .order_by(BookSection.display_order, BookSection.id)
            )
        )
        .scalars()
        .all()
    ]
    if section_ids != identity["section_ids"]:
        raise ValueError("outline_changed")
    progress_snapshot = [
        {
            "id": str(row.id),
            "current_chapter": row.current_chapter,
            "scroll_pct": row.scroll_pct,
            "chapters_read": row.chapters_read,
        }
        for row in progress
    ]
    if progress_snapshot != identity["reading_progress"]:
        raise ValueError("reading_progress_changed")
    return chapters, progress


async def apply_plan(book_id: uuid.UUID, generation_id: uuid.UUID, plan_sha256: str) -> dict:
    plan = await build_plan(book_id, include_private=True)
    if plan["active_generation_id"] != str(generation_id):
        raise ValueError("active_generation_changed")
    if plan["plan_sha256"] != plan_sha256:
        raise ValueError("saved_chapter_plan_changed")
    if not plan["all_chapter_content_preserved"] or not plan["all_chapter_titles_match"]:
        raise ValueError("saved_chapter_content_or_titles_not_preserved")
    if plan["proposed_chapter_count"] <= plan["saved_chapter_count"]:
        raise ValueError("saved_chapter_split_not_needed")
    reparsed = plan["_reparsed"]
    staged = []
    committed = False
    try:
        async with AsyncSessionLocal() as db:
            book = await db.get(Book, book_id)
            if book is None:
                raise ValueError("book_not_found")
            for row in reparsed["chapters"]:
                staged.append(
                    await stage_editor_chapter_content(
                        book,
                        chapter_number=row["number"],
                        text=row["text"],
                        html=None,
                    )
                )
            await db.rollback()
            book = (
                await db.execute(select(Book).where(Book.id == book_id).with_for_update())
            ).scalar_one()
            old_chapters, progress = await _check_locked_state(db, book, plan)
            new_rows = []
            for index, (row, content) in enumerate(zip(reparsed["chapters"], staged)):
                original = old_chapters[index] if index < len(old_chapters) else None
                if original is not None:
                    await snapshot_chapter_version_reference(
                        db,
                        book,
                        original,
                        note="Original PDF chapter before structure repair",
                        snapshot_kind="pre_replace",
                    )
                new_rows.append(
                    await apply_staged_editor_chapter_content(
                        db,
                        book,
                        chapter=original,
                        chapter_number=row["number"],
                        title=row["title"],
                        staged=content,
                        chapter_kind=row["section_type"],
                        content_version=(int(original.content_version or 1) + 1)
                        if original is not None
                        else 1,
                    )
                )
            await db.execute(delete(BookSection).where(BookSection.book_id == book_id))
            await db.flush()
            await persist_book_sections(
                db,
                book=book,
                plan=reparsed["structure_plan"],
                chapter_rows=new_rows,
                chapters=reparsed["chapters"],
            )
            for old, mapped in zip(progress, plan["reading_progress_mapping"]):
                old.current_chapter = mapped["current_chapter"]
                old.scroll_pct = mapped["scroll_pct"]
                old.chapters_read = mapped["chapters_read"]
            book.import_structure = reparsed["structure_plan"]
            book.total_chapters = len(new_rows)
            update_reprocess_metadata(
                book,
                add_pending_chapters=list(range(1, len(new_rows) + 1)),
            )
            # A lost commit acknowledgement is ambiguous; never delete staged
            # storage objects if the database may already reference them.
            committed = True
            await db.commit()
        try:
            async with AsyncSessionLocal() as db:
                await invalidate_advisor_caches_for_book(db, book_id=book_id)
            await mark_book_cache_dirty(str(book_id))
            await mark_user_dashboard_cache_dirty(str(book.user_id))
        except Exception:
            log.exception("saved_chapter_structure_cache_invalidation_failed")
        return {
            "book_id": str(book_id),
            "plan_sha256": plan_sha256,
            "chapters": len(new_rows),
            "outline_sections": len(reparsed["structure_plan"]["sections"]),
            "progress_records_mapped": len(plan["reading_progress_mapping"]),
            "old_chapter_versions_preserved": len(old_chapters),
            "ai_calls": 0,
            "analysis_reprocess_started": False,
        }
    except Exception:
        if not committed:
            await delete_storage_keys_best_effort(
                [key for item in staged for key in item.uploaded_keys],
                context="saved_chapter_structure_repair_rollback",
            )
        raise


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", required=True, type=uuid.UUID)
    parser.add_argument("--expected-generation-id", required=True, type=uuid.UUID)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--confirm-apply", required=True)
    args = parser.parse_args()
    if args.confirm_apply != "REPAIR_SAVED_PDF_CHAPTER_STRUCTURE":
        raise ValueError("explicit_structure_repair_confirmation_required")
    result = await apply_plan(
        args.book_id,
        args.expected_generation_id,
        args.expected_plan_sha256,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
