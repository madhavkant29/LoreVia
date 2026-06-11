from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

import pytest

from app.utils.privacy_utils import (
    ACCOUNT_DELETE_CONFIRMATION,
    BOOK_DELETE_CONFIRMATION,
    data_deletion_scheduled_for,
    deleted_account_email,
    hash_deleted_email,
    user_is_deleted,
    validate_account_deletion_confirmation,
    validate_book_deletion_confirmation,
)


def test_account_deletion_confirmation_requires_exact_text():
    validate_account_deletion_confirmation(ACCOUNT_DELETE_CONFIRMATION)

    with pytest.raises(ValueError):
        validate_account_deletion_confirmation("delete my account")


def test_book_deletion_confirmation_requires_exact_text():
    validate_book_deletion_confirmation(BOOK_DELETE_CONFIRMATION)

    with pytest.raises(ValueError):
        validate_book_deletion_confirmation("DELETE")


def test_user_is_deleted_checks_status_and_deleted_at():
    assert user_is_deleted(SimpleNamespace(deletion_status="active", deleted_at=None)) is False
    assert user_is_deleted(SimpleNamespace(deletion_status="pending_hard_delete", deleted_at=None)) is True
    assert user_is_deleted(SimpleNamespace(deletion_status="active", deleted_at=datetime.now(UTC))) is True


def test_data_deletion_scheduled_for_defaults_to_30_days():
    now = datetime(2026, 5, 15, tzinfo=UTC)

    assert data_deletion_scheduled_for(now).isoformat() == "2026-06-14T00:00:00+00:00"


def test_deleted_account_email_and_hash_are_stable():
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000123")

    assert deleted_account_email(user_id) == "deleted+00000000000000000000000000000123@deleted.getlorevia.local"
    assert hash_deleted_email(" Author@Example.com ") == hash_deleted_email("author@example.com")
