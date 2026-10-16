from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book
from app.models.beta_read import BetaReadAssignment
from app.models.book import (
    Book,
    BookForumComment,
    BookForumInterest,
    BookForumPost,
    Chapter,
    PublicBookAnalyticsEvent,
)
from app.models.character import Character
from app.models.user import User
from app.schemas.public import (
    PublicBookOut,
    PublicRankingMetadataOut,
)
from app.utils.beta_read_utils import (
    NEUTRAL_RATING_MIN,
    POSITIVE_RATING_MIN,
    RATED_ASSIGNMENT_STATES,
)
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
)
from app.utils.books.story_health import (
    build_story_health_payload,
    estimate_readability,
)
from app.utils.characters.governance import is_displayable_character
from app.utils.public.ranking_constants import (
    PUBLIC_RANKING_BEGINNER_FRIENDLY,
    PUBLIC_RANKING_BIG_CAST,
    PUBLIC_RANKING_LABELS,
    PUBLIC_RANKING_MOST_COMPLEX,
    PUBLIC_RANKING_MOST_POPULAR,
    PUBLIC_RANKING_MOST_WELL_WRITTEN,
    PUBLIC_RANKING_RECENTLY_UPDATED,
    PUBLIC_RANKING_SURFACE_UPLOADS,
    PUBLIC_RANKING_TOP_RATED,
    PUBLIC_RANKING_WINDOW_ALL_TIME,
    PUBLIC_RANKING_WINDOW_DAYS,
    PUBLIC_RANKING_WINDOW_LABELS,
    VALID_PUBLIC_RANKING_KEYS,
    VALID_PUBLIC_RANKING_WINDOWS,
)
from app.utils.public_utils import (
    FORUM_POST_OPEN,
    FORUM_THREAD_TYPE_NOVEL,
    PUBLIC_ANALYTICS_EVENT_BOOK_VIEW,
    PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS


def normalize_public_ranking_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in VALID_PUBLIC_RANKING_KEYS:
        raise HTTPException(400, "Invalid public ranking key.")
    return normalized


def normalize_public_ranking_window(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in VALID_PUBLIC_RANKING_WINDOWS:
        raise HTTPException(400, "Invalid public ranking window.")
    return normalized


def public_ranking_window_start(
    *, time_window: str, now: datetime | None = None
) -> datetime | None:
    normalized_window = normalize_public_ranking_window(time_window)
    if normalized_window == PUBLIC_RANKING_WINDOW_ALL_TIME:
        return None
    return (now or datetime.now(UTC)) - timedelta(
        days=PUBLIC_RANKING_WINDOW_DAYS[normalized_window]
    )


def public_ranking_label(*, ranking_key: str, time_window: str) -> str:
    return f"{PUBLIC_RANKING_LABELS[ranking_key]} {PUBLIC_RANKING_WINDOW_LABELS[time_window]}"


def build_public_ranking_metadata(
    *,
    surface: str,
    ranking_key: str,
    time_window: str,
    position: int | None = None,
    score: float | None = None,
    primary_timestamp: datetime | None = None,
) -> PublicRankingMetadataOut:
    return PublicRankingMetadataOut(
        surface=surface,
        ranking_key=ranking_key,
        time_window=time_window,
        position=position,
        score=float(score) if score is not None else None,
        label=public_ranking_label(ranking_key=ranking_key, time_window=time_window),
        supporting_note=_public_ranking_supporting_note(
            ranking_key=ranking_key, time_window=time_window
        ),
        primary_timestamp=primary_timestamp,
    )


def _public_ranking_supporting_note(*, ranking_key: str, time_window: str) -> str:
    if ranking_key == PUBLIC_RANKING_TOP_RATED:
        return "Weighted by beta-reader ratings and rating volume."
    if ranking_key == PUBLIC_RANKING_MOST_POPULAR:
        return "Weighted by recent reader activity, views, discussion, and interest."
    if ranking_key == PUBLIC_RANKING_MOST_COMPLEX:
        return (
            "Weighted by LoreVia craft-analysis signals for density, structure, and story systems."
        )
    if ranking_key == PUBLIC_RANKING_BIG_CAST:
        return "Weighted by visible character breadth across the manuscript."
    if ranking_key == PUBLIC_RANKING_MOST_WELL_WRITTEN:
        return "Weighted by LoreVia craft-analysis signals for continuity, voice, plot, and world cohesion."
    if ranking_key == PUBLIC_RANKING_BEGINNER_FRIENDLY:
        return "Weighted by accessibility, clarity, and smoother reading flow."
    if ranking_key == PUBLIC_RANKING_RECENTLY_UPDATED:
        return f"Based on the latest visible manuscript update in {PUBLIC_RANKING_WINDOW_LABELS[time_window]}."
    return f"Based on the latest release date in {PUBLIC_RANKING_WINDOW_LABELS[time_window]}."


def _safe_average(values: list[float]) -> float:
    filtered = [float(value) for value in values]
    return round(sum(filtered) / len(filtered), 2) if filtered else 0.0


def _timestamp_score(value: datetime | None) -> float:
    return value.timestamp() if value is not None else 0.0


def _book_public_activity_timestamp(book: Book) -> datetime | None:
    return (
        getattr(book, "public_updated_at", None)
        or getattr(book, "published_at", None)
        or getattr(book, "created_at", None)
    )


def _search_matches_public_book(book: PublicBookOut, normalized_search: str) -> bool:
    haystack = " ".join(
        str(getattr(book, field) or "")
        for field in (
            "title",
            "author",
            "author_username",
            "genre",
            "description",
            "source_title",
            "source_author",
        )
    ).lower()
    return normalized_search in haystack


async def _public_book_view_counts_by_window(
    db: AsyncSession,
    *,
    book_ids: list[uuid.UUID],
    window_start: datetime | None,
) -> dict[uuid.UUID, dict[str, int]]:
    if not book_ids:
        return {}

    statement = select(
        PublicBookAnalyticsEvent.book_id,
        PublicBookAnalyticsEvent.event_type,
        PublicBookAnalyticsEvent.visitor_fingerprint_hash,
    ).where(PublicBookAnalyticsEvent.book_id.in_(book_ids))
    if window_start is not None:
        statement = statement.where(PublicBookAnalyticsEvent.event_date >= window_start.date())
    rows = (await db.execute(statement)).all()
    payload: dict[uuid.UUID, dict[str, int | set[str]]] = {}
    for book_id, event_type, visitor_fingerprint_hash in rows:
        bucket = payload.setdefault(
            book_id,
            {
                "book_view_count": 0,
                "chapter_view_count": 0,
                "unique_reader_count": set(),
            },
        )
        if event_type == PUBLIC_ANALYTICS_EVENT_BOOK_VIEW:
            bucket["book_view_count"] = int(bucket["book_view_count"]) + 1
        elif event_type == PUBLIC_ANALYTICS_EVENT_CHAPTER_VIEW:
            bucket["chapter_view_count"] = int(bucket["chapter_view_count"]) + 1
        if visitor_fingerprint_hash:
            cast(set[str], bucket["unique_reader_count"]).add(str(visitor_fingerprint_hash))
    return {
        book_id: {
            "book_view_count": int(bucket["book_view_count"]),
            "chapter_view_count": int(bucket["chapter_view_count"]),
            "unique_reader_count": len(cast(set[str], bucket["unique_reader_count"])),
        }
        for book_id, bucket in payload.items()
    }


async def _book_rating_stats_by_window(
    db: AsyncSession,
    *,
    book_ids: list[uuid.UUID],
    window_start: datetime | None,
) -> dict[uuid.UUID, dict[str, Any]]:
    if not book_ids:
        return {}

    rows = (
        await db.execute(
            select(
                BetaReadAssignment.book_id,
                BetaReadAssignment.final_rating,
                BetaReadAssignment.submitted_at,
                BetaReadAssignment.completed_at,
                BetaReadAssignment.updated_at,
                BetaReadAssignment.created_at,
            ).where(
                BetaReadAssignment.book_id.in_(book_ids),
                BetaReadAssignment.state.in_(list(RATED_ASSIGNMENT_STATES)),
                BetaReadAssignment.final_rating.is_not(None),
            )
        )
    ).all()
    payload: dict[uuid.UUID, dict[str, Any]] = {}
    for book_id, rating, submitted_at, completed_at, updated_at, created_at in rows:
        event_timestamp = completed_at or submitted_at or updated_at or created_at
        if (
            window_start is not None
            and event_timestamp is not None
            and event_timestamp < window_start
        ):
            continue
        bucket = payload.setdefault(
            book_id,
            {
                "ratings": [],
                "positive_rating_count": 0,
                "neutral_rating_count": 0,
                "negative_rating_count": 0,
                "latest_rating_at": None,
            },
        )
        normalized_rating = float(rating or 0.0)
        cast(list[float], bucket["ratings"]).append(normalized_rating)
        if normalized_rating >= POSITIVE_RATING_MIN:
            bucket["positive_rating_count"] = int(bucket["positive_rating_count"]) + 1
        elif normalized_rating >= NEUTRAL_RATING_MIN:
            bucket["neutral_rating_count"] = int(bucket["neutral_rating_count"]) + 1
        else:
            bucket["negative_rating_count"] = int(bucket["negative_rating_count"]) + 1
        latest_rating_at = cast(datetime | None, bucket["latest_rating_at"])
        if event_timestamp is not None and (
            latest_rating_at is None or event_timestamp > latest_rating_at
        ):
            bucket["latest_rating_at"] = event_timestamp
    return {
        book_id: {
            "average_rating": round(
                sum(cast(list[float], bucket["ratings"]))
                / len(cast(list[float], bucket["ratings"])),
                2,
            )
            if bucket["ratings"]
            else None,
            "rating_count": len(cast(list[float], bucket["ratings"])),
            "positive_rating_count": int(bucket["positive_rating_count"]),
            "neutral_rating_count": int(bucket["neutral_rating_count"]),
            "negative_rating_count": int(bucket["negative_rating_count"]),
            "latest_rating_at": bucket["latest_rating_at"],
        }
        for book_id, bucket in payload.items()
    }


async def _book_forum_activity_by_window(
    db: AsyncSession,
    *,
    book_ids: list[uuid.UUID],
    window_start: datetime | None,
) -> dict[uuid.UUID, dict[str, Any]]:
    if not book_ids:
        return {}

    payload: dict[uuid.UUID, dict[str, Any]] = {
        book_id: {
            "open_discussion_count": 0,
            "discussion_comment_count": 0,
            "discussion_interest_count": 0,
            "latest_activity_at": None,
        }
        for book_id in book_ids
    }

    post_rows = (
        await db.execute(
            select(
                BookForumPost.id,
                BookForumPost.book_id,
                BookForumPost.status,
                BookForumPost.last_activity_at,
                BookForumPost.updated_at,
                BookForumPost.created_at,
            ).where(
                BookForumPost.book_id.in_(book_ids),
                BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
            )
        )
    ).all()
    post_ids: list[uuid.UUID] = []
    post_to_book: dict[uuid.UUID, uuid.UUID] = {}
    for post_id, book_id, status, last_activity_at, updated_at, created_at in post_rows:
        if book_id is None:
            continue
        post_ids.append(post_id)
        post_to_book[post_id] = book_id
        bucket = payload.setdefault(
            book_id,
            {
                "open_discussion_count": 0,
                "discussion_comment_count": 0,
                "discussion_interest_count": 0,
                "latest_activity_at": None,
            },
        )
        if status == FORUM_POST_OPEN:
            bucket["open_discussion_count"] = int(bucket["open_discussion_count"]) + 1
        latest_activity_at = last_activity_at or updated_at or created_at
        current_latest = cast(datetime | None, bucket["latest_activity_at"])
        if latest_activity_at is not None and (
            current_latest is None or latest_activity_at > current_latest
        ):
            bucket["latest_activity_at"] = latest_activity_at

    if not post_ids:
        return payload

    comment_statement = select(BookForumComment.post_id, func.count(BookForumComment.id)).where(
        BookForumComment.post_id.in_(post_ids)
    )
    if window_start is not None:
        comment_statement = comment_statement.where(BookForumComment.created_at >= window_start)
    comment_rows = (await db.execute(comment_statement.group_by(BookForumComment.post_id))).all()
    for post_id, comment_count in comment_rows:
        book_id = post_to_book.get(post_id)
        if book_id is None:
            continue
        payload[book_id]["discussion_comment_count"] = int(
            payload[book_id]["discussion_comment_count"]
        ) + int(comment_count or 0)

    interest_statement = select(BookForumInterest.post_id, func.count(BookForumInterest.id)).where(
        BookForumInterest.post_id.in_(post_ids)
    )
    if window_start is not None:
        interest_statement = interest_statement.where(BookForumInterest.created_at >= window_start)
    interest_rows = (await db.execute(interest_statement.group_by(BookForumInterest.post_id))).all()
    for post_id, interest_count in interest_rows:
        book_id = post_to_book.get(post_id)
        if book_id is None:
            continue
        payload[book_id]["discussion_interest_count"] = int(
            payload[book_id]["discussion_interest_count"]
        ) + int(interest_count or 0)

    return payload


async def _visible_character_count_map(
    db: AsyncSession,
    *,
    book_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    if not book_ids:
        return {}
    characters = (
        (
            await db.execute(
                select(Character)
                .where(Character.book_id.in_(book_ids))
                .order_by(Character.book_id, Character.mention_count.desc(), Character.name)
            )
        )
        .scalars()
        .all()
    )
    payload: dict[uuid.UUID, int] = {}
    for character in characters:
        if is_displayable_character(character):
            payload[character.book_id] = payload.get(character.book_id, 0) + 1
    return payload


async def _sample_public_book_text(
    db: AsyncSession,
    *,
    book: Book,
    max_chapters: int = 3,
    max_chars: int = 20_000,
) -> str:
    chapter_rows = (
        (
            await db.execute(
                select(Chapter.s3_key)
                .where(Chapter.book_id == book.id, Chapter.s3_key.is_not(None))
                .order_by(Chapter.number.asc())
                .limit(max_chapters)
            )
        )
        .scalars()
        .all()
    )
    fragments: list[str] = []
    for s3_key in chapter_rows:
        if not s3_key:
            continue
        try:
            stored = deserialize_manuscript_content(await asyncio.to_thread(download_book, s3_key))
        except STORAGE_IO_EXCEPTIONS:
            continue
        fragments.append(str(stored.get("text") or ""))
        if sum(len(fragment) for fragment in fragments) >= max_chars:
            break
    sampled = "\n\n".join(fragment for fragment in fragments if fragment).strip()
    if sampled:
        return sampled[:max_chars]
    return str(getattr(book, "public_description", None) or getattr(book, "title", "") or "")


async def _build_public_book_craft_profile(
    db: AsyncSession,
    *,
    book: Book,
    visible_character_count: int,
) -> dict[str, Any]:
    story_health = await build_story_health_payload(db, book)
    metrics_by_label = {
        str(metric.label): int(metric.score) for metric in story_health.metrics if metric.available
    }
    story_health_score = float(story_health.score) if story_health.available else None
    sampled_text = await _sample_public_book_text(db, book=book)
    readability = estimate_readability(sampled_text)
    grade_level = float(readability.get("grade_level") or 0.0)
    reading_ease = float(readability.get("reading_ease") or 0.0)
    average_sentence_length = float(readability.get("average_sentence_length") or 0.0)
    complexity_score = _safe_average(
        [
            *[
                float(metrics_by_label[label])
                for label in (
                    "Timeline clarity",
                    "Worldbuilding consistency",
                    "Plot thread closure",
                    "Dialogue/voice consistency",
                )
                if label in metrics_by_label
            ],
            min(max((grade_level / 14.0) * 100.0, 0.0), 100.0),
            min(float(visible_character_count) * 4.5, 100.0),
        ]
    )
    well_written_score = _safe_average(
        [
            *([story_health_score] if story_health_score is not None else []),
            *[
                float(metrics_by_label[label])
                for label in (
                    "Continuity",
                    "Dialogue/voice consistency",
                    "Plot thread closure",
                    "Worldbuilding consistency",
                )
                if label in metrics_by_label
            ],
        ]
    )
    beginner_friendly_score = _safe_average(
        [
            min(max(reading_ease, 0.0), 100.0),
            max(0.0, 100.0 - (grade_level * 6.0)),
            max(0.0, 100.0 - (average_sentence_length * 2.5)),
            *([story_health_score] if story_health_score is not None else []),
        ]
    )
    return {
        "story_health_score": story_health_score,
        "story_health_status": story_health.status,
        "complexity_score": complexity_score,
        "well_written_score": well_written_score,
        "beginner_friendly_score": beginner_friendly_score,
        "visible_character_count": int(visible_character_count),
        "reading_ease": reading_ease,
        "grade_level": grade_level,
        "average_sentence_length": average_sentence_length,
    }


async def _list_open_beta_ranking_books(db: AsyncSession) -> list[tuple[Book, str | None, str]]:
    rows = (
        await db.execute(
            select(BookForumPost.book_id, BookForumPost.id)
            .where(
                BookForumPost.book_id.is_not(None),
                BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
                BookForumPost.status == FORUM_POST_OPEN,
            )
            .order_by(BookForumPost.updated_at.desc(), BookForumPost.created_at.desc())
        )
    ).all()
    latest_post_ids_by_book: dict[uuid.UUID, str] = {}
    for book_id, post_id in rows:
        if book_id is not None and book_id not in latest_post_ids_by_book:
            latest_post_ids_by_book[book_id] = str(post_id)
    if not latest_post_ids_by_book:
        return []
    book_rows = (
        await db.execute(
            select(Book, User.username)
            .join(User, User.id == Book.user_id)
            .where(
                Book.id.in_(list(latest_post_ids_by_book.keys())),
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
            )
        )
    ).all()
    return [
        (book, username, latest_post_ids_by_book[book.id])
        for book, username in book_rows
        if book.id in latest_post_ids_by_book
    ]


def _structural_ranking_is_eligible(*, book: Book, window_start: datetime | None) -> bool:
    if window_start is None:
        return True
    activity_timestamp = _book_public_activity_timestamp(book)
    return activity_timestamp is not None and activity_timestamp >= window_start


def _compute_public_ranking_score(
    *,
    surface: str,
    ranking_key: str,
    book: Book,
    craft_profile: dict[str, Any],
    rating_stats: dict[str, Any],
    view_stats: dict[str, Any],
    forum_stats: dict[str, Any],
    window_start: datetime | None,
) -> tuple[float | None, datetime | None]:
    latest_activity_at = max(
        (
            timestamp
            for timestamp in (
                cast(datetime | None, forum_stats.get("latest_activity_at")),
                cast(datetime | None, rating_stats.get("latest_rating_at")),
                _book_public_activity_timestamp(book),
            )
            if timestamp is not None
        ),
        default=None,
    )
    if ranking_key == PUBLIC_RANKING_TOP_RATED:
        average_rating = float(rating_stats.get("average_rating") or 0.0)
        rating_count = int(rating_stats.get("rating_count") or 0)
        positive_rating_count = int(rating_stats.get("positive_rating_count") or 0)
        negative_rating_count = int(rating_stats.get("negative_rating_count") or 0)
        score = (
            (average_rating * 100.0)
            + (min(rating_count, 25) * 4.0)
            + (positive_rating_count * 3.0)
            - (negative_rating_count * 2.0)
        )
        return round(score, 2), cast(
            datetime | None, rating_stats.get("latest_rating_at")
        ) or latest_activity_at
    if ranking_key == PUBLIC_RANKING_MOST_POPULAR:
        if surface == PUBLIC_RANKING_SURFACE_UPLOADS:
            score = (
                (int(view_stats.get("book_view_count") or 0) * 3.0)
                + (int(view_stats.get("unique_reader_count") or 0) * 6.0)
                + float(int(view_stats.get("chapter_view_count") or 0))
                + (int(forum_stats.get("discussion_interest_count") or 0) * 8.0)
                + (int(forum_stats.get("discussion_comment_count") or 0) * 4.0)
                + (int(forum_stats.get("open_discussion_count") or 0) * 20.0)
                + (int(rating_stats.get("rating_count") or 0) * 3.0)
            )
        else:
            score = (
                (int(forum_stats.get("discussion_interest_count") or 0) * 12.0)
                + (int(forum_stats.get("discussion_comment_count") or 0) * 5.0)
                + (int(forum_stats.get("open_discussion_count") or 0) * 20.0)
                + (int(rating_stats.get("rating_count") or 0) * 5.0)
                + (float(rating_stats.get("average_rating") or 0.0) * 10.0)
            )
        return round(score, 2), latest_activity_at
    if ranking_key == PUBLIC_RANKING_MOST_COMPLEX:
        if not _structural_ranking_is_eligible(book=book, window_start=window_start):
            return None, None
        return float(craft_profile.get("complexity_score") or 0.0), _book_public_activity_timestamp(
            book
        )
    if ranking_key == PUBLIC_RANKING_BIG_CAST:
        if not _structural_ranking_is_eligible(book=book, window_start=window_start):
            return None, None
        return float(
            craft_profile.get("visible_character_count") or 0.0
        ), _book_public_activity_timestamp(book)
    if ranking_key == PUBLIC_RANKING_MOST_WELL_WRITTEN:
        if not _structural_ranking_is_eligible(book=book, window_start=window_start):
            return None, None
        return float(
            craft_profile.get("well_written_score") or 0.0
        ), _book_public_activity_timestamp(book)
    if ranking_key == PUBLIC_RANKING_BEGINNER_FRIENDLY:
        if not _structural_ranking_is_eligible(book=book, window_start=window_start):
            return None, None
        return float(
            craft_profile.get("beginner_friendly_score") or 0.0
        ), _book_public_activity_timestamp(book)
    if ranking_key == PUBLIC_RANKING_RECENTLY_UPDATED:
        updated_at = getattr(book, "public_updated_at", None)
        if updated_at is None or (window_start is not None and updated_at < window_start):
            return None, updated_at
        return _timestamp_score(updated_at), updated_at
    published_at = getattr(book, "published_at", None)
    if published_at is None or (window_start is not None and published_at < window_start):
        return None, published_at
    return _timestamp_score(published_at), published_at
