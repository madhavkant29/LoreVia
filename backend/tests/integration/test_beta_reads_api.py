from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.beta_read import BetaReadAssignment
from app.models.book import Book
from app.models.progress import ReadingProgress
from app.models.user import PointLedgerEntry, User
from app.utils.beta_read_utils import run_beta_read_jobs


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Cookie": f"lorevia_access_token={create_access_token(str(user_id))}"}


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


@pytest.mark.asyncio
async def test_beta_read_flow_requires_review_and_awards_points(client, db):
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
            "reward_points": 25,
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
    assert submitted_assignment["awarded_points"] == 38
    assert submitted_assignment["final_rating"] == 4.5
    assert submitted_assignment["rating_sentiment"] == "positive"
    assert submitted_assignment["projected_reward_points"] == 38

    ledger_entries = (
        await db.execute(
            select(PointLedgerEntry).where(PointLedgerEntry.user_id == reader.id)
        )
    ).scalars().all()
    assert len(ledger_entries) == 2
    assert sorted(entry.points_delta for entry in ledger_entries) == [2, 38]

    author_detail = await client.get(
        f"/api/v1/books/{book.id}/beta-reads/{assignment_id}",
        headers=_auth_headers(author.id),
    )
    assert author_detail.status_code == 200
    summary = author_detail.json()["feedback_summary"]
    assert summary["feedback_item_count"] == 2
    assert summary["answer_count"] == 1
    assert summary["chapter_comment_count"] == 1

    author_ledger_entries = (
        await db.execute(
            select(PointLedgerEntry).where(PointLedgerEntry.user_id == author.id)
        )
    ).scalars().all()
    assert len(author_ledger_entries) == 1
    assert author_ledger_entries[0].points_delta == 3


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
            "reward_points": 10,
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
            "reward_points": 20,
        },
    )
    assert too_short.status_code == 422
    assert "window_days" in str(too_short.json())

    too_long = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": reader.email,
            "task_label": "Long window",
            "window_days": 8,
            "reward_points": 20,
        },
    )
    assert too_long.status_code == 422
    assert "window_days" in str(too_long.json())


@pytest.mark.asyncio
async def test_unassigned_reader_cannot_access_beta_book(client, db):
    author = await _create_user(db, email="author-access@lorevia.test", tier="author")
    assigned_reader = await _create_user(db, email="assigned-access@lorevia.test", tier="reader")
    unassigned_reader = await _create_user(db, email="unassigned-access@lorevia.test", tier="reader")
    book = await _create_book(db, author_id=author.id)

    create_response = await client.post(
        f"/api/v1/books/{book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": assigned_reader.email,
            "task_label": "Assigned access",
            "window_days": 3,
            "reward_points": 15,
        },
    )
    assert create_response.status_code == 201

    denied = await client.get(
        f"/api/v1/reader/{book.id}/chapter/1",
        headers=_auth_headers(unassigned_reader.id),
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_award_job_is_idempotent_and_resets_missed_streak(client, db):
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
            "reward_points": 40,
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

    ledger_entries = (
        await db.execute(
            select(PointLedgerEntry).where(PointLedgerEntry.user_id == reader.id)
        )
    ).scalars().all()
    assert len(ledger_entries) == 2
    assert sorted(entry.points_delta for entry in ledger_entries) == [2, 52]

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
            "reward_points": 18,
        },
    )
    assignment_id = create_response.json()["id"]

    assignment = (
        await db.execute(select(BetaReadAssignment).where(BetaReadAssignment.id == uuid.UUID(assignment_id)))
    ).scalar_one()
    assignment.expires_at = assignment.expires_at - timedelta(days=10)
    await db.commit()

    await run_beta_read_jobs(db, limit=20)
    await db.commit()

    reader_assignments = await client.get("/api/v1/beta-reads?bucket=missed", headers=_auth_headers(reader.id))
    assert reader_assignments.status_code == 200
    payload = reader_assignments.json()["items"]
    assert payload[0]["state"] == "missed"
    assert payload[0]["missed_reason"] == "deadline_expired"
    assert payload[0]["counted_toward_missed_streak"] is True

    await db.refresh(reader)
    assert reader.consecutive_missed_beta_reads == 1


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
            "reward_points": 18,
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
            "reward_points": 10,
        },
    )
    assert response.status_code == 404
