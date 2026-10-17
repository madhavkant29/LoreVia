import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.routes.reader import progress as reader_progress
from app.services import book_service
from app.utils import advisor_utils
from app.utils.public import forum_foundation


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _RowsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


@pytest.mark.asyncio
async def test_book_creation_marks_book_and_dashboard_cache_dirty(monkeypatch):
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    series_id = uuid.uuid4()
    calls: list[tuple[str, str]] = []
    book = SimpleNamespace(
        id=book_id,
        user_id=user_id,
        primary_series_id=None,
        series_name=None,
        series_order=None,
    )

    class DB:
        async def commit(self):
            calls.append(("db", "commit"))

        async def refresh(self, value):
            calls.append(("db", str(value.id)))

        def add(self, _value):
            calls.append(("db", "add"))

    async def create_editor_project(*_args, **_kwargs):
        return book

    async def mark_book_cache_dirty(value):
        calls.append(("book", str(value)))

    async def mark_user_dashboard_cache_dirty(value):
        calls.append(("dashboard", str(value)))

    monkeypatch.setattr(book_service, "create_editor_project", create_editor_project)
    monkeypatch.setattr(book_service, "mark_book_cache_dirty", mark_book_cache_dirty)
    monkeypatch.setattr(
        book_service, "mark_user_dashboard_cache_dirty", mark_user_dashboard_cache_dirty
    )

    await book_service.create_empty_editor_project_with_series(
        DB(),
        user_id,
        title="Draft",
        genre=None,
        author=None,
        work_type="novel",
        selected_series=[SimpleNamespace(id=series_id, name="Series")],
    )

    assert ("book", str(book_id)) in calls
    assert ("dashboard", str(user_id)) in calls


@pytest.mark.asyncio
async def test_reader_progress_update_marks_reader_progress_cache_dirty(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    calls: list[tuple[str, str, str | None]] = []

    class DB:
        async def execute(self, _statement):
            return _ScalarResult(None)

        def add(self, _value):
            calls.append(("db", "add", None))

        async def commit(self):
            calls.append(("db", "commit", None))

    async def get_book_with_collaboration_access(*_args, **_kwargs):
        return SimpleNamespace(id=book_id), None

    async def mark_reader_progress_cache_dirty(marked_book_id, marked_user_id):
        calls.append(("reader", marked_book_id, marked_user_id))

    async def sync_beta_assignments_for_reader_book(*_args, **_kwargs):
        calls.append(("beta", str(book_id), None))

    monkeypatch.setattr(
        reader_progress,
        "get_book_with_collaboration_access",
        get_book_with_collaboration_access,
    )
    monkeypatch.setattr(reader_progress, "collaboration_allows_chapter", lambda *_args: True)
    monkeypatch.setattr(
        reader_progress,
        "mark_reader_progress_cache_dirty",
        mark_reader_progress_cache_dirty,
    )
    monkeypatch.setattr(
        reader_progress,
        "sync_beta_assignments_for_reader_book",
        sync_beta_assignments_for_reader_book,
    )

    result = await reader_progress.update_progress(
        book_id,
        current_chapter=3,
        scroll_pct=0.4,
        db=DB(),
        current_user=SimpleNamespace(id=user_id),
    )

    assert result == {"ok": True}
    assert ("reader", str(book_id), str(user_id)) in calls
    assert ("beta", str(book_id), None) in calls


@pytest.mark.asyncio
async def test_public_forum_and_profile_invalidation_bump_expected_keys(monkeypatch):
    user_id = uuid.uuid4()
    calls: list[tuple[str, str]] = []

    async def cache_set_version_marker(key):
        calls.append(("version", key))

    async def cache_del(key):
        calls.append(("delete", key))

    async def mark_public_profile_cache_dirty(value):
        calls.append(("profile", value))

    monkeypatch.setattr(forum_foundation, "cache_set_version_marker", cache_set_version_marker)
    monkeypatch.setattr(forum_foundation, "cache_del", cache_del)
    monkeypatch.setattr(
        forum_foundation, "mark_public_profile_cache_dirty", mark_public_profile_cache_dirty
    )

    await forum_foundation._invalidate_public_forum_cache()
    await forum_foundation._invalidate_public_profile_cache_for_users(user_id, None)

    assert ("version", forum_foundation.key_public_forum_cache_version()) in calls
    assert ("delete", forum_foundation.key_public_books()) in calls
    assert ("profile", str(user_id)) in calls


@pytest.mark.asyncio
async def test_advisor_invalidation_resolves_series_before_deleting_namespaces(
    monkeypatch,
):
    book_id = uuid.uuid4()
    series_id = uuid.uuid4()
    calls: list[tuple[str, str | list[str]]] = []

    class DB:
        async def execute(self, _statement):
            return _RowsResult([SimpleNamespace(series_id=series_id)])

    async def invalidate_advisor_caches(*, book_id, series_ids=None):
        calls.append(("advisor", [str(book_id), *[str(value) for value in series_ids or []]]))

    monkeypatch.setattr(advisor_utils, "invalidate_advisor_caches", invalidate_advisor_caches)

    await advisor_utils.invalidate_advisor_caches_for_book(DB(), book_id=book_id)

    assert calls == [("advisor", [str(book_id), str(series_id)])]
