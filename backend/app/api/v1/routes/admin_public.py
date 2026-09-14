from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import (
    require_admin_csrf,
    require_admin_step_up,
    require_moderation_admin,
)
from app.api.v1.routes.admin_common import admin_scopes_from_request
from app.core.database import get_db
from app.core.redis import (
    cache_del,
    key_public_book_detail,
    key_public_books,
    mark_public_catalog_cache_dirty,
)
from app.models.book import Book
from app.models.user import User
from app.schemas.admin import PendingPublicShareOut, PublicShareApprovalBody
from app.schemas.public import (
    PublicBookCreateOut,
    PublicBookManualIn,
    PublicChapterAppendOut,
    PublicChapterIn,
)
from app.services.admin_service import (
    record_admin_audit_event,
    record_admin_read,
    serialize_pending_public_shares,
)
from app.services.public_asset_service import publish_public_book_assets, revoke_public_book_assets
from app.utils.public.content import append_public_demo_book_chapter, create_public_demo_book
from app.utils.public.serialization import get_public_share_status
from app.utils.public_utils import (
    MODERATION_STATUS_CLEAN,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    PUBLIC_STATUS_HIDDEN,
    PUBLIC_STATUS_PUBLISHED,
    USER_PUBLIC_SHARE_SOURCE_KIND,
)

router = APIRouter()


@router.get("/public-shares/pending", response_model=list[PendingPublicShareOut])
async def list_pending_public_shares(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_moderation_admin),
):
    payload = await serialize_pending_public_shares(db, limit=limit, offset=offset)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="public_share_queue_viewed",
        reason="Viewed pending public-share queue.",
        metadata={"limit": limit, "offset": offset},
    )
    return payload


@router.post("/public-books/manual", response_model=PublicBookCreateOut)
async def create_admin_public_demo_book(
    request: Request,
    body: PublicBookManualIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    book, payload = await create_public_demo_book(db, admin_user=admin_user, body=body)
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        target_book_id=book.id,
        action_type="public_demo_book_created",
        result="allowed",
        reason="Created public demo book.",
        request=request,
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"chapter_count": len(body.chapters), "public_slug": book.public_slug},
    )
    await db.commit()
    return payload


@router.post("/public-books/{book_id}/chapters", response_model=PublicChapterAppendOut)
async def append_admin_public_demo_book_chapter(
    request: Request,
    book_id: uuid.UUID,
    body: PublicChapterIn,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    book, payload = await append_public_demo_book_chapter(db, book_id=book_id, body=body)
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        target_book_id=book.id,
        action_type="public_demo_book_chapter_appended",
        result="allowed",
        reason="Appended chapter to public demo book.",
        request=request,
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"chapter_number": payload.chapter_number},
    )
    await db.commit()
    return payload


@router.put("/public-shares/{book_id}")
async def review_public_share(
    request: Request,
    book_id: uuid.UUID,
    body: PublicShareApprovalBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_moderation_admin),
):
    if not body.approved and not (body.reason or "").strip():
        raise HTTPException(400, "A reason is required when rejecting public sharing.")
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    if book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(409, "This manuscript is not available for public sharing.")

    current_status = get_public_share_status(book)
    if (
        str(book.source_kind or "").strip().lower() != USER_PUBLIC_SHARE_SOURCE_KIND
        and current_status == PUBLIC_SHARE_STATUS_NOT_REQUESTED
    ):
        raise HTTPException(409, "This manuscript is not in the author public-share workflow.")
    if body.approved:
        if current_status == PUBLIC_SHARE_STATUS_NOT_REQUESTED:
            raise HTTPException(
                409, "This manuscript does not have a pending public-share request."
            )
        book.public_share_status = PUBLIC_SHARE_STATUS_APPROVED
        book.public_share_approved_at = datetime.now(UTC)
        book.public_share_approved_by_user_id = admin_user.id
        book.is_public = True
        book.public_status = PUBLIC_STATUS_PUBLISHED
        book.public_visibility = "public"
        book.moderation_status = MODERATION_STATUS_CLEAN
        visibility = "public"
    else:
        book.is_public = False
        book.public_status = PUBLIC_STATUS_HIDDEN
        book.public_visibility = "private"
        if current_status == PUBLIC_SHARE_STATUS_PENDING:
            book.public_share_status = PUBLIC_SHARE_STATUS_NOT_REQUESTED
            book.public_share_requested_at = None
        else:
            book.public_share_status = PUBLIC_SHARE_STATUS_NOT_REQUESTED
        book.public_share_approved_at = None
        book.public_share_approved_by_user_id = None
        book.source_kind = USER_PUBLIC_SHARE_SOURCE_KIND
        visibility = "private"

    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=book.user_id,
        target_book_id=book.id,
        action_type="public_share_reviewed",
        result="allowed",
        reason=(body.reason or "Public share approved.").strip(),
        request=request,
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"approved": body.approved},
    )
    if body.approved:
        await db.commit()
        await publish_public_book_assets(db, book=book)
    else:
        await revoke_public_book_assets(book.id, db=db, strict=True)
        await db.commit()
    await cache_del(key_public_books())
    await mark_public_catalog_cache_dirty()
    await cache_del(key_public_book_detail(str(book.id)))
    return {
        "book_id": str(book.id),
        "approval_status": get_public_share_status(book),
        "visibility": visibility,
        "approved": bool(body.approved),
    }
