from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from app.models.user import User


ACCOUNT_DELETE_CONFIRMATION = "DELETE MY ACCOUNT"
BOOK_DELETE_CONFIRMATION = "DELETE BOOK"
USER_DELETION_STATUS_ACTIVE = "active"
USER_DELETION_STATUS_PENDING = "pending_hard_delete"
USER_DELETION_STATUS_PROVIDER_FOLLOWUP = "provider_followup_required"
USER_DELETION_STATUS_DELETED = "deleted"
DATA_DELETION_STATUS_PENDING = "pending"
DATA_DELETION_STATUS_PROCESSING = "processing"
DATA_DELETION_STATUS_COMPLETED = "completed"
DATA_DELETION_STATUS_FAILED = "failed"


def validate_account_deletion_confirmation(value: str) -> None:
    if (value or "").strip() != ACCOUNT_DELETE_CONFIRMATION:
        raise ValueError(f"Type {ACCOUNT_DELETE_CONFIRMATION} to confirm account deletion.")


def validate_book_deletion_confirmation(value: str) -> None:
    if (value or "").strip() != BOOK_DELETE_CONFIRMATION:
        raise ValueError(f"Type {BOOK_DELETE_CONFIRMATION} to confirm manuscript deletion.")


def user_is_deleted(user: User | None) -> bool:
    if user is None:
        return False
    status = (getattr(user, "deletion_status", None) or USER_DELETION_STATUS_ACTIVE).lower()
    return status != USER_DELETION_STATUS_ACTIVE or bool(getattr(user, "deleted_at", None))


def data_deletion_scheduled_for(now: datetime | None = None, *, days: int = 30) -> datetime:
    base = now or datetime.now(UTC)
    return base + timedelta(days=days)


def hash_deleted_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def deleted_account_email(user_id: uuid.UUID) -> str:
    return f"deleted+{user_id.hex}@deleted.getlorevia.local"
