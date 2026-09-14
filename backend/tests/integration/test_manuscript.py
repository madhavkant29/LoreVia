from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.v1.routes import manuscript
from app.models.book import (
    Book,
    BookNote,
    Chapter,
    ChapterMedia,
    ChapterVersion,
    ManuscriptAnnotation,
    NovelScene,
    SceneVersion,
)
from app.models.character import Character, CharacterMention, CharacterState
from app.models.generation import BookDataGeneration
from app.models.intelligence import BookChunk, ChapterSummary
from app.models.progress import ReadingProgress
from app.models.tag import CustomTag
from app.models.user import User
from app.services.editor_project_service import complete_rebuild_if_ready
from app.utils.books.manuscript import (
    serialize_manuscript_content,
)


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

    async def _enqueue(_db, **kwargs):
        dispatched.update(kwargs)
        return SimpleNamespace(id="restore-task-123")

    monkeypatch.setattr(manuscript, "restore_chapter_version", _fake_restore)
    monkeypatch.setattr(
        "app.services.task_execution_service.enqueue_extraction_execution", _enqueue
    )

    response = await client.post(
        f"/api/v1/books/{book.id}/chapter-versions/{version.id}/restore",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "restore_queued"
    assert payload["task_id"] == "restore-task-123"
    assert dispatched["book_id"] == book.id
    assert dispatched["chapter_number"] == 1
    assert dispatched["chapter_version_id"] == version.id

    await db.refresh(version)
    assert version.restore_status == "queued"
    assert version.restore_task_id == "restore-task-123"
    assert version.restore_error is None
    assert version.restore_started_at is None
    assert version.restore_completed_at is None

    status_response = await client.get(
        f"/api/v1/books/{book.id}/chapter-versions/{version.id}/restore-status",
        headers=auth_headers,
    )

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["restore_status"] == "queued"
    assert status_payload["restore_task_id"] == "restore-task-123"


@pytest.mark.asyncio
async def test_manuscript_workspace_scene_annotation_and_version_workflow(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    user = await db.get(User, user_id)
    user.tier = "author"

    storage: dict[str, bytes] = {}

    def download(key):
        return storage[key]

    def upload(key, raw, _content_type=None):
        storage[key] = raw
        return key

    for target in (
        "app.utils.books.chapter_versions",
        "app.utils.books.scene_records",
        "app.utils.books.scene_sync",
    ):
        monkeypatch.setattr(f"{target}.download_book", download, raising=False)
        monkeypatch.setattr(f"{target}.upload_binary", upload, raising=False)

    book = Book(
        user_id=user_id,
        title="Workspace Flow",
        format="manual",
        s3_key="books/workspace-flow.txt",
        status="ready",
        mode="author",
        total_chapters=1,
        is_editor_project=True,
        writer_workspace={"index_format": "roman-upper"},
    )
    db.add(book)
    await db.flush()
    chapter_key = f"chapters/{book.id}/1.txt"
    storage[chapter_key] = serialize_manuscript_content(
        "Opening paragraph.", "<p>Opening paragraph.</p>"
    ).encode()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Opening",
        s3_key=chapter_key,
        processed=True,
        structure_version=0,
    )
    db.add(chapter)
    await db.commit()

    created = await client.post(
        f"/api/v1/books/{book.id}/scenes",
        headers=auth_headers,
        json={
            "title": "Arrival",
            "description": "The protagonist arrives.",
            "body": "Mara enters the frozen city.",
            "html_body": "<p>Mara enters the frozen city.</p>",
            "chapter_number": 1,
            "status": "assigned",
            "sort_order": 1,
            "metadata": {"pov": "Mara", "location": "Northreach"},
        },
    )
    assert created.status_code == 200, created.text
    scene_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/books/{book.id}/scenes/{scene_id}",
        headers=auth_headers,
        json={
            "title": "Arrival Revised",
            "description": "The protagonist enters through the ice gate.",
            "body": "Mara crosses the ice gate and enters Northreach.",
            "chapter_number": 1,
            "status": "assigned",
            "sort_order": 2,
            "metadata": {"pov": "Mara", "location": "Ice Gate"},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Arrival Revised"

    listed = await client.get(
        f"/api/v1/books/{book.id}/scenes?chapter_number=1&query=Arrival",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [scene_id]

    tree = await client.get(f"/api/v1/books/{book.id}/workspace/tree", headers=auth_headers)
    assert tree.status_code == 200
    assert tree.json()["chapters"][0]["scene_count"] == 1

    reader_bootstrap = await client.get(
        f"/api/v1/books/{book.id}/reader-bootstrap",
        headers=auth_headers,
    )
    assert reader_bootstrap.status_code == 200, reader_bootstrap.text
    assert reader_bootstrap.json()["profile"] == "full"
    assert reader_bootstrap.json()["overview"]["book"]["id"] == str(book.id)
    assert reader_bootstrap.json()["writer_workspace"] is not None

    reader_critical_bootstrap = await client.get(
        f"/api/v1/books/{book.id}/reader-bootstrap?profile=critical",
        headers=auth_headers,
    )
    assert reader_critical_bootstrap.status_code == 200, reader_critical_bootstrap.text
    assert reader_critical_bootstrap.json()["profile"] == "critical"
    assert reader_critical_bootstrap.json()["overview"]["book"]["id"] == str(book.id)
    assert reader_critical_bootstrap.json()["writer_workspace"] is None
    assert reader_critical_bootstrap.json()["chapter_reports"] == []

    manuscript_bootstrap = await client.get(
        f"/api/v1/books/{book.id}/manuscript-bootstrap?active_chapter_number=1",
        headers=auth_headers,
    )
    assert manuscript_bootstrap.status_code == 200, manuscript_bootstrap.text
    assert manuscript_bootstrap.json()["profile"] == "full"
    assert manuscript_bootstrap.json()["book"]["id"] == str(book.id)
    assert manuscript_bootstrap.json()["prewriting_check"] is not None

    manuscript_critical_bootstrap = await client.get(
        f"/api/v1/books/{book.id}/manuscript-bootstrap?active_chapter_number=1&profile=critical",
        headers=auth_headers,
    )
    assert manuscript_critical_bootstrap.status_code == 200, manuscript_critical_bootstrap.text
    assert manuscript_critical_bootstrap.json()["profile"] == "critical"
    assert manuscript_critical_bootstrap.json()["book"]["id"] == str(book.id)
    assert manuscript_critical_bootstrap.json()["writer_workspace"] is not None
    assert manuscript_critical_bootstrap.json()["workspace_tree"] is not None
    assert manuscript_critical_bootstrap.json()["prewriting_check"] is None
    assert manuscript_critical_bootstrap.json()["notes"] == []
    assert manuscript_critical_bootstrap.json()["chapter_versions"] == []

    search = await client.post(
        f"/api/v1/books/{book.id}/workspace/search",
        headers=auth_headers,
        json={"query": "Northreach", "scopes": ["manuscript", "scenes"]},
    )
    assert search.status_code == 200
    assert search.json()

    annotation = await client.post(
        f"/api/v1/books/{book.id}/annotations",
        headers=auth_headers,
        json={
            "chapter_number": 1,
            "category": "continuity",
            "status": "open",
            "visibility": "private",
            "quote": "ice gate",
            "comment": "Check this against the world bible.",
            "start_offset": 17,
            "end_offset": 25,
        },
    )
    assert annotation.status_code == 200
    annotation_id = annotation.json()["id"]
    annotations = await client.get(
        f"/api/v1/books/{book.id}/annotations?chapter_number=1",
        headers=auth_headers,
    )
    assert annotations.status_code == 200
    assert annotations.json()[0]["id"] == annotation_id

    snapshot = await client.post(
        f"/api/v1/books/{book.id}/scenes/{scene_id}/snapshot?note=Before revision",
        headers=auth_headers,
    )
    assert snapshot.status_code == 200, snapshot.text
    version_id = snapshot.json()["id"]
    versions = await client.get(
        f"/api/v1/books/{book.id}/scenes/{scene_id}/versions",
        headers=auth_headers,
    )
    assert versions.status_code == 200
    assert versions.json()[0]["id"] == version_id
    detail = await client.get(
        f"/api/v1/books/{book.id}/scene-versions/{version_id}",
        headers=auth_headers,
    )
    assert detail.status_code == 200
    assert "Mara crosses" in detail.json()["body"]
    restored = await client.post(
        f"/api/v1/books/{book.id}/scene-versions/{version_id}/restore",
        headers=auth_headers,
    )
    assert restored.status_code == 200

    removed_annotation = await client.delete(
        f"/api/v1/books/{book.id}/annotations/{annotation_id}",
        headers=auth_headers,
    )
    assert removed_annotation.status_code == 204
    removed_scene = await client.delete(
        f"/api/v1/books/{book.id}/scenes/{scene_id}",
        headers=auth_headers,
    )
    assert removed_scene.status_code == 204


@pytest.mark.asyncio
async def test_remove_chapter_deletes_direct_artifacts_and_preserves_version_history(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])
    user = await db.get(User, user_id)
    assert user is not None
    user.tier = "author"

    monkeypatch.setattr(
        "app.utils.books.chapter_versions.download_book",
        lambda _key: serialize_manuscript_content("Deleted chapter text.").encode("utf-8"),
    )
    monkeypatch.setattr(
        "app.utils.books.chapter_versions.upload_binary",
        lambda key, _raw, _content_type=None: key,
    )

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
        word_count=120,
        processed=True,
    )
    chapter_two = Chapter(
        book_id=book.id,
        number=2,
        title="Departure",
        s3_key="chapters/delete-chapter/2.txt",
        word_count=140,
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
            BookChunk(
                book_id=book.id, chapter_id=chapter_two.id, chunk_index=0, text="Departure chunk."
            ),
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
            CharacterState(
                character_id=character.id, at_chapter=2, trait_snapshot={"mood": "resolved"}
            ),
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
    assert (
        await db.scalar(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 2))
        is None
    )
    assert await db.scalar(select(BookChunk).where(BookChunk.chapter_id == chapter_two.id)) is None
    assert (
        await db.scalar(select(ChapterSummary).where(ChapterSummary.chapter_id == chapter_two.id))
        is None
    )
    assert (
        await db.scalar(
            select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.chapter_number == 2)
        )
        is None
    )
    assert (
        await db.scalar(select(ChapterMedia).where(ChapterMedia.chapter_id == chapter_two.id))
        is None
    )
    assert (
        await db.scalar(
            select(BookNote).where(BookNote.book_id == book.id, BookNote.chapter_number == 2)
        )
        is None
    )
    assert (
        await db.scalar(
            select(ManuscriptAnnotation).where(
                ManuscriptAnnotation.book_id == book.id, ManuscriptAnnotation.chapter_number == 2
            )
        )
        is None
    )
    assert (
        await db.scalar(
            select(CharacterMention).where(
                CharacterMention.book_id == book.id, CharacterMention.chapter_number == 2
            )
        )
        is None
    )
    assert (
        await db.scalar(
            select(CharacterState).where(
                CharacterState.character_id == character.id, CharacterState.at_chapter == 2
            )
        )
        is None
    )
    assert (
        await db.scalar(
            select(CustomTag).where(
                CustomTag.book_id == book.id, CustomTag.entity_id == chapter_two.id
            )
        )
        is None
    )

    preserved_versions = (
        (
            await db.execute(
                select(ChapterVersion).where(
                    ChapterVersion.book_id == book.id, ChapterVersion.chapter_number == 2
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(preserved_versions) == 2
    assert any(version.snapshot_kind == "pre_delete" for version in preserved_versions)
    assert all(version.chapter_id is None for version in preserved_versions)

    preserved_scene_version = await db.scalar(
        select(SceneVersion).where(
            SceneVersion.book_id == book.id, SceneVersion.chapter_number == 2
        )
    )
    assert preserved_scene_version is not None
    assert preserved_scene_version.scene_id is None
    assert preserved_scene_version.chapter_id is None

    await db.refresh(book)
    await db.refresh(character)
    progress = await db.scalar(
        select(ReadingProgress).where(
            ReadingProgress.book_id == book.id, ReadingProgress.user_id == user_id
        )
    )
    assert book.total_chapters == 1
    assert book.status == "failed"
    assert book.writer_workspace["processing"]["status"] == "failed"
    assert book.writer_workspace["processing"]["stage"] == "failed"
    assert book.writer_workspace["processing"]["chapters_completed"] == 1
    assert book.writer_workspace["processing"]["chapters_total"] == 1
    assert book.writer_workspace["processing"]["progress_pct"] == 100.0
    assert book.writer_workspace["processing"]["retry_actions"] == ["retry_extraction"]
    assert "rebuild_run_id" not in book.writer_workspace["processing"]
    assert (
        book.writer_workspace["reprocess"]["last_cancelled_rebuild_run_id"] == "active-delete-test"
    )
    assert character.first_chapter == 1
    assert character.last_seen_chapter == 1
    assert character.mention_count == 1
    assert progress is not None
    assert progress.current_chapter == 1
    assert progress.chapters_read == [1]


@pytest.mark.asyncio
async def test_complete_rebuild_recovers_stale_extraction_progress(db):
    rebuild_run_id = uuid.uuid4().hex
    user = User(
        email="stale-rebuild@example.com", username="stale-rebuild", password_hash="test-hash"
    )
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
                "rebuild_run_id": rebuild_run_id,
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
                "last_rebuild_run_id": rebuild_run_id,
            },
        },
    )
    db.add(book)
    await db.flush()
    db.add(
        BookDataGeneration(
            id=uuid.UUID(rebuild_run_id),
            book_id=book.id,
            rebuild_run_id=rebuild_run_id,
            status="staging",
            reason="stale_progress_recovery_test",
        )
    )
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
            ChapterSummary(
                chapter_id=chapter.id,
                mode="detailed",
                content=f"Summary {chapter.number}",
                generation_id=uuid.UUID(rebuild_run_id),
            )
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
    assert book.writer_workspace["reprocess"]["last_completed_rebuild_run_id"] == rebuild_run_id
