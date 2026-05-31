import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from .core import _clean_text, _read_upload_bounded
from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_manuscript_import
from app.core.config import settings
from app.core.database import get_db
from app.models.book import Book, BookNote, ObsidianVaultNoteSource
from app.schemas.books import (
    BookNoteBody,
    BookNoteOut,
    EntityTagSetOut,
    EntityTagUpdateBody,
    ObsidianGraphOut,
    ObsidianNoteLinkListOut,
    ObsidianVaultNoteBody,
    ObsidianVaultNoteOut,
    ObsidianVaultNoteSaveOut,
)
from app.utils.book_utils import (
    build_obsidian_graph,
    collaboration_allows_chapter,
    collaboration_can_comment,
    delete_book_note,
    delete_obsidian_note,
    export_obsidian_notes_zip,
    get_book_with_collaboration_access,
    get_owned_book,
    import_obsidian_notes_zip,
    list_book_notes,
    list_obsidian_note_relations,
    list_obsidian_notes,
    save_book_note,
    save_obsidian_vault_note,
)
from app.utils.tag_utils import (
    ENTITY_TYPE_NOTE,
    can_manage_tag_target,
    replace_custom_tags_for_entity,
    resolve_tag_target,
)

router = APIRouter()


@router.get("/{book_id}/notes", response_model=list[BookNoteOut])
async def get_book_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot view or leave comments.")
    return await list_book_notes(db, book, collaborator=collaborator)


@router.put("/{book_id}/revision-tags", response_model=EntityTagSetOut)
async def update_revision_tags(
    book_id: uuid.UUID,
    body: EntityTagUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    resolved_type, resolved_entity_id, target_chapter_number = await resolve_tag_target(
        db,
        book=book,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        chapter_number=body.chapter_number,
    )
    target_owner_user_id = None
    if resolved_type == ENTITY_TYPE_NOTE:
        note = await db.get(BookNote, resolved_entity_id)
        target_owner_user_id = note.user_id if note is not None else None
    if not can_manage_tag_target(
        collaborator=collaborator,
        public_entity_type=body.entity_type,
        target_chapter_number=target_chapter_number,
        target_owner_user_id=target_owner_user_id,
        current_user_id=current_user.id,
    ):
        raise HTTPException(403, "This share cannot manage tags for that item.")

    tags = await replace_custom_tags_for_entity(
        db,
        book_id=book.id,
        entity_type=resolved_type,
        entity_id=resolved_entity_id,
        created_by_user_id=current_user.id,
        tags=body.tags,
    )
    await db.commit()
    return EntityTagSetOut(
        entity_type=body.entity_type,
        entity_id=str(resolved_entity_id),
        chapter_number=target_chapter_number,
        tags=tags,
    )


@router.post("/{book_id}/notes", response_model=BookNoteOut)
async def upsert_book_note(
    book_id: uuid.UUID,
    body: BookNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot leave comments.")
    if collaborator and body.chapter_number is not None and not collaboration_allows_chapter(collaborator, body.chapter_number):
        raise HTTPException(403, "This share cannot comment on that chapter.")
    return await save_book_note(
        db,
        book=book,
        user_id=current_user.id,
        note_id=body.note_id,
        chapter_number=body.chapter_number,
        title=body.title,
        body=body.body,
    )


@router.delete("/{book_id}/notes/{note_id}", status_code=204)
async def remove_book_note(
    book_id: uuid.UUID,
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator and not collaboration_can_comment(collaborator):
        raise HTTPException(403, "This share cannot remove comments.")
    await delete_book_note(db, book=book, user_id=current_user.id, note_id=note_id)
    return Response(status_code=204)


@router.get("/{book_id}/notes/obsidian", response_model=list[ObsidianVaultNoteOut])
async def list_book_obsidian_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await list_obsidian_notes(
        db,
        book=book,
        user_id=current_user.id,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )


@router.put("/{book_id}/notes/obsidian", response_model=ObsidianVaultNoteSaveOut)
async def save_book_obsidian_note(
    book_id: uuid.UUID,
    body: ObsidianVaultNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await save_obsidian_vault_note(
        db,
        book=book,
        user_id=current_user.id,
        path=body.path,
        content=body.content,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )


@router.delete("/{book_id}/notes/obsidian/{path:path}", status_code=204)
async def delete_book_obsidian_note(
    book_id: uuid.UUID,
    path: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    await delete_obsidian_note(
        db,
        book=book,
        user_id=current_user.id,
        path=path,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )
    return Response(status_code=204)


@router.post("/{book_id}/notes/obsidian/import", response_model=list[ObsidianVaultNoteSaveOut])
async def import_book_obsidian_notes(
    book_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_manuscript_import),
):
    book = await get_owned_book(db, book_id, current_user.id)
    archive_bytes = await _read_upload_bounded(file, settings.OBSIDIAN_IMPORT_MAX_BYTES, "ZIP file")
    return await import_obsidian_notes_zip(
        db,
        book=book,
        user_id=current_user.id,
        archive_bytes=archive_bytes,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )


@router.get("/{book_id}/notes/obsidian/export")
async def export_book_obsidian_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    notes = await list_obsidian_notes(
        db,
        book=book,
        user_id=current_user.id,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )
    zip_data = export_obsidian_notes_zip(notes=notes)
    safe_title = _clean_text(book.title or "notes").strip() or "notes"
    filename = f"{safe_title.replace(' ', '-')}-obsidian-notes.zip"
    return Response(
        content=zip_data,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/{book_id}/notes/obsidian/graph", response_model=ObsidianGraphOut)
async def get_book_obsidian_graph(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    notes = await list_obsidian_notes(
        db,
        book=book,
        user_id=current_user.id,
        source=ObsidianVaultNoteSource.USER_NOTES.value,
    )
    return build_obsidian_graph(notes)


@router.get("/{book_id}/notes/obsidian/relations", response_model=ObsidianNoteLinkListOut)
async def get_book_obsidian_note_relations(
    book_id: uuid.UUID,
    path: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    return await list_obsidian_note_relations(
        db,
        book=book,
        user_id=current_user.id,
        path=path,
    )
