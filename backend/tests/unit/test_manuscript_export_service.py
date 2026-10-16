from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.operations import ManuscriptExportJob
from app.schemas.books import ManuscriptExportRequest
from app.services import manuscript_export_service
from app.utils import storage_utils


@pytest.mark.asyncio
async def test_export_chapter_storage_reads_are_bounded_and_keep_query_order(monkeypatch):
    active = 0
    peak = 0

    def download(key: str) -> bytes:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            import time

            time.sleep(0.01)
            return f'{{"format":"rich_text_v1","text":"{key}","html":"<p>{key}</p>"}}'.encode()
        finally:
            active -= 1

    monkeypatch.setattr(manuscript_export_service.storage, "download_book", download)
    monkeypatch.setattr(storage_utils.settings, "STORAGE_IO_CONCURRENCY", 2)

    chapters = await manuscript_export_service.load_manuscript_export_chapters(
        [(number, f"Chapter {number}", f"chapter-{number}") for number in range(1, 6)],
        include_scene_metadata=True,
    )

    assert [chapter["number"] for chapter in chapters] == [1, 2, 3, 4, 5]
    assert [chapter["text"] for chapter in chapters] == [
        "chapter-1",
        "chapter-2",
        "chapter-3",
        "chapter-4",
        "chapter-5",
    ]
    assert 1 < peak <= 2


@pytest.mark.asyncio
async def test_export_chapter_storage_failure_keeps_empty_placeholder(monkeypatch):
    def download(key: str) -> bytes:
        if key == "missing":
            raise OSError("object unavailable")
        return b"plain text"

    monkeypatch.setattr(manuscript_export_service.storage, "download_book", download)

    chapters = await manuscript_export_service.load_manuscript_export_chapters(
        [(1, "Missing", "missing"), (2, "Present", "present")],
        include_scene_metadata=True,
    )

    assert chapters[0]["text"] == ""
    assert chapters[1]["text"] == "plain text"


class _RowsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _StatsDb:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return _RowsResult(self.rows)


@pytest.mark.asyncio
async def test_large_export_is_queued_at_chapter_threshold(monkeypatch):
    monkeypatch.setattr(
        manuscript_export_service.settings,
        "MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_CHAPTERS",
        3,
    )
    monkeypatch.setattr(
        manuscript_export_service.settings,
        "MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_WORDS",
        1_000_000,
    )

    queued = await manuscript_export_service.should_queue_manuscript_export(
        _StatsDb(
            [
                SimpleNamespace(number=1, word_count=10),
                SimpleNamespace(number=2, word_count=10),
                SimpleNamespace(number=3, word_count=10),
            ]
        ),
        book=SimpleNamespace(id=uuid.uuid4()),
        collaborator=None,
        request=ManuscriptExportRequest(),
    )

    assert queued is True


def test_active_export_request_index_is_unique_and_partial():
    index = next(
        value
        for value in ManuscriptExportJob.__table__.indexes
        if value.name == "uq_manuscript_export_jobs_active_request"
    )

    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "user_id",
        "book_id",
        "export_kind",
        "export_format",
        "options_json",
    ]
    assert str(index.dialect_options["postgresql"]["where"]) == ("status IN ('queued', 'running')")


@pytest.mark.asyncio
async def test_concurrent_identical_export_reuses_unique_index_winner(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    book = SimpleNamespace(id=uuid.uuid4())
    now = datetime.now(UTC)
    winner = ManuscriptExportJob(
        id=uuid.uuid4(),
        user_id=user.id,
        book_id=book.id,
        status="queued",
        celery_task_id="winning-task",
        export_kind="manuscript",
        export_format="pdf",
        options_json=ManuscriptExportRequest(format="pdf").model_dump(mode="json"),
        progress_completed=0,
        progress_total=12,
        created_at=now,
        updated_at=now,
    )

    async def get_access(_db, _book_id, _current_user):
        return book, None

    async def should_queue(*_args, **_kwargs):
        return True

    async def chapter_stats(*_args, **_kwargs):
        return 10, 50_000

    monkeypatch.setattr(manuscript_export_service, "get_book_with_collaboration_access", get_access)
    monkeypatch.setattr(manuscript_export_service, "should_queue_manuscript_export", should_queue)
    monkeypatch.setattr(manuscript_export_service, "_accessible_chapter_stats", chapter_stats)

    class _ScalarResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class _Db:
        def __init__(self):
            self.results = [None, winner]
            self.added = []
            self.rollbacks = 0

        async def execute(self, _statement):
            return _ScalarResult(self.results.pop(0))

        def add(self, value):
            self.added.append(value)

        async def commit(self):
            raise manuscript_export_service.IntegrityError(
                "insert manuscript_export_jobs",
                {},
                RuntimeError("duplicate active request"),
            )

        async def rollback(self):
            self.rollbacks += 1

    db = _Db()
    prepared = await manuscript_export_service.prepare_manuscript_export(
        db,
        book_id=book.id,
        current_user=user,
        request=ManuscriptExportRequest(format="pdf"),
    )

    assert prepared.delivery == "job"
    assert prepared.job is not None
    assert prepared.job.id == winner.id
    assert db.rollbacks == 1
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_preview_export_stays_synchronous_even_for_large_book(monkeypatch):
    monkeypatch.setattr(
        manuscript_export_service.settings,
        "MANUSCRIPT_EXPORT_ASYNC_THRESHOLD_CHAPTERS",
        1,
    )

    queued = await manuscript_export_service.should_queue_manuscript_export(
        _StatsDb([SimpleNamespace(number=1, word_count=200_000)]),
        book=SimpleNamespace(id=uuid.uuid4()),
        collaborator=None,
        request=ManuscriptExportRequest(
            export_kind="novel",
            format="pdf",
            preset="standard_novel",
            preview_chapters=2,
        ),
    )

    assert queued is False


def test_completed_export_job_exposes_only_authorized_api_download_path():
    now = datetime.now(UTC)
    job = ManuscriptExportJob(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        status="completed",
        export_kind="manuscript",
        export_format="pdf",
        options_json={},
        artifact_storage_key="exports/private/export.pdf",
        artifact_filename="Draft-manuscript.pdf",
        artifact_media_type="application/pdf",
        artifact_size_bytes=42,
        progress_completed=3,
        progress_total=3,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )

    payload = manuscript_export_service.manuscript_export_job_out(job)

    assert payload.download_url == f"/api/v1/books/{job.book_id}/exports/{job.id}/download"
    assert "exports/private" not in payload.download_url
    assert payload.size_bytes == 42


@pytest.mark.asyncio
async def test_renderer_writes_directly_to_spooled_artifact(monkeypatch):
    monkeypatch.setattr(
        manuscript_export_service.settings,
        "MANUSCRIPT_EXPORT_SPOOL_MAX_MEMORY_BYTES",
        1024,
    )

    def render(*, output):
        output.write(b"x" * 2048)

    stream = await manuscript_export_service._render_export_to_stream(render, {})
    try:
        assert getattr(stream, "_rolled") is True
        assert stream.read(4) == b"xxxx"
    finally:
        stream.close()


def test_artifact_spool_uses_configured_disk_directory(monkeypatch):
    captured = {}
    sentinel = object()

    def create_spool(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        manuscript_export_service.settings,
        "MANUSCRIPT_EXPORT_SPOOL_DIRECTORY",
        "/var/lib/lorevia-export-spool",
    )
    monkeypatch.setattr(manuscript_export_service.tempfile, "SpooledTemporaryFile", create_spool)

    assert manuscript_export_service._new_artifact_stream() is sentinel
    assert captured["dir"] == "/var/lib/lorevia-export-spool"
    assert captured["mode"] == "w+b"


@pytest.mark.asyncio
async def test_spooled_renderer_supports_legacy_byte_result(monkeypatch):
    monkeypatch.setattr(
        manuscript_export_service.settings,
        "MANUSCRIPT_EXPORT_SPOOL_MAX_MEMORY_BYTES",
        1024,
    )

    stream = await manuscript_export_service._render_export_to_stream(
        lambda **_kwargs: b"legacy",
        {},
    )
    try:
        assert stream.read() == b"legacy"
    finally:
        stream.close()


@pytest.mark.asyncio
async def test_expiry_denies_download_even_when_artifact_delete_needs_retry(monkeypatch):
    job = SimpleNamespace(
        id=uuid.uuid4(),
        status="completed",
        artifact_storage_key="exports/private/draft.pdf",
    )

    class _Db:
        commits = 0

        async def commit(self):
            self.commits += 1

    db = _Db()

    def fail_delete(_key):
        raise OSError("storage unavailable")

    monkeypatch.setattr(manuscript_export_service.storage, "delete_object", fail_delete)

    await manuscript_export_service.expire_manuscript_export_job(db, job)

    assert job.status == "expired"
    assert job.artifact_storage_key == "exports/private/draft.pdf"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_cleanup_retries_only_expired_rows_that_still_have_artifacts():
    captured = {}

    class _Scalars:
        def all(self):
            return []

    class _Result:
        def scalars(self):
            return _Scalars()

    class _Db:
        async def execute(self, statement):
            captured["statement"] = str(statement)
            return _Result()

    assert await manuscript_export_service.cleanup_expired_manuscript_export_jobs(_Db()) == 0

    statement = captured["statement"]
    assert "manuscript_export_jobs.status IN" in statement
    assert "manuscript_export_jobs.status =" in statement
    assert "manuscript_export_jobs.artifact_storage_key IS NOT NULL" in statement
