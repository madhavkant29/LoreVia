from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.beta_read import BetaReadAssignmentState
from app.utils import beta_read_utils


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshes = []

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshes.append(value)


@pytest.mark.asyncio
async def test_submit_beta_read_feedback_requires_current_requirements(monkeypatch):
    async def _fake_expire(*_args, **_kwargs):
        return False

    async def _fake_sync(*_args, **_kwargs):
        return {
            "progress_pct": 100,
            "chapters_total": 12,
            "chapters_read_count": 12,
            "comment_count": 4,
            "feedback_item_count": 2,
            "answer_count": 1,
        }

    monkeypatch.setattr(beta_read_utils, "expire_beta_assignment_if_due", _fake_expire)
    monkeypatch.setattr(beta_read_utils, "sync_beta_assignment_progress", _fake_sync)

    current_user = SimpleNamespace(id=uuid.uuid4())
    assignment = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        author_user_id=uuid.uuid4(),
        state=BetaReadAssignmentState.READY_TO_SUBMIT.value,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        final_feedback=None,
        submitted_at=None,
        submission_metadata={},
        required_progress_pct=100,
        required_comment_count=1,
        required_feedback_item_count=2,
        require_final_feedback=True,
    )

    db = _FakeDB()
    updated = await beta_read_utils.submit_beta_read_feedback(
        db,
        assignment=assignment,
        current_user=current_user,
        final_feedback="Strong ending and much clearer stakes now.",
        final_rating=4.5,
    )

    assert updated.final_feedback == "Strong ending and much clearer stakes now."
    assert updated.final_rating == 4.5
    assert updated.state == BetaReadAssignmentState.SUBMITTED.value
    assert updated.submitted_progress_pct == 100
    assert updated.submitted_feedback_item_count == 2
    assert updated.submitted_answer_count == 1
    assert updated.submitted_before_deadline is True
    assert updated.late_feedback is False
    assert len(db.added) == 1
    notification = db.added[0]
    assert notification.kind == "beta_read_feedback_submitted"
    assert notification.user_id == assignment.author_user_id
    assert db.commits == 1


@pytest.mark.asyncio
async def test_submit_beta_read_feedback_rejects_stale_ready_state(monkeypatch):
    async def _fake_expire(*_args, **_kwargs):
        return False

    async def _fake_sync(*_args, **_kwargs):
        return {
            "progress_pct": 75,
            "chapters_total": 12,
            "chapters_read_count": 9,
            "comment_count": 0,
            "feedback_item_count": 0,
            "answer_count": 0,
        }

    monkeypatch.setattr(beta_read_utils, "expire_beta_assignment_if_due", _fake_expire)
    monkeypatch.setattr(beta_read_utils, "sync_beta_assignment_progress", _fake_sync)

    current_user = SimpleNamespace(id=uuid.uuid4())
    assignment = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        author_user_id=uuid.uuid4(),
        state=BetaReadAssignmentState.READY_TO_SUBMIT.value,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        final_feedback=None,
        submitted_at=None,
        submission_metadata={},
        required_progress_pct=100,
        required_comment_count=1,
        required_feedback_item_count=1,
        require_final_feedback=True,
    )

    with pytest.raises(beta_read_utils.HTTPException) as exc_info:
        await beta_read_utils.submit_beta_read_feedback(
            _FakeDB(),
            assignment=assignment,
            current_user=current_user,
            final_feedback="This should fail because the assignment no longer meets the rules.",
            final_rating=3.5,
        )

    assert exc_info.value.status_code == 409
    assert "Finish the required reading and comments" in exc_info.value.detail


def test_normalize_beta_read_rating_requires_half_steps():
    assert beta_read_utils.normalize_beta_read_rating(4.5) == 4.5
    assert beta_read_utils.normalize_beta_read_rating(1) == 1.0

    with pytest.raises(beta_read_utils.HTTPException):
        beta_read_utils.normalize_beta_read_rating(4.3)




def test_beta_feedback_item_author_metadata_defaults_to_open():
    item = SimpleNamespace(metadata_json={})

    metadata = beta_read_utils.beta_feedback_item_author_metadata(item)

    assert metadata["author_status"] == "open"
    assert metadata["author_task_id"] is None
    assert metadata["author_updated_at"] is None


def test_normalize_author_feedback_item_status_rejects_unknown_values():
    assert beta_read_utils.normalize_author_feedback_item_status("resolved") == "resolved"

    with pytest.raises(beta_read_utils.HTTPException):
        beta_read_utils.normalize_author_feedback_item_status("done")
