from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.beta_read import BetaReadAssignment
from app.models.book import Book, BookCollaborator, BookForumPost
from app.schemas.books import (
    BookVisibilitySummaryOut,
    VisibilitySummaryItemOut,
)
from app.utils.books.collaboration import build_book_access_context


def _summary_item(
    *, state: str, label: str, count: int | None = None, detail: str | None = None
) -> VisibilitySummaryItemOut:
    return VisibilitySummaryItemOut(state=state, label=label, count=count, detail=detail)


def _public_url(book: Book) -> str | None:
    slug = str(getattr(book, "public_slug", "") or "").strip()
    if not slug:
        return None
    return f"{settings.APP_URL.rstrip('/')}/public/books/{slug}"


def _public_badge(book: Book) -> str | None:
    if bool(getattr(book, "is_public", False)) and getattr(book, "public_status", "") == "published":
        return "Public sample"
    if getattr(book, "public_share_status", "") == "pending":
        return "Public review"
    return None


async def build_book_visibility_summary(
    db: AsyncSession,
    book: Book,
    collaborator: BookCollaborator | None,
    user_id,
) -> BookVisibilitySummaryOut:
    access = build_book_access_context(book, user_id=user_id, collaborator=collaborator)
    collaborator_count = int(
        (
            await db.execute(
                select(func.count(BookCollaborator.id)).where(
                    BookCollaborator.book_id == book.id,
                    BookCollaborator.invite_status == "active",
                )
            )
        ).scalar()
        or 0
    )
    beta_assignment_count = int(
        (
            await db.execute(
                select(func.count(BetaReadAssignment.id)).where(
                    BetaReadAssignment.book_id == book.id,
                    BetaReadAssignment.state.notin_(["revoked", "disqualified"]),
                )
            )
        ).scalar()
        or 0
    )
    public_post_count = int(
        (
            await db.execute(
                select(func.count(BookForumPost.id)).where(
                    BookForumPost.book_id == book.id,
                    BookForumPost.status != "removed",
                )
            )
        ).scalar()
        or 0
    )

    public_badge = _public_badge(book)
    badges = ["Private"]
    if collaborator_count:
        badges.append("Shared")
    if beta_assignment_count:
        badges.append("Beta readers")
    if public_badge:
        badges.append(public_badge)
    if public_post_count:
        badges.append("Public discussion")

    public_state = str(getattr(book, "public_status", None) or "draft")
    moderation_state = str(getattr(book, "moderation_status", None) or "clean")
    rights_confirmed = bool(getattr(book, "rights_confirmation", False))
    public_visibility = str(getattr(book, "public_visibility", None) or "private")

    return BookVisibilitySummaryOut(
        book_id=book.id,
        access_class=access.access_class,
        workspace_shell=access.workspace_shell,
        badges=badges,
        private_status=_summary_item(
            state="private",
            label="Private workspace",
            detail="Only authorized workspace users can access this project.",
        ),
        collaborators=_summary_item(
            state="shared" if collaborator_count else "not_shared",
            label="Shared collaborators" if collaborator_count else "No active collaborators",
            count=collaborator_count,
        ),
        beta_readers=_summary_item(
            state="active" if beta_assignment_count else "none",
            label="Beta readers assigned" if beta_assignment_count else "No beta readers assigned",
            count=beta_assignment_count,
        ),
        public_publishing=_summary_item(
            state=public_visibility,
            label=f"Publishing is {public_state}",
            detail=f"Public visibility: {public_visibility}",
        ),
        public_discussion=_summary_item(
            state="active" if public_post_count else "none",
            label="Public discussion active" if public_post_count else "No public discussion",
            count=public_post_count,
        ),
        rights=_summary_item(
            state="confirmed" if rights_confirmed else "unconfirmed",
            label="Rights confirmed" if rights_confirmed else "Rights not confirmed",
        ),
        moderation=_summary_item(
            state=moderation_state,
            label=f"Moderation: {moderation_state.replace('_', ' ')}",
            detail=getattr(book, "moderation_reason", None),
        ),
        public_url=_public_url(book),
    )
