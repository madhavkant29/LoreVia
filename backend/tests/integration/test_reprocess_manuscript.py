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
async def test_reprocess_requires_confirmation(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-no-ed-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    book_id = await _create_editor_project(client, headers)
    await _add_chapter(db, uuid.UUID(book_id))

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
    )

    assert response.status_code == 400
    assert "confirm" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reprocess_uploaded_manuscript_success(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-uploaded-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, BookUploadCharge

    dispatched: list = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

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
    await _add_chapter(db, book.id, 1, "Uploaded manuscript chapter content.")
    await _add_chapter(db, book.id, 2, "A second uploaded manuscript chapter.")

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers,
        json={"confirm_upload_charge": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["upload_charge_consumed"] is True
    assert body["charge_kind"] == "manual_reprocess"
    assert body["chapters_queued"] == 2
    assert len(dispatched) == 2
    assert all(item["kwargs"]["kwargs"]["rebuild_run_id"] for item in dispatched)
    charge = (
        await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == book.id))
    ).scalar_one()
    assert charge.quantity == 1
    from app.utils.billing_utils import calculate_upload_usage_summary
    from app.models.user import User

    usage = await calculate_upload_usage_summary(db, await db.get(User, user_id))
    assert usage.manuscript_uploads == 2


@pytest.mark.asyncio
async def test_reprocess_empty_manuscript(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-empty-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    book_id = await _create_editor_project(client, headers)

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
        json={"confirm_upload_charge": True},
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

    async def _fake_prepare_rebuild(db, book, **_kwargs):
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
        json={"confirm_upload_charge": True},
    )
    assert response.status_code == 200

    response2 = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
        json={"confirm_upload_charge": True},
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_reprocess_success(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-ok-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, BookUploadCharge

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
        json={"confirm_upload_charge": True},
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
    charge = (
        await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == book_id))
    ).scalar_one()
    assert charge.charge_kind == "manual_reprocess"


@pytest.mark.asyncio
async def test_reprocess_charge_failure_invalidates_queued_rebuild(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-charge-fail-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, BookUploadCharge
    from app.services.editor_project_service import get_rebuild_run_id

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    async def _fail_charge(*_args, **_kwargs):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.record_book_upload_charge",
        _fail_charge,
    )

    book = Book(
        user_id=user_id,
        title="Charge Failure",
        format="manual",
        s3_key="charge-failure.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id)

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers,
        json={"confirm_upload_charge": True},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Something went wrong. Please try again."
    assert len(dispatched) == 1
    await db.refresh(book)
    assert book.status == "failed"
    assert get_rebuild_run_id(book) is None
    charge_count = len(
        (
            await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == book.id))
        ).scalars().all()
    )
    assert charge_count == 0


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
        json={"confirm_upload_charge": True},
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
        json={"confirm_upload_charge": True},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reprocess_rejects_when_upload_capacity_is_exhausted(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-quota-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from fastapi import HTTPException
    from app.models.book import Book, BookUploadCharge

    book = Book(
        user_id=user_id,
        title="Quota Test",
        format="txt",
        s3_key="quota.txt",
        status="ready",
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id)

    async def _reject_upload_limit(*_args, **_kwargs):
        raise HTTPException(403, "Author tier includes 15 uploads. You have 0 remaining.")

    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.check_upload_limit",
        _reject_upload_limit,
    )

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers,
        json={"confirm_upload_charge": True},
    )

    assert response.status_code == 403
    assert "0 remaining" in response.json()["detail"]
    charge_count = len(
        (
            await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == book.id))
        ).scalars().all()
    )
    assert charge_count == 0


@pytest.mark.asyncio
async def test_editor_project_import_auto_reprocesses_once_at_word_threshold_without_charge(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-auto-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book_id = await _create_editor_project(client, headers, title="Auto Draft")

    from app.models.book import Book, BookUploadCharge, Chapter

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/import",
        headers=headers,
        data={
            "text": " ".join(["threshold"] * 2000),
            "title": "Opening",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )

    assert response.status_code == 200
    book = await db.get(Book, uuid.UUID(book_id))
    chapter = (
        await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 1))
    ).scalar_one()
    charge_count = len(
        (
            await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == book.id))
        ).scalars().all()
    )

    assert chapter.word_count >= 2000
    assert book.status == "processing"
    assert book.writer_workspace["reprocess"]["last_reason"] == "auto_first_2000_words"
    assert book.writer_workspace["reprocess"]["auto_first_threshold_words"] == 2000
    assert len(dispatched) == 1
    assert dispatched[0]["kwargs"]["kwargs"]["rebuild_run_id"]
    assert charge_count == 0


@pytest.mark.asyncio
async def test_manual_reprocess_mode_marks_saved_chapter_pending_without_queue(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-manual-mode-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book_id = await _create_editor_project(client, headers, title="Manual Mode Draft")

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    workspace_response = await client.put(
        f"/api/v1/books/{book_id}/writer-workspace",
        headers=headers,
        json={"reprocess": {"auto_reprocess_enabled": False}},
    )
    assert workspace_response.status_code == 200

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/import",
        headers=headers,
        data={
            "text": " ".join(["manual"] * 2000),
            "title": "Manual Opening",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )

    assert response.status_code == 200
    assert dispatched == []
    workspace = (await client.get(f"/api/v1/books/{book_id}/writer-workspace", headers=headers)).json()
    assert workspace["reprocess"]["auto_reprocess_enabled"] is False
    assert workspace["reprocess"]["pending_chapters"] == [1]
    assert workspace["reprocess"]["last_mode_changed_at"]


@pytest.mark.asyncio
async def test_manual_chapter_reprocess_queues_one_chapter_without_upload_charge(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"repr-one-chapter-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book_id = await _create_editor_project(client, headers, title="One Chapter Draft")

    import_response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/import",
        headers=headers,
        data={
            "text": "Chapter text that needs a targeted reprocess.",
            "title": "Opening",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )
    assert import_response.status_code == 200
    await client.put(
        f"/api/v1/books/{book_id}/writer-workspace",
        headers=headers,
        json={"reprocess": {"auto_reprocess_enabled": False, "pending_chapters": [1]}},
    )

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/chapters/1/reprocess",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["chapters_queued"] == 1
    assert body["upload_charge_consumed"] is False
    assert len(dispatched) == 1
    assert dispatched[0]["kwargs"]["args"] == [book_id, 1]
    assert dispatched[0]["kwargs"]["kwargs"] == {"manual_reprocess": True}
    from app.models.book import Book, BookUploadCharge

    book = await db.get(Book, uuid.UUID(book_id))
    assert book.writer_workspace["reprocess"]["pending_chapters"] == []
    charge_count = len(
        (
            await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == uuid.UUID(book_id)))
        ).scalars().all()
    )
    assert charge_count == 0
