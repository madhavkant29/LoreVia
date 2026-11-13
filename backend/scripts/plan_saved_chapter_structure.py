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
    ChapterVersion,
    ManuscriptAnnotation,
    NovelScene,
)
from app.models.generation import BookDataGeneration
from app.utils.books.chapter_boundaries import compare_saved_chapters_with_reparsed
from app.utils.books.imports import parse_structured_prose_upload
from app.utils.books.manuscript import deserialize_manuscript_content

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


async def build_plan(book_id: uuid.UUID) -> dict:
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
    sections = reparsed["structure_plan"]["sections"]
    identity = {
        "source_sha256": source_sha256,
        "generation_id": str(generation_id) if generation_id else None,
        "saved_chapters": [
            {
                "number": row["number"],
                "id": row["id"],
                "content_version": row["content_version"],
                "title": row["title"],
                "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
            }
            for row in saved
        ],
        "new_content_sha256": reparsed["structure_plan"]["content_sha256"],
    }
    plan_sha256 = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return {
        "book_id": str(book_id),
        "read_only": True,
        "active_generation_id": identity["generation_id"],
        "plan_sha256": plan_sha256,
        "saved_chapter_count": len(saved),
        "proposed_chapter_count": len(reparsed["chapters"]),
        "proposed_story_chapters": sum(row["type"] == "chapter" for row in sections),
        "all_chapter_word_sequences_match": bool(comparisons)
        and all(row["word_sequence_matches"] for row in comparisons),
        "all_chapter_titles_match": bool(comparisons)
        and all(row["title_matches"] for row in comparisons),
        "comparisons": comparisons,
        "existing_records": counts,
        "proposed_sections": [
            {
                "type": row["type"],
                "number": row["number"],
                "word_count": row["word_count"],
            }
            for row in sections
        ],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", required=True, type=uuid.UUID)
    args = parser.parse_args()
    result = await build_plan(args.book_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
