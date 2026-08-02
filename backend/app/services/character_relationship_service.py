from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import mark_book_cache_dirty
from app.models.character import Character, CharacterRelationshipCandidate
from app.models.intelligence import CharacterRelationship
from app.schemas.books import (
    RelationshipCandidateAcceptBody,
    RelationshipCandidateAttachBody,
    RelationshipCreateBody,
    RelationshipUpdateBody,
)
from app.services.quality_metrics_service import record_quality_review
from app.utils.billing_utils import require_author_access
from app.utils.books.book_text import _clean_text
from app.utils.books.notes import get_owned_book
from app.utils.characters.constants import (
    CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_REJECTED,
    CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED,
)
from app.utils.characters.review import append_character_review_audit_entry
from app.utils.characters.text import clean_optional_text
from app.utils.relationship_utils import (
    canonical_relationship_pair_ids,
    repair_relationship_timelines,
    upsert_relationship_timeline_state,
)


async def attach_relationship_candidate_a_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAttachBody,
) -> dict[str, str]:
    candidate, character = await _load_pending_candidate_and_character(
        db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
        character_id=body.character_id,
        pending_error="Only pending relationship candidates can be updated",
    )
    candidate.matched_character_a_id = character.id
    append_character_review_audit_entry(
        character,
        action="relationship_candidate_attached_a",
        details={"relationship_candidate_id": str(candidate.id)},
    )
    await db.commit()
    return {"attached_a": str(character.id), "relationship_candidate_id": str(candidate.id)}


async def attach_relationship_candidate_b_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAttachBody,
) -> dict[str, str]:
    candidate, character = await _load_pending_candidate_and_character(
        db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
        character_id=body.character_id,
        pending_error="Only pending relationship candidates can be updated",
    )
    candidate.matched_character_b_id = character.id
    append_character_review_audit_entry(
        character,
        action="relationship_candidate_attached_b",
        details={"relationship_candidate_id": str(candidate.id)},
    )
    await db.commit()
    return {"attached_b": str(character.id), "relationship_candidate_id": str(candidate.id)}


async def accept_relationship_candidate_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAcceptBody,
) -> dict[str, Any]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Relationship review is only available in author mode")
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    if candidate.status != CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending relationship candidates can be accepted")

    relationship_a = await db.get(Character, body.character_a_id)
    relationship_b = await db.get(Character, body.character_b_id)
    if (
        not relationship_a
        or relationship_a.book_id != book.id
        or not relationship_b
        or relationship_b.book_id != book.id
    ):
        raise HTTPException(404, "Character not found")
    if relationship_a.id == relationship_b.id:
        raise HTTPException(400, "Choose two different characters")

    rel_type = _normalize_relationship_type(body.rel_type or candidate.rel_type or "connection")
    from_chapter = body.from_chapter or int(candidate.chapter_number or 1)
    _validate_relationship_window(from_chapter, body.to_chapter)
    if body.sentiment is not None and not -1.0 <= body.sentiment <= 1.0:
        raise HTTPException(400, "Sentiment must be between -1.0 and 1.0")
    evidence_payload = dict(candidate.evidence or {})
    extracted_relationship = (
        evidence_payload.get("relationship")
        if isinstance(evidence_payload.get("relationship"), dict)
        else {}
    )

    relationship, _ = await upsert_relationship_timeline_state(
        db,
        book_id=book.id,
        character_a_id=relationship_a.id,
        character_b_id=relationship_b.id,
        rel_type=rel_type,
        sentiment=body.sentiment if body.sentiment is not None else candidate.sentiment,
        description=clean_optional_text(body.description)
        if body.description is not None
        else clean_optional_text(candidate.description),
        from_chapter=from_chapter,
        to_chapter=body.to_chapter,
        shared_labels=body.shared_labels
        if body.shared_labels is not None
        else extracted_relationship.get("shared_labels"),
        character_a_to_b_labels=body.character_a_to_b_labels
        if body.character_a_to_b_labels is not None
        else extracted_relationship.get("character_a_to_b_labels"),
        character_b_to_a_labels=body.character_b_to_a_labels
        if body.character_b_to_a_labels is not None
        else extracted_relationship.get("character_b_to_a_labels"),
        label_evidence=body.label_evidence
        or extracted_relationship.get("label_evidence")
        or evidence_payload,
    )
    relationship.edited_by_author = True
    candidate.matched_character_a_id = relationship_a.id
    candidate.matched_character_b_id = relationship_b.id
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="relationship_candidate",
        entity_id=candidate.id,
        outcome="accepted",
        evidence=dict(candidate.evidence or {}),
    )
    append_character_review_audit_entry(
        relationship_a,
        action="relationship_candidate_accepted",
        details={"relationship_candidate_id": str(candidate.id), "side": "a"},
    )
    append_character_review_audit_entry(
        relationship_b,
        action="relationship_candidate_accepted",
        details={"relationship_candidate_id": str(candidate.id), "side": "b"},
    )
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(relationship)
    return serialize_relationship_record(relationship)


async def resolve_relationship_candidate_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> dict[str, str]:
    book, candidate = await _load_relationship_candidate(
        db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
    )
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="relationship_candidate",
        entity_id=candidate.id,
        outcome="resolved",
        evidence=dict(candidate.evidence or {}),
    )
    await db.commit()
    return {"resolved": str(candidate.id)}


async def reject_relationship_candidate_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> dict[str, str]:
    book, candidate = await _load_relationship_candidate(
        db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
    )
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_REJECTED
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="relationship_candidate",
        entity_id=candidate.id,
        outcome="rejected",
        evidence=dict(candidate.evidence or {}),
    )
    await db.commit()
    return {"rejected": str(candidate.id)}


async def create_book_relationship_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    body: RelationshipCreateBody,
) -> dict[str, Any]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Relationship editing is only available in author mode")

    relationship_a = await db.get(Character, body.character_a_id)
    relationship_b = await db.get(Character, body.character_b_id)
    if (
        not relationship_a
        or relationship_a.book_id != book.id
        or not relationship_b
        or relationship_b.book_id != book.id
    ):
        raise HTTPException(404, "Character not found")
    if relationship_a.id == relationship_b.id:
        raise HTTPException(400, "Choose two different characters")

    rel_type = _normalize_relationship_type(body.rel_type)
    _validate_relationship_window(body.from_chapter, body.to_chapter)
    if body.sentiment is not None and not -1.0 <= body.sentiment <= 1.0:
        raise HTTPException(400, "Sentiment must be between -1.0 and 1.0")

    relationship, _ = await upsert_relationship_timeline_state(
        db,
        book_id=book.id,
        character_a_id=relationship_a.id,
        character_b_id=relationship_b.id,
        rel_type=rel_type,
        sentiment=body.sentiment,
        description=clean_optional_text(body.description),
        from_chapter=body.from_chapter,
        to_chapter=body.to_chapter,
        shared_labels=body.shared_labels,
        character_a_to_b_labels=body.character_a_to_b_labels,
        character_b_to_a_labels=body.character_b_to_a_labels,
        label_evidence=body.label_evidence,
    )
    relationship.edited_by_author = True
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="relationship",
        entity_id=relationship.id,
        outcome="manual_created",
        evidence={"corrected_fields": sorted(body.model_fields_set)},
    )
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(relationship)
    return serialize_relationship_record(relationship)


async def update_book_relationship_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
    body: RelationshipUpdateBody,
) -> dict[str, Any]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    relationship = await db.get(CharacterRelationship, relationship_id)
    if not relationship or relationship.book_id != book.id:
        raise HTTPException(404, "Relationship not found")
    if book.mode != "author":
        raise HTTPException(400, "Relationship editing is only available in author mode")

    rel_type = _normalize_relationship_type(body.rel_type)
    if body.sentiment is not None and not -1.0 <= body.sentiment <= 1.0:
        raise HTTPException(400, "Sentiment must be between -1.0 and 1.0")
    _validate_relationship_window(body.from_chapter, body.to_chapter)

    relationship, _ = await upsert_relationship_timeline_state(
        db,
        book_id=book.id,
        character_a_id=relationship.character_a_id,
        character_b_id=relationship.character_b_id,
        rel_type=rel_type,
        sentiment=body.sentiment,
        description=clean_optional_text(body.description),
        from_chapter=body.from_chapter or relationship.from_chapter,
        to_chapter=body.to_chapter,
        relationship_id=relationship.id,
        shared_labels=body.shared_labels,
        character_a_to_b_labels=body.character_a_to_b_labels,
        character_b_to_a_labels=body.character_b_to_a_labels,
        label_evidence=body.label_evidence
        if body.label_evidence is not None
        else dict(getattr(relationship, "label_evidence", None) or {}),
    )
    relationship.edited_by_author = True
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="relationship",
        entity_id=relationship.id,
        outcome="corrected",
        evidence={"corrected_fields": sorted(body.model_fields_set)},
    )
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(relationship)

    return serialize_relationship_record(relationship)


async def repair_book_relationship_timelines_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
) -> dict[str, Any]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Relationship repair is only available in author mode")

    payload = await repair_relationship_timelines(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return payload


async def delete_book_relationship_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
) -> dict[str, str]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    relationship = await db.get(CharacterRelationship, relationship_id)
    if not relationship or relationship.book_id != book.id:
        raise HTTPException(404, "Relationship not found")
    if book.mode != "author":
        raise HTTPException(400, "Relationship editing is only available in author mode")

    await db.delete(relationship)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {"deleted": str(relationship_id)}


def serialize_relationship_record(relationship: CharacterRelationship) -> dict[str, Any]:
    left_id, right_id = canonical_relationship_pair_ids(
        relationship.character_a_id,
        relationship.character_b_id,
    )
    return {
        "id": str(relationship.id),
        "character_a_id": str(left_id),
        "character_b_id": str(right_id),
        "rel_type": relationship.rel_type,
        "sentiment": relationship.sentiment,
        "description": relationship.description,
        "from_chapter": relationship.from_chapter,
        "to_chapter": relationship.to_chapter,
        "shared_labels": list(getattr(relationship, "shared_labels", None) or []),
        "character_a_to_b_labels": list(
            getattr(relationship, "character_a_to_b_labels", None) or []
        ),
        "character_b_to_a_labels": list(
            getattr(relationship, "character_b_to_a_labels", None) or []
        ),
        "label_evidence": dict(getattr(relationship, "label_evidence", None) or {}),
    }


def _normalize_relationship_type(value: str) -> str:
    rel_type = _clean_text(value).strip().lower().replace(" ", "_")
    if not rel_type:
        raise HTTPException(400, "Relationship type is required")
    return rel_type


def _validate_relationship_window(from_chapter: int | None, to_chapter: int | None) -> None:
    if from_chapter is not None and from_chapter < 1:
        raise HTTPException(400, "from_chapter must be at least 1")
    if to_chapter is not None and to_chapter < 1:
        raise HTTPException(400, "to_chapter must be at least 1")
    if from_chapter is not None and to_chapter is not None and to_chapter < from_chapter:
        raise HTTPException(400, "to_chapter cannot be earlier than from_chapter")


async def _load_pending_candidate_and_character(
    db: AsyncSession,
    *,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    character_id: uuid.UUID,
    pending_error: str,
) -> tuple[CharacterRelationshipCandidate, Character]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    character = await db.get(Character, character_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if candidate.status != CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
        raise HTTPException(400, pending_error)
    return candidate, character


async def _load_relationship_candidate(
    db: AsyncSession,
    *,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> tuple[Any, CharacterRelationshipCandidate]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    return book, candidate
