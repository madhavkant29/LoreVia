from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.schemas.public import PublicAuthorAnalyticsOut, PublicForumCommentOut, PublicUserProfileOut
from app.utils import public_utils


class _Result:
    def __init__(self, *, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class _FakeDB:
    def __init__(self, *, execute_values=None):
        self._execute_values = list(execute_values or [])

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)


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
