"""
Book utility helpers ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    BookCollaborator,
)
from app.models.user import User
from app.schemas.books import (
    BookCollaboratorOut,
    CollaborationPermissions,
    CollaborationScope,
)
from app.utils.books.collaboration import (
    apply_collaboration_permissions,
    apply_collaboration_scope,
    normalize_collaboration_email,
    normalize_collaboration_permissions,
    normalize_collaboration_role,
    normalize_collaboration_scope,
    serialize_book_collaborator,
)

if TYPE_CHECKING:
    pass


async def list_book_collaborators(db: AsyncSession, book: Book) -> list[BookCollaboratorOut]:
    rows = (
        (
            await db.execute(
                select(BookCollaborator)
                .where(BookCollaborator.book_id == book.id)
                .order_by(BookCollaborator.invited_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [serialize_book_collaborator(row) for row in rows]


async def create_book_collaborator(
    db: AsyncSession,
    book: Book,
    *,
    email: str,
    role: str,
    scope: CollaborationScope,
    permissions: CollaborationPermissions | None = None,
    display_name: str | None = None,
) -> BookCollaboratorOut:
    normalized_email = normalize_collaboration_email(email)
    normalized_role = normalize_collaboration_role(role)
    normalized_scope = normalize_collaboration_scope(scope)
    normalized_permissions = normalize_collaboration_permissions(
        permissions,
        role=normalized_role,
        scope=normalized_scope,
    )
    invited_user = (
        await db.execute(select(User).where(User.email == normalized_email))
    ).scalar_one_or_none()
    collaborator = (
        await db.execute(
            select(BookCollaborator).where(
                BookCollaborator.book_id == book.id,
                BookCollaborator.email == normalized_email,
            )
        )
    ).scalar_one_or_none()
    if collaborator is None:
        collaborator = BookCollaborator(book_id=book.id, email=normalized_email)
        db.add(collaborator)
    collaborator.display_name = str(display_name or "").strip() or None
    collaborator.role = normalized_role
    apply_collaboration_scope(collaborator, normalized_scope)
    apply_collaboration_permissions(
        collaborator,
        normalized_permissions,
        role=normalized_role,
        scope=normalized_scope,
    )
    collaborator.invite_status = "active"
    collaborator.invited_user_id = invited_user.id if invited_user else None
    await db.commit()
    await db.refresh(collaborator)
    return serialize_book_collaborator(collaborator)


async def update_book_collaborator(
    db: AsyncSession,
    book: Book,
    collaboration_id: uuid.UUID,
    *,
    role: str | None = None,
    scope: CollaborationScope | None = None,
    permissions: CollaborationPermissions | None = None,
    display_name: str | None = None,
    invite_status: str | None = None,
) -> BookCollaboratorOut:
    collaborator = await db.get(BookCollaborator, collaboration_id)
    if not collaborator or collaborator.book_id != book.id:
        raise HTTPException(404, "Collaborator not found")
    next_role = collaborator.role
    if role is not None:
        next_role = normalize_collaboration_role(role)
        collaborator.role = next_role
    next_scope = collaborator.scope
    if scope is not None:
        next_scope = normalize_collaboration_scope(scope)
        apply_collaboration_scope(collaborator, next_scope)
    if permissions is not None or role is not None or scope is not None:
        apply_collaboration_permissions(
            collaborator,
            permissions if permissions is not None else collaborator.permissions,
            role=next_role,
            scope=next_scope,
        )
    if display_name is not None:
        collaborator.display_name = str(display_name or "").strip() or None
    if invite_status is not None:
        if invite_status not in {"active", "revoked"}:
            raise HTTPException(400, "Invalid invite status")
        collaborator.invite_status = invite_status
    await db.commit()
    await db.refresh(collaborator)
    return serialize_book_collaborator(collaborator)


async def delete_book_collaborator(
    db: AsyncSession, book: Book, collaboration_id: uuid.UUID
) -> None:
    collaborator = await db.get(BookCollaborator, collaboration_id)
    if not collaborator or collaborator.book_id != book.id:
        raise HTTPException(404, "Collaborator not found")
    await db.delete(collaborator)
    await db.commit()
