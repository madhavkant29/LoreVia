from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from app.schemas.public import (
    PublicAuthorAnalyticsOut,
    PublicForumCommentCreateBody,
    PublicForumCommentOut,
    PublicForumPostCreateBody,
    PublicForumPostUpdateBody,
    PublicUserProfileOut,
)
from app.utils import public_utils


class _Result:
    def __init__(self, *, scalar=None, all_rows=None):
        self._scalar = scalar
        self._all_rows = [] if all_rows is None else all_rows

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return list(self._all_rows)


class _FakeDB:
    def __init__(self, *, execute_values=None, get_values=None):
        self._execute_values = list(execute_values or [])
        self._get_values = dict(get_values or {})
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.refreshed: list[object] = []
        self.commits = 0
        self.flush_called = False

    async def execute(self, *_args, **_kwargs):
        if self._execute_values:
            return self._execute_values.pop(0)
        return _Result()

    def add(self, value):
        self.added.append(value)

    async def get(self, model, item_id):
        return self._get_values.get((model, item_id), self._get_values.get(item_id))

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        if hasattr(value, "created_at") and value.created_at is None:
            value.created_at = datetime.now(UTC)
        if hasattr(value, "updated_at") and value.updated_at is None:
            value.updated_at = datetime.now(UTC)
        self.refreshed.append(value)

    async def flush(self):
        self.flush_called = True


class _Upload:
    def __init__(self, raw: bytes, filename: str):
        self._raw = raw
        self._offset = 0
        self.filename = filename

    async def read(self, size: int = -1):
        if size < 0:
            size = len(self._raw) - self._offset
        chunk = self._raw[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk

    async def seek(self, offset: int):
        self._offset = offset


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


@pytest.mark.asyncio
async def test_react_to_public_forum_comment_adds_switches_and_clears_reactions(monkeypatch):
    comment_id = uuid.uuid4()
    post_id = uuid.uuid4()
    author_id = uuid.uuid4()
    viewer_id = uuid.uuid4()
    now = datetime.now(UTC)
    post = SimpleNamespace(id=post_id)
    comment = SimpleNamespace(
        id=comment_id,
        post_id=post_id,
        book_id=None,
        parent_comment_id=None,
        author_user_id=author_id,
        body="Useful note",
        image_s3_key=None,
        image_filename=None,
        image_content_type=None,
        like_count=0,
        dislike_count=0,
        created_at=now,
        updated_at=now,
    )
    author = SimpleNamespace(
        id=author_id,
        username="author",
        email="author@example.test",
        reputation_score=0,
        reputation_likes_received=0,
        reputation_dislikes_received=0,
    )
    viewer = SimpleNamespace(id=viewer_id, username="viewer")

    async def visible(*_args, **_kwargs):
        return post, None

    async def no_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(public_utils, "_get_visible_forum_post", visible)
    monkeypatch.setattr(public_utils, "_invalidate_public_forum_cache", no_cache)
    monkeypatch.setattr(public_utils, "_invalidate_public_profile_cache_for_users", no_cache)

    db = _FakeDB(
        execute_values=[_Result(scalar=None)],
        get_values={(public_utils.BookForumComment, comment_id): comment, (public_utils.User, author_id): author},
    )
    payload = await public_utils.react_to_public_forum_comment(
        db,
        comment_id=comment_id,
        current_user=viewer,
        reaction="like",
    )
    assert payload.reaction == "like"
    assert comment.like_count == 1 and author.reputation_score > 0
    assert len(db.added) == 1 and db.commits == 1

    existing = SimpleNamespace(reaction="like")
    db = _FakeDB(
        execute_values=[_Result(scalar=existing)],
        get_values={(public_utils.BookForumComment, comment_id): comment, (public_utils.User, author_id): author},
    )
    cleared = await public_utils.react_to_public_forum_comment(
        db,
        comment_id=comment_id,
        current_user=viewer,
        reaction="clear",
    )
    assert cleared.reaction is None
    assert db.deleted == [existing]
    assert comment.like_count == 0


@pytest.mark.asyncio
async def test_react_to_public_forum_post_updates_counts_and_handles_noop(monkeypatch):
    post_id = uuid.uuid4()
    author_id = uuid.uuid4()
    viewer = SimpleNamespace(id=uuid.uuid4())
    post = SimpleNamespace(
        id=post_id,
        author_user_id=author_id,
        like_count=0,
        dislike_count=0,
    )
    author = SimpleNamespace(
        id=author_id,
        reputation_score=3,
        reputation_likes_received=0,
        reputation_dislikes_received=0,
    )

    async def visible(*_args, **_kwargs):
        return post, None

    async def detail(*_args, **_kwargs):
        return SimpleNamespace(reaction="like", like_count=post.like_count, dislike_count=post.dislike_count)

    async def no_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(public_utils, "_get_visible_forum_post", visible)
    monkeypatch.setattr(public_utils, "get_public_forum_post_detail", detail)
    monkeypatch.setattr(public_utils, "_invalidate_public_forum_cache", no_cache)
    monkeypatch.setattr(public_utils, "_invalidate_public_profile_cache_for_users", no_cache)

    db = _FakeDB(
        execute_values=[_Result(scalar=None)],
        get_values={(public_utils.User, author_id): author},
    )
    result = await public_utils.react_to_public_forum_post(db, post_id=post_id, current_user=viewer, reaction="like")
    assert result.like_count == 1
    assert post.like_count == 1 and len(db.added) == 1

    existing = SimpleNamespace(reaction="like")
    noop_db = _FakeDB(
        execute_values=[_Result(scalar=existing)],
        get_values={(public_utils.User, author_id): author},
    )
    await public_utils.react_to_public_forum_post(noop_db, post_id=post_id, current_user=viewer, reaction="like")
    assert noop_db.commits == 0


@pytest.mark.asyncio
async def test_create_and_update_general_forum_posts_execute_runtime_lifecycle(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4(), tier="free")
    captured = {}

    async def enforce_limit(*_args, **_kwargs):
        captured["limit"] = True

    async def detail(_db, *, post_id, current_user):
        captured["post_id"] = post_id
        return SimpleNamespace(id=str(post_id), headline="Updated headline")

    async def no_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(public_utils, "enforce_daily_general_forum_post_limit", enforce_limit)
    monkeypatch.setattr(public_utils, "get_public_forum_post_detail", detail)
    monkeypatch.setattr(public_utils, "_invalidate_public_forum_cache", no_cache)
    monkeypatch.setattr(public_utils, "_invalidate_public_profile_cache_for_users", no_cache)
    db = _FakeDB()

    created = await public_utils.create_public_forum_post(
        db,
        current_user=user,
        body=PublicForumPostCreateBody(
            thread_type="general",
            headline="  General   craft question  ",
            body=" How do you pace a difficult reveal? ",
            allow_contact_requests=True,
        ),
    )

    post = db.added[0]
    assert captured["limit"] is True
    assert post.headline == "General craft question"
    assert post.body == "How do you pace a difficult reveal?"
    assert post.book_id is None and post.allow_contact_requests is False
    assert db.commits == 1 and db.refreshed == [post]
    assert created.id == str(post.id)

    post.author_user_id = user.id
    post.thread_type = "general"
    post.image_s3_key = "forum/old.png"
    post.image_content_type = "image/png"
    post.image_filename = "old.png"
    deleted_keys = []

    async def get_post(*_args, **_kwargs):
        return post

    async def delete_key(key, *, context):
        deleted_keys.append((key, context))

    monkeypatch.setattr(public_utils, "_get_forum_post", get_post)
    monkeypatch.setattr(public_utils, "delete_storage_key_best_effort", delete_key)
    updated = await public_utils.update_public_forum_post(
        db,
        post_id=post.id,
        current_user=user,
        body=PublicForumPostUpdateBody(
            thread_type="general",
            headline="Updated headline",
            body="This updated discussion body is long enough.",
            status="closed",
            remove_image=True,
        ),
    )
    assert post.status == "closed"
    assert post.image_s3_key is None
    assert deleted_keys == [("forum/old.png", "public_forum_image")]
    assert updated.headline == "Updated headline"


@pytest.mark.asyncio
async def test_create_forum_reply_notifies_post_and_parent_authors(monkeypatch):
    post_id = uuid.uuid4()
    book_id = uuid.uuid4()
    post_author_id = uuid.uuid4()
    parent_author_id = uuid.uuid4()
    current_user = SimpleNamespace(
        id=uuid.uuid4(),
        username="replying-reader",
        reputation_score=5,
        reputation_likes_received=0,
        reputation_dislikes_received=0,
    )
    post = SimpleNamespace(
        id=post_id,
        book_id=book_id,
        author_user_id=post_author_id,
        thread_type="novel",
        last_activity_at=None,
    )
    parent = SimpleNamespace(id=uuid.uuid4(), post_id=post_id, author_user_id=parent_author_id)

    async def visible(*_args, **_kwargs):
        return post, SimpleNamespace(id=book_id)

    async def no_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(public_utils, "_get_visible_forum_post", visible)
    monkeypatch.setattr(public_utils, "_invalidate_public_forum_cache", no_cache)
    monkeypatch.setattr(public_utils, "_invalidate_public_profile_cache_for_users", no_cache)
    db = _FakeDB(get_values={(public_utils.BookForumComment, parent.id): parent})

    payload = await public_utils.create_public_forum_comment(
        db,
        post_id=post_id,
        current_user=current_user,
        body=PublicForumCommentCreateBody(body="This reply identifies the missing clue.", parent_comment_id=parent.id),
    )

    comment = next(item for item in db.added if isinstance(item, public_utils.BookForumComment))
    notifications = [item for item in db.added if isinstance(item, public_utils.Notification)]
    assert comment.parent_comment_id == parent.id
    assert payload.can_edit is True
    assert payload.author_username == "replying-reader"
    assert {notification.user_id for notification in notifications} == {post_author_id, parent_author_id}
    assert db.flush_called is True and db.commits == 1


@pytest.mark.asyncio
async def test_store_public_forum_image_validates_and_uploads_png(monkeypatch):
    captured: dict[str, object] = {}
    owner_user_id = uuid.uuid4()
    target_id = uuid.uuid4()
    upload = _Upload(b"\x89PNG\r\n\x1a\nimage-bytes", "sketch.png")

    def _upload_binary(key, raw, content_type=None):
        captured["key"] = key
        captured["raw"] = raw
        captured["content_type"] = content_type
        return key

    monkeypatch.setattr(public_utils, "upload_binary", _upload_binary)

    storage_key, content_type, filename = await public_utils.store_public_forum_image(
        upload,
        owner_user_id=owner_user_id,
        target_kind="post",
        target_id=target_id,
    )

    assert storage_key == captured["key"]
    assert str(owner_user_id) in storage_key
    assert str(target_id) in storage_key
    assert content_type == "image/png"
    assert filename == "sketch.png"
    assert captured["raw"] == b"\x89PNG\r\n\x1a\nimage-bytes"
    assert captured["content_type"] == "image/png"


@pytest.mark.asyncio
async def test_store_public_forum_image_rejects_non_image_upload():
    with pytest.raises(public_utils.HTTPException) as exc:
        await public_utils.store_public_forum_image(
            _Upload(b"not an image", "notes.txt"),
            owner_user_id=uuid.uuid4(),
            target_kind="comment",
            target_id=uuid.uuid4(),
        )

    assert exc.value.status_code == 400


def test_public_forum_image_url_uses_presigned_url_when_available(monkeypatch):
    monkeypatch.setattr(public_utils, "get_presigned_url", lambda key: f"https://assets.example/{key}")

    assert public_utils.public_forum_image_url(
        storage_key="public-forum/image.png",
        owner_user_id=uuid.uuid4(),
        target_kind="post",
        target_id=uuid.uuid4(),
    ) == "https://assets.example/public-forum/image.png"


def test_public_ranking_normalizers_accept_supported_values():
    assert public_utils.normalize_public_ranking_key(" Top_Rated ") == "top_rated"
    assert public_utils.normalize_public_ranking_window(" Monthly ") == "monthly"


def test_public_ranking_label_is_human_readable():
    assert public_utils.public_ranking_label(ranking_key="most_popular", time_window="weekly") == "Most popular this week"


def test_validate_public_content_report_target_accepts_matching_public_slug():
    app_host = (urlparse(public_utils.settings.APP_URL).hostname or "getlorevia.com").strip().lower()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        hidden_at=None,
        archived_at=None,
        public_status=public_utils.PUBLIC_STATUS_PUBLISHED,
        moderation_status=public_utils.MODERATION_STATUS_CLEAN,
        public_slug="sky-harbor",
    )

    assert public_utils.validate_public_content_report_target(
        book,
        f" https://{app_host}/public/books/sky-harbor ",
    ) == f"https://{app_host}/public/books/sky-harbor"


def test_validate_public_content_report_target_accepts_reported_book_until_hidden():
    app_host = (urlparse(public_utils.settings.APP_URL).hostname or "getlorevia.com").strip().lower()
    book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        hidden_at=None,
        archived_at=None,
        public_status=public_utils.PUBLIC_STATUS_PUBLISHED,
        moderation_status=public_utils.MODERATION_STATUS_REPORTED,
        public_slug="storm-chamber",
    )

    assert public_utils.can_view_public_book(book) is True
    assert public_utils.public_visibility_notice(book) is None
    assert public_utils.validate_public_content_report_target(
        book,
        f"https://{app_host}/public/books/storm-chamber",
    ) == f"https://{app_host}/public/books/storm-chamber"


def test_validate_public_content_report_target_uses_configured_app_host(monkeypatch):
    monkeypatch.setattr(public_utils.settings, "APP_URL", "https://stories.lorevia.test", raising=False)
    book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        hidden_at=None,
        archived_at=None,
        public_status=public_utils.PUBLIC_STATUS_PUBLISHED,
        moderation_status=public_utils.MODERATION_STATUS_CLEAN,
        public_slug="ember-run",
    )

    assert public_utils.validate_public_content_report_target(
        book,
        "https://stories.lorevia.test/public/books/ember-run",
    ) == "https://stories.lorevia.test/public/books/ember-run"
    assert public_utils.validate_public_content_report_target(
        book,
        "https://www.stories.lorevia.test/public/books/ember-run",
    ) == "https://www.stories.lorevia.test/public/books/ember-run"


@pytest.mark.parametrize(
    ("book", "reported_content_url", "status_code"),
    [
        (
            SimpleNamespace(
                id=uuid.uuid4(),
                is_public=False,
                hidden_at=None,
                archived_at=None,
                public_status=public_utils.PUBLIC_STATUS_DRAFT,
                moderation_status=public_utils.MODERATION_STATUS_CLEAN,
            ),
            None,
            404,
        ),
        (
            SimpleNamespace(
                id=uuid.uuid4(),
                is_public=True,
                hidden_at=None,
                archived_at=None,
                public_status=public_utils.PUBLIC_STATUS_PUBLISHED,
                moderation_status=public_utils.MODERATION_STATUS_CLEAN,
                public_slug="sky-harbor",
            ),
            "https://example.com/public/books/sky-harbor",
            400,
        ),
        (
            SimpleNamespace(
                id=uuid.uuid4(),
                is_public=True,
                hidden_at=None,
                archived_at=None,
                public_status=public_utils.PUBLIC_STATUS_PUBLISHED,
                moderation_status=public_utils.MODERATION_STATUS_CLEAN,
                public_slug="sky-harbor",
            ),
            "https://getlorevia.com/public/books/other-book",
            400,
        ),
    ],
)
def test_validate_public_content_report_target_rejects_invalid_targets(book, reported_content_url, status_code):
    with pytest.raises(public_utils.HTTPException) as exc:
        public_utils.validate_public_content_report_target(book, reported_content_url)

    assert exc.value.status_code == status_code


@pytest.mark.asyncio
async def test_ensure_public_content_report_not_duplicate_rejects_recent_reporter_ip():
    with pytest.raises(public_utils.HTTPException) as exc:
        await public_utils.ensure_public_content_report_not_duplicate(
            _FakeDB(execute_values=[_Result(scalar=uuid.uuid4())]),
            book_id=uuid.uuid4(),
            report_type=public_utils.REPORT_TYPE_COPYRIGHT,
            reporter_ip_hash="same-reporter",
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_copyright_report_requires_temporary_hold_after_three_distinct_reporters():
    assert await public_utils.copyright_report_requires_temporary_hold(
        _FakeDB(execute_values=[_Result(scalar=3)]),
        book_id=uuid.uuid4(),
    )
    assert not await public_utils.copyright_report_requires_temporary_hold(
        _FakeDB(execute_values=[_Result(scalar=2)]),
        book_id=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_invalidate_public_book_caches_clears_detail_chapters_profile_and_forum(monkeypatch):
    deleted_keys: list[str] = []
    invalidated_profiles: list[str] = []
    forum_versions: list[str] = []
    book = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4(), total_chapters=2)

    async def _cache_del(key):
        deleted_keys.append(key)

    async def _mark_profile_dirty(user_id):
        invalidated_profiles.append(user_id)

    async def _cache_set_version_marker(key):
        forum_versions.append(key)

    monkeypatch.setattr(public_utils, "cache_del", _cache_del)
    monkeypatch.setattr(public_utils, "mark_public_profile_cache_dirty", _mark_profile_dirty)
    monkeypatch.setattr(public_utils, "cache_set_version_marker", _cache_set_version_marker)

    await public_utils.invalidate_public_book_caches(book)

    assert deleted_keys == [
        public_utils.key_public_books(),
        public_utils.key_public_book_detail(str(book.id)),
        public_utils.key_public_chapter(str(book.id), 1),
        public_utils.key_public_chapter(str(book.id), 2),
    ]
    assert invalidated_profiles == [str(book.user_id)]
    assert forum_versions == [public_utils.key_public_forum_cache_version()]


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


@pytest.mark.asyncio
async def test_rebuild_public_rankings_scores_every_surface_and_ranking_key(monkeypatch):
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    book_id = uuid.uuid4()
    author_id = uuid.uuid4()
    book = SimpleNamespace(
        id=book_id,
        user_id=author_id,
        title="Ranked Novel",
        public_updated_at=now - timedelta(days=1),
        published_at=now - timedelta(days=2),
        created_at=now - timedelta(days=3),
    )

    async def visible_books(_db):
        return [(book, "ranked_author")]

    async def beta_books(_db):
        return [(book, "ranked_author", str(uuid.uuid4()))]

    async def character_counts(_db, *, book_ids):
        return {book_id: 12}

    async def craft_profile(_db, *, book, visible_character_count):
        return {
            "complexity_score": 91.0,
            "well_written_score": 87.0,
            "beginner_friendly_score": 74.0,
            "visible_character_count": visible_character_count,
        }

    async def rating_stats(_db, *, book_ids, window_start):
        return {
            book_id: {
                "average_rating": 0.9,
                "rating_count": 6,
                "positive_rating_count": 5,
                "neutral_rating_count": 1,
                "negative_rating_count": 0,
                "latest_rating_at": now,
            }
        }

    async def forum_stats(_db, *, book_ids, window_start):
        return {
            book_id: {
                "open_discussion_count": 1,
                "discussion_comment_count": 4,
                "discussion_interest_count": 3,
                "latest_activity_at": now,
            }
        }

    async def view_stats(_db, *, book_ids, window_start):
        return {book_id: {"book_view_count": 10, "chapter_view_count": 20, "unique_reader_count": 7}}

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(public_utils, "list_visible_creator_public_books", visible_books)
    monkeypatch.setattr(public_utils, "_list_open_beta_ranking_books", beta_books)
    monkeypatch.setattr(public_utils, "_visible_character_count_map", character_counts)
    monkeypatch.setattr(public_utils, "_build_public_book_craft_profile", craft_profile)
    monkeypatch.setattr(public_utils, "_book_rating_stats_by_window", rating_stats)
    monkeypatch.setattr(public_utils, "_book_forum_activity_by_window", forum_stats)
    monkeypatch.setattr(public_utils, "_public_book_view_counts_by_window", view_stats)
    monkeypatch.setattr(public_utils, "cache_del", noop)
    monkeypatch.setattr(public_utils, "cache_set_version_marker", noop)
    monkeypatch.setattr(public_utils, "_invalidate_public_profile_cache_for_users", noop)
    monkeypatch.setattr(public_utils, "VALID_PUBLIC_RANKING_WINDOWS", ["weekly", "all_time"])

    db = _FakeDB()
    result = await public_utils.rebuild_public_book_rankings_snapshot(db, snapshot_at=now)
    ranking_rows = [item for item in db.added if hasattr(item, "ranking_key")]

    expected = 2 * len(public_utils.VALID_PUBLIC_RANKING_WINDOWS) * len(public_utils.VALID_PUBLIC_RANKING_KEYS)
    assert result == {"snapshot_rows": expected, "book_count": 1}
    assert len(ranking_rows) == expected
    assert {row.surface for row in ranking_rows} == {
        public_utils.PUBLIC_RANKING_SURFACE_UPLOADS,
        public_utils.PUBLIC_RANKING_SURFACE_BETA,
    }
    assert {row.ranking_key for row in ranking_rows} == set(public_utils.VALID_PUBLIC_RANKING_KEYS)
    assert all(row.rank_position == 1 for row in ranking_rows)


@pytest.mark.asyncio
async def test_public_ranking_window_aggregators_count_views_ratings_and_forum_activity():
    book_id = uuid.uuid4()
    post_id = uuid.uuid4()
    now = datetime.now(UTC)

    view_payload = await public_utils._public_book_view_counts_by_window(
        _FakeDB(
            execute_values=[
                _Result(
                    all_rows=[
                        (book_id, public_utils.PUBLIC_ANALYTICS_EVENT_BOOK_VIEW, "reader-a"),
                        (book_id, public_utils.PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW, "reader-a"),
                        (book_id, public_utils.PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW, "reader-b"),
                    ]
                )
            ]
        ),
        book_ids=[book_id],
        window_start=now - timedelta(days=7),
    )
    assert view_payload[book_id] == {
        "book_view_count": 1,
        "chapter_view_count": 2,
        "unique_reader_count": 2,
    }

    rating_payload = await public_utils._book_rating_stats_by_window(
        _FakeDB(
            execute_values=[
                _Result(
                    all_rows=[
                        (book_id, 4.5, now, None, None, now),
                        (book_id, 3.0, now, None, None, now),
                        (book_id, 1.0, now, None, None, now),
                        (book_id, 5.0, now - timedelta(days=30), None, None, now),
                    ]
                )
            ]
        ),
        book_ids=[book_id],
        window_start=now - timedelta(days=7),
    )
    assert rating_payload[book_id]["rating_count"] == 3
    assert rating_payload[book_id]["positive_rating_count"] == 1
    assert rating_payload[book_id]["neutral_rating_count"] == 1
    assert rating_payload[book_id]["negative_rating_count"] == 1

    forum_payload = await public_utils._book_forum_activity_by_window(
        _FakeDB(
            execute_values=[
                _Result(all_rows=[(post_id, book_id, public_utils.FORUM_POST_OPEN, now, now, now)]),
                _Result(all_rows=[(post_id, 4)]),
                _Result(all_rows=[(post_id, 3)]),
            ]
        ),
        book_ids=[book_id],
        window_start=now - timedelta(days=7),
    )
    assert forum_payload[book_id]["open_discussion_count"] == 1
    assert forum_payload[book_id]["discussion_comment_count"] == 4
    assert forum_payload[book_id]["discussion_interest_count"] == 3
