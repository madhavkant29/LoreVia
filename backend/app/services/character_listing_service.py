import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import CharacterRelationship
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    collaboration_has_resource,
    get_book_with_collaboration_access,
)
from app.utils.characters.governance import is_cast_visible_character, is_displayable_character
from app.utils.characters.presentation import append_unique_summary, relationship_summary_for_character
from app.utils.characters.serialization import serialize_book_character
from app.utils.sparse_utils import filter_character_fields, include_requested
from app.utils.tag_utils import ENTITY_TYPE_CHARACTER, list_custom_tags_for_entity_ids


async def list_book_characters_for_viewer(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    current_user: Any,
    include: str | None = None,
    fields: str | None = None,
) -> list[dict[str, Any]]:
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_has_resource(collaborator, "character_bible"):
        raise HTTPException(403, "This share does not include the character bible.")
    if collaborator is None:
        require_author_access(current_user)

    result = await db.execute(
        select(Character)
        .where(Character.book_id == book_id)
        .options(selectinload(Character.voice_profile), selectinload(Character.alias_records))
        .order_by(Character.first_chapter, Character.name)
    )
    all_characters = list(result.scalars().all())
    characters = (
        [char for char in all_characters if is_cast_visible_character(char)]
        if book.mode == "author"
        else [char for char in all_characters if is_displayable_character(char)]
    )
    char_by_id = {char.id: char for char in characters}
    character_ids = list(char_by_id.keys())

    skip_arc_tracker = not include_requested(include, "arc_tracker")
    skip_analysis_metadata = not include_requested(include, "analysis_metadata")
    skip_tags = not include_requested(include, "tags")

    rel_summaries: dict[str, list[str]] = {}
    rel_keys: dict[str, set[str]] = {}
    states_by_character: dict[uuid.UUID, list[CharacterState]] = {
        char_id: [] for char_id in character_ids
    }
    voice_profiles_by_character: dict[uuid.UUID, CharacterVoiceProfile] = {}
    counterpart_names: dict[uuid.UUID, str] = {char.id: char.name for char in characters}
    relationships_by_character: dict[uuid.UUID, list[CharacterRelationship]] = {
        char_id: [] for char_id in character_ids
    }
    tags_by_character: dict[uuid.UUID, list[str]] = {}

    if not skip_arc_tracker or not rel_summaries:
        rel_result = await db.execute(
            select(CharacterRelationship).where(CharacterRelationship.book_id == book_id)
        )
        relationships = list(rel_result.scalars().all())

        for rel in relationships:
            a = char_by_id.get(rel.character_a_id)
            b = char_by_id.get(rel.character_b_id)
            if not a or not b:
                continue
            summary_a = relationship_summary_for_character(rel, a.name, b.name, a.name)
            summary_b = relationship_summary_for_character(rel, a.name, b.name, b.name)
            label_signature = ":".join(
                ",".join(str(item) for item in (getattr(rel, field, None) or []))
                for field in ("shared_labels", "character_a_to_b_labels", "character_b_to_a_labels")
            )
            if summary_a:
                append_unique_summary(
                    rel_summaries,
                    rel_keys,
                    str(a.id),
                    f"{rel.rel_type}:{rel.from_chapter}:{rel.to_chapter}:{label_signature}:{b.name}".lower(),
                    summary_a,
                )
            if summary_b:
                append_unique_summary(
                    rel_summaries,
                    rel_keys,
                    str(b.id),
                    f"{rel.rel_type}:{rel.from_chapter}:{rel.to_chapter}:{label_signature}:{a.name}".lower(),
                    summary_b,
                )

        if not skip_arc_tracker and character_ids:
            state_rows = (
                (
                    await db.execute(
                        select(CharacterState)
                        .where(CharacterState.character_id.in_(character_ids))
                        .order_by(CharacterState.character_id, CharacterState.at_chapter)
                    )
                )
                .scalars()
                .all()
            )
            for state in state_rows:
                states_by_character.setdefault(state.character_id, []).append(state)

            for character in all_characters:
                profile = getattr(character, "voice_profile", None)
                if profile is not None:
                    voice_profiles_by_character[character.id] = profile

            for rel in relationships:
                if rel.character_a_id in relationships_by_character:
                    relationships_by_character[rel.character_a_id].append(rel)
                if rel.character_b_id in relationships_by_character:
                    relationships_by_character[rel.character_b_id].append(rel)

    if not skip_tags:
        tags_by_character = await list_custom_tags_for_entity_ids(
            db,
            entity_type=ENTITY_TYPE_CHARACTER,
            entity_ids=character_ids,
            book_id=book.id,
        )

    result_list = [
        serialize_book_character(
            char,
            rel_summaries=rel_summaries,
            states=states_by_character.get(char.id, []),
            relationships=relationships_by_character.get(char.id, []),
            counterpart_names=counterpart_names,
            voice_profile=voice_profiles_by_character.get(char.id),
            total_chapters=book.total_chapters,
            tags=tags_by_character.get(char.id, []) if not skip_tags else [],
            skip_arc_tracker=skip_arc_tracker,
            skip_analysis_metadata=skip_analysis_metadata,
            skip_tags=skip_tags,
        )
        for char in characters
    ]

    if fields:
        result_list = filter_character_fields(result_list, fields)
    return result_list
