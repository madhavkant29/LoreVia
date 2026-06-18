import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import PlotThread
from app.models.user import User
from app.utils.ingestion_utils import ANALYSIS_INFLIGHT_TTL_SECONDS
from app.workers.consumers import analysis_consumer
from app.workers.consumers.analysis_consumer import _refresh_book_analysis_pipeline, _upsert_plot_threads


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
    def __init__(self, chapter=None, book=None, results=None):
        self.chapter = chapter
        self.book = book
        self.results = list(results or [])
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    async def get(self, model, object_id):
        if model is Chapter:
            return self.chapter
        if model is Book:
            return self.book
        return None

    async def execute(self, statement):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

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


def test_inflight_lock_ttl_exceeds_hard_limit():
    ANALYSIS_HARD_LIMIT = 15 * 60        # celery_app.py task_annotations time_limit
    MINIMUM_TTL = ANALYSIS_HARD_LIMIT + 300
    assert ANALYSIS_INFLIGHT_TTL_SECONDS >= MINIMUM_TTL


@pytest.mark.asyncio
async def test_upsert_plot_threads_resolves_related_characters_to_canonical_names(db):
    user = User(email="plot-analysis@lorevia.app", username="plotanalysis", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(user_id=user.id, title="Plot Analysis", format="pdf", s3_key="plot-analysis.pdf", status="ready")
    db.add(book)
    await db.flush()

    chapter = Chapter(id=uuid.uuid4(), book_id=book.id, number=4, title="Door", s3_key="chapter-4.txt")
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

    thread = (await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))).scalar_one()

    assert thread.character_ids == ["Grete", "Gregor"]


@pytest.mark.asyncio
async def test_analyse_chapter_handles_missing_stale_and_inflight_work(monkeypatch):
    chapter_id = str(uuid.uuid4())

    async def run(fake_db):
        monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(fake_db))
        return await analysis_consumer.analyse_chapter(chapter_id, "chapter text")

    assert await run(FakeAnalysisDb()) == {"error": "chapter not found"}

    chapter = SimpleNamespace(id=uuid.UUID(chapter_id), book_id=uuid.uuid4())
    assert await run(FakeAnalysisDb(chapter=chapter)) == {"error": "book not found"}

    book = SimpleNamespace(id=chapter.book_id, is_editor_project=False)
    monkeypatch.setattr("app.services.editor_project_service.get_rebuild_run_id", lambda value: "active-run")
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(FakeAnalysisDb(chapter=chapter, book=book)))
    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", lambda *args, **kwargs: None)
    result = await analysis_consumer.analyse_chapter(chapter_id, "chapter text", rebuild_run_id="stale-run")
    assert result == {"error": "stale_rebuild_run"}

    book.is_editor_project = True
    monkeypatch.setattr("app.services.editor_project_service.get_rebuild_run_id", lambda value: None)
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(FakeAnalysisDb(chapter=chapter, book=book)))
    assert await analysis_consumer.analyse_chapter(chapter_id, "chapter text") == {"error": "stale_editor_project_run"}

    book.is_editor_project = False
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(FakeAnalysisDb(chapter=chapter, book=book)))

    async def lock_busy(*args, **kwargs):
        return False

    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", lock_busy)
    assert await analysis_consumer.analyse_chapter(chapter_id, "chapter text") == {"skipped": "analysis_inflight"}


@pytest.mark.asyncio
async def test_analyse_chapter_generates_all_summary_modes_and_cleans_queue_keys(monkeypatch):
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
            FakeResult(scalar_values=[]),
            FakeResult(scalar=1),
            FakeResult(scalar=1),
            FakeResult(rows=[(1, {"status": "succeeded"})]),
        ],
    )
    monkeypatch.setattr(analysis_consumer, "AsyncSessionLocal", lambda: FakeSessionContext(db))
    monkeypatch.setattr("app.services.editor_project_service.get_rebuild_run_id", lambda value: None)
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
            "key_events": [{"event_title": "Gate opens", "description": "Mara turns the key"}],
            "char_changes": [],
            "clues": [{"clue": "Brass key"}],
            "themes": [{"theme": "trust"}],
        }

    async def extract_threads(*args, **kwargs):
        return []

    deleted_keys = []

    async def cache_delete(key):
        deleted_keys.append(key)

    monkeypatch.setattr(analysis_consumer, "cache_set_if_absent", async_true)
    monkeypatch.setattr(analysis_consumer, "cache_set", async_none)
    monkeypatch.setattr(analysis_consumer, "cache_del", cache_delete)
    monkeypatch.setattr(analysis_consumer, "generate_summary", generate)
    monkeypatch.setattr(analysis_consumer, "extract_plot_threads", extract_threads)
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

    result = await analysis_consumer.analyse_chapter(str(chapter.id), "Mara turns the key.", "Chapter 1")

    assert result == {
        "chapter_id": str(chapter.id),
        "summaries": {"short": "generated", "detailed": "generated", "key_points": "generated"},
    }
    assert len(db.added) == 3
    assert chapter.analysis_state["status"] == "succeeded"
    assert chapter.title == "Gate Opens"
    assert book.writer_workspace["processing"]["pipeline"]["analysis"]["status"] == "succeeded"
    assert db.commit_count == 2
    assert len(deleted_keys) == 2


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
async def test_refresh_book_analysis_pipeline_calculates_runtime_status(total, completed, rows, expected):
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
