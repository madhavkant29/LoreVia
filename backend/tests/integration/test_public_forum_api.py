from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest

from app.api.v1.routes import public
from app.core.security import create_access_token
from app.models.book import Book, Chapter
from app.models.progress import ReadingProgress
from app.models.user import User


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Cookie": f"lorevia_access_token={create_access_token(str(user_id))}"}


async def _create_user(db, *, email: str, tier: str, created_at: datetime | None = None) -> User:
    user = User(
        email=email,
        username=email.split("@", 1)[0],
        password_hash="hashed",
        tier=tier,
        created_at=created_at,
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
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "public", raising=False)


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
    assert high_submit.json()["final_rating"] == 4.5
    assert high_submit.json()["book_average_rating"] == 4.5
    assert high_submit.json()["book_rating_count"] == 1

    low_submit = await client.post(
        f"/api/v1/beta-reads/{low_assignment_id}/submit-feedback",
        headers=_auth_headers(second_reader.id),
        json={
            "final_feedback": "The premise is there, but I kept waiting for the tension to arrive.",
            "final_rating": 1.5,
        },
    )
    assert low_submit.status_code == 200
    assert low_submit.json()["final_rating"] == 1.5
    assert low_submit.json()["book_average_rating"] == 1.5
    assert low_submit.json()["book_rating_count"] == 1

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
        source_kind="user_public_share",
        public_share_status="approved",
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


@pytest.mark.asyncio
async def test_public_share_requires_admin_approval_before_author_book_surfaces(client, db):
    author = await _create_user(db, email="share-author@lorevia.test", tier="author")
    admin = await _create_user(db, email="share-admin@lorevia.test", tier="admin")
    book = await _create_book(db, author_id=author.id, title="Approval Gate")

    request_response = await client.post(
        f"/api/v1/public/shared-books/{book.id}/publish",
        headers=_auth_headers(author.id),
        json={"confirm_public_share": True, "description": "A curated public sample request."},
    )
    assert request_response.status_code == 200
    request_payload = request_response.json()
    assert request_payload["visibility"] == "private"
    assert request_payload["approval_status"] == "pending"

    pending_response = await client.get(
        "/api/v1/admin/public-shares/pending",
        headers=_auth_headers(admin.id),
    )
    assert pending_response.status_code == 200
    assert pending_response.json()[0]["book_id"] == str(book.id)

    public_list_before = await client.get("/api/v1/public/books")
    assert public_list_before.status_code == 200
    assert all(item["id"] != str(book.id) for item in public_list_before.json())

    direct_before = await client.get(f"/api/v1/public/books/{book.id}")
    assert direct_before.status_code == 404

    approval_response = await client.put(
        f"/api/v1/admin/public-shares/{book.id}",
        headers=_auth_headers(admin.id),
        json={"approved": True},
    )
    assert approval_response.status_code == 200
    assert approval_response.json()["approval_status"] == "approved"
    assert approval_response.json()["visibility"] == "public"

    public_list_after = await client.get("/api/v1/public/books")
    assert public_list_after.status_code == 200
    assert any(item["id"] == str(book.id) for item in public_list_after.json())

    direct_after = await client.get(f"/api/v1/public/books/{book.id}")
    assert direct_after.status_code == 200
    assert direct_after.json()["id"] == str(book.id)


@pytest.mark.asyncio
async def test_free_users_cannot_open_public_discussions_or_submit_public_samples(client, db):
    paid_author = await _create_user(db, email="paid-forum-author@lorevia.test", tier="author")
    expired_trial_at = datetime.now(UTC) - timedelta(days=14)
    free_author = await _create_user(db, email="free-forum-author@lorevia.test", tier="free", created_at=expired_trial_at)
    free_reader = await _create_user(db, email="free-forum-reader@lorevia.test", tier="free")

    paid_book = await _create_book(db, author_id=paid_author.id, title="Paid Harbor")
    free_book = await _create_book(db, author_id=free_author.id, title="Free Harbor")

    paid_post = await client.post(
        "/api/v1/public/forum/posts",
        headers=_auth_headers(paid_author.id),
        json={
            "book_id": str(paid_book.id),
            "headline": "Paid author seeking outside eyes.",
            "body": "Looking for honest reactions on pacing and hook strength.",
            "desired_beta_reader_count": 2,
            "allow_contact_requests": True,
        },
    )
    assert paid_post.status_code == 201

    blocked_post = await client.post(
        "/api/v1/public/forum/posts",
        headers=_auth_headers(free_author.id),
        json={
            "book_id": str(free_book.id),
            "headline": "Free author seeking outside eyes.",
            "body": "Trying to open a public discussion from the free plan.",
            "desired_beta_reader_count": 2,
            "allow_contact_requests": True,
        },
    )
    assert blocked_post.status_code == 403
    assert blocked_post.json()["detail"] == "Opening a public discussion requires Trial, Author, or Architect access."

    blocked_share = await client.post(
        f"/api/v1/public/shared-books/{free_book.id}/publish",
        headers=_auth_headers(free_author.id),
        json={"confirm_public_share": True, "description": "Trying to request a public sample on free."},
    )
    assert blocked_share.status_code == 403
    assert blocked_share.json()["detail"] == "Submitting a public sample requires Trial, Author, or Architect access."

    comment_response = await client.post(
        f"/api/v1/public/forum/posts/{paid_post.json()['id']}/comments",
        headers=_auth_headers(free_reader.id),
        json={"body": "Free readers can still comment and engage."},
    )
    assert comment_response.status_code == 201

    interest_response = await client.post(
        f"/api/v1/public/forum/posts/{paid_post.json()['id']}/interests",
        headers=_auth_headers(free_reader.id),
        json={"message": "Free readers can still offer to beta read."},
    )
    assert interest_response.status_code == 201


@pytest.mark.asyncio
async def test_trial_users_can_open_discussions_and_submit_public_samples(client, db):
    trial_author = await _create_user(db, email="trial-forum-author@lorevia.test", tier="free")
    private_book = await _create_book(db, author_id=trial_author.id, title="Trial Harbor")

    discussion_response = await client.post(
        "/api/v1/public/forum/posts",
        headers=_auth_headers(trial_author.id),
        json={
            "book_id": str(private_book.id),
            "headline": "Trial author opening a discussion.",
            "body": "Looking for early reactions while the manuscript is still in active revision.",
            "desired_beta_reader_count": 3,
            "allow_contact_requests": True,
        },
    )
    assert discussion_response.status_code == 201

    public_share_book = await _create_book(db, author_id=trial_author.id, title="Trial Public Sample")
    publish_response = await client.post(
        f"/api/v1/public/shared-books/{public_share_book.id}/publish",
        headers=_auth_headers(trial_author.id),
        json={"confirm_public_share": True, "description": "Trial user requesting a public sample."},
    )
    assert publish_response.status_code == 200


@pytest.mark.asyncio
async def test_general_public_discussions_are_open_to_signed_in_users_and_visible_on_profiles(client, db):
    member = await _create_user(db, email="general-forum-member@lorevia.test", tier="free")

    create_response = await client.post(
        "/api/v1/public/forum/posts",
        headers=_auth_headers(member.id),
        json={
            "thread_type": "general",
            "headline": "How do you keep dialogue tense in quiet scenes?",
            "body": "Looking for practical advice on preserving friction during low-action chapters without making the dialogue feel artificial.",
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["thread_type"] == "general"
    assert payload["book_id"] is None
    assert payload["allow_contact_requests"] is False

    forum_list = await client.get("/api/v1/public/forum/posts")
    assert forum_list.status_code == 200
    assert any(item["thread_type"] == "general" for item in forum_list.json()["items"])

    profile_response = await client.get(f"/api/v1/public/users/{member.username}")
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["forum_post_count"] == 1
    assert profile["posts"][0]["thread_type"] == "general"


@pytest.mark.asyncio
async def test_public_forum_beta_mode_is_read_only(client, db, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "beta", raising=False)

    author = await _create_user(db, email="beta-mode-author@lorevia.test", tier="author")
    book = await _create_book(db, author_id=author.id, title="Read Only Harbor")

    create_response = await client.post(
        "/api/v1/public/forum/posts",
        headers=_auth_headers(author.id),
        json={
            "book_id": str(book.id),
            "headline": "Looking for readers on a harbor fantasy.",
            "body": "Seeking feedback on whether the opening tension lands early and clearly enough for first-time readers.",
            "desired_beta_reader_count": 3,
            "allow_contact_requests": True,
        },
    )
    assert create_response.status_code == 403

    forum_list = await client.get("/api/v1/public/forum/posts")
    assert forum_list.status_code == 200
    assert all(item["title"] != "Read Only Harbor" for item in forum_list.json()["items"])
