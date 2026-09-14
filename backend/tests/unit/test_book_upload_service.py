import io
import threading
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import UploadFile

from app.api.v1.routes.books import lifecycle
from app.services import book_upload_service


@pytest.fixture(autouse=True)
def _mock_upload_intent_io(monkeypatch):
    monkeypatch.setattr(book_upload_service, "persist_upload_intent", AsyncMock())
    monkeypatch.setattr(
        book_upload_service,
        "clear_upload_intent",
        AsyncMock(return_value=True),
    )


class _FailingCommitDb:
    def __init__(self) -> None:
        self.added = []
        self.rollback = AsyncMock()

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        raise RuntimeError("database unavailable")


def _upload_kwargs(db):
    return {
        "db": db,
        "current_user": SimpleNamespace(id=uuid.uuid4()),
        "filename": "story.txt",
        "raw": b"Chapter one",
        "title": "Story",
        "genre": "Fantasy",
        "author": "Author",
        "resolved_work_type": "novel",
        "fmt": "txt",
        "selected_series": [],
        "visibility": "private",
        "description": None,
        "mode": "author",
        "cover_raw": b"cover",
        "cover_suffix": "png",
        "cover_content_type": "image/png",
        "preserve_chapter_numbers": False,
        "preserve_source_chapters": False,
        "force_single_manuscript": False,
    }


async def test_upload_removes_source_when_cover_upload_fails(monkeypatch):
    db = _FailingCommitDb()

    def fail_cover_upload(key, *_args):
        if key.startswith("books/"):
            return key
        raise OSError("object store unavailable")

    monkeypatch.setattr(book_upload_service.storage, "upload_binary", fail_cover_upload)
    cleanup = AsyncMock(return_value=["books/user/story.txt"])
    monkeypatch.setattr(book_upload_service, "delete_storage_keys_best_effort", cleanup)

    with pytest.raises(OSError, match="object store unavailable"):
        await book_upload_service.create_uploaded_book_from_raw(**_upload_kwargs(db))

    db.rollback.assert_awaited_once()
    cleaned_keys = cleanup.await_args.args[0]
    assert len(cleaned_keys) == 1
    assert cleaned_keys[0].startswith("books/")
    assert cleaned_keys[0].endswith("/story.txt")
    assert cleanup.await_args.kwargs == {"context": "book_upload"}


async def test_upload_removes_all_new_objects_when_database_commit_fails(monkeypatch):
    db = _FailingCommitDb()
    monkeypatch.setattr(book_upload_service.storage, "upload_binary", lambda key, *_args: key)
    monkeypatch.setattr(
        book_upload_service,
        "get_or_create_processing_run",
        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
    )
    monkeypatch.setattr(book_upload_service, "ensure_task_execution", AsyncMock())
    cleanup = AsyncMock(return_value=[])
    monkeypatch.setattr(book_upload_service, "delete_storage_keys_best_effort", cleanup)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await book_upload_service.create_uploaded_book_from_raw(**_upload_kwargs(db))

    db.rollback.assert_awaited_once()
    cleaned_keys = cleanup.await_args.args[0]
    assert len(cleaned_keys) == 2
    assert cleaned_keys[0].startswith("books/")
    assert cleaned_keys[1].startswith("covers/")
    assert cleanup.await_args.kwargs == {"context": "book_upload"}


async def test_upload_runs_blocking_storage_calls_off_the_event_loop(monkeypatch):
    db = _FailingCommitDb()
    event_loop_thread = threading.get_ident()
    storage_threads: list[int] = []

    def upload_object(key, *_args):
        storage_threads.append(threading.get_ident())
        return key

    monkeypatch.setattr(book_upload_service.storage, "upload_binary", upload_object)
    monkeypatch.setattr(
        book_upload_service,
        "get_or_create_processing_run",
        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
    )
    monkeypatch.setattr(book_upload_service, "ensure_task_execution", AsyncMock())
    monkeypatch.setattr(
        book_upload_service,
        "delete_storage_keys_best_effort",
        AsyncMock(return_value=[]),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await book_upload_service.create_uploaded_book_from_raw(**_upload_kwargs(db))

    assert storage_threads
    assert all(thread_id != event_loop_thread for thread_id in storage_threads)


async def test_cover_update_removes_new_object_when_database_commit_fails(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4(), cover_s3_key="covers/user/old.png")
    user = SimpleNamespace(id=uuid.uuid4())
    db = SimpleNamespace(commit=AsyncMock(side_effect=RuntimeError("database unavailable")))
    db.rollback = AsyncMock()
    monkeypatch.setattr(
        lifecycle,
        "get_owned_book",
        AsyncMock(return_value=book),
    )
    monkeypatch.setattr(
        lifecycle.storage,
        "upload_binary",
        lambda *_args: "covers/user/new.png",
    )
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr(lifecycle, "delete_storage_key_best_effort", cleanup)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await lifecycle.update_book_cover(
            book.id,
            cover_file=UploadFile(filename="cover.png", file=io.BytesIO(b"\x89PNGpayload")),
            db=db,
            current_user=user,
        )

    db.rollback.assert_awaited_once()
    cleanup.assert_awaited_once_with("covers/user/new.png", context="book_cover")
