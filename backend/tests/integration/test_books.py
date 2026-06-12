import time
import uuid
from io import BytesIO

from docx import Document
import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter, ChapterMedia


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token

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
    token = create_access_token(str(response.json()["id"]))
    return {"Authorization": f"Bearer {token}"}, uuid.UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_manuscript_import_dispatches_analysis_async(client, db, monkeypatch):
    headers, user_id = await _register_user(client, f"import-async-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(user_id=user_id, title="Async Import", format="txt", s3_key="async.txt", status="ready", mode="author")
    db.add(book)
    await db.commit()

    async def _fake_process_chapter(_db, _book, ch_data, queue_wait_ms=None):
        _db.add(
            Chapter(
                book_id=_book.id,
                number=int(ch_data["number"]),
                title=ch_data.get("title"),
                s3_key=f"chapters/{_book.id}/{int(ch_data['number'])}.json",
                processed=True,
            )
        )
        await _db.flush()

    monkeypatch.setattr("app.api.v1.routes.books._process_chapter", _fake_process_chapter)
    monkeypatch.setattr("app.api.v1.routes.books.extract_novel_scene_candidates", lambda **_kwargs: [])

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.api.v1.routes.books.replace_chapter_novel_scenes", _noop)
    monkeypatch.setattr("app.api.v1.routes.books.sync_chapter_content_from_novel_scenes", _noop)

    dispatched: list[dict] = []

    class _Result:
        def __init__(self, task_id: str):
            self.id = task_id

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return _Result(f"analysis-{len(dispatched)}")

    monkeypatch.setattr("app.api.v1.routes.books.imports.analyse_chapter_task.apply_async", _fake_apply_async)

    started_at = time.perf_counter()
    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/import",
        headers=headers,
        data={
            "text": "Arrival at the docks.",
            "title": "Chapter 1",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )
    elapsed = time.perf_counter() - started_at

    assert response.status_code == 200
    assert elapsed < 5
    payload = response.json()
    assert payload["status"] == "imported"
    assert payload["chapters_created"] == 1
    assert payload["analysis_dispatched"] == 1
    assert payload["analysis_tasks"][0]["task_id"] == "analysis-1"
    assert len(dispatched) == 1
    assert dispatched[0]["kwargs"] == {
        "args": [payload["analysis_tasks"][0]["chapter_id"], str(book.id)],
        "kwargs": {"is_reprocessing": False},
        "queue": "analysis",
    }

    chapter = (await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 1))).scalar_one()
    assert chapter.analysis_state["status"] == "queued"


@pytest.mark.asyncio
async def test_editor_inserted_image_reloads_and_exports_with_novel_docx(client, db, monkeypatch):
    storage: dict[str, bytes] = {}

    def _upload_text(key: str, content: str) -> str:
        storage[key] = content.encode("utf-8")
        return key

    def _upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        storage[key] = raw
        return key

    def _download_book(key: str) -> bytes:
        return storage[key]

    for target in (
        "app.core.storage",
        "app.utils.book_utils",
        "app.utils.reader_utils",
        "app.services.chapter_recovery_service",
        "app.api.v1.routes.reader.core",
    ):
        monkeypatch.setattr(f"{target}.download_book", _download_book, raising=False)
    monkeypatch.setattr("app.core.storage.upload_text", _upload_text, raising=False)
    monkeypatch.setattr("app.core.storage.upload_binary", _upload_binary, raising=False)
    monkeypatch.setattr("app.utils.book_utils.upload_text", _upload_text, raising=False)
    monkeypatch.setattr("app.utils.book_utils.upload_binary", _upload_binary, raising=False)
    monkeypatch.setattr("app.services.chapter_recovery_service.get_presigned_url", lambda _key: None, raising=False)
    monkeypatch.setattr("app.utils.reader_utils.get_presigned_url", lambda _key: None, raising=False)

    headers, user_id = await _register_user(client, f"editor-image-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(
        user_id=user_id,
        title="Image Persistence",
        format="txt",
        work_type="novel",
        s3_key="books/image-persistence.txt",
        status="ready",
        mode="author",
        is_editor_project=True,
        writer_workspace={
            "reprocess": {
                "auto_reprocess_enabled": False,
                "pending_chapters": [],
            }
        },
    )
    db.add(book)
    await db.commit()

    png_data_uri = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/import",
        headers=headers,
        data={
            "text": "Intro\n\nOutro",
            "html": f'<p>Intro</p><p><img src="{png_data_uri}" alt="Inserted map"></p><p>Outro</p>',
            "title": "Opening",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )

    assert response.status_code == 200
    chapter = (await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 1))).scalar_one()
    media = (await db.execute(select(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id))).scalar_one()
    assert media.marker.startswith("[[IMAGE:")
    assert media.content_type == "image/png"

    reload_response = await client.get(
        f"/api/v1/reader/{book.id}/chapter/1",
        headers=headers,
        params={"include": "text_content,html_content,media"},
    )

    assert reload_response.status_code == 200
    reloaded = reload_response.json()
    assert media.marker in reloaded["html_content"]
    assert reloaded["media"][0]["marker"] == media.marker
    assert reloaded["media"][0]["content_base64"]

    export_response = await client.get(
        f"/api/v1/books/{book.id}/novel/export",
        headers=headers,
        params={
            "format": "docx",
            "include_images": "true",
            "image_placement": "inline",
        },
    )

    assert export_response.status_code == 200
    doc = Document(BytesIO(export_response.content))
    assert len(doc.inline_shapes) >= 2
