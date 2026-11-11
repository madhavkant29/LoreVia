from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Chapter
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import CharacterRelationship
from app.schemas.books import CharacterCreateBody, CharacterUpdateBody
from app.services.quality_metrics_service import record_quality_review
from app.utils.billing_utils import require_author_access
from app.utils.books.book_text import _clean_text
from app.utils.books.notes import get_owned_book
from app.utils.characters.duplicates import refresh_character_duplicate_suggestions
from app.utils.characters.manual import (
    apply_graph_visibility_override,
    apply_manual_character_description,
    build_manual_character,
)
from app.utils.characters.narrator_profile_review import accept_narrator_profile_proposal
from app.utils.characters.review import append_character_review_audit_entry, mark_character_curated
from app.utils.characters.serialization import serialize_book_character
from app.utils.characters.text import clean_optional_text, clean_string_list
from app.utils.tag_utils import ENTITY_TYPE_CHARACTER, get_custom_tags_for_entity


async def create_book_character_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    body: CharacterCreateBody,
) -> dict[str, Any]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character editing is only available in author mode")

    role = _clean_text(body.role).strip().lower() if body.role is not None else None
    if role not in {None, "mc", "sc", "background"}:
        raise HTTPException(400, "Invalid role")

    try:
        character = build_manual_character(
            book_id=book.id,
            name=body.name,
            first_chapter=body.first_chapter,
            aliases=body.aliases,
            role=role,
            description=body.description,
            goal=body.goal,
            lie_they_believe=body.lie_they_believe,
            backstory_wound=body.backstory_wound,
            arc_type=body.arc_type,
            arc_summary=body.arc_summary,
            personality_tags=body.personality_tags,
            motivations=body.motivations,
            fears=body.fears,
        )
    except ValueError:
        raise HTTPException(400, "Character data is invalid.")

    db.add(character)
    await db.flush()
    append_character_review_audit_entry(
        character,
        action="manual_character_created",
        details={"created_from": "author_create_route"},
        actor_user_id=current_user.id,
        reason_codes=["manual_character"],
    )
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="character",
        entity_id=character.id,
        outcome=(
            "missed_character"
            if int(book.total_chapters or 0) > 0 and book.status == "ready"
            else "manual_created"
        ),
        evidence={
            "created_from": "author_create_route",
            "book_status": book.status,
            "chapter_count": int(book.total_chapters or 0),
        },
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await db.refresh(character)
    return serialize_book_character(
        character,
        rel_summaries={},
        states=[],
        relationships=[],
        counterpart_names={},
        voice_profile=None,
        total_chapters=book.total_chapters,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_CHARACTER,
            entity_id=character.id,
            book_id=book.id,
        ),
    )


async def update_book_character_for_user(
    *,
    db: AsyncSession,
    current_user: Any,
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterUpdateBody,
) -> dict[str, Any]:
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character editing is only available in author mode")

    if body.name is not None:
        cleaned_name = _clean_text(body.name).strip()
        if not cleaned_name:
            raise HTTPException(400, "Character name cannot be empty")
        cast(Any, character).name = cleaned_name
    if body.aliases is not None:
        character.aliases = clean_string_list(body.aliases)
    if body.role is not None:
        role = _clean_text(body.role).strip().lower() or None
        if role not in {None, "mc", "sc", "background"}:
            raise HTTPException(400, "Invalid role")
        cast(Any, character).role = role
    if body.description is not None:
        apply_manual_character_description(character, body.description)
    if body.goal is not None:
        character.goal = clean_optional_text(body.goal)
    if body.lie_they_believe is not None:
        character.lie_they_believe = clean_optional_text(body.lie_they_believe)
    if body.backstory_wound is not None:
        character.backstory_wound = clean_optional_text(body.backstory_wound)
    if body.arc_type is not None:
        character.arc_type = clean_optional_text(body.arc_type)
    if body.arc_summary is not None:
        character.arc_summary = clean_optional_text(body.arc_summary)
    if body.personality_tags is not None:
        character.personality_tags = clean_string_list(body.personality_tags)
    if body.motivations is not None:
        character.motivations = clean_string_list(body.motivations)
    if body.fears is not None:
        character.fears = clean_string_list(body.fears)
    if body.graph_visibility is not None:
        try:
            apply_graph_visibility_override(character, body.graph_visibility)
        except ValueError:
            raise HTTPException(400, "Character visibility settings are invalid.")
    if body.accept_narrator_claim_index is not None:
        metadata = character.analysis_metadata or {}
        review = (
            metadata.get("character_profile_review")
            or metadata.get("narrator_profile_review")
            or {}
        )
        proposals = review.get("proposals") or []
        index = body.accept_narrator_claim_index
        if not isinstance(proposals, list) or index >= len(proposals):
            raise HTTPException(400, "Narrator profile proposal is unavailable.")
        proposal = proposals[index]
        chapter_number = proposal.get("chapter_number") if isinstance(proposal, dict) else None
        expected_key = (review.get("chapter_s3_keys") or {}).get(str(chapter_number))
        current_key = (
            await db.execute(
                select(Chapter.s3_key).where(
                    Chapter.book_id == book.id, Chapter.number == chapter_number
                )
            )
        ).scalar_one_or_none()
        if not expected_key or current_key != expected_key:
            raise HTTPException(409, "Source chapter changed. Refresh the profile review.")
        try:
            accept_narrator_profile_proposal(character, index)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    mark_character_curated(
        character,
        protected_from_repair=body.protected_from_repair
        if body.protected_from_repair is not None
        else None,
        review_note=body.review_note if body.review_note is not None else None,
    )
    record_quality_review(
        db,
        book_id=book.id,
        user_id=current_user.id,
        entity_type="character",
        entity_id=character.id,
        outcome="corrected_after_promotion",
        evidence={
            "corrected_fields": sorted(body.model_fields_set),
            **(
                dict(character.analysis_metadata)
                if isinstance(character.analysis_metadata, dict)
                else {}
            ),
        },
    )

    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await db.refresh(character)
    return await serialize_character_detail(db, book=book, character=character)


async def serialize_character_detail(
    db: AsyncSession,
    *,
    book: Any,
    character: Character,
) -> dict[str, Any]:
    states = (
        (
            await db.execute(
                select(CharacterState)
                .where(CharacterState.character_id == character.id)
                .order_by(CharacterState.at_chapter)
            )
        )
        .scalars()
        .all()
    )
    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(
                    CharacterRelationship.book_id == book.id,
                    (CharacterRelationship.character_a_id == character.id)
                    | (CharacterRelationship.character_b_id == character.id),
                )
            )
        )
        .scalars()
        .all()
    )
    counterpart_ids = {
        rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        for rel in relationships
    }
    counterparts = (
        (await db.execute(select(Character).where(Character.id.in_(counterpart_ids))))
        .scalars()
        .all()
        if counterpart_ids
        else []
    )
    counterpart_names = {item.id: item.name for item in counterparts}
    voice_profile = (
        await db.execute(
            select(CharacterVoiceProfile).where(CharacterVoiceProfile.character_id == character.id)
        )
    ).scalar_one_or_none()

    return serialize_book_character(
        character,
        rel_summaries={},
        states=list(states),
        relationships=list(relationships),
        counterpart_names=counterpart_names,
        voice_profile=voice_profile,
        total_chapters=book.total_chapters,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_CHARACTER,
            entity_id=character.id,
            book_id=book.id,
        ),
    )
