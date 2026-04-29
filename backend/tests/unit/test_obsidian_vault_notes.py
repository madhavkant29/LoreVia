"""Unit tests for Obsidian vault note persistence helpers."""

import uuid

import pytest

from app.models.book import Book
from app.models.user import User
from app.utils.book_utils import list_obsidian_vault_notes, load_obsidian_vault_overrides, save_obsidian_vault_note


@pytest.mark.asyncio
async def test_save_list_and_load_obsidian_vault_notes(db):
    user = User(email="vault-notes@lorevia.app", username="vault-notes", password_hash="hash")
    book = Book(
        user_id=user.id,
        title="Vault Story",
        format="pdf",
        s3_key="books/vault-story.pdf",
        status="ready",
    )
    db.add_all([user, book])
    await db.commit()

    path = "LoreVia Export - Vault-Story/Characters/Aria.md"
    saved = await save_obsidian_vault_note(
        db,
        book=book,
        user_id=user.id,
        path=path,
        content="# Aria\n\nEdited content",
    )

    assert saved["persisted"] is True
    assert saved["path"] == path
    assert saved["content"] == "# Aria\n\nEdited content"

    notes = await list_obsidian_vault_notes(db, book, user.id)
    assert len(notes) == 1
    assert notes[0]["path"] == path
    assert notes[0]["content"] == "# Aria\n\nEdited content"

    overrides = await load_obsidian_vault_overrides(db, book, user.id)
    assert overrides == {path: "# Aria\n\nEdited content"}


@pytest.mark.asyncio
async def test_save_obsidian_vault_note_updates_existing_row(db):
    user = User(email="vault-notes-update@lorevia.app", username="vault-notes-update", password_hash="hash")
    book = Book(
        user_id=user.id,
        title="Vault Story",
        format="pdf",
        s3_key="books/vault-story.pdf",
        status="ready",
    )
    db.add_all([user, book])
    await db.commit()

    path = "LoreVia Export - Vault-Story/Characters/Aria.md"
    first = await save_obsidian_vault_note(db, book=book, user_id=user.id, path=path, content="first version")
    second = await save_obsidian_vault_note(db, book=book, user_id=user.id, path=path, content="second version")

    assert first["persisted"] is True
    assert second["persisted"] is True
    assert second["content"] == "second version"

    notes = await list_obsidian_vault_notes(db, book, user.id)
    assert len(notes) == 1
    assert notes[0]["content"] == "second version"
