from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book
from app.engine.world.extractor import extract_world_elements_from_text
from app.models.book import Book, Chapter
from app.models.intelligence import WorldBuildingDocument, WorldSourceObservation
from app.services.world_analysis_state_service import (
    content_sha256,
    record_world_source_observations,
)
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS, bounded_storage_map
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
            stored = deserialize_manuscript_content(await asyncio.to_thread(download_book, s3_key))
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


async def materialize_missing_story_candidate_records(
    db: AsyncSession,
    book: Book,
) -> list[dict]:
    """Backfill observations only for legacy chapters that have never been materialized.

    Normal extraction writes observations as part of chapter processing. This fallback
    is used by explicit/background snapshot refreshes so pre-migration chapters are
    downloaded once, while ordinary world-building reads remain storage-free.
    """

    chapter_rows = list(
        (
            await db.execute(
                select(Chapter)
                .where(Chapter.book_id == book.id)
                .order_by(Chapter.number.asc(), Chapter.id.asc())
            )
        )
        .scalars()
        .all()
    )
    if not chapter_rows:
        return []

    observed_chapter_ids = set(
        (
            await db.scalars(
                select(WorldSourceObservation.chapter_id).where(
                    WorldSourceObservation.book_id == book.id,
                    WorldSourceObservation.source_kind == "chapter",
                    WorldSourceObservation.chapter_id.is_not(None),
                )
            )
        ).all()
    )
    missing_chapters = [
        chapter
        for chapter in chapter_rows
        if chapter.id not in observed_chapter_ids and chapter.s3_key
    ]
    if not missing_chapters:
        return []

    async def load_chapter(chapter: Chapter) -> tuple[Chapter, str] | None:
        try:
            stored = deserialize_manuscript_content(
                await asyncio.to_thread(download_book, chapter.s3_key)
            )
        except STORAGE_IO_EXCEPTIONS:
            return None
        return chapter, str(stored.get("text") or "")

    loaded = await bounded_storage_map(missing_chapters, load_chapter)
    character_registry = await load_character_registry(db, book)
    override_lookup = await load_canon_override_lookup(db, book)
    materialized: list[dict] = []
    for loaded_chapter in loaded:
        if loaded_chapter is None:
            continue
        chapter, text = loaded_chapter
        candidates: list[dict] = []
        for candidate in _apply_character_and_override_resolution(
            extract_world_elements_from_text(text, chapter_number=chapter.number),
            character_registry=character_registry,
            override_lookup=override_lookup,
        ):
            candidate_record = dict(candidate)
            candidate_record["chapter_number"] = chapter.number
            candidate_record["chapter_title"] = chapter.title
            candidates.append(candidate_record)
        await record_world_source_observations(
            db,
            book_id=book.id,
            chapter_id=chapter.id,
            source_kind="chapter",
            source_key=str(chapter.id),
            source_fingerprint=content_sha256(text),
            candidates=candidates,
        )
        materialized.extend(candidates)
    return materialized
