import pytest

from app.models.book import Book
from app.models.intelligence import WorldElement
from app.models.user import User
from app.utils.world_building_utils import (
    classify_world_intent,
    create_world_building_documents,
    detect_integration_analysis,
    detect_world_gaps,
)


def test_classify_world_intent_prefers_integration_for_story_use_queries():
    assert classify_world_intent("How can I use the northern kingdom better?") == "story_integration"
    assert classify_world_intent("What gaps am I missing in the magic system?") == "gap_detection"


@pytest.mark.asyncio
async def test_detect_world_gap_and_integration_payloads(db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_utils.download_book", fake_download_book)

    user = User(email="world-utils@lorevia.app", username="worldutils", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="World Test", format="pdf", s3_key="world/test.pdf", status="ready")
    db.add(book)
    await db.flush()
    db.add(
        WorldElement(
            book_id=book.id,
            source_scope="story",
            element_type="geography",
            name="Northreach",
            description="Northreach is a desert capital built around a dry salt basin.",
            usage_count=3,
            analysis_metadata={"chapter_number": 2, "chapter_title": "Salt Market"},
        )
    )
    await db.flush()
    await create_world_building_documents(
        db,
        book=book,
        user_id=user.id,
        documents=[
            {
                "title": "World Bible",
                "source_name": "world-bible.txt",
                "text": "Northreach is a frozen capital ringed by ice gates.\n\nThe Ember Rite is the kingdom's winter ritual.",
                "html": None,
            }
        ],
    )
    await db.commit()

    gap_payload = await detect_world_gaps(db, book)
    integration_payload = await detect_integration_analysis(db, book)

    assert gap_payload["mode"] == "gap_detection"
    assert any(group["key"] == "story_conflicts" for group in gap_payload["gap_groups"])
    assert any(item["title"].startswith("Northreach conflicts") for item in gap_payload["priority_gaps"])
    assert integration_payload["mode"] == "story_integration"
    assert any(item["element_name"] == "The Ember Rite" for item in integration_payload["integration_opportunities"])
