from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    get_book_cache_version,
    get_book_overview_cache,
    set_book_overview_cache,
)
from app.models.book import Book, BookCollaborator
from app.models.intelligence import WorldBuildingDocument, WorldElement
from app.models.progress import ReadingProgress
from app.schemas.books import BookOverviewOut, BookWorldStatsOut
from app.services.pipeline_state_service import enqueue_processing_state_repair_if_needed
from app.utils.books.access import book_cache_access_key
from app.utils.books.serialization import book_out
from app.utils.reader_utils import (
    build_chapter_list_payload,
    build_reading_progress_payload,
    build_summary_collection_payload,
    chapter_intelligence_map,
)
from app.utils.sparse_utils import include_requested, parse_csv_param


async def build_book_world_stats(db: AsyncSession, book: Book) -> BookWorldStatsOut:
    active_document_count = int(
        (
            await db.execute(
                select(func.count(WorldBuildingDocument.id)).where(
                    WorldBuildingDocument.book_id == book.id,
                    WorldBuildingDocument.is_active.is_(True),
                    WorldBuildingDocument.archived_at.is_(None),
                )
            )
        ).scalar()
        or 0
    )
    corpus_words = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(WorldBuildingDocument.word_count), 0)).where(
                    WorldBuildingDocument.book_id == book.id,
                    WorldBuildingDocument.is_active.is_(True),
                    WorldBuildingDocument.archived_at.is_(None),
                )
            )
        ).scalar()
        or 0
    )
    extracted_element_count = int(
        (
            await db.execute(
                select(func.count(WorldElement.id)).where(WorldElement.book_id == book.id)
            )
        ).scalar()
        or 0
    )
    return BookWorldStatsOut(
        active_documents=active_document_count,
        corpus_words=corpus_words,
        extracted_elements=extracted_element_count,
        total_items=active_document_count + extracted_element_count,
    )


async def build_book_overview_payload(
    db: AsyncSession,
    *,
    book: Book,
    current_user: Any,
    collaborator: BookCollaborator | None = None,
    include: str | None = None,
    fields: str | None = None,
) -> BookOverviewOut:
    await enqueue_processing_state_repair_if_needed(book)
    include_param = include if isinstance(include, str) else None
    fields_param = fields if isinstance(fields, str) else None
    use_cache = parse_csv_param(include_param) is None and fields_param is None
    if use_cache:
        cache_version = await get_book_cache_version(str(book.id))
        access_key = book_cache_access_key(current_user.id, collaborator)
        cached = await get_book_overview_cache(
            str(book.id), str(current_user.id), access_key, cache_version
        )
        if cached is not None:
            return BookOverviewOut(**cached)

    progress = (
        (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.book_id == book.id,
                    ReadingProgress.user_id == current_user.id,
                )
            )
        )
        .scalars()
        .first()
    )
    intelligence_map = (
        await chapter_intelligence_map(db, book, current_user)
        if include_requested(include_param, "chapter_list", "summary_collection")
        else {}
    )

    book_payload = await book_out(db, book, current_user.id, collaborator, progress=progress)
    progress_payload = (
        await build_reading_progress_payload(
            db,
            book=book,
            current_user=current_user,
            collaborator=collaborator,
            progress=progress,
        )
        if include_requested(include_param, "progress")
        else None
    )
    chapter_list_payload = (
        await build_chapter_list_payload(
            db,
            book=book,
            current_user=current_user,
            collaborator=collaborator,
            progress=progress,
            intelligence_map=intelligence_map,
        )
        if include_requested(include_param, "chapter_list")
        else None
    )
    summary_collection_payload = (
        await build_summary_collection_payload(
            db,
            book=book,
            current_user=current_user,
            collaborator=collaborator,
            progress=progress,
            intelligence_map=intelligence_map,
        )
        if include_requested(include_param, "summary_collection")
        else None
    )
    world_stats = await build_book_world_stats(db, book)

    payload = BookOverviewOut(
        book=book_payload,
        progress=progress_payload,
        chapter_list=chapter_list_payload,
        summary_collection=summary_collection_payload,
        world_stats=world_stats,
    )
    if use_cache:
        await set_book_overview_cache(
            str(book.id),
            str(current_user.id),
            access_key,
            cache_version,
            payload.model_dump(mode="json"),
        )
    return payload
