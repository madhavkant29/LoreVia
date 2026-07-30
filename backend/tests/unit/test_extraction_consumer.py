import pytest

from app.core.redis import key_extraction_inflight_book
from app.utils.ingestion_utils import EXTRACTION_INFLIGHT_TTL_SECONDS
from app.workers.consumers import extraction_consumer
from app.workers.consumers.extraction_consumer import process_book


def test_inflight_lock_ttl_exceeds_hard_limit():
    EXTRACTION_HARD_LIMIT = 25 * 60  # celery_app.py task_annotations time_limit
    MINIMUM_TTL = EXTRACTION_HARD_LIMIT + 300
    assert EXTRACTION_INFLIGHT_TTL_SECONDS >= MINIMUM_TTL


@pytest.mark.asyncio
async def test_process_book_inflight_lock(monkeypatch):
    inflight_state: dict[str, str] = {}

    async def mock_set_if_absent(key: str, value: object, ttl: int) -> bool:
        if key in inflight_state:
            return False
        inflight_state[key] = str(value)
        return True

    async def mock_delete_if_owner(key: str, owner_token: str) -> bool:
        if inflight_state.get(key) == owner_token:
            del inflight_state[key]
            return True
        return False

    call_count = 0

    async def mock_impl(book_id: str, queue_wait_ms: int | None = None) -> dict:
        nonlocal call_count
        call_count += 1
        return {"book_id": book_id, "chapters": 10}

    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.cache_set_if_absent",
        mock_set_if_absent,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.cache_delete_if_owner",
        mock_delete_if_owner,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.INFLIGHT_BOOK_TTL_SECONDS",
        3600,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer._process_book_impl",
        mock_impl,
        raising=False,
    )

    book_id = "abc-123-def"
    inflight_key = key_extraction_inflight_book(book_id)

    result1 = await process_book(book_id, task_id="task-1")
    assert result1 == {"book_id": book_id, "chapters": 10}
    assert call_count == 1
    assert inflight_key not in inflight_state

    inflight_state[inflight_key] = "task-blocking"

    result2 = await process_book(book_id, task_id="task-2")
    assert result2 == {"skipped": "already_inflight"}
    assert call_count == 1

    del inflight_state[inflight_key]

    result3 = await process_book(book_id, task_id="task-3")
    assert result3 == {"book_id": book_id, "chapters": 10}
    assert call_count == 2
    assert inflight_key not in inflight_state


@pytest.mark.asyncio
async def test_process_book_inflight_lock_owner_safety(monkeypatch):
    inflight_state: dict[str, str] = {}

    async def mock_set_if_absent(key: str, value: object, ttl: int) -> bool:
        if key in inflight_state:
            return False
        inflight_state[key] = str(value)
        return True

    async def mock_delete_if_owner(key: str, owner_token: str) -> bool:
        if inflight_state.get(key) == owner_token:
            del inflight_state[key]
            return True
        return False

    call_count = 0

    async def mock_impl(book_id: str, queue_wait_ms: int | None = None) -> dict:
        nonlocal call_count
        call_count += 1
        return {"book_id": book_id, "chapters": 10}

    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.cache_set_if_absent",
        mock_set_if_absent,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.cache_delete_if_owner",
        mock_delete_if_owner,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.INFLIGHT_BOOK_TTL_SECONDS",
        3600,
        raising=False,
    )
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer._process_book_impl",
        mock_impl,
        raising=False,
    )

    book_id = "def-456-ghi"
    inflight_key = key_extraction_inflight_book(book_id)

    inflight_state[inflight_key] = "old-task-x"

    result = await process_book(book_id, task_id="new-task-1")
    assert result == {"skipped": "already_inflight"}
    assert call_count == 0
    assert inflight_state[inflight_key] == "old-task-x"

    del inflight_state[inflight_key]

    result = await process_book(book_id, task_id="new-task-2")
    assert result == {"book_id": book_id, "chapters": 10}
    assert call_count == 1
    assert inflight_key not in inflight_state


@pytest.mark.asyncio
async def test_process_book_impl_rolls_back_open_transaction_before_session_exit(monkeypatch):
    class FakeDb:
        def __init__(self):
            self.rollback_calls = 0

        def in_transaction(self):
            return True

        async def rollback(self):
            self.rollback_calls += 1

    class SessionContext:
        def __init__(self, db):
            self.db = db

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    db = FakeDb()

    async def fake_process(_db, *, book_id, queue_wait_ms):
        assert _db is db
        return {"book_id": book_id}

    monkeypatch.setattr(extraction_consumer, "AsyncSessionLocal", lambda: SessionContext(db))
    monkeypatch.setattr(
        extraction_consumer,
        "process_book_ingestion_and_queue",
        fake_process,
    )

    result = await extraction_consumer._process_book_impl("book-1", queue_wait_ms=7)

    assert result == {"book_id": "book-1"}
    assert db.rollback_calls == 1
