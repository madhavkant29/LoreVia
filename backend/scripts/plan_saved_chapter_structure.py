"""Read-only comparison of a saved PDF manuscript with its fresh chapter parse."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import uuid

from sqlalchemy import func, select, text

from app.core.database import AsyncSessionLocal
from app.core.storage import download_book
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
from app.models.progress import ReadingProgress, ReadingSession
from app.utils.books.chapter_boundaries import compare_saved_chapters_with_reparsed
from app.utils.books.imports import parse_structured_prose_upload
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.books.structure_repair import chapter_number_map, map_reading_position

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def build_plan(book_id: uuid.UUID, *, include_private: bool = False) -> dict:
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        book = await db.get(Book, book_id)
        if book is None or book.format != "pdf":
            raise ValueError("saved_pdf_book_required")
        chapters = (
            (
                await db.execute(
                    select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number)
                )
            )
            .scalars()
            .all()
        )
        generation_id = await db.scalar(
            select(BookDataGeneration.id).where(
                BookDataGeneration.book_id == book_id, BookDataGeneration.status == "active"
            )
        )
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
                await db.scalar(
                    select(func.count()).select_from(model).where(model.book_id == book_id)
                )
                or 0
            )
        counts["chapter_notes"] = int(
            await db.scalar(
                select(func.count())
                .select_from(BookNote)
                .where(BookNote.book_id == book_id, BookNote.chapter_number.is_not(None))
            )
            or 0
        )
        progress_rows = (
            (
                await db.execute(
                    select(ReadingProgress)
                    .where(ReadingProgress.book_id == book_id)
                    .order_by(ReadingProgress.id)
                )
            )
            .scalars()
            .all()
        )
        counts["reading_progress"] = len(progress_rows)
        progress_snapshot = [
            {
                "id": str(row.id),
                "current_chapter": row.current_chapter,
                "scroll_pct": row.scroll_pct,
                "chapters_read": row.chapters_read,
            }
            for row in progress_rows
        ]
        section_ids = [
            str(value)
            for value in (
                await db.execute(
                    select(BookSection.id)
                    .where(BookSection.book_id == book_id)
                    .order_by(BookSection.display_order, BookSection.id)
                )
            )
            .scalars()
            .all()
        ]
        saved = []
        for chapter in chapters:
            raw = await asyncio.to_thread(download_book, chapter.s3_key)
            current_text = str(deserialize_manuscript_content(raw).get("text") or "")
            saved.append(
                {
                    "id": str(chapter.id),
                    "number": chapter.number,
                    "content_version": chapter.content_version,
                    "title": chapter.title,
                    "text": current_text,
                    "s3_key": chapter.s3_key,
                }
            )
        raw_pdf = await asyncio.to_thread(download_book, book.s3_key)
        source_sha256 = hashlib.sha256(raw_pdf).hexdigest()
        if source_sha256 != (book.import_structure or {}).get("source_sha256"):
            raise ValueError("saved_pdf_source_hash_changed")

    reparsed = await asyncio.to_thread(
        parse_structured_prose_upload,
        format_name="pdf",
        raw=raw_pdf,
        filename="saved-manuscript.pdf",
    )
    comparisons = compare_saved_chapters_with_reparsed(saved, reparsed["chapters"])
    number_map = chapter_number_map(saved, reparsed["chapters"])
    progress_plan = [
        map_reading_position(
            number_map,
            reparsed["chapters"],
            current_chapter=row["current_chapter"],
            scroll_pct=row["scroll_pct"],
            chapters_read=row["chapters_read"],
        )
        for row in progress_snapshot
    ]
    sections = reparsed["structure_plan"]["sections"]
    identity = {
        "source_sha256": source_sha256,
        "source_key": book.s3_key,
        "generation_id": str(generation_id) if generation_id else None,
        "record_counts": counts,
        "section_ids": section_ids,
        "reading_progress": progress_snapshot,
        "saved_chapters": [
            {
                "number": row["number"],
                "id": row["id"],
                "content_version": row["content_version"],
                "title": row["title"],
                "s3_key": row["s3_key"],
                "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
            }
            for row in saved
        ],
        "new_content_sha256": reparsed["structure_plan"]["content_sha256"],
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    result = {
        "book_id": str(book_id),
        "read_only": True,
        "source_sha256": source_sha256,
        "active_generation_id": identity["generation_id"],
        "plan_sha256": plan_sha256,
        "saved_chapter_count": len(saved),
        "proposed_chapter_count": len(reparsed["chapters"]),
        "proposed_story_chapters": sum(row["type"] == "chapter" for row in sections),
        "saved_paragraphs": sum(row["current_paragraphs"] or 0 for row in comparisons),
        "proposed_paragraphs": sum(row["proposed_paragraphs"] or 0 for row in comparisons),
        "all_chapter_content_preserved": bool(comparisons)
        and all(row["content_preserved"] for row in comparisons),
        "all_chapter_titles_match": bool(comparisons)
        and all(row["title_matches"] for row in comparisons),
        "comparisons": comparisons,
        "existing_records": counts,
        "reading_progress_mapping": progress_plan,
        "proposed_sections": [
            {
                "type": row["type"],
                "number": row["number"],
                "word_count": row["word_count"],
            }
            for row in sections
        ],
    }
    if include_private:
        result["_identity"] = identity
        result["_saved_chapters"] = saved
        result["_reparsed"] = reparsed
        result["_number_map"] = number_map
        result["_progress_snapshot"] = progress_snapshot
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", required=True, type=uuid.UUID)
    args = parser.parse_args()
    result = await build_plan(args.book_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
