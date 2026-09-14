from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.schemas.notifications import NotificationListOut, NotificationOut
from app.services.notification_service import (
    DEFAULT_NOTIFICATION_LIMIT,
    load_notification_page,
    mark_user_notification_read,
    mark_user_notifications_read,
)

router = APIRouter()


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    limit: Annotated[int, Query(ge=1, le=100)] = DEFAULT_NOTIFICATION_LIMIT,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    sync_revision_digests: bool = False,
    response: Response = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if sync_revision_digests and response is not None:
        response.headers["Deprecation"] = "true"
        response.headers["Warning"] = '299 - "sync_revision_digests is deprecated and has no effect"'
    return await load_notification_page(
        db,
        current_user.id,
        limit=limit,
        cursor=cursor,
        sync_revision_digests=sync_revision_digests,
    )


@router.put("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await mark_user_notification_read(db, current_user.id, notification_id)


@router.put("/read-all", response_model=NotificationListOut)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await mark_user_notifications_read(db, current_user.id)
