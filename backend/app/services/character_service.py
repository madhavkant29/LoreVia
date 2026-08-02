import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import cache_get, cache_set, key_character_profile
from app.models.character import Character, CharacterState


async def get_character_cached(db: AsyncSession, character_id: uuid.UUID) -> dict | None:
    """Return character profile from cache or DB."""
    cached = await cache_get(key_character_profile(str(character_id)))
    if cached:
        return cast(dict[str, Any], cached)

    char = await db.get(Character, character_id)
    if not char:
        return None

    data = {
        "id": str(char.id),
        "name": char.name,
        "aliases": char.aliases or [],
        "trait_state": char.trait_state or {},
        "personality_tags": char.personality_tags or [],
        "motivations": char.motivations or [],
        "fears": char.fears or [],
        "archetype": char.archetype,
        "arc_summary": char.arc_summary,
    }
    await cache_set(
        key_character_profile(str(character_id)), data, settings.REDIS_TTL_CHARACTER_PROFILE
    )
    return data


async def get_spoiler_free_state(db: AsyncSession, character_id: uuid.UUID, chapter: int) -> dict:
    """Return character state at or before the given chapter — never ahead."""
    state = (
        await db.execute(
            select(CharacterState)
            .where(
                CharacterState.character_id == character_id, CharacterState.at_chapter <= chapter
            )
            .order_by(CharacterState.at_chapter.desc())
            .limit(1)
        )
    ).scalar()

    if state:
        return {
            "trait_state": state.trait_snapshot,
            "at_chapter": state.at_chapter,
            "arc_note": state.arc_note,
        }

    char = await db.get(Character, character_id)
    return {"trait_state": char.trait_state if char else {}, "at_chapter": 0}
