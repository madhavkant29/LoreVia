import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.v1.routes.books.character_aliases import (
    add_book_character_alias,
    delete_book_character_alias,
    list_book_character_aliases,
)
from app.api.v1.routes.books.character_aliases import router as character_aliases_router
from app.api.v1.routes.books.character_identity import (
    get_book_character_review,
    get_book_characters,
    get_character_identity_diagnostics,
    undo_character_identity_action,
)
from app.api.v1.routes.books.character_identity import router as character_identity_router
from app.api.v1.routes.books.character_reprocess import (
    apply_book_character_reprocess,
    preview_book_character_reprocess,
)
from app.api.v1.routes.books.character_reprocess import router as character_reprocess_router
from app.core.database import get_db
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
from app.services.character_merge_service import (
    accept_duplicate_suggestion_for_user,
    dismiss_duplicate_suggestion_for_user,
    merge_book_characters_for_user,
)
from app.services.character_mutation_service import (
    create_book_character_for_user,
    update_book_character_for_user,
)
from app.services.character_partition_service import partition_book_character_for_user
from app.services.character_relationship_service import (
    accept_relationship_candidate_for_user,
    attach_relationship_candidate_a_for_user,
    attach_relationship_candidate_b_for_user,
    create_book_relationship_for_user,
    delete_book_relationship_for_user,
    repair_book_relationship_timelines_for_user,
    reject_relationship_candidate_for_user,
    resolve_relationship_candidate_for_user,
    update_book_relationship_for_user,
)
from app.services.character_review_action_service import (
    approve_book_character_for_user,
    attach_book_character_candidate_for_user,
    delete_book_character_for_user,
    demote_book_character_for_user,
    mark_book_character_candidate_as_place_for_user,
    promote_book_character_candidate_for_user,
    reject_book_character_candidate_for_user,
    reject_book_character_for_user,
)
from app.services.character_share_service import share_book_character_for_user

router = APIRouter()
router.include_router(character_identity_router)
router.include_router(character_reprocess_router)
router.include_router(character_aliases_router)


# ─── Character listing & review ──────────────────────────────────────────────


# ─── Character CRUD ──────────────────────────────────────────────────────────


@router.post("/{book_id}/characters", status_code=201)
async def create_book_character(
    book_id: uuid.UUID,
    body: CharacterCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await create_book_character_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        body=body,
    )


@router.post("/{book_id}/characters/merge")
async def merge_book_characters(
    book_id: uuid.UUID,
    body: CharacterMergeBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await merge_book_characters_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        primary_id=body.primary_id,
        secondary_id=body.secondary_id,
    )


@router.post("/{book_id}/characters/{character_id}/partition")
async def partition_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterPartitionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await partition_book_character_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
        body=body,
    )


@router.put("/{book_id}/characters/{character_id}")
async def update_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await update_book_character_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
        body=body,
    )


@router.delete("/{book_id}/characters/{character_id}")
async def delete_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await delete_book_character_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )


@router.post("/{book_id}/characters/{character_id}/demote")
async def demote_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await demote_book_character_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )


@router.post("/{book_id}/characters/{character_id}/approve")
async def approve_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await approve_book_character_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )


@router.post("/{book_id}/characters/{character_id}/reject")
async def reject_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await reject_book_character_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )


# ─── Character candidate management ──────────────────────────────────────────


@router.post("/{book_id}/character-review/{candidate_id}/promote")
async def promote_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await promote_book_character_candidate_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
    )


@router.post("/{book_id}/character-review/{candidate_id}/attach")
async def attach_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: CharacterCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await attach_book_character_candidate_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
        body=body,
    )


@router.post("/{book_id}/character-review/{candidate_id}/reject")
async def reject_book_character_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await reject_book_character_candidate_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
    )


@router.post("/{book_id}/character-review/{candidate_id}/mark-place")
async def mark_book_character_candidate_as_place(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await mark_book_character_candidate_as_place_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
    )


# ─── Relationship candidate management ──────────────────────────────────────


@router.post("/{book_id}/relationship-review/{candidate_id}/attach-a")
async def attach_relationship_candidate_a(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await attach_relationship_candidate_a_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
        body=body,
    )


@router.post("/{book_id}/relationship-review/{candidate_id}/attach-b")
async def attach_relationship_candidate_b(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAttachBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await attach_relationship_candidate_b_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
        body=body,
    )


@router.post("/{book_id}/relationship-review/{candidate_id}/accept")
async def accept_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: RelationshipCandidateAcceptBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await accept_relationship_candidate_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
        body=body,
    )


@router.post("/{book_id}/relationship-review/{candidate_id}/resolve")
async def resolve_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await resolve_relationship_candidate_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
    )


@router.post("/{book_id}/relationship-review/{candidate_id}/reject")
async def reject_relationship_candidate(
    book_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await reject_relationship_candidate_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        candidate_id=candidate_id,
    )


# ─── Duplicate suggestion management ────────────────────────────────────────


@router.post("/{book_id}/duplicate-suggestions/{suggestion_id}/accept")
async def accept_character_duplicate_suggestion(
    book_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await accept_duplicate_suggestion_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        suggestion_id=suggestion_id,
    )


@router.post("/{book_id}/duplicate-suggestions/{suggestion_id}/dismiss")
async def dismiss_character_duplicate_suggestion(
    book_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await dismiss_duplicate_suggestion_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        suggestion_id=suggestion_id,
    )


# ─── Relationship CRUD ──────────────────────────────────────────────────────


@router.post("/{book_id}/relationships", status_code=201)
async def create_book_relationship(
    book_id: uuid.UUID,
    body: RelationshipCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await create_book_relationship_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        body=body,
    )


@router.put("/{book_id}/relationships/{relationship_id}")
async def update_book_relationship(
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
    body: RelationshipUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await update_book_relationship_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        relationship_id=relationship_id,
        body=body,
    )


@router.post("/{book_id}/relationships/repair")
async def repair_book_relationship_timelines(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await repair_book_relationship_timelines_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
    )


@router.delete("/{book_id}/relationships/{relationship_id}")
async def delete_book_relationship(
    book_id: uuid.UUID,
    relationship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await delete_book_relationship_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        relationship_id=relationship_id,
    )


# ─── Character sharing ──────────────────────────────────────────────────────


@router.post("/{book_id}/characters/{character_id}/share", response_model=CharacterShareOut)
async def share_book_character(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await share_book_character_for_user(
        db=db,
        current_user=current_user,
        book_id=book_id,
        character_id=character_id,
    )
