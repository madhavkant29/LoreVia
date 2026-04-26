import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.character.deduplicator import character_name_keys, names_equivalent
from app.engine.character.profile_builder import merge_profile_fields
from app.models.character import Character, CharacterState
from app.models.intelligence import CharacterRelationship
from app.utils.character_utils import update_character_classification


async def consolidate_characters(
    db: AsyncSession,
    book_id: uuid.UUID,
    up_to_chapter: int | None = None,
) -> bool:
    query = select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.created_at)
    if up_to_chapter is not None:
        query = query.where(Character.first_chapter <= up_to_chapter)

    characters = list((await db.execute(query)).scalars().all())
    if len(characters) < 2:
        return False

    key_to_primary: dict[str, Character] = {}
    merged_any = False

    for char in characters:
        keys = character_name_keys(char.name, char.aliases or [])
        primary = next((key_to_primary[key] for key in keys if key in key_to_primary), None)
        if primary is None:
            primary = next(
                (
                    existing
                    for existing in key_to_primary.values()
                    if names_equivalent(char.name, char.aliases or [], existing.name, existing.aliases or [])
                ),
                None,
            )
        if primary is None or primary.id == char.id:
            for key in keys:
                key_to_primary[key] = char
            continue

        await _merge_character_records(db, primary, char)
        merged_any = True
        for key in character_name_keys(primary.name, primary.aliases or []):
            key_to_primary[key] = primary

    if merged_any:
        await db.commit()
    
    # Recompute classification scores for all characters in the book
    for char in key_to_primary.values():
        update_character_classification(char)
    
    await db.commit()
    return merged_any


async def _merge_character_records(db: AsyncSession, primary: Character, duplicate: Character) -> None:
    merged = merge_profile_fields(primary, duplicate)
    primary.aliases = merged["aliases"]
    primary.role = merged["role"]
    primary.first_chapter = merged["first_chapter"]
    primary.trait_state = merged["trait_state"]
    primary.hair = merged["hair"]
    primary.eyes = merged["eyes"]
    primary.build = merged["build"]
    primary.age_descriptor = merged["age_descriptor"]
    primary.distinguishing = merged["distinguishing"]
    primary.personality_tags = merged["personality_tags"]
    primary.motivations = merged["motivations"]
    primary.fears = merged["fears"]
    primary.arc_summary = merged["arc_summary"]
    primary.archetype = merged["archetype"]
    if primary.embedding is None and duplicate.embedding is not None:
        primary.embedding = duplicate.embedding

    state_rows = (
        await db.execute(select(CharacterState).where(CharacterState.character_id == duplicate.id))
    ).scalars().all()
    for state in state_rows:
        existing_state = (
            await db.execute(
                select(CharacterState).where(
                    CharacterState.character_id == primary.id,
                    CharacterState.at_chapter == state.at_chapter,
                )
            )
        ).scalar()
        if existing_state:
            existing_state.trait_snapshot = state.trait_snapshot or existing_state.trait_snapshot
            if state.prompt_delta and not existing_state.prompt_delta:
                existing_state.prompt_delta = state.prompt_delta
            if state.arc_note and not existing_state.arc_note:
                existing_state.arc_note = state.arc_note
            await db.delete(state)
        else:
            state.character_id = primary.id

    rels = (
        await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.book_id == primary.book_id,
                or_(
                    CharacterRelationship.character_a_id == duplicate.id,
                    CharacterRelationship.character_b_id == duplicate.id,
                ),
            )
        )
    ).scalars().all()
    for rel in rels:
        if rel.character_a_id == duplicate.id:
            rel.character_a_id = primary.id
        if rel.character_b_id == duplicate.id:
            rel.character_b_id = primary.id
        if rel.character_a_id == rel.character_b_id:
            await db.delete(rel)

    await db.flush()
    await _dedupe_relationships(db, primary.book_id)
    await db.delete(duplicate)
    await db.flush()


async def _dedupe_relationships(db: AsyncSession, book_id: uuid.UUID) -> None:
    rels = (
        await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
    ).scalars().all()

    seen: set[tuple[str, str, str, int | None, int | None, str]] = set()
    for rel in rels:
        pair = sorted([str(rel.character_a_id), str(rel.character_b_id)])
        key = (
            pair[0],
            pair[1],
            rel.rel_type or "",
            rel.from_chapter,
            rel.to_chapter,
            (rel.description or "").strip().lower(),
        )
        if key in seen:
            await db.delete(rel)
            continue
        seen.add(key)
