import uuid
from collections import Counter
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .core import _clean_text
from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.core.redis import mark_book_cache_dirty
from app.core.security import create_asset_token
from app.models.book import Book
from app.models.character import (
    Character,
    CharacterAlias,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterIdentityAction,
    CharacterSuppression,
    CharacterRelationshipCandidate,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.intelligence import CharacterRelationship
from app.schemas.books import (
    CharacterCandidateAttachBody,
    CharacterCreateBody,
    CharacterMergeBody,
    CharacterPartitionBody,
    CharacterShareOut,
    CharacterUpdateBody,
    RelationshipCandidateAcceptBody,
    RelationshipCandidateAttachBody,
    RelationshipCreateBody,
    RelationshipUpdateBody,
)
from app.schemas.character import CharacterAliasBody, CharacterAliasOut, CharacterReviewOut
from app.services.character_identity.constraints import add_identity_constraint
from app.services.character_identity.merge import add_character_alias, record_identity_action
from app.services.character_identity.normalization import normalize_name
from app.services.character_identity.repair import CharacterIdentityRepairJob
from app.utils.billing_utils import require_author_access
from app.utils.book_utils import (
    collaboration_has_resource,
    get_book_with_collaboration_access,
    get_owned_book,
)
from app.utils.character_utils import (
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
    CHARACTER_VISIBILITY_VISIBLE,
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_DUPLICATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_REJECTED,
    CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED,
    append_unique_summary,
    append_character_review_audit_entry,
    apply_graph_visibility_override,
    apply_manual_character_description,
    attach_character_candidate,
    build_manual_character,
    clean_optional_text,
    clean_string_list,
    demote_character_to_review_candidate,
    is_displayable_character,
    is_cast_visible_character,
    list_character_review_data,
    mark_character_candidate_as_place,
    mark_character_curated,
    mark_character_candidates_merged,
    merge_characters,
    partition_character,
    promote_character_candidate,
    reject_character_candidate,
    reject_character_as_noise,
    refresh_character_duplicate_suggestions,
    relationship_summary_for_character,
    serialize_book_character,
    set_character_review_state,
)
from app.utils.public_utils import ensure_public_mode_enabled
from app.utils.relationship_utils import (
    canonical_relationship_pair_ids,
    repair_relationship_timelines,
    upsert_relationship_timeline_state,
)
from app.utils.sparse_utils import filter_character_fields, include_requested
from app.utils.tag_utils import (
    ENTITY_TYPE_CHARACTER,
    get_custom_tags_for_entity,
    list_custom_tags_for_entity_ids,
)
router = APIRouter()


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


def _serialize_relationship_record(relationship: CharacterRelationship) -> dict[str, Any]:
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
        "character_a_to_b_labels": list(getattr(relationship, "character_a_to_b_labels", None) or []),
        "character_b_to_a_labels": list(getattr(relationship, "character_b_to_a_labels", None) or []),
        "label_evidence": dict(getattr(relationship, "label_evidence", None) or {}),
    }


# ─── Character listing & review ──────────────────────────────────────────────

@router.get("/{book_id}/characters")
async def get_book_characters(
    book_id: uuid.UUID,
    include: str | None = Query(None, description="Comma-separated sub-objects: arc_tracker, analysis_metadata, tags"),
    fields: str | None = Query(None, description="Comma-separated character fields to keep"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
    characters = [char for char in all_characters if is_cast_visible_character(char)] if book.mode == "author" else [char for char in all_characters if is_displayable_character(char)]
    char_by_id = {char.id: char for char in characters}
    character_ids = list(char_by_id.keys())

    skip_arc_tracker = not include_requested(include, "arc_tracker")
    skip_analysis_metadata = not include_requested(include, "analysis_metadata")
    skip_tags = not include_requested(include, "tags")

    rel_summaries: dict[str, list[str]] = {}
    rel_keys: dict[str, set[str]] = {}
    states_by_character: dict[uuid.UUID, list[CharacterState]] = {char_id: [] for char_id in character_ids}
    voice_profiles_by_character: dict[uuid.UUID, CharacterVoiceProfile] = {}
    counterpart_names: dict[uuid.UUID, str] = {char.id: char.name for char in characters}
    relationships_by_character: dict[uuid.UUID, list[CharacterRelationship]] = {char_id: [] for char_id in character_ids}
    tags_by_character: dict[uuid.UUID, list[str]] = {}

    if not skip_arc_tracker or not rel_summaries:
        rel_result = await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
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
                append_unique_summary(rel_summaries, rel_keys, str(a.id), f"{rel.rel_type}:{rel.from_chapter}:{rel.to_chapter}:{label_signature}:{b.name}".lower(), summary_a)
            if summary_b:
                append_unique_summary(rel_summaries, rel_keys, str(b.id), f"{rel.rel_type}:{rel.from_chapter}:{rel.to_chapter}:{label_signature}:{a.name}".lower(), summary_b)

        if not skip_arc_tracker and character_ids:
            state_rows = (
                await db.execute(
                    select(CharacterState)
                    .where(CharacterState.character_id.in_(character_ids))
                    .order_by(CharacterState.character_id, CharacterState.at_chapter)
                )
            ).scalars().all()
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


@router.get("/{book_id}/character-review", response_model=CharacterReviewOut)
async def get_book_character_review(
    book_id: uuid.UUID,
    include_quarantined: bool = Query(True),
    include_places: bool = Query(False),
    include_rejected: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character review is only available in author mode")
    return await list_character_review_data(
        db,
        book_id=book.id,
        include_quarantined=include_quarantined,
        include_places=include_places,
        include_rejected=include_rejected,
    )


@router.get("/{book_id}/characters/identity-diagnostics")
async def get_character_identity_diagnostics(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    suppressions = (
        await db.execute(
            select(CharacterSuppression).where(CharacterSuppression.book_id == book.id)
        )
    ).scalars().all()
    actions = (
        await db.execute(
            select(CharacterIdentityAction)
            .where(CharacterIdentityAction.book_id == book.id)
            .order_by(CharacterIdentityAction.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    hidden_candidates = (
        await db.execute(
            select(CharacterCandidate).where(
                CharacterCandidate.book_id == book.id,
                CharacterCandidate.status == "suppressed",
            )
        )
    ).scalars().all()
    action_counts = Counter(action.action_type for action in actions)
    return {
        "suppressed_count": len(suppressions),
        "auto_merged_count": action_counts.get("auto_merge", 0),
        "auto_alias_count": action_counts.get("auto_alias", 0),
        "blocked_duplicate_count": action_counts.get("auto_block_duplicate", 0),
        "hidden_candidate_count": len(hidden_candidates),
        "suppression_reasons": dict(Counter(item.reason for item in suppressions)),
        "recent_identity_actions": [
            {
                "id": str(action.id),
                "action_type": action.action_type,
                "source_character_id": str(action.source_character_id) if action.source_character_id else None,
                "target_character_id": str(action.target_character_id) if action.target_character_id else None,
                "surface_text": action.surface_text,
                "confidence": action.confidence,
                "reason": action.reason,
                "reversible": action.reversible,
                "created_at": action.created_at,
            }
            for action in actions
        ],
    }


@router.post("/{book_id}/characters/identity-actions/{action_id}/undo")
async def undo_character_identity_action(
    book_id: uuid.UUID,
    action_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    action = await db.get(CharacterIdentityAction, action_id)
    if not action or action.book_id != book.id:
        raise HTTPException(404, "Identity action not found")
    if not action.reversible:
        raise HTTPException(400, "Identity action cannot be undone")

    reversible_data = dict(action.reversible_data or {})
    restored_character_id: uuid.UUID | None = None
    if action.action_type == "auto_merge":
        secondary = await db.get(Character, action.source_character_id) if action.source_character_id else None
        if secondary is None or secondary.book_id != book.id:
            raise HTTPException(404, "Merged character record not found")
        secondary.merged_into_character_id = None
        secondary.normalized_name = None
        secondary.is_auto_suppressed = False
        secondary.suppression_reason = None
        set_character_review_state(
            secondary,
            visibility_state=str(reversible_data.get("secondary_visibility_state") or "quarantined"),
            approval_state=str(reversible_data.get("secondary_approval_state") or CHARACTER_APPROVAL_PENDING_REVIEW),
            approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
            reason_codes=["identity_action_undone"],
            action="identity_auto_merge_undone",
            details={"identity_action_id": str(action.id), "target_character_id": str(action.target_character_id) if action.target_character_id else None},
            actor_user_id=current_user.id,
        )
        restored_character_id = secondary.id
        if action.target_character_id is not None:
            primary = await db.get(Character, action.target_character_id)
            if primary is not None and primary.book_id == book.id:
                await add_identity_constraint(
                    db,
                    book_id=book.id,
                    left_character_id=primary.id,
                    right_character_id=secondary.id,
                    left_text=primary.name,
                    right_text=secondary.name,
                    constraint_type="not_same_character",
                    reason="identity_action_undo",
                    source="manual",
                    confidence=1.0,
                )
    elif action.action_type == "auto_alias":
        target = await db.get(Character, action.target_character_id) if action.target_character_id else None
        source = await db.get(Character, action.source_character_id) if action.source_character_id else None
        normalized_alias = normalize_name(action.surface_text)
        if target is not None and target.book_id == book.id and normalized_alias:
            target.aliases = [
                alias
                for alias in clean_string_list(target.aliases or [])
                if normalize_name(alias) != normalized_alias
            ]
            alias_rows = (
                await db.execute(
                    select(CharacterAlias).where(
                        CharacterAlias.book_id == book.id,
                        CharacterAlias.character_id == target.id,
                        CharacterAlias.normalized_alias == normalized_alias,
                    )
                )
            ).scalars().all()
            for alias in alias_rows:
                await db.delete(alias)
        if source is not None and source.book_id == book.id:
            source.merged_into_character_id = None
            source.normalized_name = None
            source.is_auto_suppressed = False
            source.suppression_reason = None
            set_character_review_state(
                source,
                visibility_state="quarantined",
                approval_state=CHARACTER_APPROVAL_PENDING_REVIEW,
                approval_source=CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
                reason_codes=["identity_action_undone"],
                action="identity_auto_alias_undone",
                details={"identity_action_id": str(action.id), "target_character_id": str(action.target_character_id) if action.target_character_id else None},
                actor_user_id=current_user.id,
            )
            restored_character_id = source.id
            if target is not None and target.book_id == book.id:
                await add_identity_constraint(
                    db,
                    book_id=book.id,
                    left_character_id=source.id,
                    right_character_id=target.id,
                    left_text=source.name,
                    right_text=target.name,
                    constraint_type="not_same_character",
                    reason="identity_action_undo",
                    source="manual",
                    confidence=1.0,
                )
    else:
        raise HTTPException(400, "Unsupported undo action type")

    action.reversible = False
    await record_identity_action(
        db,
        book_id=book.id,
        action_type="undo_merge" if action.action_type == "auto_merge" else "manual_override",
        source_character_id=action.source_character_id,
        target_character_id=action.target_character_id,
        surface_text=action.surface_text,
        confidence=1.0,
        reason=f"undo:{action.action_type}",
        reversible=False,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {"undone": str(action.id), "restored_character_id": str(restored_character_id) if restored_character_id else None}


@router.get("/{book_id}/character-review/reprocess")
async def preview_book_character_reprocess(
    book_id: uuid.UUID,
    allow_merge_safe_pairs: bool = Query(True),
    allow_demote_obvious_noise: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character reprocessing is only available in author mode")
    job = CharacterIdentityRepairJob(db, book_id=book.id)
    plan = await job.preview()
    payload = plan.to_payload()
    payload["allow_merge_safe_pairs"] = allow_merge_safe_pairs
    payload["allow_demote_obvious_noise"] = allow_demote_obvious_noise
    return payload


@router.post("/{book_id}/character-review/reprocess")
async def apply_book_character_reprocess(
    book_id: uuid.UUID,
    allow_merge_safe_pairs: bool = Query(True),
    allow_demote_obvious_noise: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Character reprocessing is only available in author mode")
    job = CharacterIdentityRepairJob(db, book_id=book.id)
    result = await job.apply()
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    payload = result.to_payload()
    payload["allow_merge_safe_pairs"] = allow_merge_safe_pairs
    payload["allow_demote_obvious_noise"] = allow_demote_obvious_noise
    return payload


# ─── Character CRUD ──────────────────────────────────────────────────────────

@router.post("/{book_id}/characters", status_code=201)
async def create_book_character(
    book_id: uuid.UUID,
    body: CharacterCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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


@router.get("/{book_id}/characters/{character_id}/aliases", response_model=list[CharacterAliasOut])
async def list_book_character_aliases(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    aliases = (
        await db.execute(
            select(CharacterAlias)
            .where(CharacterAlias.book_id == book.id, CharacterAlias.character_id == character.id)
            .order_by(CharacterAlias.alias_kind, CharacterAlias.alias_text)
        )
    ).scalars().all()
    return list(aliases)


@router.post("/{book_id}/characters/{character_id}/aliases", response_model=CharacterAliasOut, status_code=201)
async def add_book_character_alias(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterAliasBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    alias = await add_character_alias(
        db,
        character=character,
        alias_text=body.alias_text,
        alias_kind=body.alias_kind,
        source="manual",
        confidence=body.confidence,
    )
    if alias is None:
        raise HTTPException(400, "Alias is invalid or duplicates the character name")
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(alias)
    return alias


@router.delete("/{book_id}/characters/{character_id}/aliases/{alias_id}")
async def delete_book_character_alias(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    alias_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    alias = await db.get(CharacterAlias, alias_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if not alias or alias.book_id != book.id or alias.character_id != character.id:
        raise HTTPException(404, "Alias not found")
    normalized_removed = alias.normalized_alias
    character.aliases = [
        value
        for value in clean_string_list(character.aliases or [])
        if normalize_name(value) != normalized_removed
    ]
    await db.delete(alias)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {"deleted": str(alias_id)}


@router.post("/{book_id}/characters/merge")
async def merge_book_characters(
    book_id: uuid.UUID,
    body: CharacterMergeBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    primary = await db.get(Character, body.primary_id)
    secondary = await db.get(Character, body.secondary_id)
    if not primary or not secondary or primary.book_id != book.id or secondary.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if primary.id == secondary.id:
        return {"merged": str(primary.id)}

    merged = await merge_characters(db, primary.id, secondary.id, book.id)
    await mark_character_candidates_merged(
        db,
        book_id=book.id,
        primary_character_id=merged.id,
        secondary_character_id=secondary.id,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(merged)
    return {"merged": str(merged.id)}


@router.post("/{book_id}/characters/{character_id}/partition")
async def partition_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterPartitionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character partition is only available in author mode")

    try:
        created = await partition_character(
            db,
            source=character,
            partitions=[{"name": item.name, "aliases": item.aliases} for item in body.partitions],
        )
    except ValueError:
        raise HTTPException(400, "Character partition request is invalid.")

    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {
        "replaced": str(character_id),
        "created": [str(item.id) for item in created],
    }


@router.put("/{book_id}/characters/{character_id}")
async def update_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
    mark_character_curated(
        character,
        protected_from_repair=body.protected_from_repair
        if body.protected_from_repair is not None
        else None,
        review_note=body.review_note if body.review_note is not None else None,
    )

    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await db.refresh(character)
    states = (
        await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id == character.id)
            .order_by(CharacterState.at_chapter)
        )
    ).scalars().all()
    relationships = (
        await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.book_id == book.id,
                (CharacterRelationship.character_a_id == character.id) | (CharacterRelationship.character_b_id == character.id),
            )
        )
    ).scalars().all()
    counterpart_ids = {
        rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        for rel in relationships
    }
    counterparts = (
        await db.execute(select(Character).where(Character.id.in_(counterpart_ids)))
    ).scalars().all() if counterpart_ids else []
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


@router.delete("/{book_id}/characters/{character_id}")
async def delete_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character correction is only available in author mode")

    await db.delete(character)
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"deleted": str(character_id)}


@router.post("/{book_id}/characters/{character_id}/demote")
async def demote_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if book.mode != "author":
        raise HTTPException(400, "Character review is only available in author mode")

    candidate = await demote_character_to_review_candidate(
        db,
        character=character,
        reason_codes=["author_requested_review"],
        review_note=(character.analysis_metadata or {}).get("review_note"),
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"demoted": str(character_id), "candidate_id": str(candidate.id)}


@router.post("/{book_id}/characters/{character_id}/approve")
async def approve_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
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


@router.post("/{book_id}/characters/{character_id}/reject")
async def reject_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
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


# ─── Character candidate management ──────────────────────────────────────────

@router.post("/{book_id}/character-review/{candidate_id}/promote")
async def promote_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    if candidate.status != CHARACTER_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending candidates can be promoted")

    character = await promote_character_candidate(db, candidate=candidate)
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"promoted": str(character.id), "candidate_id": str(candidate.id)}


@router.post("/{book_id}/character-review/{candidate_id}/attach")
async def attach_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: CharacterCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    character = await db.get(Character, body.character_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if candidate.status != CHARACTER_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending candidates can be attached")

    await attach_character_candidate(db, candidate=candidate, character=character)
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    return {"attached": str(character.id), "candidate_id": str(candidate.id)}


@router.post("/{book_id}/character-review/{candidate_id}/reject")
async def reject_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
    await db.commit()
    return {"rejected": str(candidate.id)}


@router.post("/{book_id}/character-review/{candidate_id}/mark-place")
async def mark_book_character_candidate_as_place(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Candidate not found")
    mark_character_candidate_as_place(candidate, reason_codes=["author_marked_place"])
    await db.commit()
    return {"marked": str(candidate.id), "adjudication_status": candidate.adjudication_status}


# ─── Relationship candidate management ──────────────────────────────────────

@router.post("/{book_id}/relationship-review/{candidate_id}/attach-a")
async def attach_relationship_candidate_a(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    character = await db.get(Character, body.character_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if candidate.status != CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending relationship candidates can be updated")
    candidate.matched_character_a_id = character.id
    append_character_review_audit_entry(
        character,
        action="relationship_candidate_attached_a",
        details={"relationship_candidate_id": str(candidate.id)},
    )
    await db.commit()
    return {"attached_a": str(character.id), "relationship_candidate_id": str(candidate.id)}


@router.post("/{book_id}/relationship-review/{candidate_id}/attach-b")
async def attach_relationship_candidate_b(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    character = await db.get(Character, body.character_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if candidate.status != CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
        raise HTTPException(400, "Only pending relationship candidates can be updated")
    candidate.matched_character_b_id = character.id
    append_character_review_audit_entry(
        character,
        action="relationship_candidate_attached_b",
        details={"relationship_candidate_id": str(candidate.id)},
    )
    await db.commit()
    return {"attached_b": str(character.id), "relationship_candidate_id": str(candidate.id)}


@router.post("/{book_id}/relationship-review/{candidate_id}/accept")
async def accept_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAcceptBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
    if not relationship_a or relationship_a.book_id != book.id or not relationship_b or relationship_b.book_id != book.id:
        raise HTTPException(404, "Character not found")
    if relationship_a.id == relationship_b.id:
        raise HTTPException(400, "Choose two different characters")

    rel_type = _normalize_relationship_type(body.rel_type or candidate.rel_type or "connection")
    from_chapter = body.from_chapter or int(candidate.chapter_number or 1)
    _validate_relationship_window(from_chapter, body.to_chapter)
    if body.sentiment is not None and not -1.0 <= body.sentiment <= 1.0:
        raise HTTPException(400, "Sentiment must be between -1.0 and 1.0")
    evidence_payload = dict(candidate.evidence or {})
    extracted_relationship = evidence_payload.get("relationship") if isinstance(evidence_payload.get("relationship"), dict) else {}

    relationship, _ = await upsert_relationship_timeline_state(
        db,
        book_id=book.id,
        character_a_id=relationship_a.id,
        character_b_id=relationship_b.id,
        rel_type=rel_type,
        sentiment=body.sentiment if body.sentiment is not None else candidate.sentiment,
        description=clean_optional_text(body.description) if body.description is not None else clean_optional_text(candidate.description),
        from_chapter=from_chapter,
        to_chapter=body.to_chapter,
        shared_labels=body.shared_labels if body.shared_labels is not None else extracted_relationship.get("shared_labels"),
        character_a_to_b_labels=body.character_a_to_b_labels if body.character_a_to_b_labels is not None else extracted_relationship.get("character_a_to_b_labels"),
        character_b_to_a_labels=body.character_b_to_a_labels if body.character_b_to_a_labels is not None else extracted_relationship.get("character_b_to_a_labels"),
        label_evidence=body.label_evidence or extracted_relationship.get("label_evidence") or evidence_payload,
    )
    relationship.edited_by_author = True
    candidate.matched_character_a_id = relationship_a.id
    candidate.matched_character_b_id = relationship_b.id
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_ACCEPTED
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
    return _serialize_relationship_record(relationship)


@router.post("/{book_id}/relationship-review/{candidate_id}/resolve")
async def resolve_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_RESOLVED
    await db.commit()
    return {"resolved": str(candidate.id)}


@router.post("/{book_id}/relationship-review/{candidate_id}/reject")
async def reject_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    candidate = await db.get(CharacterRelationshipCandidate, candidate_id)
    if not candidate or candidate.book_id != book.id:
        raise HTTPException(404, "Relationship candidate not found")
    candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_REJECTED
    await db.commit()
    return {"rejected": str(candidate.id)}


# ─── Duplicate suggestion management ────────────────────────────────────────

@router.post("/{book_id}/duplicate-suggestions/{suggestion_id}/accept")
async def accept_character_duplicate_suggestion(
    book_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    suggestion = await db.get(CharacterDuplicateSuggestion, suggestion_id)
    if not suggestion or suggestion.book_id != book.id:
        raise HTTPException(404, "Duplicate suggestion not found")

    primary = await db.get(Character, suggestion.primary_character_id)
    secondary = await db.get(Character, suggestion.secondary_character_id)
    if not primary or not secondary or primary.book_id != book.id or secondary.book_id != book.id:
        raise HTTPException(404, "Character not found")

    merged = await merge_characters(db, primary.id, secondary.id, book.id)
    suggestion.status = "accepted"
    await mark_character_candidates_merged(
        db,
        book_id=book.id,
        primary_character_id=merged.id,
        secondary_character_id=secondary.id,
    )
    await refresh_character_duplicate_suggestions(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return {"merged": str(merged.id), "suggestion_id": str(suggestion.id)}


@router.post("/{book_id}/duplicate-suggestions/{suggestion_id}/dismiss")
async def dismiss_character_duplicate_suggestion(
    book_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    suggestion = await db.get(CharacterDuplicateSuggestion, suggestion_id)
    if not suggestion or suggestion.book_id != book.id:
        raise HTTPException(404, "Duplicate suggestion not found")
    suggestion.status = "dismissed"
    suggestion.auto_dismissed = False
    suggestion.dismissal_reason = "user_keep_separate"
    primary = await db.get(Character, suggestion.primary_character_id)
    secondary = await db.get(Character, suggestion.secondary_character_id)
    if primary and secondary and primary.book_id == book.id and secondary.book_id == book.id:
        await add_identity_constraint(
            db,
            book_id=book.id,
            left_character_id=primary.id,
            right_character_id=secondary.id,
            left_text=primary.name,
            right_text=secondary.name,
            constraint_type="not_same_character",
            reason="user_keep_separate",
            source="manual",
            confidence=1.0,
        )
    await db.commit()
    return {"dismissed": str(suggestion.id)}


# ─── Relationship CRUD ──────────────────────────────────────────────────────

@router.post("/{book_id}/relationships", status_code=201)
async def create_book_relationship(
    book_id: uuid.UUID,
    body: RelationshipCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Relationship editing is only available in author mode")

    relationship_a = await db.get(Character, body.character_a_id)
    relationship_b = await db.get(Character, body.character_b_id)
    if not relationship_a or relationship_a.book_id != book.id or not relationship_b or relationship_b.book_id != book.id:
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
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(relationship)
    return _serialize_relationship_record(relationship)


@router.put("/{book_id}/relationships/{relationship_id}")
async def update_book_relationship(
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
    body: RelationshipUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
        label_evidence=body.label_evidence if body.label_evidence is not None else dict(getattr(relationship, "label_evidence", None) or {}),
    )
    relationship.edited_by_author = True
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    await db.refresh(relationship)

    return _serialize_relationship_record(relationship)


@router.post("/{book_id}/relationships/repair")
async def repair_book_relationship_timelines(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    if book.mode != "author":
        raise HTTPException(400, "Relationship repair is only available in author mode")

    payload = await repair_relationship_timelines(db, book_id=book.id)
    await db.commit()
    await mark_book_cache_dirty(str(book.id))
    return payload


@router.delete("/{book_id}/relationships/{relationship_id}")
async def delete_book_relationship(
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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


# ─── Character sharing ──────────────────────────────────────────────────────

@router.post("/{book_id}/characters/{character_id}/share", response_model=CharacterShareOut)
async def share_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    character = await db.get(Character, character_id)
    if not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")

    token = create_asset_token(str(current_user.id), f"character-card:{book.id}:{character.id}", expires_minutes=7 * 24 * 60)
    return CharacterShareOut(share_url=f"/share/character/{book.id}/{character.id}?token={token}", expires_in_minutes=7 * 24 * 60)
