from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.api.v1.routes import public
from app.core.security import create_access_token
from app.models.book import Book, Chapter
from app.models.progress import ReadingProgress
from app.models.user import PointLedgerEntry, User


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


async def _create_book(db, *, author_id: uuid.UUID, title: str) -> Book:
    book = Book(
        user_id=author_id,
        title=title,
        author="M. Author",
        genre="Fantasy",
        format="manual",
        work_type="novel",
        s3_key=f"books/{title.lower().replace(' ', '-')}.txt",
        mode="author",
        status="ready",
        total_chapters=1,
        is_public=False,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    db.add(
        Chapter(
            book_id=book.id,
            number=1,
            title=f"{title} Opening",
            s3_key=f"chapters/{title.lower().replace(' ', '-')}-1.txt",
            word_count=20000,
            processed=True,
        )
    )
    await db.commit()
    return book


@pytest.fixture(autouse=True)
def _enable_public_forum(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", True, raising=False)


@pytest.mark.asyncio
async def test_private_book_forum_supports_interest_and_rating_rankings(client, db):
    author = await _create_user(db, email="forum-author@lorevia.test", tier="author")
    first_reader = await _create_user(db, email="forum-reader-1@lorevia.test", tier="reader")
    second_reader = await _create_user(db, email="forum-reader-2@lorevia.test", tier="reader")
    seeker = await _create_user(db, email="forum-seeker@lorevia.test", tier="reader")

    high_book = await _create_book(db, author_id=author.id, title="Sky Harbor")
    low_book = await _create_book(db, author_id=author.id, title="Shadow Glass")

    high_post = await client.post(
        "/api/v1/public/forum/posts",
        headers=_auth_headers(author.id),
        json={
            "book_id": str(high_book.id),
            "headline": "Need first-wave beta readers for a sky-citadel fantasy.",
            "body": "Looking for chapter-level reactions on pacing, reveals, and emotional clarity while keeping the manuscript private.",
            "desired_beta_reader_count": 6,
            "allow_contact_requests": True,
        },
    )
    assert high_post.status_code == 201
    high_post_id = high_post.json()["id"]

    low_post = await client.post(
        "/api/v1/public/forum/posts",
        headers=_auth_headers(author.id),
        json={
            "book_id": str(low_book.id),
            "headline": "Seeking feedback on a darker portal fantasy draft.",
            "body": "Open to careful beta readers who can comment on clarity, momentum, and whether the hook lands early enough.",
            "desired_beta_reader_count": 4,
            "allow_contact_requests": True,
        },
    )
    assert low_post.status_code == 201
    low_post_id = low_post.json()["id"]

    interest_response = await client.post(
        f"/api/v1/public/forum/posts/{high_post_id}/interests",
        headers=_auth_headers(seeker.id),
        json={"message": "I focus on scene-level readability and would love to help with this draft."},
    )
    assert interest_response.status_code == 201

    author_interest_list = await client.get(
        f"/api/v1/public/forum/posts/{high_post_id}/interests",
        headers=_auth_headers(author.id),
    )
    assert author_interest_list.status_code == 200
    interest_items = author_interest_list.json()["items"]
    assert len(interest_items) == 1
    assert interest_items[0]["interested_email"] == seeker.email

    comment_response = await client.post(
        f"/api/v1/public/forum/posts/{high_post_id}/comments",
        headers=_auth_headers(seeker.id),
        json={"body": "I can give detailed pacing notes and line-level clarity comments if you want another pass."},
    )
    assert comment_response.status_code == 201
    comment_id = comment_response.json()["id"]
    assert comment_response.json()["author_username"] == seeker.username
    assert comment_response.json()["like_count"] == 0
    assert comment_response.json()["dislike_count"] == 0

    first_reaction = await client.put(
        f"/api/v1/public/forum/comments/{comment_id}/reaction",
        headers=_auth_headers(first_reader.id),
        json={"reaction": "like"},
    )
    assert first_reaction.status_code == 200
    assert first_reaction.json()["like_count"] == 1
    assert first_reaction.json()["author_reputation_score"] == 1

    second_reaction = await client.put(
        f"/api/v1/public/forum/comments/{comment_id}/reaction",
        headers=_auth_headers(second_reader.id),
        json={"reaction": "dislike"},
    )
    assert second_reaction.status_code == 200
    assert second_reaction.json()["dislike_count"] == 1
    assert second_reaction.json()["author_reputation_score"] == 0

    second_reaction_switch = await client.put(
        f"/api/v1/public/forum/comments/{comment_id}/reaction",
        headers=_auth_headers(second_reader.id),
        json={"reaction": "like"},
    )
    assert second_reaction_switch.status_code == 200
    assert second_reaction_switch.json()["like_count"] == 2
    assert second_reaction_switch.json()["dislike_count"] == 0
    assert second_reaction_switch.json()["author_reputation_score"] == 2

    comment_list = await client.get(
        f"/api/v1/public/forum/posts/{high_post_id}/comments",
        headers=_auth_headers(first_reader.id),
    )
    assert comment_list.status_code == 200
    assert comment_list.json()["items"][0]["reaction"] == "like"
    assert comment_list.json()["items"][0]["can_edit"] is False

    for reader, book in ((first_reader, high_book), (second_reader, low_book)):
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

    high_assignment = await client.post(
        f"/api/v1/books/{high_book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": first_reader.email,
            "task_label": "High-rated proof pass",
            "window_days": 7,
            "reward_points": 20,
            "required_feedback_item_count": 1,
        },
    )
    assert high_assignment.status_code == 201
    high_assignment_id = high_assignment.json()["id"]

    low_assignment = await client.post(
        f"/api/v1/books/{low_book.id}/beta-reads",
        headers=_auth_headers(author.id),
        json={
            "reader_email": second_reader.email,
            "task_label": "Low-rated proof pass",
            "window_days": 7,
            "reward_points": 20,
            "required_feedback_item_count": 1,
        },
    )
    assert low_assignment.status_code == 201
    low_assignment_id = low_assignment.json()["id"]

    for assignment_id, reader_id, body_text in (
        (high_assignment_id, first_reader.id, "The reveal hit hard and the opening moved quickly."),
        (low_assignment_id, second_reader.id, "I understood the setup, but the opening felt distant."),
    ):
        feedback_response = await client.post(
            f"/api/v1/beta-reads/{assignment_id}/feedback-items",
            headers=_auth_headers(reader_id),
            json={"kind": "favorite", "chapter_number": 1, "body": body_text},
        )
        assert feedback_response.status_code == 201

    high_submit = await client.post(
        f"/api/v1/beta-reads/{high_assignment_id}/submit-feedback",
        headers=_auth_headers(first_reader.id),
        json={
            "final_feedback": "Strong hook, strong control, and I wanted the next chapter immediately.",
            "final_rating": 4.5,
        },
    )
    assert high_submit.status_code == 200
    assert high_submit.json()["awarded_points"] == 30

    low_submit = await client.post(
        f"/api/v1/beta-reads/{low_assignment_id}/submit-feedback",
        headers=_auth_headers(second_reader.id),
        json={
            "final_feedback": "The premise is there, but I kept waiting for the tension to arrive.",
            "final_rating": 1.5,
        },
    )
    assert low_submit.status_code == 200
    assert low_submit.json()["awarded_points"] == 20

    forum_list = await client.get("/api/v1/public/forum/posts")
    assert forum_list.status_code == 200
    items = forum_list.json()["items"]
    assert items[0]["book_id"] == str(high_book.id)
    assert items[0]["author_username"] == author.username
    assert items[0]["comment_count"] == 1
    assert items[0]["rating_summary"]["average_rating"] == 4.5
    assert items[1]["book_id"] == str(low_book.id)
    assert items[1]["rating_summary"]["average_rating"] == 1.5

    search_list = await client.get("/api/v1/public/forum/posts", params={"q": "Shadow Glass"})
    assert search_list.status_code == 200
    assert len(search_list.json()["items"]) == 1
    assert search_list.json()["items"][0]["id"] == low_post_id

    author_profile = await client.get(f"/api/v1/public/users/{author.username}")
    assert author_profile.status_code == 200
    author_profile_payload = author_profile.json()
    assert author_profile_payload["username"] == author.username
    assert author_profile_payload["current_project"]["title"] == "Sky Harbor"
    assert author_profile_payload["current_project"]["genre"] == "Fantasy"
    assert author_profile_payload["current_project"]["progress_words"] == 20000
    assert author_profile_payload["current_project"]["source"] == "forum"
    assert author_profile_payload["current_project"]["forum_post_id"] == str(high_post_id)

    seeker_profile = await client.get(f"/api/v1/public/users/{seeker.username}")
    assert seeker_profile.status_code == 200
    seeker_profile_payload = seeker_profile.json()
    assert seeker_profile_payload["reputation_score"] == 2
    assert seeker_profile_payload["reputation_likes_received"] == 2
    assert seeker_profile_payload["reputation_dislikes_received"] == 0
    assert seeker_profile_payload["forum_comment_count"] == 1

    author_ledger_entries = (
        await db.execute(
            select(PointLedgerEntry).where(PointLedgerEntry.user_id == author.id)
        )
    ).scalars().all()
    assert len(author_ledger_entries) == 1
    assert author_ledger_entries[0].points_delta == 3


@pytest.mark.asyncio
async def test_public_profile_requires_public_presence_and_skips_private_only_project_fallback(client, db):
    private_only_user = await _create_user(db, email="private-only@lorevia.test", tier="author")
    private_only_book = await _create_book(db, author_id=private_only_user.id, title="Hidden Lantern")

    no_presence_profile = await client.get(f"/api/v1/public/users/{private_only_user.username}")
    assert no_presence_profile.status_code == 404

    public_post_response = await client.post(
        "/api/v1/public/forum/posts",
        headers=_auth_headers(private_only_user.id),
        json={
            "book_id": str(private_only_book.id),
            "headline": "Looking for careful fantasy beta readers.",
            "body": "I want honest feedback on pacing, chapter endings, and whether the emotional beats feel earned.",
            "desired_beta_reader_count": 3,
            "allow_contact_requests": True,
        },
    )
    assert public_post_response.status_code == 201

    public_profile = await client.get(f"/api/v1/public/users/{private_only_user.username}")
    assert public_profile.status_code == 200
    assert public_profile.json()["current_project"]["title"] == "Hidden Lantern"
    assert public_profile.json()["current_project"]["description"] == (
        "I want honest feedback on pacing, chapter endings, and whether the emotional beats feel earned."
    )
    assert public_profile.json()["current_project"]["source"] == "forum"

    public_book_user = await _create_user(db, email="public-book@lorevia.test", tier="author")
    public_book = Book(
        user_id=public_book_user.id,
        title="Open Atlas",
        author="M. Author",
        genre="Science Fiction",
        format="manual",
        work_type="novel",
        s3_key="books/open-atlas.txt",
        mode="author",
        status="ready",
        total_chapters=1,
        is_public=True,
        public_description="A public-facing serial project.",
    )
    db.add(public_book)
    await db.commit()
    await db.refresh(public_book)

    db.add(
        Chapter(
            book_id=public_book.id,
            number=1,
            title="Open Atlas Opening",
            s3_key="chapters/open-atlas-1.txt",
            word_count=12000,
            processed=True,
        )
    )
    await db.commit()

    public_book_profile = await client.get(f"/api/v1/public/users/{public_book_user.username}")
    assert public_book_profile.status_code == 200
    payload = public_book_profile.json()
    assert payload["current_project"]["title"] == "Open Atlas"
    assert payload["current_project"]["genre"] == "Science Fiction"
    assert payload["current_project"]["progress_words"] == 12000
    assert payload["current_project"]["source"] == "public_book"
    assert payload["current_project"]["public_book_id"] == str(public_book.id)
