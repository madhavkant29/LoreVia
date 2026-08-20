from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

from fastapi import HTTPException
import pytest

from app.core.security import decode_token
from app.utils.beta_read_guest_utils import (
    build_beta_read_guest_link,
    record_beta_read_guest_chapter,
)


def test_guest_link_is_scoped_to_assignment_and_expires_with_it(monkeypatch):
    author_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=3)
    assignment = SimpleNamespace(
        id=assignment_id,
        author_user_id=author_id,
        reader_user_id=None,
        state="active",
        expires_at=expires_at,
    )
    monkeypatch.setattr("app.utils.beta_read_guest_utils.settings.APP_URL", "https://example.test")

    result = build_beta_read_guest_link(assignment)
    token = result["share_url"].rsplit("/", 1)[-1]
    payload = decode_token(token)

    assert result["expires_at"] == expires_at
    assert payload["sub"] == str(author_id)
    assert payload["res"] == f"beta-review:{assignment_id}"
    assert payload["type"] == "asset"


def test_guest_link_rejects_assignments_owned_by_registered_readers():
    assignment = SimpleNamespace(
        id=uuid.uuid4(),
        author_user_id=uuid.uuid4(),
        reader_user_id=uuid.uuid4(),
        state="active",
        expires_at=datetime.now(UTC) + timedelta(days=3),
    )

    with pytest.raises(HTTPException) as exc_info:
        build_beta_read_guest_link(assignment)

    assert exc_info.value.status_code == 409


def test_guest_progress_records_only_scoped_chapters():
    assignment = SimpleNamespace(
        scope_kind="chapter_range",
        chapter_start=2,
        chapter_end=4,
        metadata_json={"guest_read_chapters": [2]},
    )

    record_beta_read_guest_chapter(assignment, total_chapters=8, chapter_number=3)

    assert assignment.metadata_json["guest_read_chapters"] == [2, 3]

    try:
        record_beta_read_guest_chapter(assignment, total_chapters=8, chapter_number=7)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("out-of-scope guest progress should be rejected")
