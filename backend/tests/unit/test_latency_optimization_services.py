from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import Notification
from app.models.operations import ManuscriptImportJob
from app.services import (
    book_listing_service,
    character_listing_service,
    manuscript_import_job_service,
    manuscript_import_request_service,
    notification_service,
)
from app.utils.books import chapter_versions, manuscript, revision_service


class _ScalarResult:
    def __init__(self, *, scalar=None, scalars=None):
        self._scalar = scalar
        self._scalars = list(scalars or [])

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._scalars


class _FakeDb:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.statements = []
        self.added = []
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, value):
        now = datetime.now(UTC)
        value.created_at = getattr(value, "created_at", None) or now
        value.updated_at = now


def _upload(name: str, raw: bytes, *, size: int | None = None) -> UploadFile:
    upload = UploadFile(filename=name, file=io.BytesIO(raw))
    upload.size = size
    return upload


def test_book_page_cursor_round_trip_and_rejects_invalid_values():
    created_at = datetime(2026, 9, 10, 8, 30, tzinfo=UTC)
    book_id = uuid.uuid4()

    encoded = book_listing_service.encode_book_page_cursor(created_at, book_id)

    assert book_listing_service.decode_book_page_cursor(encoded) == (created_at, book_id)
    with pytest.raises(HTTPException, match="Invalid book page cursor"):
        book_listing_service.decode_book_page_cursor("not-a-cursor")


@pytest.mark.asyncio
async def test_book_page_limits_rows_and_emits_next_cursor(monkeypatch):
    user_id = uuid.uuid4()
    books = [
        Book(
            id=uuid.uuid4(),
            user_id=user_id,
            title=f"Book {index}",
            format="txt",
            s3_key=f"book-{index}.txt",
            created_at=datetime(2026, 9, 10, 8, index, tzinfo=UTC),
        )
        for index in range(3)
    ]
    db = _FakeDb([_ScalarResult(scalars=books)])
    async def _render(*_args, books, **_kwargs):
        assert len(books) == 2
        return []

    monkeypatch.setattr(book_listing_service, "build_book_out_list", _render)

    page = await book_listing_service.list_user_books_page(
        db,
        user_id=user_id,
        user_email="author@example.com",
        include_hidden=False,
        limit=2,
        cursor=None,
    )

    assert page.next_cursor is not None


@pytest.mark.asyncio
async def test_book_selector_uses_only_navigation_fields_without_render_aggregates():
    user_id = uuid.uuid4()
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Selector Book",
        author="Mira",
        format="txt",
        s3_key="selector-book.txt",
        mode="author",
        status="ready",
        work_type="novel",
        total_chapters=4,
        created_at=datetime(2026, 9, 10, 8, tzinfo=UTC),
    )
    db = _FakeDb([_ScalarResult(scalars=[book])])

    items = await book_listing_service.list_user_book_selectors(
        db,
        user_id=user_id,
        user_email="author@example.com",
        include_hidden=False,
    )

    assert len(db.statements) == 1
    assert "writer_workspace" not in str(db.statements[0])
    assert "processing_metadata" not in str(db.statements[0])
    assert items[0].model_dump() == {
        "id": book.id,
        "title": "Selector Book",
        "author": "Mira",
        "genre": None,
        "cover_url": None,
        "mode": "author",
        "status": "ready",
        "work_type": "novel",
        "total_chapters": 4,
        "hidden_at": None,
        "archived_at": None,
        "is_public": False,
        "source_kind": None,
        "public_share_status": None,
        "public_description": None,
        "primary_series_id": None,
        "series_name": None,
        "series_order": None,
        "workspace_shell": "author",
        "access_class": "owner",
        "can_switch_workspace_mode": True,
        "collaboration_role": None,
        "collaboration_permissions": None,
    }


def test_large_or_multi_file_imports_use_background_jobs(monkeypatch):
    monkeypatch.setattr(
        manuscript_import_job_service.settings,
        "MANUSCRIPT_IMPORT_ASYNC_THRESHOLD_BYTES",
        100,
    )
    assert manuscript_import_job_service.should_queue_manuscript_import([]) is False
    assert (
        manuscript_import_job_service.should_queue_manuscript_import(
            [_upload("small.txt", b"small", size=5)]
        )
        is False
    )
    assert (
        manuscript_import_job_service.should_queue_manuscript_import(
            [_upload("large.txt", b"large", size=100)]
        )
        is True
    )
    assert (
        manuscript_import_job_service.should_queue_manuscript_import(
            [_upload("one.txt", b"1"), _upload("two.txt", b"2")]
        )
        is True
    )


@pytest.mark.asyncio
async def test_import_request_rejects_empty_input_and_delegates_large_files(monkeypatch):
    db = _FakeDb()
    book = SimpleNamespace(id=uuid.uuid4())
    user = SimpleNamespace(id=uuid.uuid4())

    with pytest.raises(HTTPException, match="Provide text or one or more files"):
        await manuscript_import_request_service.execute_manuscript_import_request(
            db,
            book=book,
            current_user=user,
            files=None,
            text=None,
            html=None,
            title=None,
            work_type=None,
            chapter_number=None,
            replace_existing="false",
            expected_content_version=None,
            chunk_long_documents="false",
            split_into_chapters="true",
        )

    queued = SimpleNamespace(id=uuid.uuid4(), status="queued")

    async def _create(*_args, **_kwargs):
        return queued

    monkeypatch.setattr(
        manuscript_import_request_service,
        "should_queue_manuscript_import",
        lambda _files: True,
    )
    monkeypatch.setattr(
        manuscript_import_request_service,
        "create_manuscript_import_job",
        _create,
    )

    result, accepted = await manuscript_import_request_service.execute_manuscript_import_request(
        db,
        book=book,
        current_user=user,
        files=[_upload("large.txt", b"chapter", size=1_000_000)],
        text=None,
        html=None,
        title=None,
        work_type=None,
        chapter_number=None,
        replace_existing="false",
        expected_content_version=None,
        chunk_long_documents="false",
        split_into_chapters="true",
    )

    assert result is queued
    assert accepted is True


@pytest.mark.asyncio
async def test_create_import_job_stages_source_and_returns_durable_status(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    book = Book(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Draft",
        format="txt",
        work_type="novel",
        s3_key="draft.txt",
    )
    db = _FakeDb()
    uploaded = []

    def _store(key, raw, content_type=None):
        uploaded.append((key, raw, content_type))
        return key

    async def _noop(*_args, **_kwargs):
        return None

    async def _no_dispatch(*_args, **_kwargs):
        return False

    monkeypatch.setattr(manuscript_import_job_service.storage, "upload_binary", _store)
    monkeypatch.setattr(manuscript_import_job_service, "ensure_source_storage_capacity", _noop)
    monkeypatch.setattr(
        manuscript_import_job_service, "dispatch_manuscript_import_job", _no_dispatch
    )

    result = await manuscript_import_job_service.create_manuscript_import_job(
        db,
        book=book,
        current_user=user,
        files=[_upload("draft.txt", b"chapter", size=7)],
        text=None,
        html=None,
        title=None,
        work_type=None,
        chapter_number=None,
        replace_existing="false",
        expected_content_version=None,
        chunk_long_documents="false",
        split_into_chapters="true",
    )

    assert result.status == "queued"
    assert result.progress_total == 2
    assert uploaded[0][1] == b"chapter"
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_import_job_lookup_cancel_retry_dispatch_and_missing_worker(monkeypatch):
    now = datetime.now(UTC)
    job = ManuscriptImportJob(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        status="running",
        source_files_json=[{"storage_key": "staged.txt"}],
        request_json={},
        created_at=now,
        updated_at=now,
    )
    db = _FakeDb([_ScalarResult(scalar=job)])

    loaded = await manuscript_import_job_service.get_manuscript_import_job(
        db,
        job_id=job.id,
        book_id=job.book_id,
        user_id=job.user_id,
    )
    assert loaded is job

    cancelled = await manuscript_import_job_service.cancel_manuscript_import_job(db, job=job)
    assert cancelled.status == "cancel_requested"

    job.status = "failed"
    dispatched = []

    async def _dispatch(_db, target):
        dispatched.append(target.id)
        return True

    monkeypatch.setattr(manuscript_import_job_service, "dispatch_manuscript_import_job", _dispatch)
    retried = await manuscript_import_job_service.retry_manuscript_import_job(db, job=job)
    assert retried.status == "queued"
    assert dispatched == [job.id]

    missing_db = _FakeDb([_ScalarResult(scalar=None)])
    result = await manuscript_import_job_service.process_manuscript_import_job(
        missing_db,
        uuid.uuid4(),
    )
    assert result["status"] == "missing"


@pytest.mark.asyncio
async def test_import_job_recovery_finishes_stale_cancellation_without_dispatch():
    now = datetime.now(UTC)
    job = ManuscriptImportJob(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        status="cancel_requested",
        source_files_json=[{"storage_key": "staged.txt"}],
        request_json={},
        created_at=now,
        updated_at=now,
    )
    db = _FakeDb([_ScalarResult(scalars=[job])])

    dispatched = await manuscript_import_job_service.dispatch_pending_manuscript_import_jobs(db)

    assert dispatched == 0
    assert job.status == "cancelled"
    assert job.completed_at is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_stage_editor_content_uses_immutable_keys_and_cleans_partial_uploads(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    stored_keys = []

    def _upload_binary(key, raw, content_type=None):
        stored_keys.append(key)
        return key

    def _upload_text(key, payload):
        stored_keys.append(key)
        return key

    monkeypatch.setattr(manuscript, "upload_binary", _upload_binary)
    monkeypatch.setattr(manuscript, "upload_text", _upload_text)

    staged = await manuscript.stage_editor_chapter_content(
        book,
        chapter_number=3,
        text="A gate opens.",
        html=None,
    )

    assert staged.storage_key.startswith(f"chapters/{book.id}/3/")
    assert staged.storage_key.endswith(".txt")
    assert staged.uploaded_keys == (staged.storage_key,)

    cleaned = []

    def _fail_text(_key, _payload):
        raise OSError("storage unavailable")

    async def _cleanup(keys, *, context):
        cleaned.extend(keys)
        assert context == "chapter_save_staging"
        return list(keys)

    monkeypatch.setattr(manuscript, "upload_text", _fail_text)
    monkeypatch.setattr(manuscript, "delete_storage_keys_best_effort", _cleanup)
    with pytest.raises(OSError, match="storage unavailable"):
        await manuscript.stage_editor_chapter_content(
            book,
            chapter_number=3,
            text="A gate closes.",
            html=None,
            images=[
                {
                    "marker": "[[IMAGE:gate]]",
                    "bytes": b"image",
                    "filename": "gate.png",
                    "content_type": "image/png",
                }
            ],
        )
    assert len(cleaned) == 1
    assert cleaned[0].startswith(f"chapter-media/{book.id}/3/")


@pytest.mark.asyncio
async def test_apply_staged_content_and_reference_snapshot_do_no_storage_io():
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())
    db = _FakeDb()
    staged = manuscript.StagedEditorChapterContent(
        text="Three clear words",
        html=None,
        storage_key=f"chapters/{book.id}/1/immutable.txt",
        media=[],
        retained_media_markers=set(),
        should_sync_media=False,
        uploaded_keys=(),
    )

    chapter = await manuscript.apply_staged_editor_chapter_content(
        db,
        book,
        chapter=None,
        chapter_number=1,
        title="Opening",
        staged=staged,
    )
    version = await chapter_versions.snapshot_chapter_version_reference(
        db,
        book,
        chapter,
        note="Before edit",
    )

    assert chapter.s3_key == staged.storage_key
    assert chapter.word_count == 3
    assert version is not None
    assert version.s3_key == staged.storage_key


@pytest.mark.asyncio
async def test_sparse_character_navigation_avoids_relationship_queries(monkeypatch):
    book_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    book = SimpleNamespace(id=book_id, mode="author", total_chapters=12)
    character = Character(
        id=uuid.uuid4(),
        book_id=book_id,
        name="Mara",
        role="protagonist",
        first_chapter=1,
        mention_count=8,
        analysis_metadata={},
        visibility_state="visible",
        approval_state="approved",
        approval_reason_codes=[],
        is_manual=False,
    )
    db = _FakeDb([_ScalarResult(scalars=[character])])

    async def _access(*_args, **_kwargs):
        return book, None

    monkeypatch.setattr(character_listing_service, "get_book_with_collaboration_access", _access)
    monkeypatch.setattr(character_listing_service, "require_author_access", lambda _user: None)

    result = await character_listing_service.list_book_characters_for_viewer(
        db,
        book_id=book_id,
        current_user=user,
        fields="id,name",
        include="",
    )

    assert result == [{"id": str(character.id), "name": "Mara"}]
    assert len(db.statements) == 1
    assert "character_relationships" not in str(db.statements[0]).lower()


@pytest.mark.asyncio
async def test_revision_cache_fill_is_coalesced_and_released(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    events = []

    async def _cache_version(_book_id):
        return 7

    async def _cache_miss(*_args):
        return None

    async def _lock(*_args, **_kwargs):
        return True

    async def _build(*_args):
        events.append("build")
        return {"book_id": str(book.id)}

    async def _set(*_args):
        events.append("set")

    async def _delete(*_args):
        events.append("delete")
        return True

    monkeypatch.setattr(revision_service, "get_book_cache_version", _cache_version)
    monkeypatch.setattr(revision_service, "get_revision_intelligence_cache", _cache_miss)
    monkeypatch.setattr(revision_service, "cache_acquire_lock", _lock)
    monkeypatch.setattr(revision_service, "_build_revision_intelligence_payload", _build)
    monkeypatch.setattr(revision_service, "set_revision_intelligence_cache", _set)
    monkeypatch.setattr(revision_service, "cache_delete_if_owner", _delete)

    payload = await revision_service.build_revision_intelligence_payload(SimpleNamespace(), book)

    assert payload == {"book_id": str(book.id)}
    assert events == ["build", "set", "delete"]


@pytest.mark.asyncio
async def test_revision_digest_refresh_coalesces_worker_dispatch(monkeypatch):
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    dispatched = []

    async def _claim(*_args, **_kwargs):
        return True

    monkeypatch.setattr(notification_service, "cache_set_if_absent", _claim)
    from app.workers.tasks import maintenance_tasks

    monkeypatch.setattr(
        maintenance_tasks.refresh_revision_digest_notification_task,
        "apply_async",
        lambda **kwargs: dispatched.append(kwargs),
    )

    assert (
        await notification_service.enqueue_revision_digest_refresh(
            user_id=user_id,
            book_id=book_id,
        )
        is True
    )
    assert dispatched[0]["queue"] == "maintenance"
    assert dispatched[0]["kwargs"]["book_id"] == str(book_id)


@pytest.mark.asyncio
async def test_revision_digest_refresh_updates_only_when_signature_changes(monkeypatch):
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        mode="author",
        status="ready",
    )
    existing = Notification(
        id=uuid.uuid4(),
        user_id=book.user_id,
        book_id=book.id,
        kind="revision_digest",
        title="Old",
        body="Old",
        data={"signature": "old"},
    )
    db = _FakeDb(
        [
            _ScalarResult(scalar=book),
            _ScalarResult(scalars=[existing]),
        ]
    )

    async def _payload(*_args):
        return {"findings": []}

    replacement = Notification(
        user_id=book.user_id,
        book_id=book.id,
        kind="revision_digest",
        title="New",
        body="New",
        data={"signature": "new"},
    )
    monkeypatch.setattr(revision_service, "build_revision_intelligence_payload", _payload)
    monkeypatch.setattr(
        notification_service,
        "build_revision_digest_notification",
        lambda *_args: replacement,
    )

    changed = await notification_service.refresh_revision_digest_for_book(db, book.id)

    assert changed is True
    assert existing.title == "New"
    assert existing.data == {"signature": "new"}
    assert db.commits == 1
