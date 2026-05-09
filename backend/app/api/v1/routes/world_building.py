from __future__ import annotations
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_world_building_ai, rate_limit_world_building_upload
from app.core.database import get_db
from app.core.storage import download_book
from app.models.book import Book, Series
from app.models.intelligence import WikiEntry, WorldBuildingDocument, WorldCanonicalIdentity, WorldElement, WorldNote
from app.schemas.world_building import (
    CanonOverrideBody,
    CanonOverrideOut,
    GapAnalysisRequest,
    GapAnalysisResponse,
    IntegrationAnalysisResponse,
    SuggestionAcceptance,
    WikiEntryOut,
    WikiGenerationResponse,
    WorldBuildingDocumentDetailOut,
    WorldBuildingDocumentOut,
    WorldBuildingDocumentUpdateBody,
    WorldElementOut,
    WorldNoteBody,
    WorldNoteOut,
    WorldNoteStatusBody,
    WorldQueryRequest,
    WorldQueryResponse,
)
from app.utils.world_building_utils import (
    build_world_logic_response,
    classify_world_intent,
    create_world_building_documents,
    delete_world_building_document,
    detect_integration_analysis,
    detect_series_world_analysis,
    detect_world_gaps,
    extract_world_elements,
    get_world_building_document,
    generate_wiki_from_manuscript,
    list_extracted_world_elements,
    list_world_building_documents,
    load_world_building_document_payload,
    prepare_world_building_uploads,
    save_canon_override,
    save_world_note,
    update_world_building_document,
)

router = APIRouter()

MAX_WORLD_UPLOAD_BYTES = 20 * 1024 * 1024


async def _read_upload_bounded(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    parts: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(413, f"{label} exceeds the maximum allowed size ({max_bytes // 1024 // 1024} MB).")
        parts.append(chunk)
    await upload.seek(0)
    return b"".join(parts)


def _serialize_note(note: WorldNote) -> WorldNoteOut:
    return WorldNoteOut(
        id=str(note.id),
        book_id=str(note.book_id),
        world_element_id=str(note.world_element_id) if note.world_element_id else None,
        world_document_id=str(note.world_document_id) if note.world_document_id else None,
        note_type=note.note_type,
        chapter_number=note.chapter_number,
        title=note.title,
        body=note.body,
        priority=note.priority,
        status=note.status,
        linked_gap_id=note.linked_gap_id,
        linked_integration_id=note.linked_integration_id,
        context_label=note.context_label,
        suggested_fix=note.suggested_fix,
        created_at=note.created_at,
        updated_at=note.updated_at,
        addressed_at=note.addressed_at,
    )


def _serialize_canon_override(identity: WorldCanonicalIdentity) -> CanonOverrideOut:
    return CanonOverrideOut(
        id=str(identity.id),
        canonical_name=" ".join(str(identity.canonical_name or "").split()).strip(),
        aliases=[
            " ".join(str(alias or "").split()).strip()
            for alias in (identity.aliases or [])
            if " ".join(str(alias or "").split()).strip()
        ],
        entity_type=" ".join(str(identity.entity_type or "").split()).strip() or None,
        notes=" ".join(str(identity.notes or "").split()).strip() or None,
        created_at=identity.created_at,
        updated_at=identity.updated_at,
    )


def _serialize_document(document: WorldBuildingDocument, payload: dict[str, str | None] | None = None) -> WorldBuildingDocumentOut | WorldBuildingDocumentDetailOut:
    base = {
        "id": str(document.id),
        "book_id": str(document.book_id),
        "title": document.title,
        "source_name": document.source_name,
        "word_count": document.word_count,
        "is_active": bool(document.is_active),
        "archived_at": document.archived_at,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }
    if payload is None:
        return WorldBuildingDocumentOut(**base)
    return WorldBuildingDocumentDetailOut(
        **base,
        text=str(payload.get("text") or ""),
        html=str(payload.get("html") or "") or None,
    )


async def _get_owned_book(db: AsyncSession, book_id: uuid.UUID, user_id: uuid.UUID) -> Book:
    book = await db.get(Book, book_id)
    if not book or book.user_id != user_id:
        raise HTTPException(404, "Book not found")
    return book


@router.get("/{book_id}/world-building/documents", response_model=list[WorldBuildingDocumentOut])
async def list_world_documents(
    book_id: uuid.UUID,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    documents = await list_world_building_documents(db, book, include_inactive=include_inactive)
    return [_serialize_document(document) for document in documents]


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
    _=Depends(rate_limit_world_building_upload),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    raw_files: list[tuple[str, bytes]] = []
    for upload in files or []:
        if not upload.filename:
            continue
        raw = await _read_upload_bounded(upload, MAX_WORLD_UPLOAD_BYTES, "World-building file")
        if raw:
            raw_files.append((upload.filename, raw))
    prepared = await prepare_world_building_uploads(files=raw_files, text=text, html=html, title=title)
    documents = await create_world_building_documents(
        db,
        book=book,
        user_id=current_user.id,
        documents=prepared,
        replace_existing=(replace_existing or "").strip().lower() in {"1", "true", "yes", "on"},
    )
    await db.commit()
    for document in documents:
        await db.refresh(document)
    return [_serialize_document(document) for document in documents]


@router.get("/{book_id}/world-building/documents/{document_id}", response_model=WorldBuildingDocumentDetailOut)
async def get_world_document(
    book_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    document = await get_world_building_document(db, book, document_id)
    payload = await load_world_building_document_payload(document)
    return _serialize_document(document, payload)


@router.patch("/{book_id}/world-building/documents/{document_id}", response_model=WorldBuildingDocumentDetailOut)
async def patch_world_document(
    book_id: uuid.UUID,
    document_id: uuid.UUID,
    body: WorldBuildingDocumentUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    document = await get_world_building_document(db, book, document_id)
    updated = await update_world_building_document(
        db,
        book=book,
        document=document,
        title=body.title,
        text=body.text,
        html=body.html,
    )
    await db.commit()
    await db.refresh(updated)
    payload = await load_world_building_document_payload(updated)
    return _serialize_document(updated, payload)


@router.delete("/{book_id}/world-building/documents/{document_id}", status_code=204)
async def remove_world_document(
    book_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    document = await get_world_building_document(db, book, document_id)
    await delete_world_building_document(db, book=book, document=document)
    await db.commit()
    return Response(status_code=204)


@router.post("/{book_id}/world-building/analyze")
async def analyze_world_building(
    book_id: uuid.UUID,
    body: GapAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_world_building_ai),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    mode = body.mode or classify_world_intent(body.query)
    await extract_world_elements(db, book)
    if mode == "story_integration":
        payload = await detect_integration_analysis(db, book)
        if body.auto_create_notes:
            for item in payload["integration_opportunities"][:5]:
                world_document_id = item.get("world_document_id")
                note = await save_world_note(
                    db,
                    user_id=current_user.id,
                    book_id=book.id,
                    world_element_id=None,
                    world_document_id=uuid.UUID(world_document_id) if world_document_id else None,
                    note_type="integration",
                    chapter_number=item.get("target_chapter"),
                    title=item.get("element_name"),
                    body=item.get("description") or "",
                    priority="high" if int(item.get("priority") or 0) >= 6 else "medium",
                    status="open",
                    linked_integration_id=item.get("id"),
                    context_label=item.get("world_document_title"),
                    suggested_fix="\n".join(str(suggestion) for suggestion in (item.get("suggestions") or [])[:2]),
                )
                await db.refresh(note)
        await db.commit()
        return payload

    payload = await detect_world_gaps(db, book)
    if body.auto_create_notes:
        for item in payload["priority_gaps"][:5]:
            priority_value = int(item.get("priority") or 0)
            note = await save_world_note(
                db,
                user_id=current_user.id,
                book_id=book.id,
                world_element_id=None,
                world_document_id=uuid.UUID(item["world_document_id"]) if item.get("world_document_id") else None,
                note_type="world_gap",
                chapter_number=item.get("story_chapter_number"),
                title=item.get("title"),
                body=item.get("description") or "",
                priority="critical" if priority_value >= 8 else ("high" if priority_value >= 6 else "medium"),
                status="open",
                linked_gap_id=item.get("id"),
                context_label=item.get("world_document_title"),
                suggested_fix=item.get("suggested_fix"),
            )
            await db.refresh(note)
    await db.commit()
    return payload


@router.get("/{book_id}/world-building/gaps", response_model=GapAnalysisResponse)
async def get_world_gaps(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_world_building_ai),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    payload = await detect_world_gaps(db, book)
    return GapAnalysisResponse(**payload)


@router.get("/{book_id}/world-building/integration", response_model=IntegrationAnalysisResponse)
async def get_world_integration(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    payload = await detect_integration_analysis(db, book)
    return IntegrationAnalysisResponse(**payload)


@router.get("/{book_id}/world-building/elements", response_model=list[WorldElementOut])
async def list_world_elements(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    return await list_extracted_world_elements(db, book)


@router.get("/{book_id}/world-building/wiki", response_model=list[WikiEntryOut])
async def list_auto_wiki(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    rows = (
        await db.execute(
            select(WikiEntry).where(WikiEntry.book_id == book.id).order_by(WikiEntry.entry_type.asc(), WikiEntry.name.asc())
        )
    ).scalars().all()
    return [
        WikiEntryOut(
            id=str(item.id),
            book_id=str(item.book_id),
            entry_type=item.entry_type,
            name=item.name,
            description=item.description,
            first_mention=item.first_mention,
            related_char_ids=item.related_char_ids,
            created_at=item.created_at,
        )
        for item in rows
    ]


@router.post("/{book_id}/world-building/wiki/generate", response_model=WikiGenerationResponse)
async def generate_auto_wiki(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    generated = await generate_wiki_from_manuscript(db, book)
    await db.commit()
    return WikiGenerationResponse(
        generated_count=len(generated),
        updated_names=[item.name for item in generated[:20]],
        entries=[
            WikiEntryOut(
                id=str(item.id),
                book_id=str(item.book_id),
                entry_type=item.entry_type,
                name=item.name,
                description=item.description,
                first_mention=item.first_mention,
                related_char_ids=item.related_char_ids,
                created_at=item.created_at,
            )
            for item in generated[:40]
        ],
    )


@router.post("/{book_id}/world-building/query", response_model=WorldQueryResponse)
async def query_world_building(
    book_id: uuid.UUID,
    body: WorldQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_world_building_ai),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    mode = body.mode or classify_world_intent(body.query)
    payload = await build_world_logic_response(db, book, body.query, mode)
    return WorldQueryResponse(**payload)


@router.get("/series/{series_id}/world-building/series-analysis")
async def get_series_world_analysis(
    series_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await db.get(Series, series_id)
    if not series or series.user_id != current_user.id:
        raise HTTPException(404, "Series not found")
    payload = await detect_series_world_analysis(db, series_id)
    return {**payload, "series_name": series.name}


@router.post("/{world_element_id}/world-building/accept-suggestion")
async def accept_world_suggestion(
    world_element_id: uuid.UUID,
    body: SuggestionAcceptance,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    element = await db.get(WorldElement, world_element_id)
    if not element:
        raise HTTPException(404, "World element not found")
    book = await db.get(Book, element.book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "World element not found")
    suggestions = list(element.suggestions or [])
    remaining = []
    for item in suggestions:
        if isinstance(item, dict):
            if str(item.get("id") or "") == body.suggestion_id:
                continue
        elif str(item) == body.suggestion_id:
            continue
        remaining.append(item)
    element.suggestions = remaining
    if body.mark_implemented:
        element.edited_by_author = True
        element.edited_at = datetime.now(UTC)
    await db.commit()
    return {"accepted": body.suggestion_id, "remaining": len(remaining)}


@router.get("/{book_id}/world-building/canon-overrides", response_model=list[CanonOverrideOut])
async def list_canon_overrides(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    overrides = (
        await db.execute(
            select(WorldCanonicalIdentity)
            .where(WorldCanonicalIdentity.book_id == book.id)
            .order_by(WorldCanonicalIdentity.updated_at.desc(), WorldCanonicalIdentity.created_at.desc())
        )
    ).scalars().all()
    return [_serialize_canon_override(identity) for identity in overrides]


@router.post("/{book_id}/world-building/canon-overrides", response_model=CanonOverrideOut)
async def create_canon_override(
    book_id: uuid.UUID,
    body: CanonOverrideBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    identity = await save_canon_override(
        db,
        user_id=current_user.id,
        book=book,
        canonical_name=body.canonical_name,
        aliases=body.aliases,
        entity_type=body.entity_type,
        notes=body.notes,
    )
    await db.commit()
    await db.refresh(identity)
    return _serialize_canon_override(identity)


@router.get("/{book_id}/world-building/notes", response_model=list[WorldNoteOut])
async def list_world_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    notes = (
        await db.execute(
            select(WorldNote)
            .where(WorldNote.book_id == book.id, WorldNote.note_type != "canon_override")
            .order_by(WorldNote.created_at.desc())
        )
    ).scalars().all()
    return [_serialize_note(note) for note in notes]


@router.post("/{book_id}/world-building/notes", response_model=WorldNoteOut)
async def create_world_note(
    book_id: uuid.UUID,
    body: WorldNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    world_element_id = uuid.UUID(body.world_element_id) if body.world_element_id else None
    world_document_id = uuid.UUID(body.world_document_id) if body.world_document_id else None
    if world_document_id:
        await get_world_building_document(db, book, world_document_id)
    note = await save_world_note(
        db,
        user_id=current_user.id,
        book_id=book.id,
        world_element_id=world_element_id,
        world_document_id=world_document_id,
        note_type=body.note_type,
        chapter_number=body.chapter_number,
        title=body.title,
        body=body.body,
        priority=body.priority,
        status=body.status,
        linked_gap_id=body.linked_gap_id,
        linked_integration_id=body.linked_integration_id,
        context_label=body.context_label,
        suggested_fix=body.suggested_fix,
    )
    await db.commit()
    await db.refresh(note)
    return _serialize_note(note)


@router.delete("/{book_id}/world-building/notes/{note_id}")
async def delete_world_note(
    book_id: uuid.UUID,
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    note = await db.get(WorldNote, note_id)
    if not note or note.book_id != book.id:
        raise HTTPException(404, "Note not found")
    await db.delete(note)
    await db.commit()
    return {"deleted": str(note_id)}


@router.patch("/{book_id}/world-building/notes/{note_id}/status", response_model=WorldNoteOut)
async def update_world_note_status(
    book_id: uuid.UUID,
    note_id: uuid.UUID,
    body: WorldNoteStatusBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    note = await db.get(WorldNote, note_id)
    if not note or note.book_id != book.id:
        raise HTTPException(404, "Note not found")
    note.status = body.status
    note.addressed_at = datetime.now(UTC) if body.status == "addressed" else None
    await db.commit()
    await db.refresh(note)
    return _serialize_note(note)


@router.get("/{book_id}/world-building/notes/by-chapter/{chapter_number}", response_model=list[WorldNoteOut])
async def get_world_notes_by_chapter(
    book_id: uuid.UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await _get_owned_book(db, book_id, current_user.id)
    notes = (
        await db.execute(
            select(WorldNote)
            .where(
                WorldNote.book_id == book.id,
                WorldNote.chapter_number == chapter_number,
                WorldNote.note_type != "canon_override",
            )
            .order_by(WorldNote.created_at.desc())
        )
    ).scalars().all()
    return [_serialize_note(note) for note in notes]
