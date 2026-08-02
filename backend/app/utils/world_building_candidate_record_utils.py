from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book
from app.engine.world.extractor import extract_world_elements_from_text
from app.models.book import Book, Chapter
from app.models.intelligence import WorldBuildingDocument
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS
from app.utils.world_building_candidate_utils import _apply_character_and_override_resolution
from app.utils.world_building_document_utils import load_world_building_document_payload
from app.utils.world_building_story_utils import (
    load_canon_override_lookup,
    load_character_registry,
)


async def collect_story_candidate_records(db: AsyncSession, book: Book) -> list[dict]:
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    if not chapter_rows:
        return []

    character_registry = await load_character_registry(db, book)
    override_lookup = await load_canon_override_lookup(db, book)
    records: list[dict] = []
    for chapter_number, chapter_title, s3_key in chapter_rows:
        if not s3_key:
            continue
        try:
            stored = deserialize_manuscript_content(download_book(s3_key))
        except STORAGE_IO_EXCEPTIONS:
            continue
        text = str(stored.get("text") or "")
        for candidate in _apply_character_and_override_resolution(
            extract_world_elements_from_text(text, chapter_number=chapter_number),
            character_registry=character_registry,
            override_lookup=override_lookup,
        ):
            candidate_record = dict(candidate)
            candidate_record["chapter_number"] = chapter_number
            candidate_record["chapter_title"] = chapter_title
            records.append(candidate_record)
    return records


async def collect_world_document_candidate_records(
    db: AsyncSession,
    book: Book,
    documents: list[WorldBuildingDocument],
) -> list[dict]:
    if not documents:
        return []

    character_registry = await load_character_registry(db, book)
    override_lookup = await load_canon_override_lookup(db, book)
    records: list[dict] = []
    for document in documents:
        payload = await load_world_building_document_payload(document)
        text = str(payload.get("text") or "")
        for candidate in _apply_character_and_override_resolution(
            extract_world_elements_from_text(text),
            character_registry=character_registry,
            override_lookup=override_lookup,
        ):
            candidate_record = dict(candidate)
            candidate_record["world_document_id"] = str(document.id)
            candidate_record["world_document_title"] = document.title
            records.append(candidate_record)
    return records
