from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.beta_read import BetaReadAssignmentState, BetaReadFeedbackKind, BetaReadScopeKind
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


class _Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return list(self.values)


class _SequenceDB(_FakeDB):
    def __init__(self, *results, get_values=None):
        super().__init__()
        self.results = list(results)
        self.get_values = dict(get_values or {})

    async def execute(self, _statement):
        return _Result(self.results.pop(0))

    async def get(self, model, item_id):
        return self.get_values.get((model, item_id), self.get_values.get(item_id))

    async def flush(self):
        return None


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


@pytest.mark.asyncio
async def test_load_beta_assignment_render_context_aggregates_counts_ratings_and_scoped_comments():
    assignment_id = uuid.uuid4()
    full_assignment_id = uuid.uuid4()
    book_id = uuid.uuid4()
    reader_id = uuid.uuid4()
    no_reader_id = uuid.uuid4()
    assignments = [
        SimpleNamespace(
            id=assignment_id,
            book_id=book_id,
            reader_user_id=reader_id,
            scope_kind=BetaReadScopeKind.CHAPTER_RANGE.value,
            chapter_start=2,
            chapter_end=4,
        ),
        SimpleNamespace(
            id=full_assignment_id,
            book_id=book_id,
            reader_user_id=None,
            scope_kind=BetaReadScopeKind.FULL_BOOK.value,
            chapter_start=None,
            chapter_end=None,
        ),
    ]
    book = SimpleNamespace(id=book_id, total_chapters=8)
    reader = SimpleNamespace(id=reader_id)
    progress = SimpleNamespace(book_id=book_id, user_id=reader_id)
    db = _SequenceDB(
        [book],
        [reader],
        [progress],
        [(book_id, 5.0), (book_id, 3.0), (book_id, None)],
        [(assignment_id, 2)],
        [(assignment_id, 5)],
        [(assignment_id, 1)],
        [(book_id, reader_id, 1), (book_id, reader_id, 3), (book_id, reader_id, None)],
        [(assignment_id, 2), (assignment_id, 6), (assignment_id, None)],
    )

    context = await beta_read_utils.load_beta_assignment_render_context(db, assignments=assignments)
    assert context.books_by_id[book_id] is book
    assert context.readers_by_id[reader_id] is reader
    assert context.progress_by_pair[(book_id, reader_id)] is progress
    assert context.rating_summary_by_book_id[book_id] == {
        "average_rating": 4.0,
        "rating_count": 2,
        "positive_rating_count": 1,
        "neutral_rating_count": 1,
        "negative_rating_count": 0,
    }
    assert context.question_count_by_assignment_id[assignment_id] == 2
    assert context.feedback_count_by_assignment_id[assignment_id] == 5
    assert context.answer_count_by_assignment_id[assignment_id] == 1
    assert context.note_comment_count_by_assignment_id[assignment_id] == 2
    assert context.chapter_comment_count_by_assignment_id[assignment_id] == 2
    assert (
        context.note_comment_count_by_assignment_id[no_reader_id]
        if no_reader_id in context.note_comment_count_by_assignment_id
        else 0 == 0
    )
    assert context.note_comment_count_by_assignment_id[full_assignment_id] == 0

    empty = await beta_read_utils.load_beta_assignment_render_context(_SequenceDB(), assignments=[])
    assert empty.books_by_id == {} and empty.rating_summary_by_book_id == {}


@pytest.mark.asyncio
async def test_serialize_feedback_items_resolves_question_scene_and_author_metadata():
    assignment_id = uuid.uuid4()
    question_id = uuid.uuid4()
    scene_id = uuid.uuid4()
    now = datetime.now(UTC)
    item = SimpleNamespace(
        id=uuid.uuid4(),
        question_id=question_id,
        scene_id=scene_id,
        kind=BetaReadFeedbackKind.ANSWER.value,
        chapter_number=2,
        reaction=None,
        anchor_text="the gate",
        body="It was clear.",
        metadata_json={
            "author_status": "resolved",
            "author_task_id": "task-1",
            "author_updated_at": now.isoformat(),
        },
        created_at=now,
        updated_at=now,
    )
    question = SimpleNamespace(id=question_id, prompt="Was the gate clear?")
    scene = SimpleNamespace(id=scene_id, title="Gate opens")
    db = _SequenceDB([item], [question], [scene])

    result = await beta_read_utils._serialize_beta_read_feedback_items(
        db, assignment_id=assignment_id
    )
    assert len(result) == 1
    assert result[0].question_prompt == "Was the gate clear?"
    assert result[0].scene_title == "Gate opens"
    assert result[0].author_status == "resolved"

    assert (
        await beta_read_utils._serialize_beta_read_feedback_items(
            _SequenceDB([]), assignment_id=assignment_id
        )
        == []
    )


@pytest.mark.asyncio
async def test_book_beta_rating_summary_and_reader_display_helpers():
    summary = await beta_read_utils.book_beta_rating_summary(
        _SequenceDB([5.0, 3.5, 1.0, None]), book_id=uuid.uuid4()
    )
    assert summary == {
        "average_rating": 3.17,
        "rating_count": 3,
        "positive_rating_count": 1,
        "neutral_rating_count": 1,
        "negative_rating_count": 1,
    }
    empty = await beta_read_utils.book_beta_rating_summary(_SequenceDB([]), book_id=uuid.uuid4())
    assert empty["rating_count"] == 0 and empty["average_rating"] is None

    assignment = SimpleNamespace(reader_email="fallback@example.test")
    assert (
        beta_read_utils._beta_feedback_reader_display_name(
            assignment=assignment,
            reader=SimpleNamespace(username="mira", email="mira@example.test"),
            collaborator=None,
        )
        == "mira"
    )
    assert (
        beta_read_utils._beta_feedback_reader_display_name(
            assignment=assignment, reader=None, collaborator=SimpleNamespace(display_name="Editor")
        )
        == "Editor"
    )
    assert (
        beta_read_utils._beta_feedback_reader_display_name(
            assignment=assignment, reader=None, collaborator=None
        )
        == "fallback@example.test"
    )

    assert (
        beta_read_utils._beta_feedback_activity_title(
            SimpleNamespace(kind=BetaReadFeedbackKind.CHAPTER_COMMENT.value)
        )
        == "Left a chapter comment"
    )
    assert (
        beta_read_utils._beta_feedback_activity_title(
            SimpleNamespace(kind=BetaReadFeedbackKind.SCENE_REACTION.value)
        )
        == "Left a scene reaction"
    )
    assert (
        beta_read_utils._beta_feedback_activity_title(
            SimpleNamespace(kind=BetaReadFeedbackKind.ANSWER.value)
        )
        == "Answered an author question"
    )
    assert (
        beta_read_utils._beta_feedback_activity_title(
            SimpleNamespace(kind=BetaReadFeedbackKind.FAVORITE.value)
        )
        == "Marked a favorite moment"
    )
    assert (
        beta_read_utils._beta_feedback_activity_title(SimpleNamespace(kind="other"))
        == "Added beta feedback"
    )


@pytest.mark.asyncio
async def test_start_beta_read_transitions_once_and_notifies_author(monkeypatch):
    async def not_expired(*_args, **_kwargs):
        return False

    monkeypatch.setattr(beta_read_utils, "expire_beta_assignment_if_due", not_expired)
    now = datetime.now(UTC)
    assignment = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        author_user_id=uuid.uuid4(),
        state=BetaReadAssignmentState.ACTIVE.value,
        starts_at=now - timedelta(days=1),
        first_opened_at=None,
        state_changed_at=None,
    )
    db = _SequenceDB()
    result = await beta_read_utils.start_beta_read(
        db, assignment=assignment, current_user=SimpleNamespace(id=uuid.uuid4())
    )
    assert result is assignment
    assert assignment.state == BetaReadAssignmentState.IN_PROGRESS.value
    assert assignment.first_opened_at is not None
    assert db.added[0].kind == "beta_read_started"
    assert db.commits == 1 and db.refreshes == [assignment]


@pytest.mark.asyncio
async def test_award_submitted_beta_reads_completes_qualified_and_disqualifies_late(monkeypatch):
    reader_good = SimpleNamespace(
        id=uuid.uuid4(),
        consecutive_missed_beta_reads=2,
        beta_read_penalty_status="warning",
        beta_read_penalty_until=None,
    )
    reader_bad = SimpleNamespace(id=uuid.uuid4())
    base = {
        "book_id": uuid.uuid4(),
        "author_user_id": uuid.uuid4(),
        "state": BetaReadAssignmentState.SUBMITTED.value,
        "required_progress_pct": 100,
        "required_comment_count": 1,
        "required_feedback_item_count": 1,
        "require_final_feedback": True,
        "final_rating": 4.5,
        "final_feedback": "Useful feedback",
        "collaborator_id": None,
        "state_changed_at": None,
        "disqualified_at": None,
        "disqualified_reason": None,
        "submitted_progress_pct": None,
        "submitted_chapters_total": None,
        "submitted_chapters_read_count": None,
        "submitted_comment_count": None,
        "submitted_feedback_item_count": None,
        "submitted_answer_count": None,
        "submitted_rating_sentiment": None,
        "submitted_before_deadline": None,
        "late_feedback": False,
    }
    good = SimpleNamespace(
        id=uuid.uuid4(),
        reader_user_id=reader_good.id,
        submission_metadata={
            "progress_pct": 100,
            "comment_count": 2,
            "feedback_item_count": 1,
            "submitted_before_deadline": True,
        },
        **base,
    )
    bad = SimpleNamespace(
        id=uuid.uuid4(),
        reader_user_id=reader_bad.id,
        submission_metadata={
            "progress_pct": 100,
            "comment_count": 2,
            "feedback_item_count": 1,
            "submitted_before_deadline": False,
        },
        **base,
    )
    notifications = []

    async def notify(*_args, **kwargs):
        notifications.append(kwargs)

    monkeypatch.setattr(beta_read_utils, "create_notification_once", notify)
    db = _SequenceDB(
        [good, bad], get_values={reader_good.id: reader_good, reader_bad.id: reader_bad}
    )
    assert await beta_read_utils.award_submitted_beta_reads(db) == 1
    assert good.state == BetaReadAssignmentState.COMPLETED.value
    assert bad.state == BetaReadAssignmentState.DISQUALIFIED.value
    assert reader_good.consecutive_missed_beta_reads == 0
    assert notifications[0]["kind"] == "beta_read_completed"
