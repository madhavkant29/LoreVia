from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.schemas.beta_reads import (
    BetaReadAssignmentOut,
    BetaReadFeedbackItemOut,
    BetaReadFeedbackSummaryOut,
    BetaReadQuestionOut,
)
from app.utils import beta_read_assignment_query_utils


@pytest.mark.asyncio
async def test_build_beta_read_assignment_detail_out_aggregates_assignment_questions_and_feedback(
    monkeypatch,
):
    assignment_id = uuid.uuid4()
    assignment = SimpleNamespace(id=assignment_id)
    assignment_out = BetaReadAssignmentOut.model_construct(
        id=str(assignment_id),
        book_id=str(uuid.uuid4()),
        author_user_id=str(uuid.uuid4()),
        reader_email="reader@example.test",
        state="active",
        view_bucket="active",
    )
    summary = BetaReadFeedbackSummaryOut(feedback_item_count=2, answer_count=1)

    async def load_context(_db, *, assignments):
        assert assignments == [assignment]
        return "render-context"

    def build_assignment_out(value, *, context, current_user=None, reader_user=None):
        assert value is assignment
        assert context == "render-context"
        assert current_user == "current-user"
        assert reader_user == "reader-user"
        return assignment_out

    async def serialize_questions(_db, *, assignment_id):
        return [
            BetaReadQuestionOut.model_construct(
                id=str(assignment_id),
                prompt="Where did you pause?",
            )
        ]

    async def serialize_feedback_items(_db, *, assignment_id):
        return [
            BetaReadFeedbackItemOut.model_construct(
                id=str(assignment_id),
                body="The reveal landed.",
            )
        ]

    async def feedback_summary(_db, *, assignment_id):
        return summary

    monkeypatch.setattr(
        beta_read_assignment_query_utils,
        "load_beta_assignment_render_context",
        load_context,
    )
    monkeypatch.setattr(
        beta_read_assignment_query_utils,
        "_build_beta_read_assignment_out_from_context",
        build_assignment_out,
    )
    monkeypatch.setattr(
        beta_read_assignment_query_utils,
        "_serialize_beta_read_questions",
        serialize_questions,
    )
    monkeypatch.setattr(
        beta_read_assignment_query_utils,
        "_serialize_beta_read_feedback_items",
        serialize_feedback_items,
    )
    monkeypatch.setattr(beta_read_assignment_query_utils, "beta_feedback_summary", feedback_summary)

    detail = await beta_read_assignment_query_utils.build_beta_read_assignment_detail_out(
        SimpleNamespace(),
        assignment=assignment,
        current_user="current-user",
        reader_user="reader-user",
    )

    assert detail.assignment is assignment_out
    assert len(detail.author_questions) == 1
    assert len(detail.feedback_items) == 1
    assert detail.feedback_summary is summary


@pytest.mark.asyncio
async def test_list_reader_beta_read_assignments_filters_by_bucket(monkeypatch):
    current_user = SimpleNamespace(id=uuid.uuid4(), email="reader@example.test")
    active_assignment = SimpleNamespace(reader_user_id=current_user.id)
    scheduled_assignment = SimpleNamespace(reader_user_id=current_user.id)
    db = SimpleNamespace(commits=0)

    async def commit():
        db.commits += 1

    async def execute(_statement):
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [active_assignment, scheduled_assignment])
        )

    db.commit = commit
    db.execute = execute

    async def sync_identity(_db, user):
        assert user is current_user

    async def expire(_db, *, assignment, now):
        return assignment is scheduled_assignment

    async def load_context(_db, *, assignments):
        assert assignments == [active_assignment, scheduled_assignment]
        return "render-context"

    def build_assignment_out(assignment, *, context, current_user=None, reader_user=None):
        assert context == "render-context"
        if assignment is active_assignment:
            return BetaReadAssignmentOut.model_construct(view_bucket="active")
        return BetaReadAssignmentOut.model_construct(view_bucket="scheduled")

    monkeypatch.setattr(
        beta_read_assignment_query_utils,
        "sync_reader_identity_for_beta_reads",
        sync_identity,
    )
    monkeypatch.setattr(beta_read_assignment_query_utils, "expire_beta_assignment_if_due", expire)
    monkeypatch.setattr(
        beta_read_assignment_query_utils,
        "load_beta_assignment_render_context",
        load_context,
    )
    monkeypatch.setattr(
        beta_read_assignment_query_utils,
        "_build_beta_read_assignment_out_from_context",
        build_assignment_out,
    )

    items = await beta_read_assignment_query_utils.list_reader_beta_read_assignments(
        db,
        current_user=current_user,
        bucket="active",
    )

    assert [item.view_bucket for item in items] == ["active"]
    assert db.commits == 1
