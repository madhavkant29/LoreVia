from datetime import UTC, datetime, timedelta
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.utils.public_utils import (
    MAX_PUBLIC_FORUM_PAGE_SIZE,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    _build_public_user_project_out,
    create_public_forum_post,
    ensure_public_authoring_access,
    ensure_public_forum_read_enabled,
    ensure_public_forum_write_enabled,
    forum_post_is_publicly_interactive,
    get_public_forum_post_detail,
    get_public_share_status,
    has_public_authoring_access,
    is_approved_user_public_share_book,
    get_public_forum_status,
    update_public_forum_post,
    list_public_forum_comments,
    list_public_forum_posts,
    list_author_public_forum_posts,
    public_forum_discoverability_score,
    public_profile_activity_counts,
    reputation_trust_level,
)
from app.schemas.public import PublicForumPostCreateBody, PublicForumPostUpdateBody


class _Result:
    def __init__(self, *, first_row=None, scalar_one=0, scalar_one_or_none=None, scalar=None, all_rows=None, scalars=None):
        self._first_row = first_row
        self._scalar_one = scalar_one
        self._scalar_one_or_none = scalar_one_or_none
        self._scalar = scalar
        self._all_rows = [] if all_rows is None else all_rows
        if scalars is not None:
            self._scalars = list(scalars)
        elif scalar_one_or_none is not None:
            self._scalars = [scalar_one_or_none]
        else:
            self._scalars = []

    def first(self):
        return self._first_row

    def scalar_one(self):
        return self._scalar_one

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalar(self):
        return self._scalar

    def all(self):
        return list(self._all_rows)

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._scalars))


class _FakeDB:
    def __init__(self, execute_values, get_values=None):
        self._execute_values = list(execute_values)
        self._get_values = list(get_values or [])
        self.execute_calls = 0
        self.commits = 0
        self.refreshes = []
        self.added = []

    async def execute(self, *_args, **_kwargs):
        self.execute_calls += 1
        return self._execute_values.pop(0)

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0)

    async def scalar(self, *_args, **_kwargs):
        return 4200

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        self.refreshes.append(value)


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


def test_get_public_forum_status_rejects_invalid_settings(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "ship-it", raising=False)
    with pytest.raises(HTTPException) as exc:
        get_public_forum_status()
    assert exc.value.status_code == 500
    assert "PUBLIC_FORUM_STATUS" in str(exc.value.detail)


def test_public_forum_guards_allow_public_reads_and_writes(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.PUBLIC_FORUM_STATUS", "public", raising=False)
    ensure_public_forum_read_enabled()
    ensure_public_forum_write_enabled()


def test_public_authoring_access_allows_trial_and_paid_author_tiers():
    assert has_public_authoring_access(SimpleNamespace(tier="author", created_at=None)) is True
    assert has_public_authoring_access(SimpleNamespace(tier="architect", created_at=None)) is True
    assert has_public_authoring_access(
        SimpleNamespace(tier="free", created_at=datetime.now(UTC) - timedelta(days=1))
    ) is True
    assert has_public_authoring_access(SimpleNamespace(tier="free", created_at=None)) is False
    with pytest.raises(HTTPException) as exc:
        ensure_public_authoring_access(SimpleNamespace(tier="free", created_at=None), action_label="Opening a public discussion")
    assert exc.value.status_code == 403


def test_public_share_status_defaults_to_not_requested_for_private_books():
    book = SimpleNamespace(is_public=False, source_kind="single_upload", public_share_status=None)
    assert get_public_share_status(book) == PUBLIC_SHARE_STATUS_NOT_REQUESTED


def test_public_share_status_treats_legacy_live_user_shares_as_approved():
    book = SimpleNamespace(is_public=True, source_kind="user_public_share", public_share_status=None)
    assert get_public_share_status(book) == PUBLIC_SHARE_STATUS_APPROVED
    assert is_approved_user_public_share_book(book) is True


def test_public_share_status_respects_pending_state():
    book = SimpleNamespace(is_public=False, source_kind="user_public_share", public_share_status="pending")
    assert get_public_share_status(book) == PUBLIC_SHARE_STATUS_PENDING
    assert is_approved_user_public_share_book(book) is False


@pytest.mark.asyncio
async def test_public_profile_activity_counts_only_reports_visible_public_presence():
    db = _FakeDB([
        _Result(scalar_one=1),
        _Result(scalar_one=2),
        _Result(scalars=[
            SimpleNamespace(is_public=True, source_kind="user_public_share", public_share_status="approved"),
            SimpleNamespace(is_public=True, source_kind="user_public_share", public_share_status="approved"),
            SimpleNamespace(is_public=False, source_kind="user_public_share", public_share_status="pending"),
            SimpleNamespace(is_public=True, source_kind="public_demo", public_share_status="approved"),
        ]),
    ])

    assert await public_profile_activity_counts(db, user_id=uuid.uuid4()) == (1, 2, 2)


@pytest.mark.asyncio
async def test_build_public_user_project_prefers_visible_forum_project():
    book = SimpleNamespace(
        id=uuid.uuid4(),
        title="Forum Draft",
        genre="Fantasy",
        public_description="Private manuscript blurb",
    )
    post = SimpleNamespace(id=uuid.uuid4(), body="A public beta forum pitch.")
    db = _FakeDB([_Result(first_row=(post, book))])

    project = await _build_public_user_project_out(db, user_id=uuid.uuid4())

    assert project is not None
    assert project.description == "A public beta forum pitch."
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
        is_public=True,
        source_kind="user_public_share",
    )
    db = _FakeDB([
        _Result(first_row=None),
        _Result(scalars=[book]),
    ])

    project = await _build_public_user_project_out(db, user_id=uuid.uuid4())

    assert project is not None
    assert project.source == "public_book"
    assert project.public_book_id == str(book.id)
    assert project.forum_post_id is None


@pytest.mark.asyncio
async def test_list_public_forum_posts_uses_pagination_and_batched_aggregates():
    post = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        author_user_id=uuid.uuid4(),
        headline="Need readers",
        body="Looking for beta feedback.",
        desired_beta_reader_count=5,
        allow_contact_requests=True,
        status="open",
        created_at="2026-05-16T00:00:00Z",
        updated_at="2026-05-16T00:00:00Z",
    )
    book = SimpleNamespace(
        id=post.book_id,
        title="Sky Harbor",
        author="Writer",
        genre="Fantasy",
        work_type="novel",
    )
    user = SimpleNamespace(
        id=post.author_user_id,
        username="writer",
        reputation_score=14,
    )
    db = _FakeDB([
        _Result(scalar_one=17),
        _Result(all_rows=[(
            post,
            book,
            user,
            4,
            3,
            4.5,
            2,
            2,
            0,
            0,
            "pending",
            488.0,
        )]),
    ])

    payload = await list_public_forum_posts(
        db,
        q="  sky harbor  ",
        page=2,
        page_size=10,
        current_user=SimpleNamespace(id=uuid.uuid4()),
    )

    assert db.execute_calls == 2
    assert payload.total == 17
    assert payload.page == 2
    assert payload.page_size == 10
    assert payload.has_more is False
    assert payload.items[0].comment_count == 4
    assert payload.items[0].interest_count == 3
    assert payload.items[0].viewer_interest_status == "pending"
    assert payload.items[0].rating_summary.average_rating == 4.5


@pytest.mark.asyncio
async def test_list_public_forum_posts_caps_page_size():
    db = _FakeDB([
        _Result(scalar_one=0),
        _Result(all_rows=[]),
    ])

    payload = await list_public_forum_posts(db, page=1, page_size=MAX_PUBLIC_FORUM_PAGE_SIZE + 500)

    assert payload.page_size == MAX_PUBLIC_FORUM_PAGE_SIZE
    assert payload.items == []


@pytest.mark.asyncio
async def test_create_public_forum_post_allows_new_post_when_previous_one_is_closed(monkeypatch):
    invalidated = []

    async def _fake_invalidate():
        invalidated.append(True)

    async def _fake_get_detail(_db, *, post_id, current_user=None):
        return SimpleNamespace(id=str(post_id), author_user_id=str(current_user.id))

    monkeypatch.setattr("app.utils.public_utils._invalidate_public_forum_cache", _fake_invalidate)
    monkeypatch.setattr("app.utils.public_utils.get_public_forum_post_detail", _fake_get_detail)

    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, is_public=False, hidden_at=None, archived_at=None)
    db = _FakeDB(
        execute_values=[_Result(scalar_one_or_none=None)],
        get_values=[book],
    )

    payload = await create_public_forum_post(
        db,
        current_user=SimpleNamespace(id=user_id, tier="author"),
        body=PublicForumPostCreateBody(
            book_id=book_id,
            headline="Need mystery beta readers",
            body="Looking for continuity and pacing feedback from thoughtful readers.",
            desired_beta_reader_count=3,
            allow_contact_requests=True,
        ),
    )

    assert payload.author_user_id == str(user_id)
    assert db.commits == 1


@pytest.mark.asyncio
async def test_create_public_forum_post_checks_only_for_existing_open_posts(monkeypatch):
    invalidated = []

    async def _fake_invalidate():
        invalidated.append(True)

    async def _fake_get_detail(_db, *, post_id, current_user=None):
        return SimpleNamespace(id=str(post_id), author_user_id=str(current_user.id))

    monkeypatch.setattr("app.utils.public_utils._invalidate_public_forum_cache", _fake_invalidate)
    monkeypatch.setattr("app.utils.public_utils.get_public_forum_post_detail", _fake_get_detail)

    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, user_id=user_id, is_public=False, hidden_at=None, archived_at=None)
    db = _FakeDB(
        execute_values=[_Result(scalar_one_or_none=None)],
        get_values=[book],
    )

    payload = await create_public_forum_post(
        db,
        current_user=SimpleNamespace(id=user_id, tier="author"),
        body=PublicForumPostCreateBody(
            book_id=book_id,
            headline="Need line-edit beta readers",
            body="Looking for close readers who can call out continuity slips and weak transitions.",
            desired_beta_reader_count=2,
            allow_contact_requests=True,
        ),
    )

    assert payload.author_user_id == str(user_id)
    assert db.commits == 1
    assert invalidated == [True]


@pytest.mark.asyncio
async def test_create_public_forum_post_blocks_free_author():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    db = _FakeDB(execute_values=[], get_values=[])

    with pytest.raises(HTTPException) as exc:
        await create_public_forum_post(
            db,
            current_user=SimpleNamespace(id=user_id, tier="free", created_at=None),
            body=PublicForumPostCreateBody(
                book_id=book_id,
                headline="Need line-edit beta readers",
                body="Looking for close readers who can call out continuity slips and weak transitions.",
                desired_beta_reader_count=2,
                allow_contact_requests=True,
            ),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_public_forum_post_allows_trial_user_for_approved_public_share(monkeypatch):
    invalidated = []

    async def _fake_invalidate():
        invalidated.append(True)

    async def _fake_get_detail(_db, *, post_id, current_user=None):
        return SimpleNamespace(id=str(post_id), author_user_id=str(current_user.id))

    monkeypatch.setattr("app.utils.public_utils._invalidate_public_forum_cache", _fake_invalidate)
    monkeypatch.setattr("app.utils.public_utils.get_public_forum_post_detail", _fake_get_detail)

    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    public_share_book = SimpleNamespace(
        id=book_id,
        user_id=user_id,
        mode="author",
        is_public=True,
        source_kind="user_public_share",
        public_share_status="approved",
        hidden_at=None,
        archived_at=None,
    )
    db = _FakeDB(
        execute_values=[_Result(scalar_one_or_none=None)],
        get_values=[public_share_book],
    )

    payload = await create_public_forum_post(
        db,
        current_user=SimpleNamespace(id=user_id, tier="free", created_at=datetime.now(UTC) - timedelta(days=1)),
        body=PublicForumPostCreateBody(
            book_id=book_id,
            headline="Need public sample readers",
            body="Looking for reactions to the public-facing sample before I widen the beta pool.",
            desired_beta_reader_count=2,
            allow_contact_requests=True,
        ),
    )

    assert payload.author_user_id == str(user_id)
    assert db.commits == 1
    assert invalidated == [True]


@pytest.mark.asyncio
async def test_list_author_public_forum_posts_returns_open_and_closed_threads():
    author_id = uuid.uuid4()
    open_post = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        author_user_id=author_id,
        headline="Open thread",
        body="Looking for active fantasy beta readers.",
        desired_beta_reader_count=3,
        allow_contact_requests=True,
        status="open",
        created_at="2026-05-16T00:00:00Z",
        updated_at="2026-05-16T00:00:00Z",
    )
    closed_post = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        author_user_id=author_id,
        headline="Closed thread",
        body="This one has already found enough readers.",
        desired_beta_reader_count=4,
        allow_contact_requests=False,
        status="closed",
        created_at="2026-05-15T00:00:00Z",
        updated_at="2026-05-15T00:00:00Z",
    )
    open_book = SimpleNamespace(id=open_post.book_id, title="Open Book", author="Writer", genre="Fantasy", work_type="novel")
    closed_book = SimpleNamespace(id=closed_post.book_id, title="Closed Book", author="Writer", genre="Sci-Fi", work_type="novel")
    user = SimpleNamespace(id=author_id, username="writer", reputation_score=12)
    db = _FakeDB([
        _Result(all_rows=[
            (open_post, open_book, user, 2, 1, 4.0, 1, 1, 0, 0, None, 410.0),
            (closed_post, closed_book, user, 5, 3, 4.5, 2, 2, 0, 0, None, 466.0),
        ]),
    ])

    payload = await list_author_public_forum_posts(db, author_user_id=author_id)

    assert [item.status for item in payload] == ["open", "closed"]
    assert db.added == []


@pytest.mark.asyncio
async def test_get_public_forum_post_detail_allows_author_to_view_closed_post():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = SimpleNamespace(
        id=post_id,
        book_id=book_id,
        author_user_id=user_id,
        headline="Closed thread",
        body="Still useful for the author to reopen later.",
        desired_beta_reader_count=2,
        allow_contact_requests=False,
        status="closed",
        created_at="2026-05-16T00:00:00Z",
        updated_at="2026-05-16T00:00:00Z",
    )
    book = SimpleNamespace(
        id=book_id,
        user_id=user_id,
        hidden_at=None,
        archived_at=None,
        is_public=False,
        title="Private Draft",
        author="Writer",
        genre="Fantasy",
        work_type="novel",
    )
    user = SimpleNamespace(id=user_id, username="writer", reputation_score=12)
    db = _FakeDB(
        execute_values=[
            _Result(first_row=None),
            _Result(first_row=(
                post,
                book,
                user,
                4,
                2,
                4.25,
                3,
                2,
                1,
                0,
                None,
                441.0,
            )),
        ],
    )

    payload = await get_public_forum_post_detail(
        db,
        post_id=post_id,
        current_user=SimpleNamespace(id=user_id),
    )

    assert payload.id == str(post_id)
    assert payload.status == "closed"
    assert payload.comment_count == 4
    assert payload.interest_count == 2
    assert payload.rating_summary.average_rating == 4.25
    assert payload.discoverability_score == 441.0


@pytest.mark.asyncio
async def test_list_public_forum_comments_allows_author_to_view_closed_post_comments():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    post_id = uuid.uuid4()
    post = SimpleNamespace(id=post_id, book_id=book_id, author_user_id=user_id, status="closed")
    book = SimpleNamespace(id=book_id, hidden_at=None, archived_at=None, is_public=False)
    comment = SimpleNamespace(
        id=uuid.uuid4(),
        post_id=post_id,
        book_id=book_id,
        author_user_id=user_id,
        body="A saved comment",
        like_count=0,
        dislike_count=0,
        created_at="2026-05-16T00:00:00Z",
        updated_at="2026-05-16T00:00:00Z",
    )
    author = SimpleNamespace(username="writer", reputation_score=12)
    db = _FakeDB(
        execute_values=[_Result(all_rows=[(comment, author)]), _Result(all_rows=[])],
        get_values=[post, book],
    )

    payload = await list_public_forum_comments(
        db,
        post_id=post_id,
        current_user=SimpleNamespace(id=user_id),
    )

    assert len(payload) == 1
    assert payload[0].body == "A saved comment"


@pytest.mark.asyncio
async def test_update_public_forum_post_blocks_reopening_when_another_open_post_exists():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    post = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        author_user_id=user_id,
        headline="Closed thread",
        body="Old body",
        desired_beta_reader_count=1,
        allow_contact_requests=True,
        status="closed",
    )
    book = SimpleNamespace(id=book_id, user_id=user_id, is_public=False, hidden_at=None, archived_at=None)
    other_open_post = SimpleNamespace(id=uuid.uuid4(), book_id=book_id, status="open")
    db = _FakeDB(
        execute_values=[_Result(scalar_one_or_none=other_open_post)],
        get_values=[post, book],
    )

    with pytest.raises(HTTPException) as exc:
            await update_public_forum_post(
                db,
                post_id=post.id,
                current_user=SimpleNamespace(id=user_id, tier="author"),
            body=PublicForumPostUpdateBody(
                headline="Reopen me",
                body="Trying to reopen with a second open thread already present.",
                desired_beta_reader_count=2,
                allow_contact_requests=True,
                status="open",
            ),
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_public_forum_post_allows_free_author_to_close_without_editing(monkeypatch):
    invalidated = []

    async def _fake_invalidate():
        invalidated.append(True)

    async def _fake_get_detail(_db, *, post_id, current_user=None):
        return SimpleNamespace(id=str(post_id), status="closed", author_user_id=str(current_user.id))

    monkeypatch.setattr("app.utils.public_utils._invalidate_public_forum_cache", _fake_invalidate)
    monkeypatch.setattr("app.utils.public_utils.get_public_forum_post_detail", _fake_get_detail)

    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    post = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        author_user_id=user_id,
        headline="Need fantasy readers",
        body="Looking for continuity feedback from active beta readers.",
        desired_beta_reader_count=3,
        allow_contact_requests=True,
        status="open",
    )
    book = SimpleNamespace(id=book_id, user_id=user_id, is_public=False, hidden_at=None, archived_at=None)
    db = _FakeDB(execute_values=[], get_values=[post, book])

    payload = await update_public_forum_post(
        db,
        post_id=post.id,
        current_user=SimpleNamespace(id=user_id, tier="free", created_at=None),
        body=PublicForumPostUpdateBody(
            headline=post.headline,
            body=post.body,
            desired_beta_reader_count=post.desired_beta_reader_count,
            allow_contact_requests=post.allow_contact_requests,
            status="closed",
        ),
    )

    assert payload.status == "closed"
    assert db.commits == 1
    assert invalidated == [True]


@pytest.mark.asyncio
async def test_update_public_forum_post_blocks_free_author_reopen():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    post = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        author_user_id=user_id,
        headline="Need fantasy readers",
        body="Looking for continuity feedback from active beta readers.",
        desired_beta_reader_count=3,
        allow_contact_requests=True,
        status="closed",
    )
    book = SimpleNamespace(id=book_id, user_id=user_id, is_public=False, hidden_at=None, archived_at=None)
    db = _FakeDB(execute_values=[], get_values=[post, book])

    with pytest.raises(HTTPException) as exc:
        await update_public_forum_post(
            db,
            post_id=post.id,
            current_user=SimpleNamespace(id=user_id, tier="free", created_at=None),
            body=PublicForumPostUpdateBody(
                headline=post.headline,
                body=post.body,
                desired_beta_reader_count=post.desired_beta_reader_count,
                allow_contact_requests=post.allow_contact_requests,
                status="open",
            ),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_public_forum_post_blocks_free_author_edit():
    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    post = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book_id,
        author_user_id=user_id,
        headline="Need fantasy readers",
        body="Looking for continuity feedback from active beta readers.",
        desired_beta_reader_count=3,
        allow_contact_requests=True,
        status="open",
    )
    book = SimpleNamespace(id=book_id, user_id=user_id, is_public=False, hidden_at=None, archived_at=None)
    db = _FakeDB(execute_values=[], get_values=[post, book])

    with pytest.raises(HTTPException) as exc:
        await update_public_forum_post(
            db,
            post_id=post.id,
            current_user=SimpleNamespace(id=user_id, tier="free", created_at=None),
            body=PublicForumPostUpdateBody(
                headline="Updated headline",
                body=post.body,
                desired_beta_reader_count=post.desired_beta_reader_count,
                allow_contact_requests=post.allow_contact_requests,
                status="open",
            ),
        )

    assert exc.value.status_code == 403


def test_forum_post_is_publicly_interactive_only_for_open_posts():
    assert forum_post_is_publicly_interactive(SimpleNamespace(status="open")) is True
    assert forum_post_is_publicly_interactive(SimpleNamespace(status="closed")) is False
