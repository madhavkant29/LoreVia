from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    book_id: str | None = None
    kind: str
    title: str
    body: str
    data: dict | None = None
    read_at: datetime | None = None
    created_at: datetime


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int
    next_cursor: str | None = None
    has_more: bool = False
