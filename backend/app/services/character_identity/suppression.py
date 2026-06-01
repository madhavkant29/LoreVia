from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import CharacterSuppression
from app.services.character_identity.merge import record_identity_action
from app.services.character_identity.normalization import normalize_name


async def suppress_candidate(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    surface_text: str,
    candidate_kind: str,
    reason: str,
    confidence: float = 0.0,
    chapter_number: int | None = None,
    character_id: uuid.UUID | None = None,
    evidence_quote: str | None = None,
    repair_run_id: str | None = None,
) -> CharacterSuppression:
    cleaned = " ".join(str(surface_text or "").split()).strip()
    normalized = normalize_name(cleaned) or cleaned.casefold()
    existing = (
        await db.execute(
            select(CharacterSuppression).where(
                CharacterSuppression.book_id == book_id,
                CharacterSuppression.normalized_text == normalized,
                CharacterSuppression.reason == reason,
                CharacterSuppression.chapter_number.is_(chapter_number) if chapter_number is None else CharacterSuppression.chapter_number == chapter_number,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if character_id is not None:
            existing.character_id = character_id
        existing.confidence = max(float(existing.confidence or 0.0), confidence)
        return existing

    suppression = CharacterSuppression(
        book_id=book_id,
        character_id=character_id,
        chapter_number=chapter_number,
        surface_text=cleaned,
        normalized_text=normalized,
        candidate_kind=candidate_kind,
        reason=reason,
        confidence=confidence,
        evidence_quote=evidence_quote,
    )
    db.add(suppression)
    await record_identity_action(
        db,
        book_id=book_id,
        action_type="auto_suppress",
        source_character_id=character_id,
        surface_text=cleaned,
        confidence=confidence,
        reason=reason,
        repair_run_id=repair_run_id,
    )
    return suppression
