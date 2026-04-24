from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.intelligence import Notification
from app.schemas.notifications import NotificationListOut, NotificationOut

router = APIRouter()


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    limit: int = Query(40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    unread_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
            )
        ).scalar_one()
    )
    return NotificationListOut(
        items=[
            NotificationOut(
                id=str(item.id),
                book_id=str(item.book_id) if item.book_id else None,
                kind=item.kind,
                title=item.title,
                body=item.body,
                data=item.data,
                read_at=item.read_at,
                created_at=item.created_at,
            )
            for item in rows
        ],
        unread_count=unread_count,
    )


@router.put("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    notification = await db.get(Notification, notification_id)
    if not notification or notification.user_id != current_user.id:
        raise HTTPException(404, "Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(notification)
    return NotificationOut(
        id=str(notification.id),
        book_id=str(notification.book_id) if notification.book_id else None,
        kind=notification.kind,
        title=notification.title,
        body=notification.body,
        data=notification.data,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


@router.put("/read-all", response_model=NotificationListOut)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(Notification).where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        )
    ).scalars().all()
    now = datetime.now(UTC)
    for notification in rows:
        notification.read_at = now
    await db.commit()
    return await list_notifications(db=db, current_user=current_user)
