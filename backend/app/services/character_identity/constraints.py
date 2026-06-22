from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import CharacterDuplicateSuggestion, CharacterIdentityConstraint
from app.services.character_identity.merge import record_identity_action


def canonical_constraint_pair(
    left_id: uuid.UUID, right_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    return (left_id, right_id) if str(left_id) < str(right_id) else (right_id, left_id)


async def add_identity_constraint(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    left_character_id: uuid.UUID,
    right_character_id: uuid.UUID,
    left_text: str,
    right_text: str,
    constraint_type: str,
    reason: str | None = None,
    source: str = "system",
    confidence: float = 1.0,
    repair_run_id: str | None = None,
) -> CharacterIdentityConstraint:
    left_id, right_id = canonical_constraint_pair(left_character_id, right_character_id)
    if left_id != left_character_id:
        left_text, right_text = right_text, left_text

    existing = (
        await db.execute(
            select(CharacterIdentityConstraint).where(
                CharacterIdentityConstraint.book_id == book_id,
                CharacterIdentityConstraint.left_character_id == left_id,
                CharacterIdentityConstraint.right_character_id == right_id,
                CharacterIdentityConstraint.constraint_type == constraint_type,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.reason = reason or existing.reason
        existing.confidence = max(float(existing.confidence or 0.0), confidence)
        return existing

    constraint = CharacterIdentityConstraint(
        book_id=book_id,
        left_character_id=left_id,
        right_character_id=right_id,
        left_text=left_text,
        right_text=right_text,
        constraint_type=constraint_type,
        reason=reason,
        source=source,
        confidence=confidence,
    )
    db.add(constraint)
    await record_identity_action(
        db,
        book_id=book_id,
        action_type="auto_block_duplicate" if source != "manual" else "manual_override",
        source_character_id=left_id,
        target_character_id=right_id,
        confidence=confidence,
        reason=reason or constraint_type,
        repair_run_id=repair_run_id,
    )

    if constraint_type in {"not_same_character", "blocked_merge"}:
        suggestions = (
            (
                await db.execute(
                    select(CharacterDuplicateSuggestion).where(
                        CharacterDuplicateSuggestion.book_id == book_id,
                        or_(
                            (
                                (CharacterDuplicateSuggestion.primary_character_id == left_id)
                                & (CharacterDuplicateSuggestion.secondary_character_id == right_id)
                            ),
                            (
                                (CharacterDuplicateSuggestion.primary_character_id == right_id)
                                & (CharacterDuplicateSuggestion.secondary_character_id == left_id)
                            ),
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        for suggestion in suggestions:
            if suggestion.status == "pending":
                suggestion.status = "dismissed"
            suggestion.dismissal_reason = reason or constraint_type
            suggestion.auto_dismissed = source != "manual"
    return constraint


async def has_blocking_identity_constraint(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    left_character_id: uuid.UUID,
    right_character_id: uuid.UUID,
) -> bool:
    left_id, right_id = canonical_constraint_pair(left_character_id, right_character_id)
    constraint = (
        await db.execute(
            select(CharacterIdentityConstraint.id).where(
                CharacterIdentityConstraint.book_id == book_id,
                CharacterIdentityConstraint.left_character_id == left_id,
                CharacterIdentityConstraint.right_character_id == right_id,
                CharacterIdentityConstraint.constraint_type.in_(
                    ("not_same_character", "blocked_merge")
                ),
            )
        )
    ).scalar_one_or_none()
    return constraint is not None
