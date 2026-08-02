from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.intelligence import WorldCanonicalIdentity, WorldNote
from app.utils.world_building_candidate_utils import _dedupe_strings
from app.utils.world_building_conflict_utils import _world_names_equivalent


async def save_world_note(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
    world_element_id: uuid.UUID | None,
    world_document_id: uuid.UUID | None,
    note_type: str,
    chapter_number: int | None,
    title: str | None,
    body: str,
    priority: str,
    status: str,
    linked_gap_id: str | None = None,
    linked_integration_id: str | None = None,
    context_label: str | None = None,
    suggested_fix: str | None = None,
) -> WorldNote:
    note = WorldNote(
        user_id=user_id,
        book_id=book_id,
        world_element_id=world_element_id,
        world_document_id=world_document_id,
        note_type=note_type,
        chapter_number=chapter_number,
        title=title,
        body=body,
        priority=priority,
        status=status,
        linked_gap_id=linked_gap_id,
        linked_integration_id=linked_integration_id,
        context_label=context_label,
        suggested_fix=suggested_fix,
        addressed_at=datetime.now(UTC) if status == "addressed" else None,
    )
    db.add(note)
    await db.flush()
    return note


async def save_canon_override(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    book: Book,
    canonical_name: str,
    aliases: list[str],
    entity_type: str | None = None,
    notes: str | None = None,
) -> WorldCanonicalIdentity:
    cleaned_canonical = " ".join((canonical_name or "").split()).strip()
    if not cleaned_canonical:
        raise HTTPException(400, "Canonical name is required")
    cleaned_aliases = _dedupe_strings(
        [alias for alias in aliases if alias and " ".join(alias.split()).strip()]
    )
    normalized_entity_type = " ".join((entity_type or "").split()).strip() or None
    normalized_notes = " ".join((notes or "").split()).strip() or None

    existing_rows = (
        (
            await db.execute(
                select(WorldCanonicalIdentity)
                .where(WorldCanonicalIdentity.book_id == book.id)
                .order_by(
                    WorldCanonicalIdentity.updated_at.desc(),
                    WorldCanonicalIdentity.created_at.desc(),
                )
            )
        )
        .scalars()
        .all()
    )
    for identity in existing_rows:
        existing_canonical = " ".join(str(identity.canonical_name or "").split()).strip()
        existing_aliases = [
            str(alias).strip() for alias in (identity.aliases or []) if str(alias).strip()
        ]
        if _world_names_equivalent(cleaned_canonical, existing_canonical) or any(
            _world_names_equivalent(alias, cleaned_canonical) for alias in existing_aliases
        ):
            identity.canonical_name = cleaned_canonical
            identity.entity_type = normalized_entity_type
            identity.aliases = _dedupe_strings([*existing_aliases, *cleaned_aliases])
            identity.notes = normalized_notes
            identity.source = "author_override"
            identity.confidence = 0.99
            metadata = dict(identity.metadata_json or {})
            metadata["updated_by_user_id"] = str(user_id)
            identity.metadata_json = metadata
            identity.updated_at = datetime.now(UTC)
            await db.flush()
            return identity

    identity = WorldCanonicalIdentity(
        book_id=book.id,
        canonical_name=cleaned_canonical,
        entity_type=normalized_entity_type,
        aliases=cleaned_aliases or None,
        source="author_override",
        confidence=0.99,
        notes=normalized_notes,
        metadata_json={"created_by_user_id": str(user_id)},
    )
    db.add(identity)
    await db.flush()
    return identity
