import io
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter, ChapterVersion, Series, SeriesBook
from app.models.character import Character
from app.models.user import User


@pytest.fixture(autouse=True)
def _mock_storage_uploads(monkeypatch):
    def _fake_upload_book_bytes(raw: bytes, user_id: str, filename: str) -> str:
        return f"books/{user_id}/test/{uuid.uuid4()}/{filename}"

    def _noop_apply_async(*args, **kwargs):
        return None

    monkeypatch.setattr("app.core.storage.upload_book_bytes", _fake_upload_book_bytes)
    # Celery's @task decorator yields a lazy proxy in tests; stubbing the whole
    # task object is more reliable than patching proxy attributes.
    monkeypatch.setattr(
        "app.api.v1.routes.books.process_book_task",
        SimpleNamespace(apply_async=_noop_apply_async),
    )


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token
    username = email.split("@")[0][:32]
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "TestPass123!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex[:24]}",
        },
    )
    assert response.status_code == 201
    token = create_access_token(str(response.json()["id"]))
    assert token
    me_response = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={token}"})
    assert me_response.status_code == 200
    return {"Cookie": f"lorevia_access_token={token}"}, uuid.UUID(me_response.json()["id"])


@pytest.mark.asyncio
async def test_character_routes_do_not_leak_across_users(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-access@lorevia.app")
    intruder_headers, _ = await _register_user(client, "intruder-access@lorevia.app")

    owner_book = Book(
        user_id=owner_id,
        title="Private Book",
        format="pdf",
        s3_key="private/book.pdf",
        status="ready",
    )
    db.add(owner_book)
    await db.flush()

    character = Character(
        book_id=owner_book.id,
        name="Hidden Character",
        first_chapter=1,
        trait_state={"mood": "guarded"},
    )
    db.add(character)
    await db.commit()

    direct = await client.get(f"/api/v1/characters/{character.id}", headers=intruder_headers)
    state = await client.get(
        f"/api/v1/characters/{character.id}/state",
        headers=intruder_headers,
        params={"chapter": 1},
    )

    assert direct.status_code == 404
    assert state.status_code == 404

    owner_visible = await client.get(f"/api/v1/characters/{character.id}", headers=owner_headers)
    assert owner_visible.status_code == 200


@pytest.mark.asyncio
async def test_series_routes_require_book_ownership(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-series@lorevia.app")
    intruder_headers, intruder_id = await _register_user(client, "intruder-series@lorevia.app")

    owner_book = Book(
        user_id=owner_id,
        title="Owner Book",
        format="pdf",
        s3_key="owner/book.pdf",
        status="ready",
        total_chapters=3,
    )
    owner_series = Series(user_id=owner_id, name="Owner Saga")
    intruder_series = Series(user_id=intruder_id, name="Intruder Saga")
    db.add_all([owner_book, owner_series, intruder_series])
    await db.commit()

    add_to_foreign_series = await client.post(
        f"/api/v1/books/series/{owner_series.id}/books/{owner_book.id}",
        headers=intruder_headers,
        json={"position": 1},
    )
    add_foreign_book = await client.post(
        f"/api/v1/books/series/{intruder_series.id}/books/{owner_book.id}",
        headers=intruder_headers,
        json={"position": 1},
    )

    assert add_to_foreign_series.status_code == 404
    assert add_foreign_book.status_code == 404


@pytest.mark.asyncio
async def test_mark_book_read_updates_only_current_user_progress(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-progress@lorevia.app")
    intruder_headers, _ = await _register_user(client, "intruder-progress@lorevia.app")

    book = Book(
        user_id=owner_id,
        title="Series Volume",
        format="pdf",
        s3_key="series/volume.pdf",
        status="ready",
        total_chapters=4,
    )
    series = Series(user_id=owner_id, name="Long Saga")
    db.add_all([book, series])
    await db.flush()

    for number in range(1, 5):
        db.add(Chapter(book_id=book.id, number=number, title=f"Chapter {number}", s3_key=f"chapter-{number}.txt"))
    await db.commit()

    response = await client.post(
        f"/api/v1/books/series/{series.id}/books/{book.id}",
        headers=owner_headers,
        json={"position": 1},
    )
    assert response.status_code == 200

    marked = await client.put(
        f"/api/v1/books/series/{series.id}/books/{book.id}/status",
        headers=owner_headers,
        json={"marked_complete": True},
    )
    assert marked.status_code == 200
    assert marked.json()["progress_pct"] == 100.0

    owner_progress = await client.get(f"/api/v1/reader/{book.id}/progress", headers=owner_headers)
    intruder_progress = await client.get(f"/api/v1/reader/{book.id}/progress", headers=intruder_headers)

    assert owner_progress.status_code == 200
    assert owner_progress.json()["percent_complete"] == 100.0
    assert intruder_progress.status_code == 404


@pytest.mark.asyncio
async def test_progress_write_routes_require_book_ownership(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-write-progress@lorevia.app")
    intruder_headers, _ = await _register_user(client, "intruder-write-progress@lorevia.app")

    book = Book(
        user_id=owner_id,
        title="Locked Progress Book",
        format="pdf",
        s3_key="locked/progress.pdf",
        status="ready",
        total_chapters=2,
    )
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=1, title="Chapter 1", s3_key="chapter-1.txt"))
    db.add(Chapter(book_id=book.id, number=2, title="Chapter 2", s3_key="chapter-2.txt"))
    await db.commit()

    update_progress = await client.put(
        f"/api/v1/reader/{book.id}/progress",
        headers=intruder_headers,
        params={"current_chapter": 1, "scroll_pct": 0.5},
    )
    update_chapter = await client.put(
        f"/api/v1/reader/{book.id}/progress/chapter-status",
        headers=intruder_headers,
        params={"chapter": 1, "read": True},
    )

    assert update_progress.status_code == 404
    assert update_chapter.status_code == 404


@pytest.mark.asyncio
async def test_upload_attaches_book_to_multiple_owned_series(client, db):
    headers, user_id = await _register_user(client, "owner-upload-series@lorevia.app")
    first_series = Series(user_id=user_id, name="Saga One")
    second_series = Series(user_id=user_id, name="Saga Two")
    db.add_all([first_series, second_series])
    await db.commit()

    response = await client.post(
        "/api/v1/books/upload",
        headers=headers,
        files={"file": ("attached.pdf", b"%PDF-1.4 test payload", "application/pdf")},
        data={
            "title": "Attached Book",
            "series_ids": [str(first_series.id), str(second_series.id)],
        },
    )

    assert response.status_code == 202
    book_id = uuid.UUID(response.json()["book_id"])
    book = await db.get(Book, book_id)
    assert book is not None
    assert book.user_id == user_id
    assert book.primary_series_id == first_series.id

    memberships = (
        await db.execute(
            select(SeriesBook).where(SeriesBook.book_id == book_id)
        )
    ).scalars().all()
    assert {membership.series_id for membership in memberships} == {first_series.id, second_series.id}


@pytest.mark.asyncio
async def test_upload_rejects_foreign_series_ids(client, db):
    headers, user_id = await _register_user(client, "owner-upload-idor@lorevia.app")
    _, other_user_id = await _register_user(client, "intruder-upload-idor@lorevia.app")
    foreign_series = Series(user_id=other_user_id, name="Other User Saga")
    db.add(foreign_series)
    await db.commit()

    response = await client.post(
        "/api/v1/books/upload",
        headers=headers,
        files={"file": ("rejected.pdf", b"%PDF-1.4 test payload", "application/pdf")},
        data={
            "title": "Rejected Book",
            "series_ids": [str(foreign_series.id)],
        },
    )

    assert response.status_code == 404
    books = (
        await db.execute(
            select(Book).where(Book.user_id == user_id, Book.title == "Rejected Book")
        )
    ).scalars().all()
    assert books == []


@pytest.mark.asyncio
async def test_story_scoped_collaboration_limits_shared_book_access(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-collab@lorevia.app")
    collaborator_headers, _ = await _register_user(client, "beta-collab@lorevia.app")
    owner = await db.get(User, owner_id)
    assert owner is not None
    owner.tier = "author"

    book = Book(
        user_id=owner_id,
        title="Shared Draft",
        format="docx",
        s3_key="shared/draft.docx",
        status="ready",
        total_chapters=3,
        mode="author",
    )
    db.add(book)
    await db.flush()
    for number in range(1, 4):
        db.add(Chapter(book_id=book.id, number=number, title=f"Chapter {number}", s3_key=f"chapter-{number}.txt"))
    db.add(Character(book_id=book.id, name="Nora Vale", first_chapter=1, role="mc"))
    await db.commit()

    create = await client.post(
        f"/api/v1/books/{book.id}/collaborators",
        headers=owner_headers,
        json={
            "email": "beta-collab@lorevia.app",
            "display_name": "Beta Reader",
            "role": "beta_reader",
            "scope": {
                "chapter_start": 1,
                "chapter_end": 2,
                "character_bible": True,
                "continuity_report": False,
                "reader_confusion_report": False,
            },
        },
    )

    assert create.status_code == 201
    assert create.json()["scope"]["chapter_end"] == 2

    shared_books = await client.get("/api/v1/books", headers=collaborator_headers)
    assert shared_books.status_code == 200
    shared_payload = shared_books.json()
    assert shared_payload[0]["id"] == str(book.id)
    assert shared_payload[0]["collaboration_role"] == "beta_reader"

    chapters = await client.get(f"/api/v1/reader/{book.id}/chapters", headers=collaborator_headers)
    assert chapters.status_code == 200
    assert [item["number"] for item in chapters.json()["chapters"]] == [1, 2]

    allowed_chapter = await client.get(f"/api/v1/reader/{book.id}/chapter/2", headers=collaborator_headers)
    blocked_chapter = await client.get(f"/api/v1/reader/{book.id}/chapter/3", headers=collaborator_headers)
    assert allowed_chapter.status_code == 200
    assert blocked_chapter.status_code == 403

    characters = await client.get(f"/api/v1/books/{book.id}/characters", headers=collaborator_headers)
    continuity = await client.get(f"/api/v1/books/{book.id}/chapter-reports", headers=collaborator_headers)
    assert characters.status_code == 200
    assert continuity.status_code == 403


@pytest.mark.asyncio
async def test_collaboration_permissions_gate_comments_and_manuscript_tools(client, db):
    owner_headers, owner_id = await _register_user(client, "owner-permissions@lorevia.app")
    collaborator_headers, _ = await _register_user(client, "commenter-permissions@lorevia.app")
    owner = await db.get(User, owner_id)
    assert owner is not None
    owner.tier = "author"

    book = Book(
        user_id=owner_id,
        title="Permissions Draft",
        format="docx",
        s3_key="shared/permissions.docx",
        status="ready",
        total_chapters=3,
        mode="author",
    )
    db.add(book)
    await db.flush()
    for number in range(1, 4):
        db.add(Chapter(book_id=book.id, number=number, title=f"Chapter {number}", s3_key=f"chapter-{number}.txt"))
    await db.commit()

    create = await client.post(
        f"/api/v1/books/{book.id}/collaborators",
        headers=owner_headers,
        json={
            "email": "commenter-permissions@lorevia.app",
            "display_name": "Commenter",
            "role": "commenter",
            "scope": {
                "chapter_start": 1,
                "chapter_end": 2,
                "character_bible": False,
                "continuity_report": False,
                "reader_confusion_report": False,
            },
            "permissions": {
                "can_edit_manuscript": False,
                "can_view_story_bible": False,
                "can_run_ai_scans": False,
                "can_export": False,
                "can_comment": True,
                "can_view_selected_chapters_only": True,
            },
        },
    )

    assert create.status_code == 201
    assert create.json()["permissions"]["can_comment"] is True
    assert create.json()["permissions"]["can_edit_manuscript"] is False

    note = await client.post(
        f"/api/v1/books/{book.id}/notes",
        headers=collaborator_headers,
        json={
            "chapter_number": 1,
            "title": "Reader note",
            "body": "The opening lands well.",
        },
    )
    blocked_note = await client.post(
        f"/api/v1/books/{book.id}/notes",
        headers=collaborator_headers,
        json={
            "chapter_number": 3,
            "title": "Blocked note",
            "body": "This should be out of scope.",
        },
    )
    writer_workspace = await client.get(f"/api/v1/books/{book.id}/writer-workspace", headers=collaborator_headers)
    manuscript_tree = await client.get(f"/api/v1/books/{book.id}/workspace/tree", headers=collaborator_headers)

    assert note.status_code == 200
    assert blocked_note.status_code == 403
    assert writer_workspace.status_code == 403
    assert manuscript_tree.status_code == 403


@pytest.mark.asyncio
async def test_collaboration_manuscript_export_respects_selected_chapter_scope(client, db, monkeypatch):
    owner_headers, owner_id = await _register_user(client, "owner-export-scope@lorevia.app")
    collaborator_headers, _ = await _register_user(client, "export-scope@lorevia.app")
    owner = await db.get(User, owner_id)
    assert owner is not None
    owner.tier = "author"

    book = Book(
        user_id=owner_id,
        title="Scoped Export",
        format="docx",
        s3_key="shared/scoped-export.docx",
        status="ready",
        total_chapters=3,
        mode="author",
    )
    db.add(book)
    await db.flush()
    for number in range(1, 4):
        db.add(Chapter(book_id=book.id, number=number, title=f"Chapter {number}", s3_key=f"chapter-{number}.txt"))
    await db.commit()

    captured: dict[str, object] = {}

    def _fake_manuscript_docx(*, title, chapters, scenes, preset, front_matter):
        captured["title"] = title
        captured["chapters"] = chapters
        return b"docx-bytes"

    monkeypatch.setattr("app.api.v1.routes.books.manuscript_docx", _fake_manuscript_docx)
    monkeypatch.setattr(
        "app.api.v1.routes.books.storage.download_book",
        lambda _key: b'{"text":"Body text","html":"<p>Body text</p>"}',
    )

    create = await client.post(
        f"/api/v1/books/{book.id}/collaborators",
        headers=owner_headers,
        json={
            "email": "export-scope@lorevia.app",
            "display_name": "Scoped Exporter",
            "role": "developmental_editor",
            "scope": {
                "chapter_start": 1,
                "chapter_end": 2,
                "character_bible": False,
                "continuity_report": False,
                "reader_confusion_report": False,
            },
            "permissions": {
                "can_edit_manuscript": True,
                "can_view_story_bible": False,
                "can_run_ai_scans": False,
                "can_export": True,
                "can_comment": True,
                "can_view_selected_chapters_only": True,
            },
        },
    )
    assert create.status_code == 201

    export = await client.get(
        f"/api/v1/books/{book.id}/manuscript/export",
        headers=collaborator_headers,
        params={"format": "docx"},
    )

    assert export.status_code == 200
    assert export.content == b"docx-bytes"
    assert [chapter["number"] for chapter in captured["chapters"]] == [1, 2]


@pytest.mark.asyncio
async def test_collaboration_restore_rejects_out_of_scope_version_before_mutation(client, db, monkeypatch):
    owner_headers, owner_id = await _register_user(client, "owner-restore-scope@lorevia.app")
    collaborator_headers, _ = await _register_user(client, "restore-scope@lorevia.app")
    owner = await db.get(User, owner_id)
    assert owner is not None
    owner.tier = "author"

    book = Book(
        user_id=owner_id,
        title="Restore Scope",
        format="docx",
        s3_key="shared/restore-scope.docx",
        status="ready",
        total_chapters=3,
        mode="author",
    )
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=3, title="Chapter 3", s3_key="chapter-3.txt"))
    await db.flush()
    version = ChapterVersion(
        book_id=book.id,
        chapter_number=3,
        title="Chapter 3",
        s3_key="versions/chapter-3.txt",
        snapshot_kind="manual",
    )
    db.add(version)
    await db.commit()

    create = await client.post(
        f"/api/v1/books/{book.id}/collaborators",
        headers=owner_headers,
        json={
            "email": "restore-scope@lorevia.app",
            "display_name": "Scoped Editor",
            "role": "editor",
            "scope": {
                "chapter_start": 1,
                "chapter_end": 2,
                "character_bible": False,
                "continuity_report": False,
                "reader_confusion_report": False,
            },
            "permissions": {
                "can_edit_manuscript": True,
                "can_view_story_bible": False,
                "can_run_ai_scans": False,
                "can_export": False,
                "can_comment": True,
                "can_view_selected_chapters_only": True,
            },
        },
    )
    assert create.status_code == 201

    called = {"restore": False}

    async def _fake_restore(*args, **kwargs):
        called["restore"] = True
        return {"chapter_number": 3, "title": "Chapter 3", "text": "body", "html": None}

    monkeypatch.setattr("app.api.v1.routes.manuscript.restore_chapter_version", _fake_restore)

    response = await client.post(
        f"/api/v1/books/{book.id}/chapter-versions/{version.id}/restore",
        headers=collaborator_headers,
    )

    assert response.status_code == 403
    assert called["restore"] is False
