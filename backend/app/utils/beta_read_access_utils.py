from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.beta_read import BetaReadAssignment, BetaReadAssignmentState, BetaReadScopeKind
from app.models.book import Book, BookCollaborator
from app.models.user import User
from app.utils.books.collaboration import (
    apply_collaboration_permissions,
    apply_collaboration_scope,
    normalize_collaboration_email,
    normalize_collaboration_permissions,
    normalize_collaboration_scope,
)


def _reader_match_clause(current_user: User):
    email = normalize_collaboration_email(current_user.email)
    return or_(
        BetaReadAssignment.reader_user_id == current_user.id,
        BetaReadAssignment.reader_email == email,
    )


async def sync_reader_identity_for_beta_reads(db: AsyncSession, current_user: User) -> None:
    email = normalize_collaboration_email(current_user.email)
    assignments = (
        (
            await db.execute(
                select(BetaReadAssignment).where(
                    BetaReadAssignment.reader_user_id.is_(None),
                    BetaReadAssignment.reader_email == email,
                )
            )
        )
        .scalars()
        .all()
    )
    changed = False
    for assignment in assignments:
        assignment.reader_user_id = current_user.id
        changed = True
    if changed:
        await db.flush()


async def get_beta_assignment_for_author(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
    author_user_id: uuid.UUID,
) -> BetaReadAssignment:
    assignment = (
        await db.execute(
            select(BetaReadAssignment).where(
                BetaReadAssignment.id == assignment_id,
                BetaReadAssignment.author_user_id == author_user_id,
            )
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(404, "Beta read assignment not found.")
    return assignment


async def get_beta_assignment_for_reader(
    db: AsyncSession,
    *,
    assignment_id: uuid.UUID,
    current_user: User,
) -> BetaReadAssignment:
    await sync_reader_identity_for_beta_reads(db, current_user)
    assignment = (
        await db.execute(
            select(BetaReadAssignment).where(
                BetaReadAssignment.id == assignment_id,
                _reader_match_clause(current_user),
            )
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(404, "Beta read assignment not found.")
    return assignment


async def _upsert_beta_read_collaborator(
    db: AsyncSession,
    *,
    book: Book,
    reader_email: str,
    reader_user: User | None,
    scope_kind: str,
    chapter_start: int | None,
    chapter_end: int | None,
) -> BookCollaborator:
    normalized_email = normalize_collaboration_email(reader_email)
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

    scope = normalize_collaboration_scope(
        {
            "chapter_start": chapter_start
            if scope_kind != BetaReadScopeKind.FULL_BOOK.value
            else None,
            "chapter_end": chapter_end if scope_kind != BetaReadScopeKind.FULL_BOOK.value else None,
            "character_bible": False,
            "continuity_report": False,
            "reader_confusion_report": False,
        }
    )
    permissions = normalize_collaboration_permissions(
        {
            "can_edit_manuscript": False,
            "can_view_story_bible": False,
            "can_run_ai_scans": False,
            "can_export": False,
            "can_comment": True,
            "can_view_selected_chapters_only": scope_kind != BetaReadScopeKind.FULL_BOOK.value,
        },
        role="beta_reader",
        scope=scope,
    )
    collaborator.display_name = collaborator.display_name or "Beta Reader"
    collaborator.invited_user_id = reader_user.id if reader_user else collaborator.invited_user_id
    collaborator.role = "beta_reader"
    apply_collaboration_scope(collaborator, scope)
    apply_collaboration_permissions(
        collaborator,
        permissions,
        role="beta_reader",
        scope=scope,
    )
    collaborator.invite_status = "active"
    await db.flush()
    return collaborator


def sync_beta_read_access(
    assignment: BetaReadAssignment, collaborator: BookCollaborator | None
) -> None:
    if collaborator is None:
        return
    if assignment.state in {
        BetaReadAssignmentState.REVOKED.value,
        BetaReadAssignmentState.DISQUALIFIED.value,
    }:
        collaborator.invite_status = "revoked"
        return
    if (
        assignment.state == BetaReadAssignmentState.MISSED.value
        and assignment.missed_reason != "deadline_expired"
    ):
        collaborator.invite_status = "revoked"
        return
    if (
        assignment.state == BetaReadAssignmentState.MISSED.value
        and assignment.missed_reason == "deadline_expired"
        and not settings.BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY
    ):
        collaborator.invite_status = "revoked"
        return
    if (
        assignment.state == BetaReadAssignmentState.EXPIRED.value
        and not settings.BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY
    ):
        collaborator.invite_status = "revoked"
