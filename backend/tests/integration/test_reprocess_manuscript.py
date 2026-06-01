import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token


async def _register_author(client, email: str, monkeypatch) -> tuple[dict[str, str], uuid.UUID]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0][:24],
            "password": "StrongPass123!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex[:24]}",
        },
    )
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.require_author_access",
        lambda *_args, **_kwargs: None,
    )

    async def _fake_check_upload_limit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.check_upload_limit",
        _fake_check_upload_limit,
    )
    return headers, user_id


async def _create_editor_project(client, headers, title="Test Project") -> str:
    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={"title": title},
    )
    assert response.status_code == 200
    return response.json()["book_id"]


async def _add_chapter(db, book_id: uuid.UUID, number: int = 1, text: str = "Some story content."):
    from app.models.book import Chapter

    chapter = Chapter(
        book_id=book_id,
        number=number,
        title=f"Chapter {number}",
        s3_key=f"chapters/{book_id}/{number}.txt",
        word_count=len(text.split()),
    )
    db.add(chapter)
    await db.commit()
    return chapter


@pytest.mark.asyncio
async def test_reprocess_not_editor_project(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-no-ed-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book

    book = Book(
        user_id=user_id,
        title="Regular Book",
        format="txt",
        s3_key="regular.txt",
        status="ready",
        is_editor_project=False,
    )
    db.add(book)
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers,
    )

    assert response.status_code == 400
    assert "editor project" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reprocess_empty_manuscript(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-empty-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    book_id = await _create_editor_project(client, headers)

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
    )

    assert response.status_code == 400
    assert "chapter" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reprocess_duplicate_run(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-dup-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book

    book_id = uuid.uuid4()

    async def _fake_prepare_rebuild(db, book):
        book.status = "processing"
        ws = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
        ws["processing"] = {"rebuild_run_id": "fake-run-id", "status": "processing"}
        book.writer_workspace = ws
        await db.commit()
        return "fake-run-id"

    monkeypatch.setattr(
        "app.services.editor_project_service.prepare_rebuild",
        _fake_prepare_rebuild,
    )

    book = Book(
        id=book_id,
        user_id=user_id,
        title="Dup Run",
        format="manual",
        s3_key="dup.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    chapter = await _add_chapter(db, book_id)

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
    )
    assert response.status_code == 200

    response2 = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_reprocess_success(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-ok-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book

    dispatched: list = []

    class _FakeResult:
        def __init__(self, tid):
            self.id = tid

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return _FakeResult(f"task-{len(dispatched)}")

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    book_id = uuid.uuid4()
    book = Book(
        id=book_id,
        user_id=user_id,
        title="Reprocess OK",
        format="manual",
        s3_key="reprocess.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    chapter1 = await _add_chapter(db, book_id, 1, "First chapter content here.")
    chapter2 = await _add_chapter(db, book_id, 2, "Second chapter content too.")

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processing"
    assert body["chapters_queued"] >= 1
    assert body["total_words"] > 0
    assert len(dispatched) >= 1

    book_after = await db.get(Book, book_id)
    assert book_after.status == "processing"
    ws = book_after.writer_workspace or {}
    assert ws.get("processing", {}).get("rebuild_run_id") is not None


@pytest.mark.asyncio
async def test_reprocess_requires_ownership(client, db, monkeypatch):
    headers1, user1 = await _register_author(
        client, f"repr-own1-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    headers2, user2 = await _register_author(
        client, f"repr-own2-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book

    book = Book(
        user_id=user1,
        title="Owner Book",
        format="manual",
        s3_key="owner.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers2,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reprocess_requires_author_access(client, db, monkeypatch):
    headers1, user1 = await _register_author(
        client, f"repr-auth-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book

    book = Book(
        user_id=user1,
        title="Auth Test Book",
        format="manual",
        s3_key="auth.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.require_author_access",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            __import__("fastapi").HTTPException(403, "Requires Author plan")
        ),
    )

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers1,
    )

    assert response.status_code == 403
