import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.models.beta_read import BetaReadAssignmentState, BetaReadScopeKind
from app.utils.beta_read_output_utils import _build_beta_read_assignment_out_from_context
from app.utils.beta_read_policy_utils import BetaAssignmentRenderContext


def test_build_beta_read_assignment_out_from_context_maps_progress_and_status():
    now = datetime.now(UTC)
    book_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    author_id = uuid.uuid4()
    reader_id = uuid.uuid4()
    assignment = SimpleNamespace(
        id=assignment_id,
        book_id=book_id,
        author_user_id=author_id,
        reader_user_id=reader_id,
        reader_email="reader@example.com",
        collaborator_id=None,
        state=BetaReadAssignmentState.READY_TO_SUBMIT.value,
        task_label="Read the opening",
        scope_kind=BetaReadScopeKind.CHAPTER_RANGE.value,
        section_label="Opening",
        chapter_start=1,
        chapter_end=2,
        window_days=3,
        required_progress_pct=100,
        required_comment_count=1,
        required_feedback_item_count=1,
        require_final_feedback=True,
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=2),
        access_granted_at=now - timedelta(days=1),
        submitted_at=None,
        completed_at=None,
        first_opened_at=now - timedelta(hours=2),
        missed_reason=None,
        counted_toward_missed_streak=False,
        revoked_at=None,
        revoked_reason=None,
        disqualified_at=None,
        disqualified_reason=None,
        final_rating=4.5,
    )
    book = SimpleNamespace(id=book_id, title="The Test Book", author="A. Writer", total_chapters=5)
    reader = SimpleNamespace(
        id=reader_id,
        consecutive_missed_beta_reads=1,
        beta_read_penalty_status="warning",
    )
    progress = SimpleNamespace(
        book_id=book_id,
        user_id=reader_id,
        chapters_read=[1, 2],
        current_chapter=2,
    )
    context = BetaAssignmentRenderContext(
        books_by_id={book_id: book},
        readers_by_id={reader_id: reader},
        progress_by_pair={(book_id, reader_id): progress},
        rating_summary_by_book_id={
            book_id: {
                "average_rating": 4.25,
                "rating_count": 2,
                "positive_rating_count": 2,
                "neutral_rating_count": 0,
                "negative_rating_count": 0,
            }
        },
        question_count_by_assignment_id={assignment_id: 3},
        feedback_count_by_assignment_id={assignment_id: 1},
        answer_count_by_assignment_id={assignment_id: 2},
        note_comment_count_by_assignment_id={assignment_id: 1},
        chapter_comment_count_by_assignment_id={assignment_id: 0},
    )

    output = _build_beta_read_assignment_out_from_context(assignment, context=context)

    assert output.id == str(assignment_id)
    assert output.book_title == "The Test Book"
    assert output.progress_pct == 100.0
    assert output.comment_count == 1
    assert output.feedback_item_count == 1
    assert output.question_count == 3
    assert output.answered_question_count == 2
    assert output.submission_allowed is True
    assert output.primary_action == "Submit feedback"
    assert output.penalty_status == "warning"
    assert output.rating_sentiment == "positive"
    assert output.book_average_rating == 4.25
