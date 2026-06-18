"""Unit coverage for book service persistence wrappers."""

from io import BytesIO
import uuid

import pytest

from app.services import book_service


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class FakeDB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.refreshed = []

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        self.flushes += 1

    async def refresh(self, value):
        self.refreshed.append(value)

    async def execute(self, _statement):
        return FakeResult(self.results.pop(0))


@pytest.mark.asyncio
async def test_create_book_uploads_source_and_persists_pending_record(monkeypatch):
    captured = []
    monkeypatch.setattr(book_service, "upload_book", lambda file, user_id, filename: captured.append((file.read(), user_id, filename)) or "books/source.docx")
    db = FakeDB()
    user_id = uuid.uuid4()
    book = await book_service.create_book(
        db,
        user_id,
        "Atlas",
        "Fantasy",
        "A. Writer",
        "docx",
        BytesIO(b"manuscript"),
        "atlas.docx",
        "9780000000000",
    )

    assert captured == [(b"manuscript", str(user_id), "atlas.docx")]
    assert book.title == "Atlas" and book.status == "pending"
    assert book.s3_key == "books/source.docx" and book.isbn == "9780000000000"
    assert db.added == [book] and db.commits == 1 and db.refreshed == [book]


@pytest.mark.asyncio
async def test_create_editor_project_initializes_ready_manual_workspace(monkeypatch):
    uploads = []
    monkeypatch.setattr(book_service, "upload_text", lambda key, text: uploads.append((key, text)))
    monkeypatch.setattr(book_service, "normalize_writer_workspace", lambda _value: {"processing": {}})
    db = FakeDB()
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = await book_service.create_editor_project(
        db,
        user_id,
        book_id=book_id,
        title="New Draft",
        genre=None,
        author="A. Writer",
        work_type="novel",
    )

    expected_key = f"books/{user_id}/{book_id}/empty.txt"
    assert uploads == [(expected_key, "")]
    assert book.id == book_id and book.s3_key == expected_key
    assert book.status == "ready" and book.mode == "author"
    assert book.source_kind == "manual" and book.is_editor_project is True
    assert book.writer_workspace["processing"]["is_fully_ready"] is True
    assert db.added == [book] and db.flushes == 1


@pytest.mark.asyncio
async def test_get_and_count_user_books_return_scalar_values():
    marker = object()
    db = FakeDB(marker, 4, None)
    assert await book_service.get_user_book(db, uuid.uuid4(), uuid.uuid4()) is marker
    assert await book_service.count_user_books(db, uuid.uuid4()) == 4
    assert await book_service.count_user_books(db, uuid.uuid4()) == 0
