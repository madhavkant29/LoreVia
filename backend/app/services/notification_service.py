"""Bounded notification reads and user-scoped read-state mutations."""

import base64
import binascii
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    REDIS_OPERATION_EXCEPTIONS,
    cache_delete_if_owner,
    cache_set_if_absent,
    key_revision_digest_refresh,
)
from app.models.book import Book
from app.models.intelligence import Notification
from app.schemas.notifications import NotificationListOut, NotificationOut
from app.utils.notification_utils import build_revision_digest_notification, notification_out
from app.utils.task_queue_errors import TASK_ENQUEUE_ERRORS

DEFAULT_NOTIFICATION_LIMIT = 40
REVISION_DIGEST_REFRESH_TTL_SECONDS = 5 * 60
log = logging.getLogger("lorevia.notifications")


def encode_notification_cursor(created_at: datetime, notification_id: uuid.UUID) -> str:
    """Encode the complete notification ordering tuple into an opaque cursor."""
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(notification_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_notification_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode a cursor, rejecting malformed or timezone-less timestamps."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        if created_at.tzinfo is None:
            raise ValueError("Cursor timestamp must include a timezone")
        return created_at, uuid.UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise HTTPException(400, "Invalid notification cursor") from exc


async def load_notification_page(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = DEFAULT_NOTIFICATION_LIMIT,
    cursor: str | None = None,
    sync_revision_digests: bool = False,
) -> NotificationListOut:
    """Read a stable notification page without performing derived-data work."""
    limit = max(1, min(limit, 100))
    if sync_revision_digests:
        # Kept for one client release only. Reads must never rebuild revision
        # intelligence; post-commit workers own that work now.
        log.info(
            "deprecated_notification_digest_sync_requested",
            extra={
                "metric": "notifications.deprecated_sync_revision_digests",
                "user_id": str(user_id),
            },
        )
    statement = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit + 1)
        .execution_options(populate_existing=True)
    )
    if cursor:
        cursor_created_at, cursor_id = decode_notification_cursor(cursor)
        statement = statement.where(
            (Notification.created_at < cursor_created_at)
            | ((Notification.created_at == cursor_created_at) & (Notification.id < cursor_id))
        )
    rows = (await db.execute(statement)).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]
    unread_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            )
        ).scalar_one()
    )
    return NotificationListOut(
        items=[notification_out(item) for item in items],
        unread_count=unread_count,
        next_cursor=(
            encode_notification_cursor(items[-1].created_at, items[-1].id)
            if has_more and items
            else None
        ),
        has_more=has_more,
    )


async def mark_user_notifications_read(db: AsyncSession, user_id: uuid.UUID) -> NotificationListOut:
    """Mark the user's unread rows with one UPDATE, without rebuilding digests."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    # Count again: a notification arriving after the UPDATE must remain unread.
    return await load_notification_page(db, user_id)


async def mark_user_notification_read(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> NotificationOut:
    """Mark one owned notification, preserving its first read timestamp."""
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise HTTPException(404, "Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(notification)
    return notification_out(notification)


async def refresh_revision_digest_for_book(db: AsyncSession, book_id: uuid.UUID) -> bool:
    """Rebuild one stored digest after committed manuscript/intelligence changes."""
    book = (
        await db.execute(
            select(Book).where(
                Book.id == book_id,
                Book.mode == "author",
                Book.status == "ready",
            )
        )
    ).scalar_one_or_none()
    if book is None:
        return False

    existing = list(
        (
            await db.execute(
                select(Notification)
                .where(
                    Notification.book_id == book.id,
                    Notification.user_id == book.user_id,
                    Notification.kind == "revision_digest",
                )
                .order_by(Notification.created_at.desc(), Notification.id.desc())
            )
        )
        .scalars()
        .all()
    )
    latest = existing[0] if existing else None
    for duplicate in existing[1:]:
        await db.delete(duplicate)

    from app.utils.books.revision_service import build_revision_intelligence_payload

    payload = await build_revision_intelligence_payload(db, book)
    next_notification = build_revision_digest_notification(book, payload)
    changed = len(existing) > 1
    if next_notification is None:
        if latest is not None and latest.read_at is None:
            latest.read_at = datetime.now(UTC)
            changed = True
    elif latest is None:
        db.add(next_notification)
        changed = True
    else:
        next_signature = str((next_notification.data or {}).get("signature") or "")
        current_signature = (
            str((latest.data or {}).get("signature") or "") if isinstance(latest.data, dict) else ""
        )
        if next_signature != current_signature:
            latest.title = next_notification.title
            latest.body = next_notification.body
            latest.data = next_notification.data
            latest.read_at = None
            changed = True

    if changed:
        await db.commit()
    return changed


async def enqueue_revision_digest_refresh(*, user_id: uuid.UUID, book_id: uuid.UUID) -> bool:
    """Coalesce and enqueue a retryable digest rebuild outside request paths."""
    lock_key = key_revision_digest_refresh(str(book_id))
    owner_token = uuid.uuid4().hex
    try:
        claimed = await cache_set_if_absent(
            lock_key,
            owner_token,
            ttl=REVISION_DIGEST_REFRESH_TTL_SECONDS,
        )
    except REDIS_OPERATION_EXCEPTIONS:
        log.warning("revision_digest_refresh_coalesce_failed book_id=%s", book_id, exc_info=True)
        claimed = True
    if not claimed:
        return False
    try:
        from app.workers.tasks.maintenance_tasks import refresh_revision_digest_notification_task

        refresh_revision_digest_notification_task.apply_async(
            kwargs={
                "user_id": str(user_id),
                "book_id": str(book_id),
                "owner_token": owner_token,
            },
            queue="maintenance",
        )
    except TASK_ENQUEUE_ERRORS:
        await cache_delete_if_owner(lock_key, owner_token)
        log.exception("revision_digest_refresh_enqueue_failed book_id=%s", book_id)
        return False
    return True
