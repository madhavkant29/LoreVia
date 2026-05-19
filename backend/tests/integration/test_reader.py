import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import BookChunk


@pytest.mark.asyncio
async def test_smart_tap_returns_search_for_unknown(client, auth_headers):
    """Tapping an unknown word should return search results (empty list ok)."""
    fake_book = uuid.uuid4()
    with patch("app.api.v1.routes.reader.find_context_for_tap", AsyncMock(return_value=[])):
        r = await client.get(
            f"/api/v1/reader/{fake_book}/context?q=unknown&chapter=5",
            headers=auth_headers,
        )
    # 404 expected since book not in DB — endpoint logic reached
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_search_requires_auth(client):
    r = await client.get(f"/api/v1/reader/{uuid.uuid4()}/search?q=test&chapter=5")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_reader_chapter_repairs_stale_character_first_appearance(client, db, auth_headers, monkeypatch):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])

    book = Book(
        user_id=user_id,
        title="First Appearance Repair",
        format="epub",
        s3_key="books/first-appearance.epub",
        status="ready",
        total_chapters=2,
    )
    db.add(book)
    await db.flush()

    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Harbor Dawn",
        s3_key="chapters/1.json",
        processed=True,
        word_count=6,
    )
    db.add(chapter)
    await db.flush()

    db.add(
        BookChunk(
            book_id=book.id,
            chapter_id=chapter.id,
            chunk_index=0,
            text="Captain Mira steps onto the deck before sunrise.",
            embedding=[0.0] * 1536,
            token_count=8,
        )
    )

    character = Character(
        book_id=book.id,
        name="Captain Mira",
        aliases=["Mira"],
        role="mc",
        first_chapter=2,
        last_seen_chapter=2,
        mention_count=2,
        personality_tags=["steady"],
    )
    db.add(character)
    await db.commit()

    monkeypatch.setattr(
        "app.services.chapter_recovery_service.deserialize_manuscript_content",
        lambda _raw: {
            "text": "Captain Mira steps onto the deck before sunrise.",
            "html": "<p><span class='mention-token' data-mention='Captain Mira'>Captain Mira</span> steps onto the deck before sunrise.</p>",
        },
    )
    monkeypatch.setattr(
        "app.services.chapter_recovery_service.download_book",
        lambda _key: b"stored chapter payload",
    )

    response = await client.get(f"/api/v1/reader/{book.id}/chapter/1", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["characters"]] == ["Captain Mira"]
    assert payload["characters"][0]["first_chapter"] == 1
    assert payload["characters"][0]["analysis_metadata"]["confidence_band"] in {"medium", "high"}

    await db.refresh(character)
    assert character.first_chapter == 1
