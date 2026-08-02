from __future__ import annotations

from app.models.intelligence import (
    WorldBuildingDocument,
    WorldCanonicalIdentity,
    WorldNote,
)
from app.schemas.world_building import (
    CanonOverrideOut,
    WorldBuildingDocumentDetailOut,
    WorldBuildingDocumentOut,
    WorldNoteOut,
)


def serialize_world_note(note: WorldNote, *, tags: list[str] | None = None) -> WorldNoteOut:
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
        tags=tags or [],
        created_at=note.created_at,
        updated_at=note.updated_at,
        addressed_at=note.addressed_at,
    )


def serialize_canon_override(identity: WorldCanonicalIdentity) -> CanonOverrideOut:
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


def serialize_world_document(
    document: WorldBuildingDocument,
    *,
    payload: dict[str, str | None] | None = None,
) -> WorldBuildingDocumentOut | WorldBuildingDocumentDetailOut:
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
