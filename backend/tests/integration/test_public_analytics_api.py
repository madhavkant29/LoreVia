from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.security import create_access_token
from app.models.book import Book, Chapter
from app.models.user import User


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Cookie": f"lorevia_access_token={create_access_token(str(user_id))}"}


async def _create_user(db, *, email: str, tier: str) -> User:
    user = User(
        email=email,
        username=email.split("@", 1)[0],
        password_hash="hashed",
        tier=tier,
        created_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_public_book(
    db, *, author_id: uuid.UUID, title: str, is_public: bool = True
) -> Book:
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
        total_chapters=2,
        is_public=is_public,
        source_kind="user_public_share",
        public_status="published" if is_public else "draft",
        public_visibility="public" if is_public else "private",
        moderation_status="clean",
        public_share_status="approved" if is_public else "not_requested",
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    db.add_all(
        [
            Chapter(
                book_id=book.id,
                number=1,
                title=f"{title} Opening",
                s3_key=f"chapters/{title.lower().replace(' ', '-')}-1.txt",
                word_count=1200,
                processed=True,
            ),
            Chapter(
                book_id=book.id,
                number=2,
                title=f"{title} Next",
                s3_key=f"chapters/{title.lower().replace(' ', '-')}-2.txt",
                word_count=900,
                processed=True,
            ),
        ]
    )
    await db.commit()
    return book


@pytest.fixture(autouse=True)
def _enable_public_mode(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_MODE_ENABLED", True, raising=False)


@pytest.mark.asyncio
async def test_public_analytics_endpoint_tracks_views_and_surfaces_aggregates(client, db):
    author = await _create_user(db, email="public-analytics-author@lorevia.test", tier="author")
    book = await _create_public_book(db, author_id=author.id, title="Public Analytics Book")

    first_book_view = await client.post(
        f"/api/v1/public/books/{book.id}/analytics/view",
        headers={"user-agent": "integration-suite/1.0", "x-forwarded-for": "203.0.113.9"},
        json={"event_type": "book_view"},
    )
    assert first_book_view.status_code == 204

    duplicate_book_view = await client.post(
        f"/api/v1/public/books/{book.id}/analytics/view",
        headers={"user-agent": "integration-suite/1.0", "x-forwarded-for": "203.0.113.9"},
        json={"event_type": "book_view"},
    )
    assert duplicate_book_view.status_code == 204

    chapter_view = await client.post(
        f"/api/v1/public/books/{book.id}/analytics/view",
        headers={"user-agent": "integration-suite/1.0", "x-forwarded-for": "198.51.100.12"},
        json={"event_type": "chapter_view", "chapter_number": 1},
    )
    assert chapter_view.status_code == 204

    public_book = await client.get(f"/api/v1/public/books/{book.id}")
    assert public_book.status_code == 200
    assert public_book.json()["analytics"]["book_view_count"] == 1
    assert public_book.json()["analytics"]["chapter_view_count"] == 1
    assert public_book.json()["analytics"]["unique_reader_count_30d"] == 2

    public_profile = await client.get(f"/api/v1/public/users/{author.username}")
    assert public_profile.status_code == 200
    assert public_profile.json()["public_analytics"]["total_book_views"] == 1
    assert public_profile.json()["public_analytics"]["total_chapter_views"] == 1
    assert public_profile.json()["public_analytics"]["total_unique_readers_30d"] == 2
    assert public_profile.json()["public_books_count"] >= 1
    assert any(item["id"] == str(book.id) for item in public_profile.json()["public_books"])

    uploads_catalog = await client.get("/api/v1/public/uploads")
    assert uploads_catalog.status_code == 200
    upload_items = uploads_catalog.json()
    assert any(item["id"] == str(book.id) for item in upload_items)

    uploads_overview = await client.get("/api/v1/public/analytics")
    assert uploads_overview.status_code == 200
    assert uploads_overview.json()["total_public_books"] >= 1
    assert uploads_overview.json()["total_authors"] >= 1
    assert uploads_overview.json()["total_visible_chapters"] >= 2
    assert any(item["id"] == str(book.id) for item in uploads_overview.json()["recent_uploads"])


@pytest.mark.asyncio
async def test_public_analytics_endpoint_rejects_unpublished_books(client, db):
    author = await _create_user(db, email="private-analytics-author@lorevia.test", tier="author")
    private_book = await _create_public_book(
        db, author_id=author.id, title="Private Draft", is_public=False
    )

    response = await client.post(
        f"/api/v1/public/books/{private_book.id}/analytics/view",
        headers={"user-agent": "integration-suite/1.0", "x-forwarded-for": "203.0.113.9"},
        json={"event_type": "book_view"},
    )

    assert response.status_code == 404
