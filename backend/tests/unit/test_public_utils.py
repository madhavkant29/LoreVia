from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.schemas.public import PublicAuthorAnalyticsOut, PublicForumCommentOut, PublicUserProfileOut
from app.utils import public_utils


class _Result:
    def __init__(self, *, scalar=None, all_rows=None):
        self._scalar = scalar
        self._all_rows = [] if all_rows is None else all_rows

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return list(self._all_rows)


class _FakeDB:
    def __init__(self, *, execute_values=None):
        self._execute_values = list(execute_values or [])
        self.added: list[object] = []
        self.flush_called = False

    async def execute(self, *_args, **_kwargs):
        if self._execute_values:
            return self._execute_values.pop(0)
        return _Result()

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_called = True


def _profile_payload(user_id: uuid.UUID, username: str) -> PublicUserProfileOut:
    return PublicUserProfileOut(
        user_id=str(user_id),
        username=username,
        reputation_score=0,
        reputation_likes_received=0,
        reputation_dislikes_received=0,
        trust_level="Trusted",
        forum_post_count=1,
        forum_comment_count=2,
        current_project=None,
        public_books_count=0,
        public_books=[],
        public_analytics=PublicAuthorAnalyticsOut(),
        posts=[],
        comments=[],
        created_at="2026-05-16T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_get_public_user_profile_returns_cached_payload(monkeypatch):
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, username="Writer")

    async def _presence(*_args, **_kwargs):
        return True

    async def _cache_version(*_args, **_kwargs):
        return 5

    async def _cached_profile(*_args, **_kwargs):
        return _profile_payload(user_id, "Writer").model_dump(mode="json")

    monkeypatch.setattr(public_utils, "_user_has_public_profile_presence", _presence)
    monkeypatch.setattr(public_utils, "get_public_profile_cache_version", _cache_version)
    monkeypatch.setattr(public_utils, "get_public_user_profile_cache", _cached_profile)

    payload = await public_utils.get_public_user_profile(
        _FakeDB(execute_values=[_Result(scalar=user)]),
        username="writer",
    )

    assert payload.username == "Writer"
    assert payload.forum_comment_count == 2


@pytest.mark.asyncio
async def test_get_public_user_profile_caches_built_payload(monkeypatch):
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, username="Writer")
    captured = {}

    async def _presence(*_args, **_kwargs):
        return True

    async def _cache_version(*_args, **_kwargs):
        return 9

    async def _cache_miss(*_args, **_kwargs):
        return None

    async def _set_cache(user_id_arg, username_arg, version_arg, payload):
        captured["args"] = (user_id_arg, username_arg, version_arg, payload)

    async def _build_profile(*_args, **_kwargs):
        return _profile_payload(user_id, "Writer")

    monkeypatch.setattr(public_utils, "_user_has_public_profile_presence", _presence)
    monkeypatch.setattr(public_utils, "get_public_profile_cache_version", _cache_version)
    monkeypatch.setattr(public_utils, "get_public_user_profile_cache", _cache_miss)
    monkeypatch.setattr(public_utils, "set_public_user_profile_cache", _set_cache)
    monkeypatch.setattr(public_utils, "build_public_user_profile_out", _build_profile)

    payload = await public_utils.get_public_user_profile(
        _FakeDB(execute_values=[_Result(scalar=user)]),
        username=" Writer ",
    )

    assert payload.username == "Writer"
    assert captured["args"][0] == str(user_id)
    assert captured["args"][1] == "writer"
    assert captured["args"][2] == 9


def test_nest_public_forum_comments_builds_reply_tree():
    parent_id = str(uuid.uuid4())
    reply_id = str(uuid.uuid4())
    root = PublicForumCommentOut(
        id=parent_id,
        post_id=str(uuid.uuid4()),
        parent_comment_id=None,
        book_id=None,
        author_user_id=str(uuid.uuid4()),
        author_username="author",
        author_reputation_score=4,
        author_trust_level="New member",
        body="Top-level note",
        like_count=0,
        dislike_count=0,
        reaction=None,
        can_edit=False,
        replies=[],
        created_at="2026-05-22T10:00:00Z",
        updated_at="2026-05-22T10:00:00Z",
    )
    reply = PublicForumCommentOut(
        id=reply_id,
        post_id=root.post_id,
        parent_comment_id=parent_id,
        book_id=None,
        author_user_id=str(uuid.uuid4()),
        author_username="reader",
        author_reputation_score=8,
        author_trust_level="Trusted",
        body="Nested reply",
        like_count=0,
        dislike_count=0,
        reaction=None,
        can_edit=False,
        replies=[],
        created_at="2026-05-22T10:05:00Z",
        updated_at="2026-05-22T10:05:00Z",
    )

    nested = public_utils._nest_public_forum_comments([root, reply])

    assert len(nested) == 1
    assert nested[0].id == parent_id
    assert len(nested[0].replies) == 1
    assert nested[0].replies[0].id == reply_id


def test_public_ranking_normalizers_accept_supported_values():
    assert public_utils.normalize_public_ranking_key(" Top_Rated ") == "top_rated"
    assert public_utils.normalize_public_ranking_window(" Monthly ") == "monthly"


def test_public_ranking_label_is_human_readable():
    assert public_utils.public_ranking_label(ranking_key="most_popular", time_window="weekly") == "Most popular this week"


def test_recently_updated_ranking_uses_public_content_timestamp_not_forum_activity():
    old_update = datetime.now(UTC) - timedelta(days=10)
    recent_forum_activity = datetime.now(UTC)
    book = SimpleNamespace(public_updated_at=old_update, published_at=old_update, created_at=old_update)

    score, primary_timestamp = public_utils._compute_public_ranking_score(
        surface="beta_novels",
        ranking_key="recently_updated",
        book=book,
        craft_profile={},
        rating_stats={},
        view_stats={},
        forum_stats={"latest_activity_at": recent_forum_activity},
        window_start=datetime.now(UTC) - timedelta(days=30),
    )

    assert score == old_update.timestamp()
    assert primary_timestamp == old_update


def test_top_rated_score_weights_average_and_rating_volume():
    latest_rating_at = datetime.now(UTC)
    book = SimpleNamespace(
        public_updated_at=latest_rating_at - timedelta(days=2),
        published_at=latest_rating_at - timedelta(days=10),
        created_at=latest_rating_at - timedelta(days=20),
    )

    score, primary_timestamp = public_utils._compute_public_ranking_score(
        surface="beta_novels",
        ranking_key="top_rated",
        book=book,
        craft_profile={},
        rating_stats={
            "average_rating": 4.8,
            "rating_count": 12,
            "positive_rating_count": 10,
            "negative_rating_count": 1,
            "latest_rating_at": latest_rating_at,
        },
        view_stats={},
        forum_stats={},
        window_start=datetime.now(UTC) - timedelta(days=30),
    )

    assert score == 556.0
    assert primary_timestamp == latest_rating_at


def test_structural_ranking_requires_recent_public_activity_inside_window():
    old_update = datetime.now(UTC) - timedelta(days=60)
    book = SimpleNamespace(
        public_updated_at=old_update,
        published_at=old_update,
        created_at=old_update,
    )

    score, primary_timestamp = public_utils._compute_public_ranking_score(
        surface="creator_uploads",
        ranking_key="most_complex",
        book=book,
        craft_profile={"complexity_score": 88.5},
        rating_stats={},
        view_stats={},
        forum_stats={},
        window_start=datetime.now(UTC) - timedelta(days=30),
    )

    assert score is None
    assert primary_timestamp is None


def test_recently_released_ranking_filters_books_outside_window():
    published_at = datetime.now(UTC) - timedelta(days=90)
    book = SimpleNamespace(
        public_updated_at=published_at,
        published_at=published_at,
        created_at=published_at,
    )

    score, primary_timestamp = public_utils._compute_public_ranking_score(
        surface="creator_uploads",
        ranking_key="recently_released",
        book=book,
        craft_profile={},
        rating_stats={},
        view_stats={},
        forum_stats={},
        window_start=datetime.now(UTC) - timedelta(days=30),
    )

    assert score is None
    assert primary_timestamp == published_at


@pytest.mark.asyncio
async def test_rebuild_public_rankings_uses_timestamp_then_title_tie_breakers_and_invalidates_profiles(monkeypatch):
    newer_timestamp = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    shared_timestamp = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    author_a = uuid.uuid4()
    author_b = uuid.uuid4()
    author_c = uuid.uuid4()
    book_newer = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=author_a,
        title="Zephyr Signal",
        public_updated_at=newer_timestamp,
        published_at=shared_timestamp,
        created_at=shared_timestamp,
    )
    book_alpha = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=author_b,
        title="Alpha Harbor",
        public_updated_at=shared_timestamp,
        published_at=shared_timestamp,
        created_at=shared_timestamp,
    )
    book_omega = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=author_c,
        title="Omega Harbor",
        public_updated_at=shared_timestamp,
        published_at=shared_timestamp,
        created_at=shared_timestamp,
    )

    invalidated_user_ids: list[uuid.UUID] = []

    async def _list_visible_creator_public_books(*_args, **_kwargs):
        return [
            (book_newer, "writer-a"),
            (book_alpha, "writer-b"),
            (book_omega, "writer-c"),
        ]

    async def _list_open_beta_ranking_books(*_args, **_kwargs):
        return []

    async def _visible_character_count_map(*_args, **_kwargs):
        return {}

    async def _build_public_book_craft_profile(*_args, **_kwargs):
        return {}

    async def _book_rating_stats_by_window(*_args, **_kwargs):
        return {}

    async def _book_forum_activity_by_window(*_args, **_kwargs):
        return {
            book_newer.id: {"latest_activity_at": newer_timestamp, "discussion_interest_count": 0, "discussion_comment_count": 0, "open_discussion_count": 0},
            book_alpha.id: {"latest_activity_at": shared_timestamp, "discussion_interest_count": 0, "discussion_comment_count": 0, "open_discussion_count": 0},
            book_omega.id: {"latest_activity_at": shared_timestamp, "discussion_interest_count": 0, "discussion_comment_count": 0, "open_discussion_count": 0},
        }

    async def _public_book_view_counts_by_window(*_args, **_kwargs):
        return {
            book_newer.id: {"book_view_count": 0, "chapter_view_count": 0, "unique_reader_count": 0},
            book_alpha.id: {"book_view_count": 0, "chapter_view_count": 0, "unique_reader_count": 0},
            book_omega.id: {"book_view_count": 0, "chapter_view_count": 0, "unique_reader_count": 0},
        }

    async def _cache_del(*_args, **_kwargs):
        return None

    async def _cache_set_version_marker(*_args, **_kwargs):
        return None

    async def _invalidate_public_profile_cache_for_users(*user_ids):
        invalidated_user_ids.extend([user_id for user_id in user_ids if user_id is not None])

    monkeypatch.setattr(public_utils, "list_visible_creator_public_books", _list_visible_creator_public_books)
    monkeypatch.setattr(public_utils, "_list_open_beta_ranking_books", _list_open_beta_ranking_books)
    monkeypatch.setattr(public_utils, "_visible_character_count_map", _visible_character_count_map)
    monkeypatch.setattr(public_utils, "_build_public_book_craft_profile", _build_public_book_craft_profile)
    monkeypatch.setattr(public_utils, "_book_rating_stats_by_window", _book_rating_stats_by_window)
    monkeypatch.setattr(public_utils, "_book_forum_activity_by_window", _book_forum_activity_by_window)
    monkeypatch.setattr(public_utils, "_public_book_view_counts_by_window", _public_book_view_counts_by_window)
    monkeypatch.setattr(public_utils, "cache_del", _cache_del)
    monkeypatch.setattr(public_utils, "cache_set_version_marker", _cache_set_version_marker)
    monkeypatch.setattr(public_utils, "_invalidate_public_profile_cache_for_users", _invalidate_public_profile_cache_for_users)
    monkeypatch.setattr(public_utils, "VALID_PUBLIC_RANKING_WINDOWS", ["monthly"])
    monkeypatch.setattr(public_utils, "VALID_PUBLIC_RANKING_KEYS", ["most_popular"])

    db = _FakeDB()
    result = await public_utils.rebuild_public_book_rankings_snapshot(db, snapshot_at=datetime(2026, 5, 24, 18, 0, tzinfo=UTC))

    ranking_rows = [row for row in db.added if getattr(row, "surface", None) == "creator_uploads"]

    assert db.flush_called is True
    assert result == {"snapshot_rows": 3, "book_count": 3}
    assert [row.book_id for row in ranking_rows] == [book_newer.id, book_alpha.id, book_omega.id]
    assert [row.rank_position for row in ranking_rows] == [1, 2, 3]
    assert set(invalidated_user_ids) == {author_a, author_b, author_c}


@pytest.mark.asyncio
async def test_list_public_forum_interests_for_author_uses_joined_user_rows(monkeypatch):
    post_id = uuid.uuid4()
    author_user_id = uuid.uuid4()
    interested_user_id = uuid.uuid4()
    post = SimpleNamespace(id=post_id, author_user_id=author_user_id, thread_type="novel")
    interest = SimpleNamespace(
        id=uuid.uuid4(),
        post_id=post_id,
        book_id=uuid.uuid4(),
        author_user_id=author_user_id,
        interested_user_id=interested_user_id,
        message="Happy to beta read.",
        status="pending",
        created_at="2026-05-22T10:00:00Z",
        updated_at="2026-05-22T10:00:00Z",
    )
    interested_user = SimpleNamespace(username="reader", email="reader@example.com")

    async def _fake_get_forum_post(*_args, **_kwargs):
        return post

    monkeypatch.setattr(public_utils, "_get_forum_post", _fake_get_forum_post)
    monkeypatch.setattr(public_utils, "_is_general_forum_post", lambda _post: False)

    items = await public_utils.list_public_forum_interests_for_author(
        _FakeDB(execute_values=[_Result(all_rows=[(interest, interested_user)])]),
        post_id=post_id,
        author_user_id=author_user_id,
    )

    assert items[0].interested_username == "reader"
    assert items[0].interested_email == "reader@example.com"
