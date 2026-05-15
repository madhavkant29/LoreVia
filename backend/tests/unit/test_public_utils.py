import uuid
from types import SimpleNamespace

import pytest

from app.utils.public_utils import (
    _build_public_user_project_out,
    public_forum_discoverability_score,
    public_profile_activity_counts,
    reputation_trust_level,
)


class _Result:
    def __init__(self, *, first_row=None, scalar_one=0, scalar_one_or_none=None, scalar=None):
        self._first_row = first_row
        self._scalar_one = scalar_one
        self._scalar_one_or_none = scalar_one_or_none
        self._scalar = scalar

    def first(self):
        return self._first_row

    def scalar_one(self):
        return self._scalar_one

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalar(self):
        return self._scalar


class _FakeDB:
    def __init__(self, execute_values):
        self._execute_values = list(execute_values)

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)

    async def scalar(self, *_args, **_kwargs):
        return 4200


def test_public_forum_discoverability_score_rewards_stronger_ratings_and_interest():
    stronger = public_forum_discoverability_score(
        average_rating=4.5,
        rating_count=4,
        positive_rating_count=4,
        negative_rating_count=0,
        interest_count=3,
    )
    weaker = public_forum_discoverability_score(
        average_rating=2.0,
        rating_count=4,
        positive_rating_count=0,
        negative_rating_count=3,
        interest_count=0,
    )

    assert stronger > weaker


def test_reputation_trust_level_scales_from_low_to_high():
    assert reputation_trust_level(-12) == "Low trust"
    assert reputation_trust_level(0) == "New member"
    assert reputation_trust_level(12) == "Trusted"
    assert reputation_trust_level(40) == "Highly trusted"


@pytest.mark.asyncio
async def test_public_profile_activity_counts_only_reports_visible_public_presence():
    db = _FakeDB([
        _Result(scalar_one=1),
        _Result(scalar_one=2),
        _Result(scalar_one=3),
    ])

    assert await public_profile_activity_counts(db, user_id=uuid.uuid4()) == (1, 2, 3)


@pytest.mark.asyncio
async def test_build_public_user_project_prefers_visible_forum_project():
    book = SimpleNamespace(
        id=uuid.uuid4(),
        title="Forum Draft",
        genre="Fantasy",
        public_description=None,
    )
    post = SimpleNamespace(id=uuid.uuid4(), body="A public beta forum pitch.")
    db = _FakeDB([_Result(first_row=(post, book))])

    project = await _build_public_user_project_out(db, user_id=uuid.uuid4())

    assert project is not None
    assert project.source == "forum"
    assert project.forum_post_id == str(post.id)
    assert project.public_book_id is None


@pytest.mark.asyncio
async def test_build_public_user_project_uses_true_public_book_when_no_visible_forum_project():
    book = SimpleNamespace(
        id=uuid.uuid4(),
        title="Public Sample",
        genre="Fantasy",
        public_description="A safe public sample.",
    )
    db = _FakeDB([
        _Result(first_row=None),
        _Result(scalar_one_or_none=book),
    ])

    project = await _build_public_user_project_out(db, user_id=uuid.uuid4())

    assert project is not None
    assert project.source == "public_book"
    assert project.public_book_id == str(book.id)
    assert project.forum_post_id is None
