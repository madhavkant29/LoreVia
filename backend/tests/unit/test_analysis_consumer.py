import uuid
from types import SimpleNamespace

import pytest
from httpx import Request
from openai import APIConnectionError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import PlotThread
from app.models.user import User
from app.utils.ingestion_utils import ANALYSIS_INFLIGHT_TTL_SECONDS
from app.workers.consumers import analysis_consumer
from app.workers.consumers.analysis_consumer import (
    _refresh_book_analysis_pipeline,
    _upsert_plot_threads,
)


class FakeResult:
    def __init__(self, *, scalar=None, scalar_values=None, rows=None):
        self.scalar = scalar
        self.scalar_values = scalar_values or []
        self.rows = rows or []

    def scalar_one(self):
        return self.scalar

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self.scalar_values))

    def all(self):
        return list(self.rows)


class FakeAnalysisDb:
    def __init__(self, chapter=None, book=None, user=None, results=None, scalar_results=None):
        self.chapter = chapter
        self.book = book
        self.user = user
        self.results = list(results or [])
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0
        self.flush_count = 0

    async def get(self, model, object_id):
        if model is Chapter:
            return self.chapter
        if model is Book:
            return self.book
        if model is User:
            return self.user
        return None

    async def execute(self, statement):
        return self.results.pop(0)

    async def scalar(self, statement):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        entity = statement.column_descriptions[0].get("entity")
        if entity is Chapter:
            return self.chapter
        if entity is Book:
            return self.book
        return None

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


class FakeSessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, traceback):
        return False


@pytest.fixture(autouse=True)
def _treat_books_as_not_frozen(monkeypatch):
    """These tests predate the administrative-freeze guard; keep them unfrozen."""

    async def _not_frozen(*_args, **_kwargs):
        return False

    monkeypatch.setattr(analysis_consumer, "book_is_frozen", _not_frozen)


def test_inflight_lock_ttl_exceeds_hard_limit():
    ANALYSIS_HARD_LIMIT = 15 * 60  # celery_app.py task_annotations time_limit
    MINIMUM_TTL = ANALYSIS_HARD_LIMIT + 300
    assert ANALYSIS_INFLIGHT_TTL_SECONDS >= MINIMUM_TTL


@pytest.mark.asyncio
async def test_upsert_plot_threads_resolves_related_characters_to_canonical_names(db):
    user = User(email="plot-analysis@lorevia.app", username="plotanalysis", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Plot Analysis",
        format="pdf",
        s3_key="plot-analysis.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    chapter = Chapter(
        id=uuid.uuid4(), book_id=book.id, number=4, title="Door", s3_key="chapter-4.txt"
    )
    grete = Character(book_id=book.id, name="Grete", aliases=[], first_chapter=1, mention_count=3)
    gregor = Character(book_id=book.id, name="Gregor", aliases=[], first_chapter=1, mention_count=3)
    db.add_all([chapter, grete, gregor])
    await db.commit()

    await _upsert_plot_threads(
        db,
        book,
        chapter,
        [
            {
                "title": "The door plea",
                "description": "Grete, Gregor's sister, begs him to answer.",
                "status": "developing",
                "characters_involved": ["Gregor's sister", "Gregor"],
                "importance": 7,
            }
        ],
    )
    await db.commit()

    thread = (
        await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))
    ).scalar_one()

    assert thread.character_ids == ["Grete", "Gregor"]


@pytest.mark.asyncio
async def test_analyse_chapter_handles_missing_stale_and_inflight_work(monkeypatch):
    chapter_id = str(uuid.uuid4())

    async def run(fake_db):
        monkeypatch.setattr(
            analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(fake_db)
        )
        return await analysis_consumer.analyse_chapter(chapter_id, "chapter text")

    assert await run(FakeAnalysisDb()) == {"error": "chapter not found"}

    chapter = SimpleNamespace(id=uuid.UUID(chapter_id), book_id=uuid.uuid4())
    assert await run(FakeAnalysisDb(chapter=chapter)) == {"error": "book not found"}

    book = SimpleNamespace(id=chapter.book_id, is_editor_project=False)
    monkeypatch.setattr(
        "app.services.editor_project_service.get_rebuild_run_id", lambda value: "active-run"
    )
    monkeypatch.setattr(
        analysis_consumer,
        "AsyncSessionLocal",
        lambda: FakeSessionContext(FakeAnalysisDb(chapter=chapter, book=book)),
    )
    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", lambda *args, **kwargs: None)
    result = await analysis_consumer.analyse_chapter(
        chapter_id, "chapter text", rebuild_run_id="stale-run"
    )
    assert result == {"error": "stale_rebuild_run"}

    book.is_editor_project = True
    monkeypatch.setattr(
        "app.services.editor_project_service.get_rebuild_run_id", lambda value: None
    )
    monkeypatch.setattr(
        analysis_consumer,
        "AsyncSessionLocal",
        lambda: FakeSessionContext(FakeAnalysisDb(chapter=chapter, book=book)),
    )
    assert await analysis_consumer.analyse_chapter(chapter_id, "chapter text") == {
        "error": "stale_editor_project_run"
    }

    book.is_editor_project = False
    monkeypatch.setattr(
        analysis_consumer,
        "AsyncSessionLocal",
        lambda: FakeSessionContext(FakeAnalysisDb(chapter=chapter, book=book)),
    )

    async def lock_busy(*args, **kwargs):
        return False

    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", lock_busy)
    assert await analysis_consumer.analyse_chapter(chapter_id, "chapter text") == {
        "skipped": "analysis_inflight"
    }


@pytest.mark.asyncio
async def test_manual_analyse_chapter_refreshes_all_summary_modes_after_commit(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        number=1,
        title="Chapter 1",
        analysis_state={"status": "queued"},
        word_count=120,
    )
    book = SimpleNamespace(
        id=chapter.book_id,
        user_id=uuid.uuid4(),
        title="The Gate",
        is_editor_project=False,
        writer_workspace={},
    )
    db = FakeAnalysisDb(
        chapter=chapter,
        book=book,
        results=[
            FakeResult(scalar=1),
            FakeResult(scalar=0),
            FakeResult(rows=[(1, {"status": "running"})]),
            FakeResult(
                scalar_values=[
                    SimpleNamespace(mode="short"),
                    SimpleNamespace(mode="detailed"),
                    SimpleNamespace(mode="key_points"),
                ]
            ),
            FakeResult(scalar=1),
            FakeResult(scalar=1),
            FakeResult(rows=[(1, {"status": "succeeded"})]),
        ],
    )
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(db))
    monkeypatch.setattr(
        "app.services.editor_project_service.get_rebuild_run_id", lambda value: None
    )
    monkeypatch.setattr(analysis_consumer.settings, "OPENAI_API_KEY", "")

    async def async_true(*args, **kwargs):
        return True

    async def async_false(*args, **kwargs):
        return False

    async def async_none(*args, **kwargs):
        return None

    cache_commit_counts = []

    async def cache_summary(*args, **kwargs):
        cache_commit_counts.append(db.commit_count)

    async def generate(*args, **kwargs):
        return {
            "content": "Mara opens the gate and chooses trust.",
            "key_events": [{"event_title": "Gate opens", "description": "Mara turns the key"}],
            "char_changes": [],
            "clues": [{"clue": "Brass key"}],
            "themes": [{"theme": "trust"}],
        }

    async def extract_threads(*args, **kwargs):
        return []

    async def persist_summaries(fake_db, *, chapter_id, payloads):
        for mode, payload in payloads.items():
            fake_db.add(
                SimpleNamespace(
                    chapter_id=chapter_id,
                    mode=mode,
                    content=payload["content"],
                )
            )
        return [mode for mode in ("short", "detailed", "key_points") if mode in payloads]

    deleted_keys = []

    async def cache_delete(key):
        deleted_keys.append(key)

    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", async_true)
    monkeypatch.setattr(analysis_consumer, "cache_set", cache_summary)
    monkeypatch.setattr(analysis_consumer, "cache_del", cache_delete)
    monkeypatch.setattr(analysis_consumer, "generate_summary", generate)
    monkeypatch.setattr(analysis_consumer, "extract_plot_threads", extract_threads)
    monkeypatch.setattr(
        analysis_consumer,
        "persist_chapter_summary_payloads",
        persist_summaries,
    )
    monkeypatch.setattr(analysis_consumer, "is_book_hidden", async_false)
    monkeypatch.setattr(analysis_consumer, "_upsert_plot_threads", async_none)
    monkeypatch.setattr(analysis_consumer, "link_summary_events", async_none)
    monkeypatch.setattr(analysis_consumer, "ingest_world_elements_from_chapter", async_none)
    monkeypatch.setattr("app.services.editor_project_service.complete_rebuild_if_ready", async_none)
    monkeypatch.setattr(
        analysis_consumer,
        "collect_book_ready_stats",
        lambda *args, **kwargs: _ready_stats(False),
    )
    monkeypatch.setattr("app.utils.advisor_utils.invalidate_advisor_caches_for_book", async_none)

    result = await analysis_consumer.analyse_chapter(
        str(chapter.id),
        "Mara turns the key.",
        "Chapter 1",
        manual_reprocess=True,
    )

    assert result == {
        "chapter_id": str(chapter.id),
        "summaries": {"short": "generated", "detailed": "generated", "key_points": "generated"},
    }
    assert len(db.added) == 4
    assert next(row.content for row in db.added if row.mode == "editorial_note") == (
        '{"concerns": [], "revision_question": null}'
    )
    assert chapter.analysis_state["status"] == "succeeded"
    assert chapter.title == "Gate Opens"
    assert book.writer_workspace["processing"]["pipeline"]["analysis"]["status"] == "succeeded"
    assert db.commit_count == 4
    assert cache_commit_counts == [3, 3, 3]
    assert len(deleted_keys) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("existing_ready_payload", "expected_queue_calls"),
    [
        (None, 1),
        ({"analysis_complete": True}, 0),
    ],
)
async def test_analyse_chapter_queues_first_impression_only_on_first_ready_transition(
    monkeypatch,
    existing_ready_payload,
    expected_queue_calls,
):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        number=1,
        title="Chapter 1",
        analysis_state={"status": "queued"},
        word_count=120,
        content_version=1,
    )
    book = SimpleNamespace(
        id=chapter.book_id,
        user_id=uuid.uuid4(),
        title="The Gate",
        is_editor_project=False,
        mode="author",
        writer_workspace={},
    )
    user = SimpleNamespace(id=book.user_id, email="author@example.com")
    existing_ready_notification = (
        None if existing_ready_payload is None else SimpleNamespace(data=existing_ready_payload)
    )
    db = FakeAnalysisDb(
        chapter=chapter,
        book=book,
        user=user,
        results=[
            FakeResult(scalar=1),
            FakeResult(scalar=0),
            FakeResult(rows=[(1, {"status": "running"})]),
            FakeResult(scalar_values=[]),
            FakeResult(scalar=1),
            FakeResult(scalar=1),
            FakeResult(rows=[(1, {"status": "succeeded"})]),
            FakeResult(scalar=existing_ready_notification),
        ],
    )
    queue_calls = []
    notifications = []
    completed_books = []

    async def complete_book(*args, **kwargs):
        completed_books.append(kwargs)
        return True

    monkeypatch.setattr(
        "app.services.pipeline_state_service.complete_book_after_analysis",
        complete_book,
    )

    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(db))
    monkeypatch.setattr(
        "app.services.editor_project_service.get_rebuild_run_id", lambda value: None
    )
    monkeypatch.setattr(analysis_consumer.settings, "OPENAI_API_KEY", "")

    async def async_true(*args, **kwargs):
        return True

    async def async_false(*args, **kwargs):
        return False

    async def async_none(*args, **kwargs):
        return None

    async def generate(*args, **kwargs):
        return {
            "content": "Mara opens the gate and chooses trust.",
            "key_events": [],
            "char_changes": [],
            "clues": [],
            "themes": [],
        }

    async def extract_threads(*args, **kwargs):
        return []

    async def persist_summaries(fake_db, *, chapter_id, payloads):
        return [mode for mode in ("short", "detailed", "key_points") if mode in payloads]

    async def upsert_notification(*args, **kwargs):
        notifications.append(args)

    async def queue_first_impression(*args, **kwargs):
        queue_calls.append(kwargs)
        return None

    async def send_email(*args, **kwargs):
        return None

    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", async_true)
    monkeypatch.setattr(analysis_consumer, "cache_set", async_none)
    monkeypatch.setattr(analysis_consumer, "cache_del", async_none)
    monkeypatch.setattr(analysis_consumer, "generate_summary", generate)
    monkeypatch.setattr(analysis_consumer, "extract_plot_threads", extract_threads)
    monkeypatch.setattr(
        analysis_consumer,
        "persist_chapter_summary_payloads",
        persist_summaries,
    )
    monkeypatch.setattr(analysis_consumer, "is_book_hidden", async_false)
    monkeypatch.setattr(analysis_consumer, "_upsert_plot_threads", async_none)
    monkeypatch.setattr(analysis_consumer, "link_summary_events", async_none)
    monkeypatch.setattr(analysis_consumer, "ingest_world_elements_from_chapter", async_none)
    monkeypatch.setattr("app.services.editor_project_service.complete_rebuild_if_ready", async_none)
    monkeypatch.setattr(
        analysis_consumer,
        "collect_book_ready_stats",
        lambda *args, **kwargs: _ready_stats(True),
    )
    monkeypatch.setattr(analysis_consumer, "upsert_book_ready_notification", upsert_notification)
    monkeypatch.setattr("app.utils.advisor_utils.invalidate_advisor_caches_for_book", async_none)
    monkeypatch.setattr(
        "app.services.first_impression_service.queue_first_impression",
        queue_first_impression,
    )
    monkeypatch.setattr(
        "app.services.continuity.scan_service.run_live_canon_guard_if_needed",
        async_none,
    )
    monkeypatch.setattr(analysis_consumer, "send_processing_complete_with_stats", send_email)

    result = await analysis_consumer.analyse_chapter(
        str(chapter.id), "Mara turns the key.", "Chapter 1"
    )

    assert result["chapter_id"] == str(chapter.id)
    assert len(notifications) == 1
    assert len(queue_calls) == expected_queue_calls
    assert len(completed_books) == 1
    assert completed_books[0] == {"book_id": book.id}
    if expected_queue_calls:
        assert queue_calls[0] == {
            "book_id": book.id,
            "user_id": user.id,
            "strict": False,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("replacement_version", "expected_skip"),
    [
        (None, "chapter_replaced"),
        (2, "stale_chapter_content"),
    ],
)
async def test_analyse_chapter_skips_results_when_source_changes_during_provider_call(
    monkeypatch,
    replacement_version,
    expected_skip,
):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        number=1,
        title="Chapter 1",
        content_version=1,
        analysis_state={"status": "queued"},
        word_count=120,
    )
    book = SimpleNamespace(
        id=chapter.book_id,
        user_id=uuid.uuid4(),
        title="Replaced Chapter",
        is_editor_project=False,
        writer_workspace={},
    )
    db = FakeAnalysisDb(
        chapter=chapter,
        book=book,
        results=[
            FakeResult(scalar=1),
            FakeResult(scalar=0),
            FakeResult(rows=[(1, {"status": "running"})]),
            FakeResult(scalar_values=[]),
        ],
        scalar_results=[
            book,
            (
                None
                if replacement_version is None
                else SimpleNamespace(content_version=replacement_version)
            ),
        ],
    )
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(db))
    monkeypatch.setattr(
        "app.services.editor_project_service.get_rebuild_run_id", lambda value: None
    )
    monkeypatch.setattr(analysis_consumer.settings, "OPENAI_API_KEY", "")

    async def async_true(*args, **kwargs):
        return True

    async def async_none(*args, **kwargs):
        return None

    async def generate(*args, **kwargs):
        return {
            "content": "Stale result",
            "key_events": [],
            "char_changes": [],
            "clues": [],
            "themes": [],
        }

    deleted_keys = []

    async def cache_delete(key):
        deleted_keys.append(key)

    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", async_true)
    monkeypatch.setattr(analysis_consumer, "cache_del", cache_delete)
    monkeypatch.setattr(analysis_consumer, "generate_summary", generate)
    monkeypatch.setattr(analysis_consumer, "extract_plot_threads", async_none)

    result = await analysis_consumer.analyse_chapter(
        str(chapter.id),
        "Content that was replaced during analysis.",
        "Chapter 1",
    )

    assert result == {"skipped": expected_skip}
    assert db.added == []
    assert db.commit_count == 2
    assert len(deleted_keys) == 2


@pytest.mark.asyncio
async def test_analyse_chapter_initial_deadlock_clears_inflight_keys(monkeypatch):
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        number=1,
        title="Chapter 1",
        content_version=1,
        analysis_state={"status": "queued"},
        word_count=40,
    )
    book = SimpleNamespace(
        id=chapter.book_id,
        user_id=uuid.uuid4(),
        title="Initial Deadlock",
        is_editor_project=False,
        writer_workspace={},
    )

    class InitialDeadlockDb(FakeAnalysisDb):
        async def commit(self):
            raise OperationalError(
                "UPDATE books SET writer_workspace = '{}'",
                {},
                RuntimeError("deadlock detected"),
            )

    db = InitialDeadlockDb(
        chapter=chapter,
        book=book,
        results=[
            FakeResult(scalar=1),
            FakeResult(scalar=0),
            FakeResult(rows=[(1, {"status": "running"})]),
        ],
    )
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(db))
    monkeypatch.setattr(
        "app.services.editor_project_service.get_rebuild_run_id", lambda value: None
    )

    async def async_true(*args, **kwargs):
        return True

    deleted_keys = []

    async def cache_delete(key):
        deleted_keys.append(key)

    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", async_true)
    monkeypatch.setattr(analysis_consumer, "cache_del", cache_delete)

    with pytest.raises(OperationalError, match="deadlock detected"):
        await analysis_consumer.analyse_chapter(
            str(chapter.id),
            "A short chapter.",
            "Chapter 1",
        )

    assert db.rollback_count == 1
    assert len(deleted_keys) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "retryable_error",
    [
        OperationalError(
            "UPDATE books SET writer_workspace = '{}'",
            {},
            RuntimeError("deadlock detected"),
        ),
        APIConnectionError(request=Request("POST", "https://api.openai.com/v1/chat/completions")),
    ],
    ids=["database-deadlock", "openai-connection"],
)
async def test_analyse_chapter_retryable_failure_does_not_read_expired_chapter(
    monkeypatch,
    retryable_error,
):
    chapter_id = uuid.uuid4()
    book_id = uuid.uuid4()

    class ExpiringChapter:
        def __init__(self):
            self._id = chapter_id
            self.expired = False
            self.book_id = book_id
            self.number = 1
            self.title = "Chapter 1"
            self.word_count = 40
            self.analysis_state = {"status": "queued"}

        @property
        def id(self):
            if self.expired:
                raise AssertionError("expired chapter ORM state was accessed after rollback")
            return self._id

    chapter = ExpiringChapter()
    book = SimpleNamespace(
        id=book_id,
        user_id=uuid.uuid4(),
        title="Deadlock",
        is_editor_project=False,
        writer_workspace={},
    )
    fresh_chapter = SimpleNamespace(
        id=chapter_id,
        book_id=book_id,
        analysis_state={"status": "running"},
    )
    fresh_book = SimpleNamespace(id=book_id, writer_workspace={})

    class DeadlockDb(FakeAnalysisDb):
        async def get(self, model, object_id):
            if self.rollback_count:
                if model is Chapter:
                    return fresh_chapter
                if model is Book:
                    return fresh_book
            return await super().get(model, object_id)

        async def rollback(self):
            await super().rollback()
            chapter.expired = True

    db = DeadlockDb(
        chapter=chapter,
        book=book,
        results=[
            FakeResult(scalar=1),
            FakeResult(scalar=0),
            FakeResult(rows=[(1, {"status": "running"})]),
            FakeResult(scalar_values=[]),
            FakeResult(scalar=1),
            FakeResult(scalar=0),
            FakeResult(rows=[(1, {"status": "queued"})]),
        ],
    )
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(db))
    monkeypatch.setattr(
        "app.services.editor_project_service.get_rebuild_run_id", lambda value: None
    )

    async def async_true(*args, **kwargs):
        return True

    async def async_none(*args, **kwargs):
        return None

    async def raise_retryable_error(*args, **kwargs):
        raise retryable_error

    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", async_true)
    monkeypatch.setattr(analysis_consumer, "cache_del", async_none)
    monkeypatch.setattr(analysis_consumer, "generate_summary", raise_retryable_error)
    monkeypatch.setattr(analysis_consumer.settings, "OPENAI_API_KEY", "")

    with pytest.raises(type(retryable_error)):
        await analysis_consumer.analyse_chapter(
            str(chapter_id),
            "A short chapter.",
            "Chapter 1",
        )

    assert db.rollback_count == 1
    assert fresh_chapter.analysis_state["status"] == "queued"


async def _ready_stats(analysis_complete):
    return SimpleNamespace(
        analysis_complete=analysis_complete,
        character_count=0,
        relationship_count=0,
        plot_thread_count=0,
        continuity_issue_count=0,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("total", "completed", "rows", "expected"),
    [
        (2, 2, [(1, {"status": "succeeded"}), (2, {"status": "succeeded"})], "succeeded"),
        (2, 1, [(1, {"status": "failed"}), (2, {"status": "queued"})], "failed"),
        (2, 0, [(1, {"status": "queued"}), (2, None)], "running"),
        (2, 0, [(1, None), (2, None)], "pending"),
    ],
)
async def test_refresh_book_analysis_pipeline_calculates_runtime_status(
    total, completed, rows, expected
):
    book = SimpleNamespace(id=uuid.uuid4(), writer_workspace={})
    db = FakeAnalysisDb(
        results=[
            FakeResult(scalar=total),
            FakeResult(scalar=completed),
            FakeResult(rows=rows),
        ]
    )

    await _refresh_book_analysis_pipeline(db, book)

    analysis = book.writer_workspace["processing"]["pipeline"]["analysis"]
    assert analysis["status"] == expected
    assert analysis["completed_chapters"] == completed
    assert analysis["total_chapters"] == total
