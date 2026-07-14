from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.beta_read import BetaReadAssignment
from app.models.book import Book, BookCollaborator, Chapter
from app.models.intelligence import Notification
from app.models.progress import ReadingProgress
from app.models.user import User
from app.utils.auth_csrf import AUTH_CSRF_COOKIE_NAME, AUTH_CSRF_HEADER_NAME, create_auth_csrf_token
from app.utils.beta_read_job_utils import run_beta_read_jobs


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    csrf_token = create_auth_csrf_token()
    return {
        "Cookie": f"lorevia_access_token={create_access_token(str(user_id))}; {AUTH_CSRF_COOKIE_NAME}={csrf_token}",
        AUTH_CSRF_HEADER_NAME: csrf_token,
        "Origin": "https://getlorevia.com",
    }


async def _create_user(db, *, email: str, tier: str) -> User:
    user = User(
        email=email,
        username=email.split("@", 1)[0],
        password_hash="hashed",
        tier=tier,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_book(db, *, author_id: uuid.UUID) -> Book:
    book = Book(
        user_id=author_id,
        title="The Lantern Trial",
        author="M. Author",
        genre="Fantasy",
        format="manual",
        work_type="novel",
        s3_key="books/lantern.txt",
        mode="author",
        status="ready",
        total_chapters=1,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def _add_book_chapter(db, *, book_id: uuid.UUID, chapter_number: int) -> Chapter:
    chapter = Chapter(
        book_id=book_id,
        number=chapter_number,
        title=f"Chapter {chapter_number}",
        s3_key=f"books/chapter-{chapter_number}.json",
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@pytest.mark.asyncio
async def test_beta_read_flow_requires_review_and_tracks_feedback_completion(client, db):
    author = await _create_user(db, email="author@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    db.add(
        ReadingProgress(
            user_id=reader.id,
            book_id=book.id,
            current_chapter=1,
            chapters_read=[1],
            scroll_pct=1.0,
        )
    )
    await db.commit()

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Reader response pass",
            "window_days": 7,
            "required_progress_pct": 100,
            "required_comment_count": 1,
            "required_feedback_item_count": 2,
            "author_questions": [
                "Did Chapter 3 hook you?",
                "Where did you get confused?",
            ],
        },
    )
    assert create_response.status_code == 201
    assignment = create_response.json()
    assignment_id = assignment["id"]
    assert assignment["required_feedback_item_count"] == 2
    assert assignment["question_count"] == 2

    append_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads/{assignment_id}/questions",
        headers=_auth_headers(author.id),
        json={"questions": ["Which character did you care about most?"]},
    )
    assert append_response.status_code == 200
    assert len(append_response.json()) == 3

    reader_detail = await client.get(
        f"/api/v1/beta-reads/{assignment_id}",
        headers=_auth_headers(reader.id),
    )
    assert reader_detail.status_code == 200
    detail_payload = reader_detail.json()
    assert len(detail_payload["author_questions"]) == 3

    answer_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/feedback-items",
        headers=_auth_headers(reader.id),
        json={
            "kind": "answer",
            "question_id": detail_payload["author_questions"][0]["id"],
            "body": "The opener landed quickly and made me want the next page.",
        },
    )
    assert answer_response.status_code == 201
    assert answer_response.json()["assignment"]["submission_allowed"] is False

    comment_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/feedback-items",
        headers=_auth_headers(reader.id),
        json={
            "kind": "chapter_comment",
            "chapter_number": 1,
            "body": "The villain reveal felt strong, but the bridge into it could be tighter.",
        },
    )
    assert comment_response.status_code == 201
    ready_payload = comment_response.json()
    assert ready_payload["assignment"]["submission_allowed"] is True
    assert ready_payload["feedback_summary"]["answer_count"] == 1
    assert ready_payload["feedback_summary"]["chapter_comment_count"] == 1

    submit_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/submit-feedback",
        headers=_auth_headers(reader.id),
        json={
            "final_feedback": "The chapter hooked me, the reveal worked, and the emotional center stayed clear.",
            "final_rating": 4.5,
        },
    )
    assert submit_response.status_code == 200
    submitted_assignment = submit_response.json()
    assert submitted_assignment["state"] == "completed"
    assert submitted_assignment["final_rating"] == 4.5
    assert submitted_assignment["rating_sentiment"] == "positive"
    assert submitted_assignment["book_average_rating"] == 4.5
    assert submitted_assignment["book_rating_count"] == 1

    author_detail = await client.get(
        f"/api/v1/books/{book.id}/beta-reads/{assignment_id}",
        headers=_auth_headers(author.id),
    )
    assert author_detail.status_code == 200
    summary = author_detail.json()["feedback_summary"]
    assert summary["feedback_item_count"] == 2
    assert summary["answer_count"] == 1
    assert summary["chapter_comment_count"] == 1

    assert author_detail.json()["assignment"]["book_average_rating"] == 4.5
    assert author_detail.json()["assignment"]["book_rating_count"] == 1


@pytest.mark.asyncio
async def test_reader_chapter_payload_surfaces_beta_comments_for_author_and_chapter_collaborators(
    client, db, monkeypatch
):
    author = await _create_user(db, email="author-chapter-comments@lorevia.test", tier="author")
    first_reader = await _create_user(db, email="reader-one@lorevia.test", tier="reader")
    second_reader = await _create_user(db, email="reader-two@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)
    await _add_book_chapter(db, book_id=book.id, chapter_number=1)

    db.add_all(
        [
            ReadingProgress(
                user_id=first_reader.id,
                book_id=book.id,
                current_chapter=1,
                chapters_read=[1],
                scroll_pct=1.0,
            ),
            ReadingProgress(
                user_id=second_reader.id,
                book_id=book.id,
                current_chapter=1,
                chapters_read=[1],
                scroll_pct=1.0,
            ),
        ]
    )
    await db.commit()

    monkeypatch.setattr(
        "app.services.chapter_recovery_service.deserialize_manuscript_content",
        lambda _raw: {
            "text": "Lantern fire cracked across the bridge.",
            "html": "<p>Lantern fire cracked across the bridge.</p>",
        },
    )
    monkeypatch.setattr(
        "app.services.chapter_recovery_service.download_book",
        lambda _key: b"stored chapter payload",
    )

    first_assignment = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": first_reader.email,
            "task_label": "First pass",
            "window_days": 7,
            "required_feedback_item_count": 1,
        },
    )
    second_assignment = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": second_reader.email,
            "task_label": "Second pass",
            "window_days": 7,
            "required_feedback_item_count": 1,
        },
    )
    assert first_assignment.status_code == 201
    assert second_assignment.status_code == 201

    first_assignment_id = first_assignment.json()["id"]
    second_assignment_id = second_assignment.json()["id"]

    first_comment = await client.post(
        f"/api/v1/beta-reads/{first_assignment_id}/feedback-items",
        headers=_auth_headers(first_reader.id),
        json={
            "kind": "chapter_comment",
            "chapter_number": 1,
            "body": "The bridge argument lands, but I wanted one more line before the reveal.",
        },
    )
    second_comment = await client.post(
        f"/api/v1/beta-reads/{second_assignment_id}/feedback-items",
        headers=_auth_headers(second_reader.id),
        json={
            "kind": "chapter_comment",
            "chapter_number": 1,
            "body": "The closing beat is clear, but the turn into it still feels abrupt.",
        },
    )
    assert first_comment.status_code == 201
    assert second_comment.status_code == 201

    author_chapter = await client.get(
        f"/api/v1/reader/{book.id}/chapter/1", headers=_auth_headers(author.id)
    )
    first_reader_chapter = await client.get(
        f"/api/v1/reader/{book.id}/chapter/1", headers=_auth_headers(first_reader.id)
    )

    assert author_chapter.status_code == 200
    assert first_reader_chapter.status_code == 200

    author_feedback = author_chapter.json()["beta_feedback"]
    reader_feedback = first_reader_chapter.json()["beta_feedback"]

    assert len(author_feedback) == 2
    assert {item["body"] for item in author_feedback} == {
        "The bridge argument lands, but I wanted one more line before the reveal.",
        "The closing beat is clear, but the turn into it still feels abrupt.",
    }
    assert len(reader_feedback) == 2
    assert {item["body"] for item in reader_feedback} == {
        "The bridge argument lands, but I wanted one more line before the reveal.",
        "The closing beat is clear, but the turn into it still feels abrupt.",
    }


@pytest.mark.asyncio
async def test_collaborator_activity_endpoint_includes_beta_feedback_timeline(client, db):
    author = await _create_user(db, email="author-collab-activity@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-collab-activity@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    db.add(
        ReadingProgress(
            user_id=reader.id,
            book_id=book.id,
            current_chapter=1,
            chapters_read=[1],
            scroll_pct=1.0,
        )
    )
    await db.commit()

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Activity timeline pass",
            "window_days": 7,
            "required_progress_pct": 100,
            "required_comment_count": 1,
            "required_feedback_item_count": 1,
        },
    )
    assert create_response.status_code == 201
    assignment_payload = create_response.json()
    assignment_id = assignment_payload["id"]
    collaborator_id = assignment_payload["collaborator_id"]
    assert collaborator_id is not None

    comment_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/feedback-items",
        headers=_auth_headers(reader.id),
        json={
            "kind": "chapter_comment",
            "chapter_number": 1,
            "body": "The midpoint is strong once the argument reaches the lantern room.",
        },
    )
    assert comment_response.status_code == 201

    submit_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/submit-feedback",
        headers=_auth_headers(reader.id),
        json={
            "final_feedback": "The emotional center held and the ending turn was memorable.",
            "final_rating": 4.0,
        },
    )
    assert submit_response.status_code == 200

    activity_response = await client.get(
        f"/api/v1/books/{book.id}/collaborators/{collaborator_id}/activity",
        headers=_auth_headers(author.id),
    )
    assert activity_response.status_code == 200
    payload = activity_response.json()

    assert payload["collaborator"]["email"] == reader.email
    assert payload["chapter_comment_count"] == 1
    assert payload["assignments"][0]["id"] == assignment_id
    assert {item["kind"] for item in payload["items"]} >= {"chapter_comment", "beta_read_submitted"}
    assert any(
        item["body"] == "The midpoint is strong once the argument reaches the lantern room."
        for item in payload["items"]
    )


@pytest.mark.asyncio
async def test_deleting_feedback_item_moves_assignment_out_of_ready_state(client, db):
    author = await _create_user(db, email="author-delete@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-delete@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    db.add(
        ReadingProgress(
            user_id=reader.id,
            book_id=book.id,
            current_chapter=1,
            chapters_read=[1],
            scroll_pct=1.0,
        )
    )
    await db.commit()

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Tighten pacing feedback",
            "window_days": 7,
            "required_progress_pct": 100,
            "required_comment_count": 0,
            "required_feedback_item_count": 1,
            "author_questions": [],
        },
    )
    assignment_id = create_response.json()["id"]

    feedback_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/feedback-items",
        headers=_auth_headers(reader.id),
        json={
            "kind": "favorite",
            "chapter_number": 1,
            "anchor_text": "The lantern finally answered.",
            "body": "This was the first moment I felt fully locked into the story promise.",
        },
    )
    assert feedback_response.status_code == 201
    detail = feedback_response.json()
    assert detail["assignment"]["submission_allowed"] is True

    delete_response = await client.delete(
        f"/api/v1/beta-reads/{assignment_id}/feedback-items/{detail['feedback_items'][0]['id']}",
        headers=_auth_headers(reader.id),
    )
    assert delete_response.status_code == 200
    updated_detail = delete_response.json()
    assert updated_detail["assignment"]["submission_allowed"] is False
    assert updated_detail["feedback_summary"]["feedback_item_count"] == 0


@pytest.mark.asyncio
async def test_author_can_triage_beta_feedback_items(client, db):
    author = await _create_user(db, email="author-triage@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-triage@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    db.add(
        ReadingProgress(
            user_id=reader.id,
            book_id=book.id,
            current_chapter=1,
            chapters_read=[1],
            scroll_pct=1.0,
        )
    )
    await db.commit()

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Collect confusion feedback",
            "window_days": 7,
            "required_feedback_item_count": 1,
        },
    )
    assignment_id = create_response.json()["id"]

    feedback_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/feedback-items",
        headers=_auth_headers(reader.id),
        json={
            "kind": "confusing",
            "chapter_number": 1,
            "anchor_text": "The lantern answers in a different voice here.",
            "body": "I lost track of whether this was the same presence from the opener.",
        },
    )
    assert feedback_response.status_code == 201
    feedback_item_id = feedback_response.json()["feedback_items"][0]["id"]

    task_created = await client.put(
        f"/api/v1/books/{book.id}/beta-reads/{assignment_id}/feedback-items/{feedback_item_id}",
        headers=_auth_headers(author.id),
        json={
            "author_status": "task_created",
            "author_task_id": "revision-task:lantern-voice",
        },
    )
    assert task_created.status_code == 200
    item = task_created.json()["feedback_items"][0]
    assert item["author_status"] == "task_created"
    assert item["author_task_id"] == "revision-task:lantern-voice"
    assert item["author_updated_at"] is not None

    resolved = await client.put(
        f"/api/v1/books/{book.id}/beta-reads/{assignment_id}/feedback-items/{feedback_item_id}",
        headers=_auth_headers(author.id),
        json={
            "author_status": "resolved",
            "author_task_id": None,
        },
    )
    assert resolved.status_code == 200
    resolved_item = resolved.json()["feedback_items"][0]
    assert resolved_item["author_status"] == "resolved"
    assert resolved_item["author_task_id"] is None


@pytest.mark.asyncio
async def test_beta_read_assignment_rejects_windows_outside_three_to_seven_days(client, db):
    author = await _create_user(db, email="author-window@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-window@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    too_short = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Short window",
            "window_days": 2,
        },
    )
    assert too_short.status_code == 422
    response_detail = too_short.json().get("detail")
    assert isinstance(response_detail, (str, list)) and len(str(response_detail)) > 0

    too_long = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Long window",
            "window_days": 8,
        },
    )
    assert too_long.status_code == 422
    response_detail = too_long.json().get("detail")
    assert isinstance(response_detail, (str, list)) and len(str(response_detail)) > 0


@pytest.mark.asyncio
async def test_unassigned_reader_cannot_access_beta_book(client, db):
    author = await _create_user(db, email="author-access@lorevia.test", tier="author")
    assigned_reader = await _create_user(db, email="assigned-access@lorevia.test", tier="reader")
    unassigned_reader = await _create_user(
        db, email="unassigned-access@lorevia.test", tier="reader"
    )
    book = await _create_book(db, author_id=author.id)

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": assigned_reader.email,
            "task_label": "Assigned access",
            "window_days": 3,
        },
    )
    assert create_response.status_code == 201

    denied = await client.get(
        f"/api/v1/reader/{book.id}/chapter/1",
        headers=_auth_headers(unassigned_reader.id),
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_completion_job_is_idempotent_and_resets_missed_streak(client, db):
    author = await _create_user(db, email="author-idem@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-idem@lorevia.test", tier="reader")
    reader.consecutive_missed_beta_reads = 2
    reader.beta_read_penalty_status = "strong_warning"
    await db.commit()
    book = await _create_book(db, author_id=author.id)

    db.add(
        ReadingProgress(
            user_id=reader.id,
            book_id=book.id,
            current_chapter=1,
            chapters_read=[1],
            scroll_pct=1.0,
        )
    )
    await db.commit()

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Idempotent award",
            "window_days": 7,
            "required_progress_pct": 100,
            "required_comment_count": 0,
            "required_feedback_item_count": 1,
        },
    )
    assignment_id = create_response.json()["id"]

    feedback_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/feedback-items",
        headers=_auth_headers(reader.id),
        json={
            "kind": "favorite",
            "chapter_number": 1,
            "body": "The midpoint reveal landed well.",
        },
    )
    assert feedback_response.status_code == 201

    submit_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/submit-feedback",
        headers=_auth_headers(reader.id),
        json={
            "final_feedback": "Clear payoff, strong setup, and a good emotional turn.",
            "final_rating": 4.0,
        },
    )
    assert submit_response.status_code == 200
    assert submit_response.json()["state"] == "completed"

    await run_beta_read_jobs(db, limit=20)
    await db.commit()

    await db.refresh(reader)
    assert reader.consecutive_missed_beta_reads == 0
    assert reader.beta_read_penalty_status == "none"


@pytest.mark.asyncio
async def test_expired_assignments_move_to_missed_and_increment_consecutive_count(client, db):
    author = await _create_user(db, email="author-expire@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-expire@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Expire me",
            "window_days": 3,
        },
    )
    assignment_id = create_response.json()["id"]

    assignment = (
        await db.execute(
            select(BetaReadAssignment).where(BetaReadAssignment.id == uuid.UUID(assignment_id))
        )
    ).scalar_one()
    assignment.expires_at = assignment.expires_at - timedelta(days=10)
    await db.commit()

    await run_beta_read_jobs(db, limit=20)
    await db.commit()

    reader_assignments = await client.get(
        "/api/v1/beta-reads?bucket=missed", headers=_auth_headers(reader.id)
    )
    assert reader_assignments.status_code == 200
    payload = reader_assignments.json()["items"]
    assert payload[0]["state"] == "missed"
    assert payload[0]["missed_reason"] == "deadline_expired"
    assert payload[0]["counted_toward_missed_streak"] is True

    await db.refresh(reader)
    assert reader.consecutive_missed_beta_reads == 1


@pytest.mark.asyncio
async def test_beta_read_jobs_are_idempotent_for_expirations_and_notifications(client, db):
    author = await _create_user(db, email="author-idempotent-expire@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-idempotent-expire@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Idempotent expiry",
            "window_days": 3,
        },
    )
    assignment_id = create_response.json()["id"]

    assignment = (
        await db.execute(
            select(BetaReadAssignment).where(BetaReadAssignment.id == uuid.UUID(assignment_id))
        )
    ).scalar_one()
    assignment.expires_at = assignment.expires_at - timedelta(days=10)
    await db.commit()

    await run_beta_read_jobs(db, limit=20)
    await run_beta_read_jobs(db, limit=20)
    await db.commit()

    await db.refresh(reader)
    await db.refresh(assignment)

    notifications = (
        (
            await db.execute(
                select(Notification).where(
                    Notification.book_id == book.id,
                    Notification.kind.in_(
                        [
                            "beta_read_deadline_missed",
                            "beta_read_missed_author_notice",
                            "beta_read_penalty_warning",
                        ]
                    ),
                )
            )
        )
        .scalars()
        .all()
    )

    assert assignment.state == "missed"
    assert assignment.counted_toward_missed_streak is True
    assert reader.consecutive_missed_beta_reads == 1
    assert sorted(notification.kind for notification in notifications) == [
        "beta_read_deadline_missed",
        "beta_read_missed_author_notice",
        "beta_read_penalty_warning",
    ]


@pytest.mark.asyncio
async def test_beta_read_jobs_do_not_duplicate_deadline_reminders(client, db):
    author = await _create_user(db, email="author-idempotent-reminder@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-idempotent-reminder@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Reminder me once",
            "window_days": 3,
        },
    )
    assignment_id = create_response.json()["id"]

    assignment = (
        await db.execute(
            select(BetaReadAssignment).where(BetaReadAssignment.id == uuid.UUID(assignment_id))
        )
    ).scalar_one()
    assignment.expires_at = datetime.now(UTC) + timedelta(hours=23, minutes=30)
    await db.commit()

    await run_beta_read_jobs(db, limit=20)
    await run_beta_read_jobs(db, limit=20)
    await db.commit()
    await db.refresh(assignment)

    reminders = (
        (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == reader.id,
                    Notification.book_id == book.id,
                    Notification.kind == "beta_read_deadline_reminder",
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(reminders) == 1
    assert assignment.reminder_24h_sent_at is not None


@pytest.mark.asyncio
async def test_expired_beta_read_revokes_book_invite_access(client, db):
    author = await _create_user(db, email="author-invite-expire@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-invite-expire@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Temporary access",
            "window_days": 3,
        },
    )
    assert create_response.status_code == 201

    before_expiry = await client.get("/api/v1/books/", headers=_auth_headers(reader.id))
    assert before_expiry.status_code == 200
    assert any(item["id"] == str(book.id) for item in before_expiry.json())

    assignment = (
        await db.execute(select(BetaReadAssignment).where(BetaReadAssignment.book_id == book.id))
    ).scalar_one()
    collaborator = (
        await db.execute(
            select(BookCollaborator).where(
                BookCollaborator.book_id == book.id,
                BookCollaborator.email == reader.email,
            )
        )
    ).scalar_one()
    assignment.expires_at = assignment.expires_at - timedelta(days=10)
    await db.commit()

    await run_beta_read_jobs(db, limit=20)
    await db.commit()

    await db.refresh(collaborator)
    assert collaborator.invite_status == "revoked"

    after_expiry = await client.get("/api/v1/books/", headers=_auth_headers(reader.id))
    assert after_expiry.status_code == 200
    assert all(item["id"] != str(book.id) for item in after_expiry.json())


@pytest.mark.asyncio
async def test_revoked_assignments_cannot_be_completed(client, db):
    author = await _create_user(db, email="author-revoke@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-revoke@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    db.add(
        ReadingProgress(
            user_id=reader.id,
            book_id=book.id,
            current_chapter=1,
            chapters_read=[1],
            scroll_pct=1.0,
        )
    )
    await db.commit()

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Revoke me",
            "window_days": 3,
            "required_feedback_item_count": 1,
        },
    )
    assignment_id = create_response.json()["id"]

    revoke_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads/{assignment_id}/revoke",
        headers=_auth_headers(author.id),
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["state"] == "revoked"

    submit_response = await client.post(
        f"/api/v1/beta-reads/{assignment_id}/submit-feedback",
        headers=_auth_headers(reader.id),
        json={"final_feedback": "Too late after revocation.", "final_rating": 2.0},
    )
    assert submit_response.status_code == 409


@pytest.mark.asyncio
async def test_author_cannot_assign_beta_readers_to_another_authors_book(client, db):
    owner = await _create_user(db, email="owner-book@lorevia.test", tier="author")
    other_author = await _create_user(db, email="other-book@lorevia.test", tier="author")
    reader = await _create_user(db, email="reader-book@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=owner.id)

    response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(other_author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Unauthorized assign",
            "window_days": 3,
        },
    )
    assert response.status_code == 404
