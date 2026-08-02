from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_binary
from app.engine.world.extractor import extract_world_elements_from_text, infer_element_type
from app.models.book import Book
from app.models.intelligence import WorldBuildingDocument, WorldElement
from app.utils.books.manuscript import clean_manuscript_html, serialize_manuscript_content
from app.utils.world_building_candidate_utils import (
    _apply_character_and_override_resolution,
)
from app.utils.world_building_document_utils import (
    list_world_building_documents,
    load_world_building_document_payload,
)
from app.utils.world_building_serialization_utils import count_words
from app.utils.world_building_story_utils import (
    load_canon_override_lookup,
    load_character_registry,
)


async def create_world_building_documents(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    documents: list[dict],
    replace_existing: bool = False,
) -> list[WorldBuildingDocument]:
    if not documents:
        raise HTTPException(400, "No world-building content was provided")

    if replace_existing:
        active_documents = await list_world_building_documents(db, book)
        for current in active_documents:
            current.is_active = False
            current.archived_at = datetime.now(UTC)

    created: list[WorldBuildingDocument] = []
    for payload in documents:
        text = str(payload.get("text") or "").strip()
        if not text:
            continue
        title = (
            " ".join(str(payload.get("title") or "").split()).strip() or "Worldbuilding Manuscript"
        )
        html = str(payload.get("html") or "").strip() or None
        serialized = serialize_manuscript_content(text, html).encode("utf-8")
        storage_key = upload_binary(
            f"worldbuilding/{user_id}/{book.id}/{uuid.uuid4()}.json",
            serialized,
            "application/json",
        )
        document = WorldBuildingDocument(
            book_id=book.id,
            title=title,
            source_name=" ".join(str(payload.get("source_name") or "").split()).strip() or None,
            s3_key=storage_key,
            word_count=count_words(text),
            source_size_bytes=len(serialized),
            is_active=True,
        )
        db.add(document)
        created.append(document)

    if not created:
        raise HTTPException(400, "No importable world-building content was found")

    await db.flush()
    await sync_world_document_elements(db, book)
    return created


async def update_world_building_document(
    db: AsyncSession,
    *,
    book: Book,
    document: WorldBuildingDocument,
    title: str | None,
    text: str,
    html: str | None = None,
) -> WorldBuildingDocument:
    body = text.strip()
    if not body:
        raise HTTPException(400, "World-building document text is required")

    next_title = (
        " ".join((title or document.title or "").split()).strip() or "Worldbuilding Manuscript"
    )
    cleaned_html = clean_manuscript_html(html) if html else None
    document.title = next_title
    document.word_count = count_words(body)
    document.s3_key = upload_binary(
        f"worldbuilding/{book.user_id}/{book.id}/{uuid.uuid4()}.json",
        serialize_manuscript_content(body, cleaned_html).encode("utf-8"),
        "application/json",
    )
    document.updated_at = datetime.now(UTC)
    document.is_active = True
    document.archived_at = None
    await db.flush()
    await sync_world_document_elements(db, book)
    return document


async def delete_world_building_document(
    db: AsyncSession,
    *,
    book: Book,
    document: WorldBuildingDocument,
) -> None:
    if document.book_id != book.id:
        raise HTTPException(404, "World-building document not found")
    await db.delete(document)
    await db.flush()
    await sync_world_document_elements(db, book)


async def sync_world_document_elements(db: AsyncSession, book: Book) -> list[WorldElement]:
    documents = await list_world_building_documents(db, book)
    character_registry = await load_character_registry(db, book)
    override_lookup = await load_canon_override_lookup(db, book)
    await db.execute(
        delete(WorldElement).where(
            WorldElement.book_id == book.id,
            WorldElement.source_scope == "worldbuilding",
        )
    )
    await db.flush()

    created: list[WorldElement] = []
    for document in documents:
        payload = await load_world_building_document_payload(document)
        text = str(payload.get("text") or "")
        raw_candidates = extract_world_elements_from_text(text)
        normalized_candidates = _apply_character_and_override_resolution(
            raw_candidates,
            character_registry=character_registry,
            override_lookup=override_lookup,
        )
        for candidate in normalized_candidates:
            name = str(candidate.get("canonical_name") or candidate.get("name") or "").strip()
            if not name:
                continue
            element = WorldElement(
                book_id=book.id,
                series_id=book.primary_series_id,
                source_book_id=book.id,
                world_document_id=document.id,
                source_scope="worldbuilding",
                element_type=str(
                    candidate.get("element_type")
                    or infer_element_type(name, str(candidate.get("description") or ""))
                ),
                name=name,
                description=str(candidate.get("description") or "").strip() or None,
                usage_count=int(candidate.get("usage_count") or 1),
                dependencies=list(candidate.get("claims") or []),
                analysis_metadata={
                    "source": "world_document",
                    "world_document_title": document.title,
                    "world_document_source_name": document.source_name,
                    "canonical_name": name,
                    "aliases": list(candidate.get("aliases") or []),
                    "confidence": float(candidate.get("confidence") or 0.0),
                    "provenance": list(candidate.get("provenance") or []),
                    "claims": list(candidate.get("claims") or []),
                    "chapter_numbers": list(candidate.get("chapter_numbers") or []),
                    "chapter_count": len(candidate.get("chapter_numbers") or []),
                    "presence_score": float(candidate.get("presence_score") or 0.0),
                    "narrative_modes": list(candidate.get("narrative_modes") or []),
                    "source_excerpt": candidate.get("source_excerpt"),
                    "character_id": candidate.get("character_id"),
                    "author_override": bool(candidate.get("author_override")),
                },
                is_series_canonical=bool(book.primary_series_id),
            )
            db.add(element)
            created.append(element)
    await db.flush()
    return created
