from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.routes import manuscript
from app.models.book import Book, Chapter, ChapterVersion
from app.models.user import User


@pytest.mark.asyncio
async def test_restore_version_dispatches_async(client, db, auth_headers, monkeypatch):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])
    user = await db.get(User, user_id)
    assert user is not None
    user.tier = "author"

    book = Book(
        user_id=user_id,
        title="Async Restore",
        format="docx",
        s3_key="books/async-restore.docx",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Chapter 1",
        s3_key="chapters/async-restore/1.txt",
        processed=True,
    )
    db.add(chapter)
    await db.flush()
    version = ChapterVersion(
        book_id=book.id,
        chapter_id=chapter.id,
        chapter_number=1,
        title="Chapter 1",
        s3_key="versions/async-restore/1.txt",
        snapshot_kind="manual",
    )
    db.add(version)
    await db.commit()
    book_id = book.id

    async def _fake_restore(_db, *, book, version_id):
        assert book.id == book_id
        assert version_id == version.id
        return {
            "chapter_number": 1,
            "title": "Chapter 1",
            "text": "Restored chapter text.",
            "html": "<p>Restored chapter text.</p>",
        }

    dispatched: dict[str, object] = {}

    class _Task:
        @staticmethod
        def apply_async(*args, **kwargs):
            dispatched["args"] = args
            dispatched["kwargs"] = kwargs
            return SimpleNamespace(id="restore-task-123")

    monkeypatch.setattr(manuscript, "restore_chapter_version", _fake_restore)
    monkeypatch.setattr(manuscript, "process_chapter_task", _Task())

    response = await client.post(
        f"/api/v1/books/{book.id}/chapter-versions/{version.id}/restore",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "restore_queued"
    assert payload["task_id"] == "restore-task-123"
    assert dispatched["kwargs"] == {
        "args": [str(book.id), 1, str(version.id)],
        "queue": "extraction",
    }

    await db.refresh(version)
    assert version.restore_status == "processing"
    assert version.restore_task_id == "restore-task-123"
    assert version.restore_error is None
    assert version.restore_started_at is not None
    assert version.restore_completed_at is None

    status_response = await client.get(
        f"/api/v1/books/{book.id}/chapter-versions/{version.id}/restore-status",
        headers=auth_headers,
    )

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["restore_status"] == "processing"
    assert status_payload["restore_task_id"] == "restore-task-123"
