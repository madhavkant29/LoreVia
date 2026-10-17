from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import enforce_world_building_upload_rate_limit
from app.core.config import settings
from app.core.database import get_db
from app.schemas.world_building import (
    WorldBuildingDocumentDetailOut,
    WorldBuildingDocumentOut,
    WorldBuildingDocumentUpdateBody,
)
from app.services.processing_allowance_service import (
    ensure_active_word_capacity,
    ensure_project_writable,
    ensure_source_storage_capacity,
)
from app.services.world_analysis_refresh_service import enqueue_world_analysis_refresh
from app.services.world_building_access_service import get_owned_world_building_book
from app.utils.billing_utils import require_author_access
from app.utils.books.manuscript import serialize_manuscript_content
from app.utils.storage_utils import delete_storage_keys_best_effort
from app.utils.upload_security_utils import read_upload_bounded
from app.utils.world_building_document_utils import (
    get_world_building_document,
    list_world_building_documents,
    load_world_building_document_payload,
    prepare_world_building_uploads,
)
from app.utils.world_building_document_workflow_utils import (
    create_world_building_documents,
    delete_world_building_document,
    update_world_building_document,
)
from app.utils.world_building_response_utils import serialize_world_document

router = APIRouter()


@router.get("/{book_id}/world-building/documents", response_model=list[WorldBuildingDocumentOut])
async def list_world_documents(
    book_id: uuid.UUID,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    documents = await list_world_building_documents(db, book, include_inactive=include_inactive)
    return [serialize_world_document(document) for document in documents]


@router.post("/{book_id}/world-building/documents", response_model=list[WorldBuildingDocumentOut])
async def upload_world_documents(
    book_id: uuid.UUID,
    files: list[UploadFile] | None = File(None),
    text: str | None = Form(None),
    html: str | None = Form(None),
    title: str | None = Form(None),
    replace_existing: str = Form("false"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await ensure_project_writable(db, book)
    upload_files = [upload for upload in (files or []) if upload.filename]

    if upload_files:
        await enforce_world_building_upload_rate_limit(db, current_user.id)
    if len(upload_files) > settings.WORLD_BUILDING_UPLOAD_MAX_FILES:
        raise HTTPException(
            413,
            f"World-building upload accepts at most {settings.WORLD_BUILDING_UPLOAD_MAX_FILES} files at once.",
        )

    current_documents = await list_world_building_documents(db, book)
    replace_flag = (replace_existing or "").strip().lower() in {"1", "true", "yes", "on"}

    raw_files: list[tuple[str, bytes]] = []
    total_file_size = 0
    for upload in upload_files:
        raw = await read_upload_bounded(
            upload, settings.WORLD_BUILDING_UPLOAD_MAX_BYTES, "World-building file"
        )
        if raw:
            total_file_size += len(raw)
            if total_file_size > settings.WORLD_BUILDING_UPLOAD_MAX_TOTAL_BYTES:
                raise HTTPException(
                    413, "World-building upload exceeds the maximum aggregate upload size."
                )
            raw_files.append((upload.filename, raw))
    prepared = await prepare_world_building_uploads(
        files=raw_files, text=text, html=html, title=title
    )
    requested_words = sum(len(str(item.get("text") or "").split()) for item in prepared)
    requested_storage = sum(
        len(
            serialize_manuscript_content(str(item.get("text") or ""), item.get("html")).encode(
                "utf-8"
            )
        )
        for item in prepared
    )
    released_words = (
        sum(int(document.word_count or 0) for document in current_documents) if replace_flag else 0
    )
    released_storage = (
        sum(int(document.source_size_bytes or 0) for document in current_documents)
        if replace_flag
        else 0
    )
    await ensure_active_word_capacity(db, current_user, max(requested_words - released_words, 0))
    await ensure_source_storage_capacity(
        db, current_user, requested_storage, released_bytes=released_storage
    )
    replaced_document_keys: list[str] = []
    if replace_flag:
        replaced_document_keys = [
            document.s3_key for document in current_documents if document.s3_key
        ]
    documents = await create_world_building_documents(
        db,
        book=book,
        user_id=current_user.id,
        documents=prepared,
        replace_existing=replace_flag,
    )
    await db.commit()
    await enqueue_world_analysis_refresh(scope="book", target_id=book.id)
    await delete_storage_keys_best_effort(replaced_document_keys, context="world_building_document")
    for document in documents:
        await db.refresh(document)
    return [serialize_world_document(document) for document in documents]


@router.get(
    "/{book_id}/world-building/documents/{document_id}",
    response_model=WorldBuildingDocumentDetailOut,
)
async def get_world_document(
    book_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await ensure_project_writable(db, book)
    document = await get_world_building_document(db, book, document_id)
    payload = await load_world_building_document_payload(document)
    return serialize_world_document(document, payload=payload)


@router.patch(
    "/{book_id}/world-building/documents/{document_id}",
    response_model=WorldBuildingDocumentDetailOut,
)
async def patch_world_document(
    book_id: uuid.UUID,
    document_id: uuid.UUID,
    body: WorldBuildingDocumentUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await ensure_project_writable(db, book)
    document = await get_world_building_document(db, book, document_id)
    previous_s3_key = document.s3_key
    updated = await update_world_building_document(
        db,
        book=book,
        document=document,
        title=body.title,
        text=body.text,
        html=body.html,
    )
    await db.commit()
    await enqueue_world_analysis_refresh(scope="book", target_id=book.id)
    if previous_s3_key and previous_s3_key != updated.s3_key:
        await delete_storage_keys_best_effort([previous_s3_key], context="world_building_document")
    await db.refresh(updated)
    payload = await load_world_building_document_payload(updated)
    return serialize_world_document(updated, payload=payload)


@router.delete("/{book_id}/world-building/documents/{document_id}", status_code=204)
async def remove_world_document(
    book_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    document = await get_world_building_document(db, book, document_id)
    previous_s3_key = document.s3_key
    await delete_world_building_document(db, book=book, document=document)
    await db.commit()
    await enqueue_world_analysis_refresh(scope="book", target_id=book.id)
    await delete_storage_keys_best_effort([previous_s3_key], context="world_building_document")
    return Response(status_code=204)
