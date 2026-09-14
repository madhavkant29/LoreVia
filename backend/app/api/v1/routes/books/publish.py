import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_public_publish, rate_limit_public_unpublish
from app.core.database import get_db
from app.models.book import Book
from app.schemas.public import PublicBookCreateOut, PublicBookShareBody
from app.services.public_asset_service import revoke_public_book_assets
from app.services.public_publish_service import submit_public_share
from app.utils.billing_utils import require_author_access
from app.utils.client_identity import trusted_client_ip
from app.utils.public.moderation import (
    add_moderation_action,
)
from app.utils.public_utils import (
    PUBLIC_STATUS_HIDDEN,
    USER_PUBLIC_SHARE_SOURCE_KIND,
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
    if (
        not book
        or book.user_id != current_user.id
        or book.hidden_at is not None
        or book.archived_at is not None
    ):
        raise HTTPException(404, "Book not found")
    require_author_access(current_user)
    return await submit_public_share(
        db,
        book=book,
        user=current_user,
        body=body,
        request_ip=trusted_client_ip(request),
        user_agent=request.headers.get("user-agent"),
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
    require_author_access(current_user)
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
    await revoke_public_book_assets(book.id, db=db, strict=True)
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
