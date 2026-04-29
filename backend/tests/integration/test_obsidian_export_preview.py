"""Integration tests for the Obsidian export preview endpoint."""

import uuid

import pytest

from app.api.deps.auth import get_current_user
from app.main import app
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, PlotThread, WikiEntry
from app.models.user import User


async def _build_obsidian_preview_book(db):
    user = User(
        email="obsidian-preview@lorevia.app",
        username="obsidian-preview",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Preview Story",
        format="pdf",
        s3_key="books/preview-story.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    aria = Character(
        book_id=book.id,
        name="Aria",
        first_chapter=1,
        mention_count=5,
        trait_state={},
        personality_tags=["curious"],
        motivations=["find the truth"],
        fears=["losing Blaire"],
    )
    blaire = Character(
        book_id=book.id,
        name="Blaire",
        first_chapter=2,
        mention_count=3,
        trait_state={},
        personality_tags=["calm"],
    )
    db.add_all([aria, blaire])
    await db.flush()

    chapter_one = Chapter(
        book_id=book.id,
        number=1,
        title="Arrival",
        s3_key="chapters/1.txt",
    )
    db.add(chapter_one)
    await db.flush()
    db.add(
        ChapterSummary(
            chapter_id=chapter_one.id,
            mode="short",
            content="Aria reaches the capital.",
            key_events=[
                {
                    "event": "Aria arrives",
                    "description": "Aria arrives in the capital with Blaire.",
                    "importance": 9,
                    "involved_characters": ["Aria", "Blaire"],
                }
            ],
        )
    )
    db.add(
        PlotThread(
            book_id=book.id,
            title="The Hidden Map",
            status="ongoing",
            importance=8,
            introduced_at=1,
            note="Aria and Blaire pursue the map.",
            character_ids=["Aria", "Blaire"],
        )
    )
    db.add(
        WikiEntry(
            book_id=book.id,
            entry_type="location",
            name="The Capital",
            description="Aria and Blaire meet in the capital.",
            first_mention=1,
            related_char_ids=[str(aria.id), str(blaire.id)],
        )
    )
    await db.commit()
    return user, book


@pytest.mark.asyncio
async def test_obsidian_bible_preview_returns_folder_manifest(client, db):
    user, book = await _build_obsidian_preview_book(db)

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    try:
        response = await client.get(f"/api/v1/books/{book.id}/export/character-bible/preview")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["root_folder"] == "LoreVia Export - Preview-Story"
    assert payload["files"][0]["path"].endswith("000 - Index.md")
    assert any(file["path"].endswith("Characters/Aria.md") for file in payload["files"])
    assert any(file["path"].endswith("Major Events/Aria-arrives.md") for file in payload["files"])
    assert any("[[Characters/Blaire|Blaire]]" in file["content"] for file in payload["files"] if file["path"].endswith("Characters/Aria.md"))


@pytest.mark.asyncio
async def test_obsidian_bible_notes_save_is_visible_in_preview_and_notes_list(client, db):
    user, book = await _build_obsidian_preview_book(db)

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    try:
        preview_before = await client.get(f"/api/v1/books/{book.id}/export/character-bible/preview")
        assert preview_before.status_code == 200
        baseline = preview_before.json()
        target_path = next(file["path"] for file in baseline["files"] if file["path"].endswith("Characters/Aria.md"))

        save_response = await client.put(
            f"/api/v1/books/{book.id}/export/character-bible/notes",
            json={"path": target_path, "content": "# Aria\n\nEdited in app"},
        )
        assert save_response.status_code == 200
        assert save_response.json()["persisted"] is True

        preview_after = await client.get(f"/api/v1/books/{book.id}/export/character-bible/preview")
        assert preview_after.status_code == 200
        updated = preview_after.json()
        updated_aria = next(file for file in updated["files"] if file["path"] == target_path)
        assert "Edited in app" in updated_aria["content"]

        notes_response = await client.get(f"/api/v1/books/{book.id}/export/character-bible/notes")
        assert notes_response.status_code == 200
        notes = notes_response.json()
        assert len(notes) == 1
        assert notes[0]["path"] == target_path
        assert "Edited in app" in notes[0]["content"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
