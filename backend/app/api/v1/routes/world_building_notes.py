from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.intelligence import WorldNote
from app.schemas.world_building import WorldNoteBody, WorldNoteOut, WorldNoteStatusBody
from app.services.world_building_access_service import get_owned_world_building_book
from app.utils.billing_utils import require_author_access
from app.utils.tag_utils import (
    ENTITY_TYPE_WORLD_NOTE,
    get_custom_tags_for_entity,
    list_custom_tags_for_entity_ids,
)
from app.utils.world_building_document_utils import get_world_building_document
from app.utils.world_building_note_utils import save_world_note
from app.utils.world_building_response_utils import serialize_world_note

router = APIRouter()


@router.get("/{book_id}/world-building/notes", response_model=list[WorldNoteOut])
async def list_world_notes(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    notes = (
        (
            await db.execute(
                select(WorldNote)
                .where(WorldNote.book_id == book.id, WorldNote.note_type != "canon_override")
                .order_by(WorldNote.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    tags_by_note = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_WORLD_NOTE,
        entity_ids=[note.id for note in notes],
        book_id=book.id,
    )
    return [serialize_world_note(note, tags=tags_by_note.get(note.id, [])) for note in notes]


@router.post("/{book_id}/world-building/notes", response_model=WorldNoteOut)
async def create_world_note(
    book_id: uuid.UUID,
    body: WorldNoteBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
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
    return serialize_world_note(
        note,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_WORLD_NOTE,
            entity_id=note.id,
            book_id=book.id,
        ),
    )


@router.delete("/{book_id}/world-building/notes/{note_id}")
async def delete_world_note(
    book_id: uuid.UUID,
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
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
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    note = await db.get(WorldNote, note_id)
    if not note or note.book_id != book.id:
        raise HTTPException(404, "Note not found")
    note.status = body.status
    note.addressed_at = datetime.now(UTC) if body.status == "addressed" else None
    await db.commit()
    await db.refresh(note)
    return serialize_world_note(
        note,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_WORLD_NOTE,
            entity_id=note.id,
            book_id=book.id,
        ),
    )


@router.get(
    "/{book_id}/world-building/notes/by-chapter/{chapter_number}", response_model=list[WorldNoteOut]
)
async def get_world_notes_by_chapter(
    book_id: uuid.UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    notes = (
        (
            await db.execute(
                select(WorldNote)
                .where(
                    WorldNote.book_id == book.id,
                    WorldNote.chapter_number == chapter_number,
                    WorldNote.note_type != "canon_override",
                )
                .order_by(WorldNote.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    tags_by_note = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_WORLD_NOTE,
        entity_ids=[note.id for note in notes],
        book_id=book.id,
    )
    return [serialize_world_note(note, tags=tags_by_note.get(note.id, [])) for note in notes]
