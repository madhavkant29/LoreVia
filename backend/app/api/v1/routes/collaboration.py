import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.schemas.books import (
    BookCollaboratorCreateBody,
    BookCollaboratorOut,
    BookCollaboratorUpdateBody,
    CollaboratorActivityOut,
)
from app.utils.beta_read_utils import get_book_collaborator_activity
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_management import (
    create_book_collaborator,
    delete_book_collaborator,
    list_book_collaborators,
    update_book_collaborator,
)
from app.utils.books.notes import (
    get_owned_book,
)

router = APIRouter()


@router.get("/{book_id}/collaborators", response_model=list[BookCollaboratorOut])
async def list_collaborators(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await list_book_collaborators(db, book)


@router.get(
    "/{book_id}/collaborators/{collaboration_id}/activity", response_model=CollaboratorActivityOut
)
async def get_collaborator_activity(
    book_id: uuid.UUID,
    collaboration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await get_book_collaborator_activity(
        db,
        book=book,
        collaborator_id=collaboration_id,
    )


@router.post("/{book_id}/collaborators", response_model=BookCollaboratorOut, status_code=201)
async def create_collaborator(
    book_id: uuid.UUID,
    body: BookCollaboratorCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await create_book_collaborator(
        db,
        book,
        email=body.email,
        display_name=body.display_name,
        role=body.role,
        scope=body.scope,
        permissions=body.permissions,
    )


@router.put("/{book_id}/collaborators/{collaboration_id}", response_model=BookCollaboratorOut)
async def update_collaborator(
    book_id: uuid.UUID,
    collaboration_id: uuid.UUID,
    body: BookCollaboratorUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    return await update_book_collaborator(
        db,
        book,
        collaboration_id,
        display_name=body.display_name,
        role=body.role,
        scope=body.scope,
        permissions=body.permissions,
        invite_status=body.invite_status,
    )


@router.delete("/{book_id}/collaborators/{collaboration_id}", status_code=204)
async def remove_collaborator(
    book_id: uuid.UUID,
    collaboration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    await delete_book_collaborator(db, book, collaboration_id)
    return Response(status_code=204)
