from __future__ import annotations

import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import DataDeletionRequest
from app.services import privacy_service
from app.utils.privacy_utils import (
    DATA_DELETION_STATUS_COMPLETED,
    DATA_DELETION_STATUS_FAILED,
    DATA_DELETION_STATUS_PENDING,
    DATA_DELETION_STATUS_PROCESSING,
)


class FakeScalarResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class FakeDb:
    def __init__(self, *, rows=None, get_map=None):
        self.rows = rows or []
        self.get_map = get_map or {}
        self.added = []
        self.committed = 0
        self.flushed = 0
        self.refreshed = []
        self.deleted = []

    async def execute(self, statement):
        return FakeScalarResult(self.rows)

    async def get(self, model, item_id):
        return self.get_map.get((model, item_id), self.get_map.get(item_id))

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed += 1

    async def flush(self):
        self.flushed += 1

    async def refresh(self, item):
        self.refreshed.append(item)

    async def delete(self, item):
        self.deleted.append(item)


def test_json_export_helpers_serialize_models_and_special_values():
    now = datetime(2026, 6, 17, tzinfo=UTC)
    item_id = uuid.uuid4()
    model = SimpleNamespace(id=item_id, created_at=now, missing=None)

    payload = privacy_service._model_payload(model, ["id", "created_at", "missing", "absent"])
    assert payload == {"id": item_id, "created_at": now, "missing": None, "absent": None}

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        privacy_service._write_json(archive, "account.json", payload)

    with zipfile.ZipFile(BytesIO(buffer.getvalue())) as archive:
        exported = json.loads(archive.read("account.json"))

    assert exported["id"] == str(item_id)
    assert exported["created_at"] == str(now)


@pytest.mark.asyncio
async def test_download_text_or_error_handles_structured_plain_and_failed_downloads(monkeypatch):
    def fake_download_book(key: str):
        if key == "structured":
            return b"structured bytes"
        if key == "plain":
            return b"Plain text"
        raise RuntimeError("missing object")

    def fake_deserialize(raw: bytes):
        if raw == b"structured bytes":
            return SimpleNamespace(text="Text", html="<p>Text</p>", metadata={"source": "json"})
        raise ValueError("not structured")

    monkeypatch.setattr(privacy_service.storage, "download_book", fake_download_book)
    monkeypatch.setattr(privacy_service, "deserialize_manuscript_content", fake_deserialize)

    assert await privacy_service._download_text_or_error("structured") == {
        "storage_key": "structured",
        "text": "Text",
        "html": "<p>Text</p>",
        "metadata": {"source": "json"},
    }
    assert await privacy_service._download_text_or_error("plain") == {
        "storage_key": "plain",
        "text": "Plain text",
    }
    failed = await privacy_service._download_text_or_error("missing")
    assert failed["storage_key"] == "missing"
    assert "missing object" in failed["error"]


@pytest.mark.asyncio
async def test_build_user_data_export_includes_account_book_chapter_and_domain_files(monkeypatch):
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="mara@example.test",
        username="mara",
        tier="author",
        reading_mode="author",
        daily_word_goal=1200,
        legal_version="2026-01",
        legal_accepted_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    book = SimpleNamespace(
        id=uuid.uuid4(),
        title="Gate Draft",
        author="Mara",
        genre="Fantasy",
        format="novel",
        work_type="novel",
        status="ready",
        mode="author",
        source_kind="upload",
        total_chapters=1,
        total_tokens=400,
        total_words=300,
        is_public=False,
        public_description=None,
        public_status="private",
        created_at=datetime.now(UTC),
        archived_at=None,
        hidden_at=None,
    )
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        number=1,
        title="The Gate",
        description="Opening",
        chapter_kind="chapter",
        word_count=300,
        token_count=400,
        s3_key="books/gate/chapter-1.json",
    )
    preference = SimpleNamespace(
        marketing_enabled=False,
        product_enabled=True,
        beta_reader_enabled=True,
        updated_at=datetime.now(UTC),
    )
    domain_row = SimpleNamespace(
        id=uuid.uuid4(),
        title="Note",
        body="Remember the key",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    class SequenceDb:
        def __init__(self):
            self.results = [[book], [preference], [chapter]] + [[domain_row] for _ in range(10)]

        async def execute(self, _statement):
            return FakeScalarResult(self.results.pop(0))

    async def fake_download(key):
        assert key == chapter.s3_key
        return {
            "storage_key": key,
            "text": "Chapter body",
            "html": "<p>Chapter body</p>",
            "metadata": {},
        }

    monkeypatch.setattr(privacy_service, "_download_text_or_error", fake_download)

    archive_bytes = await privacy_service.build_user_data_export(SequenceDb(), user)

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())
        account = json.loads(archive.read("account.json"))
        chapters = json.loads(archive.read(f"books/{book.id}/chapters.json"))
        notes = json.loads(archive.read(f"books/{book.id}/notes.json"))

    assert account["email"] == "mara@example.test"
    assert chapters[0]["manuscript"]["text"] == "Chapter body"
    assert notes[0]["title"] == "Note"
    assert f"books/{book.id}/beta_read_assignments.json" in names


@pytest.mark.asyncio
async def test_collect_book_storage_keys_collects_and_deduplicates_all_runtime_models():
    book_id = uuid.uuid4()
    book = SimpleNamespace(s3_key="source/book.json", cover_s3_key="covers/book.jpg")

    class SequenceDb:
        def __init__(self):
            self.results = [
                ["chapters/1.json", "source/book.json"],
                ["versions/chapter-1.json"],
                ["versions/scene-1.json"],
                ["world/canon.txt"],
                ["media/map.png"],
                ["forum/post.png"],
                ["forum/comment.png", "media/map.png"],
            ]

        async def get(self, model, item_id):
            assert item_id == book_id
            return book

        async def execute(self, _statement):
            return FakeScalarResult(self.results.pop(0))

    keys = await privacy_service.collect_book_storage_keys(SequenceDb(), book_id)

    assert keys == [
        "source/book.json",
        "covers/book.jpg",
        "chapters/1.json",
        "versions/chapter-1.json",
        "versions/scene-1.json",
        "world/canon.txt",
        "media/map.png",
        "forum/post.png",
        "forum/comment.png",
    ]


@pytest.mark.asyncio
async def test_delete_storage_keys_dedupes_keys_and_reports_errors(monkeypatch):
    deleted = []

    def fake_delete_object(key: str):
        if key == "bad":
            raise RuntimeError("storage unavailable")
        deleted.append(key)

    monkeypatch.setattr(privacy_service.storage, "delete_object", fake_delete_object)

    result = await privacy_service.delete_storage_keys(["one", "", "one", "bad", "two"])

    assert deleted == ["one", "two"]
    assert result["deleted"] == ["one", "two"]
    assert result["errors"] == {"bad": "storage unavailable"}


@pytest.mark.asyncio
async def test_queue_book_permanent_deletion_hides_book_and_creates_request(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        title="Delete Me",
        hidden_at=None,
        archived_at=datetime.now(UTC),
        is_public=True,
        public_status="published",
        public_visibility="public",
        public_share_status="shared",
    )
    user = SimpleNamespace(id=user_id)

    async def fake_collect(db, requested_book_id):
        assert requested_book_id == book_id
        return ["book/source.txt", "cover.png"]

    monkeypatch.setattr(privacy_service, "collect_book_storage_keys", fake_collect)
    db = FakeDb()

    request = await privacy_service.queue_book_permanent_deletion(db, book, "DELETE BOOK", user)

    assert book.hidden_at is not None
    assert book.archived_at is None
    assert book.is_public is False
    assert book.public_status == "removed"
    assert request in db.added
    assert request.request_type == "book"
    assert request.status == DATA_DELETION_STATUS_PENDING
    assert request.storage_keys_json == ["book/source.txt", "cover.png"]
    assert request.metadata_json["title"] == "Delete Me"
    assert db.committed == 1
    assert db.refreshed == [request]

    with pytest.raises(HTTPException) as exc:
        await privacy_service.queue_book_permanent_deletion(FakeDb(), book, "wrong", user)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_request_account_deletion_anonymizes_user_books_and_tracks_provider_followup(
    monkeypatch,
):
    user_id = uuid.uuid4()
    user = SimpleNamespace(
        id=user_id,
        email="Mara@Example.test",
        username="mara",
        password_hash="hash",
        tier="architect",
        token_version=2,
        supabase_auth_id="auth-1",
        deletion_status="active",
        deletion_requested_at=None,
        deletion_scheduled_for=None,
        deletion_provider_status=None,
        deletion_provider_metadata_json=None,
        deleted_email_hash=None,
        deleted_at=None,
    )
    successful_subscription = SimpleNamespace(paddle_sub_id="sub-ok", status="active")
    failed_subscription = SimpleNamespace(paddle_sub_id="sub-fail", status="active")
    book = SimpleNamespace(
        id=uuid.uuid4(),
        hidden_at=None,
        archived_at=datetime.now(UTC),
        is_public=True,
        public_status="published",
        public_visibility="public",
        public_share_status="shared",
    )

    class SequenceDb(FakeDb):
        def __init__(self):
            super().__init__()
            self.results = [
                [successful_subscription, failed_subscription],
                [book],
                ["forum/post.png"],
                ["forum/comment.png", "forum/post.png"],
            ]

        async def execute(self, _statement):
            return FakeScalarResult(self.results.pop(0))

    async def fake_cancel(subscription_id):
        if subscription_id == "sub-fail":
            raise RuntimeError("provider unavailable")
        return {"scheduled_change": "cancel"}

    async def fake_supabase_delete(auth_id):
        assert auth_id == "auth-1"
        return {"deleted": True, "followup_required": False}

    async def fake_collect(_db, requested_book_id):
        assert requested_book_id == book.id
        return ["book/source.json", "forum/post.png"]

    monkeypatch.setattr(privacy_service, "cancel_subscription_at_period_end", fake_cancel)
    monkeypatch.setattr(privacy_service, "delete_supabase_auth_user", fake_supabase_delete)
    monkeypatch.setattr(privacy_service, "collect_book_storage_keys", fake_collect)
    monkeypatch.setattr(privacy_service, "hash_password", lambda value: f"hashed:{len(value)}")
    monkeypatch.setattr(
        privacy_service, "next_token_version", lambda value: value.token_version + 1
    )
    db = SequenceDb()

    request, followup = await privacy_service.request_account_deletion(
        db,
        user,
        confirmation_text="DELETE MY ACCOUNT",
        password=None,
    )

    assert followup is True
    assert successful_subscription.status == "cancelling"
    assert failed_subscription.status == "active"
    assert user.email.startswith("deleted+")
    assert user.username is None
    assert user.tier == "free"
    assert user.token_version == 3
    assert user.supabase_auth_id is None
    assert user.deletion_status == "provider_followup_required"
    assert book.hidden_at is not None and book.is_public is False
    assert request.storage_keys_json == ["book/source.json", "forum/post.png", "forum/comment.png"]
    assert request.provider_actions_json["paddle"][1]["status"] == "followup_required"
    assert request in db.added and db.committed == 1 and db.refreshed == [request]


@pytest.mark.asyncio
async def test_request_account_deletion_rejects_invalid_local_credentials(monkeypatch):
    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="mara@example.test",
        supabase_auth_id=None,
        password_hash="hash",
        deletion_status="active",
        deleted_at=None,
    )

    with pytest.raises(HTTPException) as missing_password:
        await privacy_service.request_account_deletion(
            FakeDb(), user, confirmation_text="DELETE MY ACCOUNT", password=None
        )
    assert missing_password.value.status_code == 400

    monkeypatch.setattr(privacy_service, "verify_password", lambda password, hashed: False)
    with pytest.raises(HTTPException) as wrong_password:
        await privacy_service.request_account_deletion(
            FakeDb(), user, confirmation_text="DELETE MY ACCOUNT", password="wrong"
        )
    assert wrong_password.value.status_code == 403

    user.deletion_status = "pending_hard_delete"
    with pytest.raises(HTTPException) as duplicate:
        await privacy_service.request_account_deletion(
            FakeDb(), user, confirmation_text="DELETE MY ACCOUNT", password="anything"
        )
    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_hard_delete_account_product_data_deletes_books_rows_and_finalizes_user():
    user_id = uuid.uuid4()
    book_ids = [uuid.uuid4(), uuid.uuid4()]
    user = SimpleNamespace(
        id=user_id,
        deletion_status="pending_hard_delete",
        deletion_provider_status=None,
        email="old@example.test",
        username="old",
        tier="author",
        supabase_auth_id="auth-1",
        deletion_scheduled_for=datetime.now(UTC),
        deleted_at=None,
    )

    class DeleteDb(FakeDb):
        def __init__(self):
            super().__init__(get_map={(privacy_service.User, user_id): user})
            self.execute_count = 0

        async def execute(self, _statement):
            self.execute_count += 1
            return FakeScalarResult(book_ids if self.execute_count == 1 else [])

    db = DeleteDb()
    request = SimpleNamespace(user_id=user_id)

    await privacy_service._hard_delete_account_product_data(db, request)

    assert db.execute_count > 15
    assert user.deletion_status == "deleted"
    assert user.deletion_provider_status == "completed"
    assert user.email.startswith("deleted+")
    assert user.supabase_auth_id is None
    assert user.deletion_scheduled_for is None


@pytest.mark.asyncio
async def test_process_data_deletion_request_handles_completed_errors_book_and_unknown(monkeypatch):
    completed = SimpleNamespace(id=uuid.uuid4(), status=DATA_DELETION_STATUS_COMPLETED)
    assert await privacy_service.process_data_deletion_request(FakeDb(), completed) == {
        "id": str(completed.id),
        "status": DATA_DELETION_STATUS_COMPLETED,
        "skipped": True,
    }

    async def failing_delete_storage(keys):
        return {"deleted": [], "errors": {"bad": "failed"}}

    monkeypatch.setattr(privacy_service, "delete_storage_keys", failing_delete_storage)
    failed = SimpleNamespace(
        id=uuid.uuid4(),
        status=DATA_DELETION_STATUS_PENDING,
        started_at=None,
        attempts=0,
        storage_keys_json=["bad"],
        request_type="book",
        book_id=uuid.uuid4(),
        error_detail=None,
    )
    failed_result = await privacy_service.process_data_deletion_request(FakeDb(), failed)
    assert failed_result["status"] == DATA_DELETION_STATUS_FAILED
    assert failed.status == DATA_DELETION_STATUS_FAILED
    assert "bad" in failed.error_detail

    deleted_books = []

    async def successful_delete_storage(keys):
        return {"deleted": keys, "errors": {}}

    async def fake_hard_delete_book(db, book_id):
        deleted_books.append(book_id)

    monkeypatch.setattr(privacy_service, "delete_storage_keys", successful_delete_storage)
    monkeypatch.setattr(privacy_service, "_hard_delete_book", fake_hard_delete_book)
    book_request = SimpleNamespace(
        id=uuid.uuid4(),
        status=DATA_DELETION_STATUS_PENDING,
        started_at=None,
        attempts=None,
        storage_keys_json=["one"],
        request_type="book",
        book_id=uuid.uuid4(),
        error_detail="old",
        completed_at=None,
    )
    book_result = await privacy_service.process_data_deletion_request(FakeDb(), book_request)
    assert book_result["status"] == DATA_DELETION_STATUS_COMPLETED
    assert book_request.status == DATA_DELETION_STATUS_COMPLETED
    assert book_request.error_detail is None
    assert deleted_books == [book_request.book_id]

    unknown = SimpleNamespace(
        id=uuid.uuid4(),
        status=DATA_DELETION_STATUS_PENDING,
        started_at=None,
        attempts=0,
        storage_keys_json=[],
        request_type="mystery",
        book_id=None,
        error_detail=None,
    )
    unknown_result = await privacy_service.process_data_deletion_request(FakeDb(), unknown)
    assert unknown_result["status"] == DATA_DELETION_STATUS_FAILED
    assert "Unknown deletion request type" in unknown.error_detail


@pytest.mark.asyncio
async def test_process_due_data_deletion_requests_processes_matching_rows(monkeypatch):
    now = datetime.now(UTC)
    requests = [
        SimpleNamespace(
            id=uuid.uuid4(),
            status=DATA_DELETION_STATUS_PENDING,
            scheduled_for=now - timedelta(minutes=1),
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            status=DATA_DELETION_STATUS_FAILED,
            scheduled_for=now - timedelta(minutes=2),
        ),
    ]
    processed = []

    async def fake_process(db, request):
        processed.append(request.id)
        request.status = DATA_DELETION_STATUS_PROCESSING
        return {"id": str(request.id), "status": request.status}

    monkeypatch.setattr(privacy_service, "process_data_deletion_request", fake_process)
    db = FakeDb(rows=requests)

    result = await privacy_service.process_due_data_deletion_requests(db, limit=10)

    assert result["processed"] == 2
    assert processed == [request.id for request in requests]
    assert db.committed == 2
