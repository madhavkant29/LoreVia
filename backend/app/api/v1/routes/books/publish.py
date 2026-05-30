import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .core import _clean_optional_text
from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_public_publish, rate_limit_public_unpublish
from app.core.database import get_db
from app.models.book import Book
from app.schemas.public import PublicBookCreateOut, PublicBookShareBody
from app.utils.book_utils import touch_public_book_updated_at
from app.utils.public_utils import (
    CONTENT_SOURCE_TYPE_ADMIN_SEEDED,
    CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN,
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REMOVED,
    MODERATION_STATUS_UNDER_REVIEW,
    PUBLIC_DEMO_SOURCE_KIND,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_STATUS_HIDDEN,
    PUBLIC_STATUS_PUBLISHED,
    USER_PUBLIC_SHARE_SOURCE_KIND,
    add_moderation_action,
    enforce_daily_public_publish_limit,
    ensure_content_source_allowed_for_user,
    hash_text,
    normalize_public_slug,
)

router = APIRouter()


@router.post(
    "/{book_id}/publish",
    response_model=PublicBookCreateOut,
    dependencies=[Depends(rate_limit_public_publish)],
)
async def publish_book_publicly(
    book_id: uuid.UUID,
    body: PublicBookShareBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id or book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(404, "Book not found")
    if getattr(current_user, "email_verified_at", None) is None:
        raise HTTPException(403, "Verify your email before publishing a public book.")

    moderation_status = str(getattr(book, "moderation_status", "") or "").strip().lower()
    if moderation_status in {MODERATION_STATUS_HIDDEN, MODERATION_STATUS_REMOVED, MODERATION_STATUS_UNDER_REVIEW}:
        raise HTTPException(409, "This book is not eligible for public publishing right now.")
    if getattr(book, "takedown_at", None) is not None:
        raise HTTPException(409, "This book is under takedown and cannot be republished.")
    if not (body.rights_confirmation or body.confirm_public_share):
        raise HTTPException(400, "Public publishing requires explicit rights confirmation.")
    if not body.public_slug:
        raise HTTPException(400, "Public publishing requires a public URL slug.")

    content_source_type = ensure_content_source_allowed_for_user(current_user, body.content_source_type)
    await enforce_daily_public_publish_limit(db, user=current_user)

    normalized_slug = normalize_public_slug(body.public_slug)
    existing_slug = (
        await db.execute(
            select(Book.id).where(
                Book.public_slug == normalized_slug,
                Book.id != book.id,
            )
        )
    ).scalar_one_or_none()
    if existing_slug is not None:
        raise HTTPException(409, "That public URL is already in use.")

    previous_status = str(getattr(book, "public_status", "") or "") or None
    now = datetime.now(UTC)
    source_kind = (
        PUBLIC_DEMO_SOURCE_KIND
        if content_source_type in {CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN, CONTENT_SOURCE_TYPE_ADMIN_SEEDED}
        else USER_PUBLIC_SHARE_SOURCE_KIND
    )

    book.public_slug = normalized_slug
    book.public_description = _clean_optional_text(body.description)
    book.rights_confirmation = True
    book.rights_confirmation_at = now
    book.rights_confirmation_ip_hash = hash_text(request.client.host if request.client else None)
    book.rights_confirmation_user_agent = request.headers.get("user-agent")
    book.content_source_type = content_source_type
    book.source_kind = source_kind
    book.public_visibility = "public"
    book.public_status = PUBLIC_STATUS_PUBLISHED
    book.moderation_status = "clean"
    book.moderation_reason = None
    book.takedown_reason = None
    book.takedown_at = None
    book.takedown_by_user_id = None
    book.published_at = book.published_at or now
    touch_public_book_updated_at(book, changed_at=now)
    book.public_upload_counted_at = now
    book.is_public = True
    book.public_share_status = PUBLIC_SHARE_STATUS_APPROVED
    book.public_share_requested_at = now
    book.public_share_approved_at = now
    book.public_share_approved_by_user_id = None
    await add_moderation_action(
        db,
        action_type="book_published",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        book_id=book.id,
        previous_status=previous_status,
        new_status=book.public_status,
        reason="Creator published book publicly with rights confirmation.",
        metadata={
            "public_slug": normalized_slug,
            "content_source_type": content_source_type,
        },
    )
    await db.commit()
    return PublicBookCreateOut(
        book_id=str(book.id),
        status=book.status,
        visibility="public",
        public_kind=source_kind,
        approval_status=book.public_status,
        public_slug=book.public_slug,
        message="Public book is now live.",
    )


@router.post(
    "/{book_id}/unpublish",
    response_model=PublicBookCreateOut,
    dependencies=[Depends(rate_limit_public_unpublish)],
)
async def unpublish_book_publicly(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    previous_status = str(getattr(book, "public_status", "") or "") or None
    book.is_public = False
    book.public_status = PUBLIC_STATUS_HIDDEN
    book.public_visibility = "private"
    await add_moderation_action(
        db,
        action_type="book_unpublished",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        book_id=book.id,
        previous_status=previous_status,
        new_status=book.public_status,
        reason="Creator unpublished book from public view.",
    )
    await db.commit()
    return PublicBookCreateOut(
        book_id=str(book.id),
        status=book.status,
        visibility="private",
        public_kind=book.source_kind or USER_PUBLIC_SHARE_SOURCE_KIND,
        approval_status=book.public_status,
        public_slug=book.public_slug,
        message="Book removed from public view.",
    )
