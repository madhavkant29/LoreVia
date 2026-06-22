"""
Book utility helpers ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.beta_read import BetaReadAssignment, BetaReadAssignmentState
from app.models.book import (
    Book,
    BookCollaborator,
)
from app.models.user import User
from app.utils.books.collaboration import (
    BookAccessContext,
    _collaboration_permissions_for_role,
    build_book_access_context,
    collaboration_permissions_payload,
    collaboration_scope_payload,
    normalize_collaboration_email,
)

if TYPE_CHECKING:
    pass


def collaboration_allows_chapter(
    collaborator: BookCollaborator | None, chapter_number: int
) -> bool:
    if collaborator is None:
        return True
    scope = collaboration_scope_payload(collaborator)
    permissions = collaboration_permissions_payload(
        collaborator, role=collaborator.role, scope=scope
    )
    if not permissions["can_view_selected_chapters_only"]:
        return True
    chapter_start = scope.get("chapter_start")
    chapter_end = scope.get("chapter_end")
    if chapter_start is not None and chapter_number < chapter_start:
        return False
    if chapter_end is not None and chapter_number > chapter_end:
        return False
    return True


def collaboration_can_comment(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_comment"]


def collaboration_can_edit(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_edit_manuscript"]


def collaboration_can_export(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_export"]


def collaboration_can_copy_manuscript(book: Book, collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    if bool(book.is_public):
        return True
    return collaboration_can_edit(collaborator)


def collaboration_can_view_story_bible(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_view_story_bible"]


def collaboration_can_run_ai_scans(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_run_ai_scans"]


def collaboration_has_resource(collaborator: BookCollaborator | None, resource: str) -> bool:
    if collaborator is None:
        return True
    scope = collaboration_scope_payload(collaborator)
    if not bool(scope.get(resource)):
        return False
    if resource == "character_bible":
        return collaboration_can_view_story_bible(collaborator)
    if resource in {"continuity_report", "reader_confusion_report"}:
        return collaboration_can_run_ai_scans(collaborator)
    return True


async def find_active_book_collaboration(
    db: AsyncSession,
    book_id: uuid.UUID,
    user: User,
) -> BookCollaborator | None:
    email = normalize_collaboration_email(user.email)
    collaborator = (
        await db.execute(
            select(BookCollaborator).where(
                BookCollaborator.book_id == book_id,
                BookCollaborator.email == email,
                BookCollaborator.invite_status == "active",
            )
        )
    ).scalar_one_or_none()
    if collaborator is None or collaborator.role != "beta_reader":
        return collaborator

    latest_assignment = (
        await db.execute(
            select(BetaReadAssignment)
            .where(
                BetaReadAssignment.book_id == book_id,
                BetaReadAssignment.reader_email == email,
            )
            .order_by(BetaReadAssignment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_assignment is None:
        return collaborator

    current = datetime.now(UTC)
    if latest_assignment.state in {
        BetaReadAssignmentState.REVOKED.value,
        BetaReadAssignmentState.DISQUALIFIED.value,
    }:
        return None
    if latest_assignment.state == BetaReadAssignmentState.MISSED.value:
        if (
            latest_assignment.missed_reason == "deadline_expired"
            and settings.BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY
        ):
            return collaborator
        return None
    if (
        latest_assignment.state
        in {
            BetaReadAssignmentState.ACTIVE.value,
            BetaReadAssignmentState.IN_PROGRESS.value,
            BetaReadAssignmentState.READY_TO_SUBMIT.value,
            BetaReadAssignmentState.EXPIRED.value,
        }
        and latest_assignment.expires_at
        and latest_assignment.expires_at <= current
        and not settings.BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY
    ):
        return None
    return collaborator


async def get_book_with_collaboration_access(
    db: AsyncSession,
    book_id: uuid.UUID,
    user: User,
    *,
    options: tuple | None = None,
) -> tuple[Book, BookCollaborator | None]:
    if options:
        result = await db.execute(select(Book).where(Book.id == book_id).options(*options))
        book = result.scalars().first()
    else:
        book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    if book.user_id == user.id:
        return book, None
    collaborator = await find_active_book_collaboration(db, book_id, user)
    if collaborator:
        return book, collaborator
    raise HTTPException(404, "Book not found")


def require_book_owner_access(
    book: Book,
    user: User,
    collaborator: BookCollaborator | None = None,
) -> BookAccessContext:
    if collaborator is not None or book.user_id != user.id:
        raise HTTPException(403, "Only the book owner can use this route.")
    return build_book_access_context(book, user_id=user.id, collaborator=None)


def assert_editor_project_not_rebuilding(book: Book) -> None:
    if getattr(book, "is_editor_project", False):
        from app.services.editor_project_service import get_rebuild_run_id

        if get_rebuild_run_id(book) is not None:
            raise HTTPException(
                409, "Cannot edit the manuscript while reprocessing is in progress."
            )


def require_author_shell_access(
    book: Book,
    user: User,
    collaborator: BookCollaborator | None = None,
) -> BookAccessContext:
    access = build_book_access_context(book, user_id=user.id, collaborator=collaborator)
    if access.workspace_shell != "author":
        raise HTTPException(403, "This share is limited to the reader workspace.")
    return access


def require_reader_shell_access(
    book: Book,
    user: User,
    collaborator: BookCollaborator | None = None,
) -> BookAccessContext:
    access = build_book_access_context(book, user_id=user.id, collaborator=collaborator)
    if access.workspace_shell != "reader":
        raise HTTPException(403, "This route is only available in the reader workspace.")
    return access


def require_collaboration_chapter_access(
    collaborator: BookCollaborator | None,
    chapter_number: int,
) -> None:
    if not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share does not include that chapter.")
