from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest

from app.models.book import Book, BookForumPost, Chapter, PublicBookRanking
from app.models.user import User


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


async def _create_book(
    db,
    *,
    author_id: uuid.UUID,
    title: str,
    is_public: bool,
    public_status: str,
    hidden_at: datetime | None = None,
    source_kind: str = "single_upload",
    public_share_status: str = "not_requested",
) -> Book:
    now = datetime.now(UTC)
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
        is_public=is_public,
        source_kind=source_kind,
        public_status=public_status,
        public_slug=title.lower().replace(" ", "-"),
        public_description=f"{title} description",
        public_visibility="public" if is_public else "private",
        public_share_status=public_share_status,
        published_at=now - timedelta(days=2),
        public_updated_at=now - timedelta(hours=6),
        hidden_at=hidden_at,
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
            word_count=1200,
            processed=True,
        )
    )
    await db.commit()
    return book


@pytest.fixture(autouse=True)
def _enable_public_surfaces(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", True, raising=False)
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "public", raising=False)


@pytest.mark.asyncio
async def test_ranked_public_uploads_endpoint_returns_ranked_visible_books(client, db):
    author = await _create_user(db, email="uploads-rankings@lorevia.test", tier="author")
    visible_book = await _create_book(
        db,
        author_id=author.id,
        title="Ember Harbor",
        is_public=True,
        public_status="published",
        source_kind="user_public_share",
        public_share_status="approved",
    )
    hidden_book = await _create_book(
        db,
        author_id=author.id,
        title="Shadow Vault",
        is_public=True,
        public_status="published",
        hidden_at=datetime.now(UTC),
        source_kind="user_public_share",
        public_share_status="approved",
    )
    snapshot_date = datetime.now(UTC).date()
    db.add_all([
        PublicBookRanking(
            book_id=visible_book.id,
            surface="creator_uploads",
            ranking_key="most_popular",
            time_window="monthly",
            snapshot_date=snapshot_date,
            rank_position=1,
            score=412.5,
            primary_timestamp=visible_book.public_updated_at,
        ),
        PublicBookRanking(
            book_id=hidden_book.id,
            surface="creator_uploads",
            ranking_key="most_popular",
            time_window="monthly",
            snapshot_date=snapshot_date,
            rank_position=2,
            score=380.0,
            primary_timestamp=hidden_book.public_updated_at,
        ),
    ])
    await db.commit()

    response = await client.get("/api/v1/public/rankings/uploads?ranking=most_popular&time_window=monthly")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Ember Harbor"
    assert payload["items"][0]["ranking"]["position"] == 1
    assert payload["items"][0]["ranking"]["ranking_key"] == "most_popular"
    assert payload["items"][0]["ranking"]["time_window"] == "monthly"


@pytest.mark.asyncio
async def test_ranked_beta_novels_endpoint_returns_open_ranked_threads_only(client, db):
    author = await _create_user(db, email="beta-rankings@lorevia.test", tier="author")
    ranked_book = await _create_book(db, author_id=author.id, title="Sky Citadel", is_public=False, public_status="draft")
    closed_book = await _create_book(db, author_id=author.id, title="Glass Current", is_public=False, public_status="draft")
    snapshot_date = datetime.now(UTC).date()

    open_post = BookForumPost(
        book_id=ranked_book.id,
        author_user_id=author.id,
        thread_type="novel",
        headline="Need beta readers for Sky Citadel",
        body="Looking for feedback on pacing, clarity, and continuity in a private fantasy manuscript.",
        desired_beta_reader_count=5,
        allow_contact_requests=True,
        status="open",
    )
    closed_post = BookForumPost(
        book_id=closed_book.id,
        author_user_id=author.id,
        thread_type="novel",
        headline="Need beta readers for Glass Current",
        body="Looking for worldbuilding and hook feedback.",
        desired_beta_reader_count=3,
        allow_contact_requests=True,
        status="closed",
    )
    db.add_all([open_post, closed_post])
    await db.commit()
    await db.refresh(open_post)

    db.add_all([
        PublicBookRanking(
            book_id=ranked_book.id,
            surface="beta_novels",
            ranking_key="top_rated",
            time_window="monthly",
            snapshot_date=snapshot_date,
            rank_position=1,
            score=501.0,
            primary_timestamp=ranked_book.public_updated_at,
        ),
        PublicBookRanking(
            book_id=closed_book.id,
            surface="beta_novels",
            ranking_key="top_rated",
            time_window="monthly",
            snapshot_date=snapshot_date,
            rank_position=2,
            score=480.0,
            primary_timestamp=closed_book.public_updated_at,
        ),
    ])
    await db.commit()

    response = await client.get("/api/v1/public/rankings/beta-novels?ranking=top_rated&time_window=monthly")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["headline"] == "Need beta readers for Sky Citadel"
    assert payload["items"][0]["ranking"]["surface"] == "beta_novels"
    assert payload["items"][0]["ranking"]["position"] == 1
