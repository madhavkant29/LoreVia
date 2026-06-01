from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character, CharacterAlias, CharacterIdentityAction
from app.services.character_identity.normalization import normalize_name


async def record_identity_action(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    action_type: str,
    source_character_id: uuid.UUID | None = None,
    target_character_id: uuid.UUID | None = None,
    surface_text: str | None = None,
    confidence: float = 0.0,
    reason: str | None = None,
    reversible: bool = False,
    reversible_data: dict | None = None,
    repair_run_id: str | None = None,
) -> CharacterIdentityAction:
    action = CharacterIdentityAction(
        book_id=book_id,
        action_type=action_type,
        source_character_id=source_character_id,
        target_character_id=target_character_id,
        surface_text=surface_text,
        confidence=confidence,
        reason=reason,
        reversible=reversible,
        reversible_data=reversible_data or {},
        repair_run_id=repair_run_id,
    )
    db.add(action)
    return action


async def add_character_alias(
    db: AsyncSession,
    *,
    character: Character,
    alias_text: str,
    alias_kind: str,
    source: str = "system",
    confidence: float = 0.88,
    repair_run_id: str | None = None,
) -> CharacterAlias | None:
    cleaned = " ".join(str(alias_text or "").split()).strip()
    normalized = normalize_name(cleaned)
    if not cleaned or not normalized or normalized == normalize_name(character.name):
        return None

    existing_aliases = list(character.aliases or [])
    if normalized not in {normalize_name(alias) for alias in existing_aliases}:
        character.aliases = [*existing_aliases, cleaned]

    existing = (
        await db.execute(
            select(CharacterAlias).where(
                CharacterAlias.book_id == character.book_id,
                CharacterAlias.character_id == character.id,
                CharacterAlias.normalized_alias == normalized,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.alias_text = cleaned
        existing.alias_kind = alias_kind
        existing.source = source
        existing.confidence = max(float(existing.confidence or 0.0), confidence)
        return existing

    alias = CharacterAlias(
        book_id=character.book_id,
        character_id=character.id,
        alias_text=cleaned,
        normalized_alias=normalized,
        alias_kind=alias_kind,
        source=source,
        confidence=confidence,
    )
    db.add(alias)
    await record_identity_action(
        db,
        book_id=character.book_id,
        action_type="auto_alias" if source != "manual" else "manual_override",
        target_character_id=character.id,
        surface_text=cleaned,
        confidence=confidence,
        reason=alias_kind,
        repair_run_id=repair_run_id,
    )
    return alias
