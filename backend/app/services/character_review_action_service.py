from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character, CharacterCandidate
from app.schemas.books import CharacterCandidateAttachBody
from app.services.quality_metrics_service import record_quality_review
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_VISIBILITY_VISIBLE,
)
from app.utils.characters.duplicates import refresh_character_duplicate_suggestions
from app.utils.characters.review import (
    attach_character_candidate,
    demote_character_to_review_candidate,
    mark_character_candidate_as_place,
    promote_character_candidate,
    reject_character_as_noise,
    reject_character_candidate,
    set_character_review_state,
)


async def delete_book_character_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
) -> dict[str, str]:
    book, character = await _load_author_character(
        db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
        mode_error="Character correction is only available in author mode",
    )
    await db.delete(character)
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"deleted": str(character_id)}


async def demote_book_character_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
) -> dict[str, str]:
    book, character = await _load_author_character(
        db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
        mode_error="Character review is only available in author mode",
    )
    candidate = await demote_character_to_review_candidate(
        db,
        character=character,
        reason_codes=["author_requested_review"],
        review_note=(character.analysis_metadata or {}).get("review_note"),
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"demoted": str(character_id), "candidate_id": str(candidate.id)}


async def approve_book_character_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
) -> dict[str, str]:
    book, character = await _load_author_character(
        db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
        mode_error=None,
    )
    set_character_review_state(
        character,
        visibility_state=CHARACTER_VISIBILITY_VISIBLE,
        approval_state=CHARACTER_APPROVAL_APPROVED,
        approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
        reason_codes=["author_approved_character"],
        action="character_approved_from_review",
        details={"route": "approve_character"},
        actor_user_id=current_user.id,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"approved": str(character.id)}


async def reject_book_character_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
) -> dict[str, str]:
    book, character = await _load_author_character(
        db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
        mode_error=None,
    )
    reject_character_as_noise(
        character,
        reason_codes=["author_rejected_character"],
        action="character_rejected_from_review",
        details={"route": "reject_character"},
        actor_user_id=current_user.id,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"rejected": str(character.id)}


async def promote_book_character_candidate_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> dict[str, str]:
    book, candidate = await _load_pending_character_candidate(
        db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
        pending_error="Only pending candidates can be promoted",
    )
    character = await promote_character_candidate(db, candidate=candidate)
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="character_candidate",
        entity_id=candidate.id,
        outcome="promoted",
        evidence=dict(candidate.evidence or {}),
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"promoted": str(character.id), "candidate_id": str(candidate.id)}


async def attach_book_character_candidate_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: CharacterCandidateAttachBody,
) -> dict[str, str]:
    book, candidate = await _load_pending_character_candidate(
        db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
        pending_error="Only pending candidates can be attached",
    )
    character = await db.get(Character, body.character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")

    await attach_character_candidate(db, candidate=candidate, character=character)
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="character_candidate",
        entity_id=candidate.id,
        outcome="accepted",
        evidence=dict(candidate.evidence or {}),
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"attached": str(character.id), "candidate_id": str(candidate.id)}


async def reject_book_character_candidate_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> dict[str, str]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    if candidate.matched_character_id is not None:
        character = await db.get(Character, candidate.matched_character_id)
        if (
            character is not None
            and character.book_id == book.id
            and character.approval_state == CHARACTER_APPROVAL_PENDING_REVIEW
        ):
            reject_character_as_noise(
                character,
                reason_codes=["candidate_rejected", *(candidate.reason_codes or [])],
                action="character_review_candidate_rejected",
                details={"candidate_id": str(candidate.id)},
                actor_user_id=current_user.id,
            )
    reject_character_candidate(candidate, reason_codes=["author_rejected_candidate"])
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="character_candidate",
        entity_id=candidate.id,
        outcome="rejected",
        evidence=dict(candidate.evidence or {}),
    )
    await db.commit()
    return {"rejected": str(candidate.id)}


async def mark_book_character_candidate_as_place_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> dict[str, str]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    mark_character_candidate_as_place(candidate, reason_codes=["author_marked_place"])
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="character_candidate",
        entity_id=candidate.id,
        outcome="suppressed",
        evidence=dict(candidate.evidence or {}),
    )
    await db.commit()
    return {"marked": str(candidate.id), "adjudication_status": candidate.adjudication_status}


async def _load_author_character(
    db: AsyncSession,
    *,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    mode_error: str | None,
) -> tuple[Any, Character]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if mode_error is not None and book.mode != "author":
        raise HTTPException(400, mode_error)
    return book, character


async def _load_pending_character_candidate(
    db: AsyncSession,
    *,
    current_user: Any,
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    pending_error: str,
) -> tuple[Any, CharacterCandidate]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    if candidate.status != CHARACTER_CANDIDATE_PENDING:
        raise HTTPException(400, pending_error)
    return book, candidate
