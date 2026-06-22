from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import (
    cache_del,
    cache_set_version_marker,
    key_public_books,
    key_public_forum_cache_version,
)
from app.models.book import (
    Book,
    BookForumPost,
    PublicBookRanking,
)
from app.models.user import User
from app.schemas.public import (
    PublicBookOut,
    PublicForumPostListOut,
    PublicForumPostOut,
    PublicForumRatingSummaryOut,
    PublicRankedBookListOut,
)
from app.utils.public.analytics import build_public_book_analytics_map
from app.utils.public.catalog import (
    _creator_public_book_forum_stats_map,
    list_visible_creator_public_books,
)
from app.utils.public.forum_foundation import (
    _invalidate_public_profile_cache_for_users,
    _public_forum_post_select_statement,
)
from app.utils.public.forum_posts import build_public_forum_post_out
from app.utils.public.ranking_constants import (
    PUBLIC_RANKING_SURFACE_BETA,
    PUBLIC_RANKING_SURFACE_UPLOADS,
    VALID_PUBLIC_RANKING_KEYS,
    VALID_PUBLIC_RANKING_WINDOWS,
)
from app.utils.public.ranking_core import (
    _book_forum_activity_by_window,
    _book_rating_stats_by_window,
    _build_public_book_craft_profile,
    _compute_public_ranking_score,
    _list_open_beta_ranking_books,
    _public_book_view_counts_by_window,
    _search_matches_public_book,
    _visible_character_count_map,
    build_public_ranking_metadata,
    normalize_public_ranking_key,
    normalize_public_ranking_window,
    public_ranking_window_start,
)
from app.utils.public.serialization import (
    build_public_book_out,
)
from app.utils.public_utils import (
    DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
)


async def rebuild_public_book_rankings_snapshot(
    db: AsyncSession,
    *,
    snapshot_at: datetime | None = None,
) -> dict[str, int]:
    now = snapshot_at or datetime.now(UTC)
    snapshot_date = now.date()
    upload_rows = await list_visible_creator_public_books(db)
    beta_rows = await _list_open_beta_ranking_books(db)
    all_books_by_id: dict[uuid.UUID, Book] = {
        **{book.id: book for book, _username in upload_rows},
        **{book.id: book for book, _username, _post_id in beta_rows},
    }
    all_book_ids = list(all_books_by_id.keys())
    visible_character_counts = await _visible_character_count_map(db, book_ids=all_book_ids)
    craft_profiles = {
        book_id: await _build_public_book_craft_profile(
            db,
            book=book,
            visible_character_count=visible_character_counts.get(book_id, 0),
        )
        for book_id, book in all_books_by_id.items()
    }

    upload_book_ids = [book.id for book, _username in upload_rows]
    beta_book_ids = [book.id for book, _username, _post_id in beta_rows]
    await db.execute(
        delete(PublicBookRanking).where(PublicBookRanking.snapshot_date == snapshot_date)
    )

    created_rows = 0
    for surface, eligible_book_ids in (
        (PUBLIC_RANKING_SURFACE_UPLOADS, upload_book_ids),
        (PUBLIC_RANKING_SURFACE_BETA, beta_book_ids),
    ):
        if not eligible_book_ids:
            continue
        for time_window in VALID_PUBLIC_RANKING_WINDOWS:
            window_start = public_ranking_window_start(time_window=time_window, now=now)
            rating_stats_map = await _book_rating_stats_by_window(
                db, book_ids=eligible_book_ids, window_start=window_start
            )
            forum_stats_map = await _book_forum_activity_by_window(
                db, book_ids=eligible_book_ids, window_start=window_start
            )
            view_stats_map = (
                await _public_book_view_counts_by_window(
                    db, book_ids=eligible_book_ids, window_start=window_start
                )
                if surface == PUBLIC_RANKING_SURFACE_UPLOADS
                else {}
            )
            for ranking_key in VALID_PUBLIC_RANKING_KEYS:
                scored_rows: list[tuple[uuid.UUID, float, datetime | None]] = []
                for book_id in eligible_book_ids:
                    book = all_books_by_id[book_id]
                    score, primary_timestamp = _compute_public_ranking_score(
                        surface=surface,
                        ranking_key=ranking_key,
                        book=book,
                        craft_profile=craft_profiles.get(book_id, {}),
                        rating_stats=rating_stats_map.get(book_id, {}),
                        view_stats=view_stats_map.get(book_id, {}),
                        forum_stats=forum_stats_map.get(book_id, {}),
                        window_start=window_start,
                    )
                    if score is None:
                        continue
                    scored_rows.append((book_id, float(score), primary_timestamp))
                scored_rows.sort(
                    key=lambda item: (
                        -item[1],
                        -(item[2].timestamp() if item[2] is not None else 0.0),
                        all_books_by_id[item[0]].title.lower(),
                    )
                )
                for index, (book_id, score, primary_timestamp) in enumerate(scored_rows, start=1):
                    db.add(
                        PublicBookRanking(
                            book_id=book_id,
                            surface=surface,
                            ranking_key=ranking_key,
                            time_window=time_window,
                            snapshot_date=snapshot_date,
                            rank_position=index,
                            score=round(score, 2),
                            primary_timestamp=primary_timestamp,
                        )
                    )
                    created_rows += 1
    await db.flush()
    profile_user_ids = list(
        dict.fromkeys(
            book.user_id
            for book in all_books_by_id.values()
            if getattr(book, "user_id", None) is not None
        )
    )
    await cache_del(key_public_books())
    await cache_set_version_marker(key_public_forum_cache_version())
    await _invalidate_public_profile_cache_for_users(*profile_user_ids)
    return {"snapshot_rows": created_rows, "book_count": len(all_book_ids)}


async def _latest_public_ranking_snapshot_date(
    db: AsyncSession,
    *,
    surface: str,
    ranking_key: str,
    time_window: str,
) -> date | None:
    return (
        await db.execute(
            select(func.max(PublicBookRanking.snapshot_date)).where(
                PublicBookRanking.surface == surface,
                PublicBookRanking.ranking_key == ranking_key,
                PublicBookRanking.time_window == time_window,
            )
        )
    ).scalar_one_or_none()


async def _ensure_public_ranking_snapshot(
    db: AsyncSession,
    *,
    surface: str,
    ranking_key: str,
    time_window: str,
) -> date | None:
    latest_snapshot_date = await _latest_public_ranking_snapshot_date(
        db,
        surface=surface,
        ranking_key=ranking_key,
        time_window=time_window,
    )
    if latest_snapshot_date is not None:
        return latest_snapshot_date
    await rebuild_public_book_rankings_snapshot(db)
    return await _latest_public_ranking_snapshot_date(
        db,
        surface=surface,
        ranking_key=ranking_key,
        time_window=time_window,
    )


async def list_ranked_public_uploads(
    db: AsyncSession,
    *,
    ranking_key: str,
    time_window: str,
    search: str | None = None,
    page: int = 1,
    limit: int = 24,
) -> PublicRankedBookListOut:
    normalized_ranking = normalize_public_ranking_key(ranking_key)
    normalized_window = normalize_public_ranking_window(time_window)
    latest_snapshot_date = await _ensure_public_ranking_snapshot(
        db,
        surface=PUBLIC_RANKING_SURFACE_UPLOADS,
        ranking_key=normalized_ranking,
        time_window=normalized_window,
    )
    if latest_snapshot_date is None:
        return PublicRankedBookListOut(
            items=[],
            total=0,
            page=page,
            limit=limit,
            has_more=False,
            ranking_key=normalized_ranking,
            time_window=normalized_window,
        )
    ranking_rows = (
        (
            await db.execute(
                select(PublicBookRanking)
                .where(
                    PublicBookRanking.surface == PUBLIC_RANKING_SURFACE_UPLOADS,
                    PublicBookRanking.ranking_key == normalized_ranking,
                    PublicBookRanking.time_window == normalized_window,
                    PublicBookRanking.snapshot_date == latest_snapshot_date,
                )
                .order_by(
                    PublicBookRanking.rank_position.asc(),
                    PublicBookRanking.primary_timestamp.desc(),
                    PublicBookRanking.book_id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    if not ranking_rows:
        return PublicRankedBookListOut(
            items=[],
            total=0,
            page=page,
            limit=limit,
            has_more=False,
            ranking_key=normalized_ranking,
            time_window=normalized_window,
        )
    rows = await list_visible_creator_public_books(db)
    book_rows_by_id = {book.id: (book, username) for book, username in rows}
    active_post_ids = await _creator_public_book_forum_stats_map(
        db, book_ids=[book.id for book, _username in rows]
    )
    analytics_map = await build_public_book_analytics_map(
        db, book_ids=[book.id for book, _username in rows]
    )
    ranked_items: list[PublicBookOut] = []
    for ranking_row in ranking_rows:
        if ranking_row.book_id not in book_rows_by_id:
            continue
        book, username = book_rows_by_id[ranking_row.book_id]
        book_out = build_public_book_out(
            book,
            author_username=username,
            active_forum_post_id=active_post_ids.get(book.id, {}).get("active_forum_post_id"),
            analytics=analytics_map.get(book.id),
        )
        book_out.ranking = build_public_ranking_metadata(
            surface=PUBLIC_RANKING_SURFACE_UPLOADS,
            ranking_key=normalized_ranking,
            time_window=normalized_window,
            position=ranking_row.rank_position,
            score=ranking_row.score,
            primary_timestamp=ranking_row.primary_timestamp,
        )
        ranked_items.append(book_out)
    normalized_search = " ".join((search or "").split()).strip().lower()
    if normalized_search:
        ranked_items = [
            item for item in ranked_items if _search_matches_public_book(item, normalized_search)
        ]
    start = max(page - 1, 0) * limit
    page_items = ranked_items[start : start + limit]
    return PublicRankedBookListOut(
        items=page_items,
        total=len(ranked_items),
        page=page,
        limit=limit,
        has_more=(start + limit) < len(ranked_items),
        ranking_key=normalized_ranking,
        time_window=normalized_window,
    )


async def list_ranked_public_beta_novels(
    db: AsyncSession,
    *,
    ranking_key: str,
    time_window: str,
    q: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
    current_user: User | None = None,
) -> PublicForumPostListOut:
    normalized_ranking = normalize_public_ranking_key(ranking_key)
    normalized_window = normalize_public_ranking_window(time_window)
    latest_snapshot_date = await _ensure_public_ranking_snapshot(
        db,
        surface=PUBLIC_RANKING_SURFACE_BETA,
        ranking_key=normalized_ranking,
        time_window=normalized_window,
    )
    if latest_snapshot_date is None:
        return PublicForumPostListOut(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            has_more=False,
            ranking_key=normalized_ranking,
            time_window=normalized_window,
            surface=PUBLIC_RANKING_SURFACE_BETA,
        )
    ranking_rows = (
        (
            await db.execute(
                select(PublicBookRanking)
                .where(
                    PublicBookRanking.surface == PUBLIC_RANKING_SURFACE_BETA,
                    PublicBookRanking.ranking_key == normalized_ranking,
                    PublicBookRanking.time_window == normalized_window,
                    PublicBookRanking.snapshot_date == latest_snapshot_date,
                )
                .order_by(
                    PublicBookRanking.rank_position.asc(),
                    PublicBookRanking.primary_timestamp.desc(),
                    PublicBookRanking.book_id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    if not ranking_rows:
        return PublicForumPostListOut(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            has_more=False,
            ranking_key=normalized_ranking,
            time_window=normalized_window,
            surface=PUBLIC_RANKING_SURFACE_BETA,
        )
    open_beta_rows = await _list_open_beta_ranking_books(db)
    post_id_by_book_id = {book.id: post_id for book, _username, post_id in open_beta_rows}
    ranked_post_ids: list[uuid.UUID] = []
    ranking_by_post_id: dict[uuid.UUID, PublicBookRanking] = {}
    for ranking_row in ranking_rows:
        post_id = post_id_by_book_id.get(ranking_row.book_id)
        if not post_id:
            continue
        parsed_post_id = uuid.UUID(post_id)
        ranked_post_ids.append(parsed_post_id)
        ranking_by_post_id[parsed_post_id] = ranking_row
    if not ranked_post_ids:
        return PublicForumPostListOut(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            has_more=False,
            ranking_key=normalized_ranking,
            time_window=normalized_window,
            surface=PUBLIC_RANKING_SURFACE_BETA,
        )
    ranked_rows = (
        await db.execute(
            _public_forum_post_select_statement(
                viewer_user_id=getattr(current_user, "id", None)
            ).where(BookForumPost.id.in_(ranked_post_ids))
        )
    ).all()
    row_by_post_id = {post.id: row for row in ranked_rows for post in [row[0]]}
    ranked_items: list[PublicForumPostOut] = []
    for post_id in ranked_post_ids:
        row = row_by_post_id.get(post_id)
        if row is None:
            continue
        (
            post,
            book,
            author_user,
            comment_count,
            interest_count,
            average_rating,
            rating_count,
            positive_rating_count,
            neutral_rating_count,
            negative_rating_count,
            viewer_interest_status,
            viewer_reaction,
            discoverability_score,
        ) = row
        post_out = build_public_forum_post_out(
            post=post,
            book=book,
            author_user=author_user,
            rating_summary=PublicForumRatingSummaryOut(
                average_rating=float(average_rating) if average_rating is not None else None,
                rating_count=int(rating_count or 0),
                positive_rating_count=int(positive_rating_count or 0),
                neutral_rating_count=int(neutral_rating_count or 0),
                negative_rating_count=int(negative_rating_count or 0),
            ),
            interest_count=int(interest_count or 0),
            comment_count=int(comment_count or 0),
            viewer_interest_status=viewer_interest_status,
            viewer_reaction=viewer_reaction,
            discoverability_score=float(discoverability_score or 0.0),
        )
        ranking_row = ranking_by_post_id.get(post_id)
        if ranking_row is not None:
            post_out.ranking = build_public_ranking_metadata(
                surface=PUBLIC_RANKING_SURFACE_BETA,
                ranking_key=normalized_ranking,
                time_window=normalized_window,
                position=ranking_row.rank_position,
                score=ranking_row.score,
                primary_timestamp=ranking_row.primary_timestamp,
            )
        ranked_items.append(post_out)
    normalized_query = " ".join((q or "").split()).strip().lower()
    if normalized_query:
        ranked_items = [
            item
            for item in ranked_items
            if normalized_query
            in " ".join(
                str(getattr(item, field) or "")
                for field in (
                    "title",
                    "genre",
                    "author_username",
                    "headline",
                    "body",
                    "description",
                )
            ).lower()
        ]
    start = max(page - 1, 0) * page_size
    page_items = ranked_items[start : start + page_size]
    return PublicForumPostListOut(
        items=page_items,
        total=len(ranked_items),
        page=page,
        page_size=page_size,
        has_more=(start + page_size) < len(ranked_items),
        ranking_key=normalized_ranking,
        time_window=normalized_window,
        surface=PUBLIC_RANKING_SURFACE_BETA,
    )
