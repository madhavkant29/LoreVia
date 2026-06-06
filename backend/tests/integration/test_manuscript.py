from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.v1.routes import manuscript
from app.models.book import Book, BookNote, Chapter, ChapterMedia, ChapterVersion, ManuscriptAnnotation, NovelScene, SceneVersion
from app.models.character import Character, CharacterMention, CharacterState
from app.models.intelligence import BookChunk, ChapterSummary
from app.models.progress import ReadingProgress
from app.services.editor_project_service import complete_rebuild_if_ready
from app.models.tag import CustomTag
from app.models.user import User
from app.utils.book_utils import serialize_manuscript_content


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


@pytest.mark.asyncio
async def test_remove_chapter_deletes_direct_artifacts_and_preserves_version_history(client, db, auth_headers, monkeypatch):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])
    user = await db.get(User, user_id)
    assert user is not None
    user.tier = "author"

    monkeypatch.setattr(
        "app.utils.book_utils.download_book",
        lambda _key: serialize_manuscript_content("Deleted chapter text.").encode("utf-8"),
    )
    monkeypatch.setattr("app.utils.book_utils.upload_binary", lambda key, _raw, _content_type=None: key)

    book = Book(
        user_id=user_id,
        title="Delete Chapter",
        format="manual",
        s3_key="books/delete-chapter.txt",
        status="processing",
        mode="author",
        total_chapters=2,
        is_editor_project=True,
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "extraction",
                "rebuild_run_id": "active-delete-test",
                "chapters_completed": 0,
                "chapters_total": 2,
            },
            "reprocess": {
                "last_started_at": "2026-06-01T00:00:00+00:00",
                "last_rebuild_run_id": "active-delete-test",
            },
        },
    )
    db.add(book)
    await db.flush()

    chapter_one = Chapter(
        book_id=book.id,
        number=1,
        title="Arrival",
        s3_key="chapters/delete-chapter/1.txt",
        processed=True,
    )
    chapter_two = Chapter(
        book_id=book.id,
        number=2,
        title="Departure",
        s3_key="chapters/delete-chapter/2.txt",
        processed=True,
    )
    character = Character(
        book_id=book.id,
        name="Nora",
        normalized_name="nora",
        first_chapter=1,
        last_seen_chapter=2,
        mention_count=2,
    )
    scene_id = uuid.uuid4()
    db.add_all([chapter_one, chapter_two, character])
    await db.flush()

    db.add_all(
        [
            BookChunk(book_id=book.id, chapter_id=chapter_two.id, chunk_index=0, text="Departure chunk."),
            ChapterSummary(chapter_id=chapter_two.id, mode="short", content="Departure summary."),
            ChapterVersion(
                book_id=book.id,
                chapter_id=chapter_two.id,
                chapter_number=2,
                title="Departure",
                s3_key="versions/delete-chapter/2.txt",
                snapshot_kind="manual",
            ),
            NovelScene(
                id=scene_id,
                book_id=book.id,
                chapter_id=chapter_two.id,
                chapter_number=2,
                title="Gate closes",
                body="Nora leaves.",
                path="scenes/chapter-02/gate-closes.md",
                status="assigned",
                sort_order=1,
            ),
            SceneVersion(
                book_id=book.id,
                scene_id=scene_id,
                chapter_id=chapter_two.id,
                chapter_number=2,
                scene_title="Gate closes",
                scene_path="scenes/chapter-02/gate-closes.md",
                s3_key="scene-versions/delete-chapter/gate-closes.txt",
                snapshot_kind="manual",
            ),
            ChapterMedia(
                book_id=book.id,
                chapter_id=chapter_two.id,
                marker="chapter-2-map",
                storage_key="chapter-media/delete-chapter/map.png",
            ),
            BookNote(
                user_id=user_id,
                book_id=book.id,
                chapter_number=2,
                title="Cut note",
                body="This belongs to the deleted chapter.",
            ),
            ManuscriptAnnotation(
                user_id=user_id,
                book_id=book.id,
                chapter_number=2,
                quote="Nora leaves.",
                comment="Revise this.",
            ),
            CharacterMention(
                book_id=book.id,
                chapter_number=1,
                raw_name="Nora",
                normalized_name="nora",
                matched_character_id=character.id,
            ),
            CharacterMention(
                book_id=book.id,
                chapter_number=2,
                raw_name="Nora",
                normalized_name="nora",
                matched_character_id=character.id,
            ),
            CharacterState(character_id=character.id, at_chapter=2, trait_snapshot={"mood": "resolved"}),
            CustomTag(
                book_id=book.id,
                created_by_user_id=user_id,
                entity_type="chapter",
                entity_id=chapter_two.id,
                tag_name="cut-candidate",
            ),
            ReadingProgress(
                user_id=user_id,
                book_id=book.id,
                current_chapter=2,
                scroll_pct=42,
                chapters_read=[1, 2],
            ),
        ]
    )
    await db.commit()

    response = await client.delete(f"/api/v1/books/{book.id}/chapters/2", headers=auth_headers)

    assert response.status_code == 204
    assert await db.scalar(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 2)) is None
    assert await db.scalar(select(BookChunk).where(BookChunk.chapter_id == chapter_two.id)) is None
    assert await db.scalar(select(ChapterSummary).where(ChapterSummary.chapter_id == chapter_two.id)) is None
    assert await db.scalar(select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.chapter_number == 2)) is None
    assert await db.scalar(select(ChapterMedia).where(ChapterMedia.chapter_id == chapter_two.id)) is None
    assert await db.scalar(select(BookNote).where(BookNote.book_id == book.id, BookNote.chapter_number == 2)) is None
    assert await db.scalar(select(ManuscriptAnnotation).where(ManuscriptAnnotation.book_id == book.id, ManuscriptAnnotation.chapter_number == 2)) is None
    assert await db.scalar(select(CharacterMention).where(CharacterMention.book_id == book.id, CharacterMention.chapter_number == 2)) is None
    assert await db.scalar(select(CharacterState).where(CharacterState.character_id == character.id, CharacterState.at_chapter == 2)) is None
    assert await db.scalar(select(CustomTag).where(CustomTag.book_id == book.id, CustomTag.entity_id == chapter_two.id)) is None

    preserved_versions = (
        await db.execute(select(ChapterVersion).where(ChapterVersion.book_id == book.id, ChapterVersion.chapter_number == 2))
    ).scalars().all()
    assert len(preserved_versions) == 2
    assert any(version.snapshot_kind == "pre_delete" for version in preserved_versions)
    assert all(version.chapter_id is None for version in preserved_versions)

    preserved_scene_version = await db.scalar(select(SceneVersion).where(SceneVersion.book_id == book.id, SceneVersion.chapter_number == 2))
    assert preserved_scene_version is not None
    assert preserved_scene_version.scene_id is None
    assert preserved_scene_version.chapter_id is None

    await db.refresh(book)
    await db.refresh(character)
    progress = await db.scalar(select(ReadingProgress).where(ReadingProgress.book_id == book.id, ReadingProgress.user_id == user_id))
    assert book.total_chapters == 1
    assert book.status == "ready"
    assert book.writer_workspace["processing"]["status"] == "cancelled"
    assert "rebuild_run_id" not in book.writer_workspace["processing"]
    assert book.writer_workspace["reprocess"]["last_cancelled_rebuild_run_id"] == "active-delete-test"
    assert character.first_chapter == 1
    assert character.last_seen_chapter == 1
    assert character.mention_count == 1
    assert progress is not None
    assert progress.current_chapter == 1
    assert progress.chapters_read == [1]


@pytest.mark.asyncio
async def test_complete_rebuild_recovers_stale_extraction_progress(db):
    user = User(email="stale-rebuild@example.com", username="stale-rebuild", password_hash="test-hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Stale Rebuild",
        format="manual",
        s3_key="books/stale-rebuild.txt",
        status="processing",
        mode="author",
        total_chapters=2,
        is_editor_project=True,
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "extraction",
                "rebuild_run_id": "stale-run",
                "chapters_completed": 0,
                "chapters_total": 2,
                "pipeline": {
                    "analysis": {
                        "status": "succeeded",
                        "completed_chapters": 2,
                        "total_chapters": 2,
                    }
                },
            },
            "reprocess": {
                "last_started_at": "2026-06-01T00:00:00+00:00",
                "last_rebuild_run_id": "stale-run",
            },
        },
    )
    db.add(book)
    await db.flush()
    chapters = [
        Chapter(
            book_id=book.id,
            number=number,
            title=f"Chapter {number}",
            s3_key=f"chapters/stale-rebuild/{number}.txt",
            processed=True,
            word_count=100,
        )
        for number in (1, 2)
    ]
    db.add_all(chapters)
    await db.flush()
    db.add_all(
        [
            ChapterSummary(chapter_id=chapter.id, mode="detailed", content=f"Summary {chapter.number}")
            for chapter in chapters
        ]
    )
    await db.commit()

    completed = await complete_rebuild_if_ready(db, book)
    await db.commit()

    assert completed is True
    assert book.status == "ready"
    assert book.writer_workspace["processing"]["status"] == "ready"
    assert book.writer_workspace["processing"]["stage"] == "complete"
    assert book.writer_workspace["processing"]["pipeline"]["extraction"]["status"] == "succeeded"
    assert book.writer_workspace["processing"]["pipeline"]["analysis"]["status"] == "succeeded"
    assert book.writer_workspace["processing"]["is_fully_ready"] is True
    assert "rebuild_run_id" not in book.writer_workspace["processing"]
    assert book.writer_workspace["reprocess"]["last_completed_rebuild_run_id"] == "stale-run"
