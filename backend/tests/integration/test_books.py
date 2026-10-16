import time
import uuid
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from docx import Document
from sqlalchemy import select

from app.models.book import Book, BookNote, Chapter, ChapterMedia
from app.models.intelligence import QuoteEntry
from app.models.operations import ManuscriptExportJob, ManuscriptImportJob


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
async def test_large_export_prepare_creates_private_durable_job(client, db, monkeypatch):
    from app.services import manuscript_export_service

    headers, user_id = await _register_user(
        client, f"export-job-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
    other_headers, _other_user_id = await _register_user(
        client, f"export-job-other-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
    book = Book(
        user_id=user_id,
        title="Long Draft",
        format="txt",
        s3_key="long-draft.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    db.add_all(
        [
            Chapter(
                book_id=book.id,
                number=number,
                title=f"Chapter {number}",
                s3_key=f"chapters/{number}.txt",
                word_count=100,
            )
            for number in range(1, 3)
        ]
    )
    await db.commit()
    monkeypatch.setattr(
        manuscript_export_service.settings,
        "MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_CHAPTERS",
        2,
    )
    monkeypatch.setattr(
        manuscript_export_service.settings,
        "MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_WORDS",
        1_000_000,
    )

    prepared = await client.post(
        f"/api/v1/books/{book.id}/exports/prepare",
        headers=headers,
        json={
            "export_kind": "manuscript",
            "format": "pdf",
            "preset": "standard_manuscript",
        },
    )

    assert prepared.status_code == 202
    payload = prepared.json()
    assert payload["delivery"] == "job"
    assert payload["job"]["status"] == "queued"
    assert payload["job"]["download_url"] is None

    legacy = await client.get(
        f"/api/v1/books/{book.id}/manuscript/export?format=pdf",
        headers=headers,
    )
    assert legacy.status_code == 202
    assert legacy.headers["location"] == f"/api/v1/books/{book.id}/exports/{payload['job']['id']}"
    assert legacy.json()["job"]["id"] == payload["job"]["id"]
    job_id = uuid.UUID(payload["job"]["id"])
    job = await db.get(ManuscriptExportJob, job_id)
    assert job is not None
    assert job.user_id == user_id
    assert job.artifact_storage_key is None

    status_response = await client.get(
        f"/api/v1/books/{book.id}/exports/{job_id}",
        headers=headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["id"] == str(job_id)

    processed = await manuscript_export_service.process_manuscript_export_job(db, job_id)
    assert processed == {"status": "completed", "job_id": str(job_id)}

    completed_status = await client.get(
        f"/api/v1/books/{book.id}/exports/{job_id}",
        headers=headers,
    )
    assert completed_status.status_code == 200
    assert completed_status.json()["status"] == "completed"
    assert completed_status.json()["download_url"].endswith(f"/{job_id}/download")

    downloaded = await client.get(
        f"/api/v1/books/{book.id}/exports/{job_id}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")

    job = await db.get(ManuscriptExportJob, job_id)
    assert job is not None
    job.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    assert await manuscript_export_service.cleanup_expired_manuscript_export_jobs(db) == 1

    expired_download = await client.get(
        f"/api/v1/books/{book.id}/exports/{job_id}/download",
        headers=headers,
    )
    assert expired_download.status_code == 410

    other_status = await client.get(
        f"/api/v1/books/{book.id}/exports/{job_id}",
        headers=other_headers,
    )
    assert other_status.status_code == 404


@pytest.mark.asyncio
async def test_saved_quotes_and_notes_cursor_endpoints_page_tied_rows(client, db):
    headers, user_id = await _register_user(
        client, f"saved-pages-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
    book = Book(
        user_id=user_id,
        title="Saved Pages",
        format="txt",
        s3_key="saved-pages.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    for index in range(3):
        db.add(
            QuoteEntry(
                user_id=user_id,
                book_id=book.id,
                quote_text=f"Quote {index}",
            )
        )
        db.add(
            BookNote(
                user_id=user_id,
                book_id=book.id,
                title=f"Note {index}",
                body=f"Body {index}",
            )
        )
    await db.commit()

    quote_first = await client.get("/api/v1/books/quotes/page?limit=2", headers=headers)
    note_first = await client.get("/api/v1/books/notes/page?limit=2", headers=headers)
    assert quote_first.status_code == 200
    assert note_first.status_code == 200
    assert quote_first.json()["has_more"] is True
    assert note_first.json()["has_more"] is True
    assert all(item["body"] is None for item in note_first.json()["items"])

    quote_second = await client.get(
        "/api/v1/books/quotes/page",
        headers=headers,
        params={"limit": 2, "cursor": quote_first.json()["next_cursor"]},
    )
    note_second = await client.get(
        "/api/v1/books/notes/page",
        headers=headers,
        params={
            "limit": 2,
            "cursor": note_first.json()["next_cursor"],
            "include_body": True,
        },
    )
    assert quote_second.status_code == 200
    assert note_second.status_code == 200
    quote_ids = {
        item["id"] for item in [*quote_first.json()["items"], *quote_second.json()["items"]]
    }
    note_ids = {item["id"] for item in [*note_first.json()["items"], *note_second.json()["items"]]}
    assert len(quote_ids) == 3
    assert len(note_ids) == 3
    assert note_second.json()["items"][0]["body"].startswith("Body ")


@pytest.mark.asyncio
async def test_manuscript_import_dispatches_analysis_async(client, db, monkeypatch):
    headers, user_id = await _register_user(
        client, f"import-async-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
    book = Book(
        user_id=user_id,
        title="Async Import",
        format="txt",
        s3_key="async.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()

    process_chapter_calls: list[dict] = []

    async def _fake_process_chapter(
        _db,
        _book,
        ch_data,
        queue_wait_ms=None,
        dispatch_analysis=True,
        check_book_completion=True,
    ):
        process_chapter_calls.append(
            {
                "dispatch_analysis": dispatch_analysis,
                "check_book_completion": check_book_completion,
            }
        )
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

    monkeypatch.setattr(
        "app.services.manuscript_import_service._process_chapter", _fake_process_chapter
    )
    monkeypatch.setattr(
        "app.services.manuscript_import_service.extract_novel_scene_candidates",
        lambda **_kwargs: [],
    )

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.services.manuscript_import_service.replace_chapter_novel_scenes", _noop
    )
    monkeypatch.setattr(
        "app.services.manuscript_import_service.sync_chapter_content_from_novel_scenes", _noop
    )

    dispatched: list[dict] = []

    class _Result:
        def __init__(self, task_id: str):
            self.id = task_id

    async def _fake_enqueue(_db, **kwargs):
        dispatched.append(kwargs)
        return _Result(f"analysis-{len(dispatched)}")

    monkeypatch.setattr(
        "app.services.manuscript_import_service.enqueue_analysis_execution", _fake_enqueue
    )

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
    assert process_chapter_calls == [
        {
            "dispatch_analysis": False,
            "check_book_completion": False,
        }
    ]
    assert payload["analysis_tasks"][0]["task_id"] == "analysis-1"
    assert len(dispatched) == 1
    assert str(dispatched[0]["chapter_id"]) == payload["analysis_tasks"][0]["chapter_id"]
    assert dispatched[0]["book_id"] == book.id

    chapter = (
        await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 1))
    ).scalar_one()
    assert chapter.analysis_state["status"] == "queued"


@pytest.mark.asyncio
async def test_large_manuscript_import_returns_durable_job_with_status_cancel_and_retry(
    client,
    db,
    monkeypatch,
):
    headers, user_id = await _register_user(
        client,
        f"durable-import-{uuid.uuid4().hex[:8]}@lorevia.app",
    )
    book = Book(
        user_id=user_id,
        title="Durable Import",
        format="txt",
        work_type="novel",
        s3_key="durable.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()

    staged: dict[str, bytes] = {}

    def _upload_binary(key: str, raw: bytes, _content_type: str | None = None) -> str:
        staged[key] = raw
        return key

    async def _skip_dispatch(_db, _job):
        return False

    monkeypatch.setattr(
        "app.services.manuscript_import_job_service.storage.upload_binary",
        _upload_binary,
    )
    monkeypatch.setattr(
        "app.services.manuscript_import_job_service.dispatch_manuscript_import_job",
        _skip_dispatch,
    )

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/import",
        headers=headers,
        files=[
            ("files", ("chapter-1.txt", b"The first gate opens.", "text/plain")),
            ("files", ("chapter-2.txt", b"The second gate closes.", "text/plain")),
        ],
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["progress_completed"] == 0
    assert payload["progress_total"] == 3
    assert len(staged) == 2

    job_id = uuid.UUID(payload["id"])
    job = await db.get(ManuscriptImportJob, job_id)
    assert job is not None
    assert job.book_id == book.id
    assert len(job.source_files_json) == 2

    status_response = await client.get(
        f"/api/v1/books/{book.id}/manuscript/import/{job_id}",
        headers=headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "queued"

    cancel_response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/import/{job_id}/cancel",
        headers=headers,
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    retry_response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/import/{job_id}/retry",
        headers=headers,
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "queued"


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
        "app.utils.books.manuscript",
        "app.utils.reader_utils",
        "app.services.chapter_recovery_service",
        "app.api.v1.routes.reader.core",
    ):
        monkeypatch.setattr(f"{target}.download_book", _download_book, raising=False)
    monkeypatch.setattr("app.core.storage.upload_text", _upload_text, raising=False)
    monkeypatch.setattr("app.core.storage.upload_binary", _upload_binary, raising=False)
    monkeypatch.setattr("app.utils.books.manuscript.upload_text", _upload_text, raising=False)
    monkeypatch.setattr("app.utils.books.manuscript.upload_binary", _upload_binary, raising=False)
    monkeypatch.setattr(
        "app.services.chapter_recovery_service.get_presigned_url", lambda _key: None, raising=False
    )
    monkeypatch.setattr(
        "app.utils.reader_utils.get_presigned_url", lambda _key: None, raising=False
    )

    headers, user_id = await _register_user(
        client, f"editor-image-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
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
    chapter = (
        await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 1))
    ).scalar_one()
    media = (
        await db.execute(select(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id))
    ).scalar_one()
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
