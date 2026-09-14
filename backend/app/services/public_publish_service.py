from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book
from app.models.book import Book
from app.models.user import User
from app.schemas.public import PublicBookCreateOut, PublicBookShareBody
from app.services.public_asset_service import publish_public_book_assets, revoke_public_book_assets
from app.utils.books.writer_workspace import (
    touch_public_book_updated_at,
)
from app.utils.compliance.copyright_check import evaluate_document_copyright
from app.utils.public.content import (
    normalize_public_slug,
)
from app.utils.public.moderation import (
    add_moderation_action,
    enforce_daily_public_publish_limit,
    ensure_content_source_allowed_for_user,
    invalidate_public_book_caches,
)
from app.utils.public.requests import (
    hash_text,
)
from app.utils.public_utils import (
    CONTENT_SOURCE_TYPE_ADMIN_SEEDED,
    CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN,
    CONTENT_SOURCE_TYPE_USER_ORIGINAL,
    MODERATION_STATUS_CLEAN,
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REMOVED,
    MODERATION_STATUS_UNDER_REVIEW,
    PUBLIC_DEMO_SOURCE_KIND,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_SHARE_STATUS_PENDING,
    PUBLIC_STATUS_PENDING_REVIEW,
    PUBLIC_STATUS_PUBLISHED,
    USER_PUBLIC_SHARE_SOURCE_KIND,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS

log = logging.getLogger("lorevia.public_publish")


async def submit_public_share(
    db: AsyncSession,
    *,
    book: Book,
    user: User,
    body: PublicBookShareBody,
    request_ip: str | None,
    user_agent: str | None,
) -> PublicBookCreateOut:
    if (
        getattr(book, "hidden_at", None) is not None
        or getattr(book, "archived_at", None) is not None
    ):
        raise HTTPException(404, "Book not found")
    moderation_status = str(getattr(book, "moderation_status", "") or "").strip().lower()
    if moderation_status in {
        MODERATION_STATUS_HIDDEN,
        MODERATION_STATUS_REMOVED,
        MODERATION_STATUS_UNDER_REVIEW,
    }:
        raise HTTPException(409, "This book is not eligible for public publishing right now.")
    if getattr(book, "takedown_at", None) is not None:
        raise HTTPException(409, "This book is under takedown and cannot be republished.")
    if not (body.rights_confirmation or body.confirm_public_share):
        raise HTTPException(400, "Public publishing requires explicit rights confirmation.")

    content_source_type = ensure_content_source_allowed_for_user(user, body.content_source_type)
    await enforce_daily_public_publish_limit(db, user=user)
    public_slug = await _resolve_public_slug(db, book=book, requested_slug=body.public_slug)
    copyright_check_available = await _refresh_copyright_signals(book)
    now = datetime.now(UTC)
    source_kind = (
        PUBLIC_DEMO_SOURCE_KIND
        if content_source_type
        in {CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN, CONTENT_SOURCE_TYPE_ADMIN_SEEDED}
        else USER_PUBLIC_SHARE_SOURCE_KIND
    )
    can_publish_automatically = source_kind == PUBLIC_DEMO_SOURCE_KIND or (
        content_source_type == CONTENT_SOURCE_TYPE_USER_ORIGINAL
        and getattr(user, "email_verified_at", None) is not None
        and str(getattr(book, "status", "") or "").strip().lower() == "ready"
        and public_slug is not None
        and copyright_check_available
        and not bool(getattr(book, "copyright_warning", False))
    )

    book.public_slug = public_slug
    if body.description is not None:
        book.public_description = body.description.strip() or None
    book.rights_confirmation = True
    book.rights_confirmation_at = now
    book.rights_confirmation_ip_hash = hash_text(request_ip)
    book.rights_confirmation_user_agent = user_agent
    book.content_source_type = content_source_type
    book.source_kind = source_kind
    book.public_share_requested_at = now
    book.public_upload_counted_at = now
    book.public_share_approved_by_user_id = None

    if can_publish_automatically:
        book.is_public = True
        book.public_visibility = "public"
        book.public_status = PUBLIC_STATUS_PUBLISHED
        book.public_share_status = PUBLIC_SHARE_STATUS_APPROVED
        book.public_share_approved_at = now
        book.moderation_status = MODERATION_STATUS_CLEAN
        book.moderation_reason = None
        book.published_at = book.published_at or now
        touch_public_book_updated_at(book, changed_at=now)
        action_type = "book_published"
        message = "Public sample is now live."
        visibility = "public"
    else:
        book.is_public = False
        book.public_visibility = "private"
        book.public_status = PUBLIC_STATUS_PENDING_REVIEW
        book.public_share_status = PUBLIC_SHARE_STATUS_PENDING
        book.public_share_approved_at = None
        action_type = "public_share_review_requested"
        message = "Public sample is pending review."
        visibility = "private"

    await add_moderation_action(
        db,
        action_type=action_type,
        actor_user_id=user.id,
        target_user_id=user.id,
        book_id=book.id,
        new_status=book.public_status,
        reason=message,
        metadata={
            "content_source_type": content_source_type,
            "copyright_check_available": copyright_check_available,
        },
    )
    if can_publish_automatically:
        await db.commit()
        await publish_public_book_assets(db, book=book)
    else:
        await revoke_public_book_assets(book.id, db=db, strict=True)
        await db.commit()
    await invalidate_public_book_caches(book)
    return PublicBookCreateOut(
        book_id=str(book.id),
        status=book.status,
        visibility=visibility,
        public_kind=source_kind,
        approval_status=book.public_share_status,
        public_slug=book.public_slug,
        message=message,
    )


async def _resolve_public_slug(
    db: AsyncSession, *, book: Book, requested_slug: str | None
) -> str | None:
    raw_slug = requested_slug or getattr(book, "public_slug", None)
    if not raw_slug:
        return None
    normalized_slug = normalize_public_slug(raw_slug)
    existing_slug = (
        await db.execute(
            select(Book.id).where(Book.public_slug == normalized_slug, Book.id != book.id)
        )
    ).scalar_one_or_none()
    if existing_slug is not None:
        raise HTTPException(409, "That public URL is already in use.")
    return normalized_slug


async def _refresh_copyright_signals(book: Book) -> bool:
    if not getattr(book, "s3_key", None) or getattr(book, "format", None) == "manual":
        return True
    try:
        raw = await asyncio.to_thread(download_book, book.s3_key)
    except STORAGE_IO_EXCEPTIONS:
        log.exception("public_share_copyright_check_failed", extra={"book_id": str(book.id)})
        return False
    copyright_info = await evaluate_document_copyright(
        format_name=getattr(book, "format", None),
        raw=raw,
        existing_isbn=getattr(book, "isbn", None),
    )
    if copyright_info.get("isbn"):
        book.isbn = str(copyright_info["isbn"])
    book.copyright_warning = bool(copyright_info.get("copyright_warning", False))
    return True
