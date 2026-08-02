from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book
from app.models.book import Book
from app.models.intelligence import WorldBuildingDocument
from app.utils.books.imports import parse_import_upload
from app.utils.books.manuscript import clean_manuscript_html, deserialize_manuscript_content
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS
from app.utils.world_building_serialization_utils import filename_title


async def list_world_building_documents(
    db: AsyncSession,
    book: Book,
    *,
    include_inactive: bool = False,
) -> list[WorldBuildingDocument]:
    stmt = select(WorldBuildingDocument).where(WorldBuildingDocument.book_id == book.id)
    if not include_inactive:
        stmt = stmt.where(WorldBuildingDocument.is_active.is_(True))
    stmt = stmt.order_by(
        WorldBuildingDocument.updated_at.desc(), WorldBuildingDocument.created_at.desc()
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_world_building_document(
    db: AsyncSession,
    book: Book,
    document_id: uuid.UUID,
    *,
    include_inactive: bool = True,
) -> WorldBuildingDocument:
    document = await db.get(WorldBuildingDocument, document_id)
    if (
        not document
        or document.book_id != book.id
        or (not include_inactive and not document.is_active)
    ):
        raise HTTPException(404, "World-building document not found")
    return document


async def load_world_building_document_payload(
    document: WorldBuildingDocument,
) -> dict[str, str | None]:
    try:
        raw = download_book(document.s3_key)
    except STORAGE_IO_EXCEPTIONS as exc:
        raise HTTPException(404, "World-building document content is unavailable") from exc
    return deserialize_manuscript_content(raw)


async def prepare_world_building_uploads(
    *,
    files: list[tuple[str, bytes]],
    text: str | None,
    html: str | None,
    title: str | None,
) -> list[dict]:
    uploads: list[dict] = []
    cleaned_title = " ".join((title or "").split()).strip() or None
    cleaned_html = clean_manuscript_html(html) if html else None

    if text and text.strip():
        body = text.strip()
        uploads.append(
            {
                "title": cleaned_title or "Worldbuilding Manuscript",
                "source_name": cleaned_title or "worldbuilding",
                "text": body,
                "html": cleaned_html,
            }
        )

    for filename, raw in files:
        parsed = await parse_import_upload(filename, raw, split_into_chapters=False)
        if not parsed:
            continue
        merged_text = "\n\n".join(
            str(item.get("text") or "").strip()
            for item in parsed
            if str(item.get("text") or "").strip()
        ).strip()
        merged_html = (
            "\n".join(
                str(item.get("html") or "").strip()
                for item in parsed
                if str(item.get("html") or "").strip()
            ).strip()
            or None
        )
        if not merged_text:
            continue
        uploads.append(
            {
                "title": cleaned_title or filename_title(filename),
                "source_name": filename,
                "text": merged_text,
                "html": clean_manuscript_html(merged_html) if merged_html else None,
            }
        )

    return uploads
